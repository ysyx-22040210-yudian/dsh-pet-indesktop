"""Long-lived responsibilities: real storage, scheduling and GUI delivery seams."""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def wait_for(predicate, timeout_ms=15000):
    if predicate():
        return
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    timer.start()
    deadline.start(timeout_ms)
    loop.exec()
    timer.stop()
    deadline.stop()
    assert predicate(), 'asynchronous condition did not arrive'


def test_task_and_memory_survive_reopening(tmp_path):
    from pet.companion_store import TaskStore

    store = TaskStore(tmp_path)
    task = store.create_task('整理这个项目的交付清单', workspace=str(tmp_path))
    memory = store.put_memory('报告使用中文，并给出实际验证结果')
    reopened = TaskStore(tmp_path)
    assert reopened.get_task(task['id'])['instruction'] == task['instruction']
    assert reopened.memories()[0]['text'] == memory['text']
    assert reopened.tasks()[0]['status'] == 'queued'


def test_corrupt_store_is_not_overwritten(tmp_path):
    from pet.companion_store import StoreError, TaskStore

    path = tmp_path / 'state.json'
    path.write_text('{unfinished', encoding='utf-8')
    with pytest.raises(StoreError):
        TaskStore(tmp_path)
    assert path.read_text(encoding='utf-8') == '{unfinished'


def test_schedule_claim_is_persisted_and_overdue_runs_once(tmp_path):
    from pet.companion_store import TaskStore

    store = TaskStore(tmp_path)
    task = store.create_task('检查进展', engine='chat', run_at=200)
    assert store.claim_due(199) == []
    claimed = store.claim_due(400)
    assert [x['id'] for x in claimed] == [task['id']]
    assert store.claim_due(400) == []
    assert TaskStore(tmp_path).get_task(task['id'])['run_id'] == claimed[0]['run_id']


def test_interrupted_task_requires_explicit_resume(tmp_path):
    from pet.companion_store import TaskStore

    store = TaskStore(tmp_path)
    task = store.create_task('完成分析', engine='chat')
    store.claim_due(100)
    reopened = TaskStore(tmp_path)
    reopened.recover_interrupted()
    assert reopened.get_task(task['id'])['status'] == 'paused'
    assert reopened.claim_due(200) == []
    reopened.resume(task['id'], '继续分析，先看结论', now=200)
    assert reopened.claim_due(200)[0]['instruction'] == task['instruction']


def test_overlapping_workspaces_do_not_execute_together(tmp_path):
    from pet.companion_store import TaskStore

    store = TaskStore(tmp_path / 'state')
    parent = store.create_task('改父目录', workspace=str(tmp_path), write_access=True)
    nested = store.create_task('改子目录', workspace=str(tmp_path / 'sub'), write_access=True)
    independent = store.create_task('另一个任务', engine='chat')
    batch = store.claim_due(100, limit=2)
    assert {x['id'] for x in batch} == {parent['id'], independent['id']}
    assert store.get_task(nested['id'])['status'] == 'queued'


def test_finish_records_output_and_rejects_late_cancelled_result(tmp_path):
    from pet.companion_store import TaskOutcome, TaskStore

    store = TaskStore(tmp_path)
    task = store.create_task('分析', engine='chat')
    run = store.claim_due(100)[0]
    finished = store.finish(task['id'], run['run_id'], TaskOutcome('实际结果'), now=110)
    assert finished['status'] == 'completed'
    assert Path(finished['output_path']).read_text(encoding='utf-8') == '实际结果'
    other = store.create_task('第二项', engine='chat')
    run = store.claim_due(120)[0]
    store.pause(other['id'])
    assert store.finish(other['id'], run['run_id'], TaskOutcome('迟到结果'), now=130) is None
    assert store.get_task(other['id'])['status'] == 'paused'


def test_waiting_question_resumes_with_answer_and_context(tmp_path):
    from pet.companion_store import TaskOutcome, TaskStore, build_task_prompt

    store = TaskStore(tmp_path)
    task = store.create_task('持续整理项目', engine='chat')
    run = store.claim_due(100)[0]
    store.finish(task['id'], run['run_id'], TaskOutcome('你希望哪种格式？', 'waiting'), now=110)
    assert store.claim_due(200) == []
    store.resume(task['id'], '使用 Markdown', now=200)
    current = store.claim_due(200)[0]
    prompt = build_task_prompt(current, store.memories(), now=200)
    assert '使用 Markdown' in prompt
    assert '你希望哪种格式' in prompt


def test_self_wake_requires_task_opt_in_and_does_not_busy_loop(tmp_path):
    from pet.companion_store import TaskOutcome, TaskStore

    store = TaskStore(tmp_path)
    task = store.create_task('跟进变化', engine='chat', follow_up=True)
    run = store.claim_due(100)[0]
    result = store.finish(task['id'], run['run_id'], TaskOutcome('稍后再看', 'followup', wake_at=101), now=110)
    assert result['status'] == 'scheduled'
    assert result['next_run'] >= 170
    assert store.claim_due(169) == []
    second = store.create_task('一次整理', engine='chat', follow_up=False)
    run = store.claim_due(120)[0]
    result = store.finish(second['id'], run['run_id'], TaskOutcome('下次再看', 'followup', wake_at=300), now=130)
    assert result['status'] == 'waiting'


def test_recurring_schedule_advances_to_future_instead_of_backfilling(tmp_path):
    from pet.companion_store import TaskOutcome, TaskStore

    store = TaskStore(tmp_path)
    task = store.create_task('每小时整理', engine='chat', run_at=100, repeat_minutes=60)
    run = store.claim_due(11000)[0]
    result = store.finish(task['id'], run['run_id'], TaskOutcome('本轮整理完成'), now=11010)
    assert result['status'] == 'scheduled'
    assert result['next_run'] == 14500
    assert store.claim_due(11010) == []


def test_memory_enters_chat_prompt_and_is_removed_immediately(tmp_path):
    from pet.chat.models import ChatSettings
    from pet.chat.prompt import PromptBuilder
    from pet.companion_store import TaskStore

    store = TaskStore(tmp_path)
    memory = store.put_memory('每次结果都要列出验证方式')
    builder = PromptBuilder(memory_path=store.path)
    messages = builder.build_messages(ChatSettings.defaults(), 'qilin', [], '给我结果')
    assert '每次结果都要列出验证方式' in messages[0]['content']
    store.delete_memory(memory['id'])
    messages = builder.build_messages(ChatSettings.defaults(), 'qilin', [], '给我结果')
    assert '每次结果都要列出验证方式' not in messages[0]['content']


def test_codex_command_keeps_sandbox_and_uses_exact_session(tmp_path):
    from pet.companion_runner import codex_command

    task = {'workspace': str(tmp_path), 'write_access': False, 'thread_id': ''}
    command = codex_command(['codex.exe'], task, tmp_path / 'result-schema.json')
    assert '--sandbox' in command and 'read-only' in command
    assert command[-1] == '-'
    assert not any('dangerous' in x or x == '--ignore-rules' for x in command)
    task['thread_id'] = '0199a213-81c0-7800-8aa1-bbab2a035a53'
    command = codex_command(['codex.exe'], task, tmp_path / 'result-schema.json')
    assert 'resume' in command and task['thread_id'] in command
    assert '--last' not in command


def test_real_process_protocol_and_utf8_input(tmp_path):
    from pet.companion_runner import CodexRunner

    fixture = tmp_path / 'cli_fixture.py'
    fixture.write_text(
        "import sys,json\n"
        "prompt=sys.stdin.buffer.read().decode('utf-8')\n"
        "assert '麒麟任务' in prompt\n"
        "print(json.dumps({'type':'thread.started','thread_id':'0199a213-81c0-7800-8aa1-bbab2a035a53'}),flush=True)\n"
        "result=json.dumps({'message':'整理完成','status':'completed','wake_at':None,'memory_suggestions':[]},ensure_ascii=False)\n"
        "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':result}}),flush=True)\n"
        "print(json.dumps({'type':'turn.completed'}),flush=True)\n", encoding='utf-8',
    )
    events = []
    runner = CodexRunner([sys.executable, str(fixture)])
    task = {'workspace': str(tmp_path), 'write_access': False, 'thread_id': '', 'id': 'fixture'}
    result = runner.run(task, '麒麟任务', threading.Event(), events.append, tmp_path)
    assert result.text == '整理完成'
    assert result.thread_id == '0199a213-81c0-7800-8aa1-bbab2a035a53'
    assert not result.status == 'error'


def test_success_exit_without_completed_turn_is_not_claimed_as_complete(tmp_path):
    from pet.companion_runner import CodexRunner, RunnerError

    fixture = tmp_path / 'empty_fixture.py'
    fixture.write_text("import sys;sys.stdin.buffer.read()\n", encoding='utf-8')
    task = {'workspace': str(tmp_path), 'write_access': False, 'thread_id': '', 'id': 'fixture'}
    with pytest.raises(RunnerError):
        CodexRunner([sys.executable, str(fixture)]).run(task, 'task', threading.Event(), lambda e: None, tmp_path)


def test_service_survives_panel_closing_and_queues_gui_completion(tmp_path, qapp):
    from pet.companion_service import CompanionService
    from pet.companion_store import TaskOutcome

    started, release = threading.Event(), threading.Event()
    threads = []

    class NetworkBoundary:
        def run(self, task, prompt, cancel, progress, output_root):
            started.set()
            release.wait(10)
            return TaskOutcome('后台完成')
        def cancel(self):
            release.set()

    service = CompanionService(tmp_path, runner_factory=lambda task: NetworkBoundary())
    service.changed.connect(lambda: threads.append(threading.get_ident()))
    try:
        task = service.create_task('后台整理', engine='chat')
        wait_for(started.is_set)
        service.tick()
        assert service.store.get_task(task['id'])['status'] == 'running'
        release.set()
        wait_for(lambda: service.store.get_task(task['id'])['status'] == 'completed')
        assert set(threads) == {threading.get_ident()}
    finally:
        release.set()
        service.stop()


def test_service_lock_prevents_duplicate_scheduler(tmp_path, qapp):
    from pet.companion_service import CompanionService

    first = CompanionService(tmp_path)
    second = CompanionService(tmp_path)
    try:
        assert first.available
        assert not second.available
        assert second.unavailable_reason
    finally:
        second.stop()
        first.stop()


def test_menu_has_discoverable_companion_action_and_preserves_hidden_override(qapp):
    from pet.context_menus.registry import MENU_ACTIONS
    from pet.menu_layout import load_default_menu_layout, resolve_menu_layout

    assert 'companion' in MENU_ACTIONS.ids
    layout = load_default_menu_layout()
    node = next(x for x in layout['nodes'] if x.get('id') == 'companion')
    assert node['visible'] is True
    old = json.loads(json.dumps(layout))
    old['layout_id'] = 'user'
    old['nodes'] = [x for x in old['nodes'] if x.get('id') != 'companion']
    resolved = resolve_menu_layout(old, registered_actions=MENU_ACTIONS.ids, available_actions=MENU_ACTIONS.ids)
    assert any(x.get('id') == 'companion' for x in resolved.nodes)
    node['visible'] = False
    layout['layout_id'] = 'user'
    resolved = resolve_menu_layout(layout, registered_actions=MENU_ACTIONS.ids, available_actions=MENU_ACTIONS.ids)
    assert not any(x.get('id') == 'companion' for x in resolved.nodes)


def test_panel_creates_waiting_task_and_can_continue_after_close(tmp_path, qapp):
    from pet.companion_panel import CompanionPanel
    from pet.companion_service import CompanionService
    from pet.companion_store import TaskOutcome

    class NetworkBoundary:
        def run(self, task, prompt, cancel, progress, output_root):
            return TaskOutcome('请选择报告范围', 'waiting')
        def cancel(self):
            pass

    service = CompanionService(tmp_path, runner_factory=lambda task: NetworkBoundary())
    panel = CompanionPanel(service)
    try:
        panel.show()
        panel.engine.setCurrentIndex(1)
        panel.prefill('整理一份中文报告')
        panel.submit.click()
        wait_for(lambda: service.store.tasks() and service.store.tasks()[0]['status'] == 'waiting')
        task = service.store.tasks()[0]
        panel.select_task(task['id'])
        assert panel.resume_button.isEnabled()
        assert '请选择报告范围' in panel.result.toPlainText()
        assert panel.instruction.accessibleName()
        panel.close()
        assert service.available
        service.resume(task['id'], '只分析已有资料')
        wait_for(lambda: service.store.get_task(task['id'])['status'] == 'waiting')
        assert service.store.get_task(task['id'])['followups'] == ['只分析已有资料']
    finally:
        panel.close()
        service.stop()


def test_cancel_reaps_only_our_real_process_tree(tmp_path, qapp):
    import psutil
    from pet.companion_runner import CodexRunner, RunCancelled

    child_file = tmp_path / 'owned-child.txt'
    fixture = tmp_path / 'long_fixture.py'
    fixture.write_text(
        "import sys,json,subprocess,time,pathlib\n"
        "sys.stdin.buffer.read()\n"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n"
        "pathlib.Path('owned-child.txt').write_text(str(child.pid))\n"
        "print(json.dumps({'type':'thread.started','thread_id':'0199a213-81c0-7800-8aa1-bbab2a035a53'}),flush=True)\n"
        "time.sleep(60)\n", encoding='utf-8',
    )
    cancel = threading.Event()
    ready = threading.Event()
    stopped = []
    runner = CodexRunner([sys.executable, str(fixture)], timeout=30)
    task = {'workspace': str(tmp_path), 'write_access': False, 'thread_id': ''}

    def work():
        try:
            runner.run(task, '测试任务', cancel, lambda event: ready.set(), tmp_path)
        except RunCancelled:
            stopped.append(True)

    worker = threading.Thread(target=work)
    worker.start()
    child_pid = None
    try:
        assert ready.wait(15), 'external process did not reach the ready event'
        child_pid = int(child_file.read_text())
        cancel.set()
        runner.cancel()
        worker.join(15)
        assert not worker.is_alive() and stopped == [True]
        wait_for(lambda: not psutil.pid_exists(child_pid))
    finally:
        cancel.set()
        runner.cancel()
        worker.join(15)


def test_memory_save_failure_keeps_previous_state(tmp_path, monkeypatch):
    from pet import companion_store

    store = companion_store.TaskStore(tmp_path)
    store.put_memory('原始偏好')
    original = store.path.read_bytes()
    monkeypatch.setattr(companion_store.os, 'replace', lambda *a: (_ for _ in ()).throw(OSError('disk unavailable')))
    with pytest.raises(companion_store.StoreError):
        store.put_memory('没有写入成功的偏好')
    assert store.path.read_bytes() == original
    assert [x['text'] for x in store.memories()] == ['原始偏好']


def test_plain_chat_reply_is_not_a_task_completion(tmp_path):
    from pet.chat.models import ProviderConfig
    from pet.companion_runner import ChatRunner, RunnerError

    class NetworkBoundary:
        def stream(self, messages, config, cancel, response_holder=None):
            yield '我会稍后帮你整理。'

    with pytest.raises(RunnerError):
        ChatRunner(ProviderConfig('fixture'), NetworkBoundary()).run(
            {}, '任务', threading.Event(), lambda event: None, tmp_path)


def test_unchanged_followup_is_quiet_but_new_result_notifies(tmp_path, qapp):
    from pet.companion_service import CompanionService
    from pet.companion_store import TaskOutcome

    outcomes = [TaskOutcome('没有新变化', 'followup', wake_at=500),
                TaskOutcome('没有新变化', 'followup', wake_at=600), TaskOutcome('目标已完成')]

    class NetworkBoundary:
        def run(self, *args):
            return outcomes.pop(0)
        def cancel(self):
            pass

    service = CompanionService(tmp_path, runner_factory=lambda task: NetworkBoundary())
    notices = []
    service.notification.connect(notices.append)
    try:
        task = service.create_task('持续跟进', engine='chat')
        wait_for(lambda: service.store.get_task(task['id'])['status'] == 'scheduled')
        service.resume(task['id'])
        wait_for(lambda: service.store.get_task(task['id'])['runs'] == 2 and service.store.get_task(task['id'])['status'] == 'scheduled')
        service.resume(task['id'])
        wait_for(lambda: service.store.get_task(task['id'])['status'] == 'completed')
        assert len(notices) == 2
        assert notices[-1]['result'] == '目标已完成'
    finally:
        service.stop()


def test_task_memory_budget_keeps_valid_complete_json(tmp_path):
    from pet.companion_store import TaskStore, build_task_prompt

    store = TaskStore(tmp_path)
    task = store.create_task('分析已有内容', engine='chat')
    notes = [{'text': '长期偏好' * 250} for _ in range(80)]
    prompt = build_task_prompt(task, notes)
    assert len(prompt) < 11000
    context = json.loads(prompt.split('\n', 1)[1].split('\n最终返回JSON', 1)[0])
    assert context['长期记忆'] and all(len(x) <= 1000 for x in context['长期记忆'])


def test_failed_pause_leaves_running_work_intact(tmp_path, qapp, monkeypatch):
    from pet.companion_service import CompanionService
    from pet.companion_store import StoreError, TaskOutcome

    ready, release, cancelled = threading.Event(), threading.Event(), threading.Event()

    class NetworkBoundary:
        def run(self, *args):
            ready.set()
            release.wait(15)
            return TaskOutcome('已执行的结果')
        def cancel(self):
            cancelled.set()
            release.set()

    service = CompanionService(tmp_path, runner_factory=lambda task: NetworkBoundary())
    try:
        task = service.create_task('独立文字任务', engine='chat')
        wait_for(ready.is_set)
        with monkeypatch.context() as patch:
            patch.setattr(service.store, '_commit', lambda data: (_ for _ in ()).throw(StoreError('保存失败')))
            with pytest.raises(StoreError):
                service.pause(task['id'])
            assert not cancelled.is_set()
            assert service.store.get_task(task['id'])['status'] == 'running'
        release.set()
        wait_for(lambda: service.store.get_task(task['id'])['status'] == 'completed')
    finally:
        release.set()
        service.stop()


def test_panel_memory_delete_failure_is_visible_and_recoverable(tmp_path, qapp, monkeypatch):
    from pet.companion_panel import CompanionPanel
    from pet.companion_service import CompanionService
    from pet.companion_store import StoreError

    service = CompanionService(tmp_path)
    memory = service.put_memory('报告使用中文')
    panel = CompanionPanel(service)
    try:
        panel.memory_list.setCurrentRow(0)
        with monkeypatch.context() as patch:
            patch.setattr(service.store, '_commit', lambda data: (_ for _ in ()).throw(StoreError('磁盘保存失败')))
            panel._delete_memory()
            assert '磁盘保存失败' in panel.feedback.text()
            assert service.store.memories()[0]['id'] == memory['id']
        panel._delete_memory()
        assert not service.store.memories()
    finally:
        panel.close()
        service.stop()


def test_new_task_primary_action_stays_visible_in_short_window(tmp_path, qapp):
    from pet.companion_panel import CompanionPanel
    from pet.companion_service import CompanionService

    service = CompanionService(tmp_path)
    panel = CompanionPanel(service)
    try:
        panel.resize(720, 500)
        panel.show()
        qapp.processEvents()
        assert not panel.submit.visibleRegion().isEmpty()
        panel.tabs.setCurrentKey('memory')
        assert not panel.submit.isVisible()
        panel.tabs.setCurrentKey('new')
        assert panel.submit.isVisible()
    finally:
        panel.close()
        service.stop()


def test_progress_burst_is_throttled_without_losing_session(tmp_path, qapp, monkeypatch):
    from pet.companion_service import CompanionService

    service = CompanionService(tmp_path)
    try:
        task = service.store.create_task('独立验收任务', engine='chat')
        run = service.store.claim_due(100)[0]
        monkeypatch.setattr('pet.companion_service.time.monotonic', lambda: 1000.0)
        for number in range(100):
            service._on_progress(task['id'], run['run_id'], {'text': str(number), 'thread_id': 'exact-session'})
        assert service.store.get_task(task['id'])['thread_id'] == 'exact-session'
        assert len([x for x in service.store.activity() if x['kind'] == 'progress']) == 1
    finally:
        service.stop()


def test_scheduler_storage_error_disables_mutations_and_preserves_file(tmp_path, qapp, monkeypatch):
    from pet.companion_service import CompanionService
    from pet.companion_store import StoreError

    service = CompanionService(tmp_path)
    try:
        service.store.create_task('还没有执行', engine='chat')
        original = service.store.path.read_bytes()
        monkeypatch.setattr(service.store, '_commit', lambda data: (_ for _ in ()).throw(StoreError('记录保存失败')))
        service.tick()
        assert not service.available and '重启' in service.unavailable_reason
        assert service.store.path.read_bytes() == original
        with pytest.raises(StoreError):
            service.create_task('不应继续提交', engine='chat')
    finally:
        service.stop()


def test_incomplete_saved_task_has_explained_error_instead_of_ui_crash(tmp_path):
    from pet.companion_store import TaskStore, StoreError

    store = TaskStore(tmp_path)
    store.create_task('需要保留的任务', engine='chat')
    data = json.loads(store.path.read_text(encoding='utf-8'))
    del data['tasks'][0]['title']
    original = json.dumps(data, ensure_ascii=False)
    store.path.write_text(original, encoding='utf-8')
    with pytest.raises(StoreError, match='原文件已保留'):
        TaskStore(tmp_path)
    assert store.path.read_text(encoding='utf-8') == original
