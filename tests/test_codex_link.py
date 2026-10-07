import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pet.agent_discovery import RunningProgram, find_program_sources, validate_source
from pet.config import Config


def row(kind, payload, *, timestamp=None):
    return {'timestamp': timestamp or datetime.now(timezone.utc).isoformat(), 'type': kind, 'payload': payload}


def append(path, *rows):
    with path.open('a', encoding='utf-8') as stream:
        for record in rows:
            stream.write(json.dumps(record) + '\n')


def session(root, name='root', *, source='cli'):
    path = root / '2026' / '10' / '03' / f'rollout-{name}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    append(path, row('session_meta', {'id': name, 'source': source}))
    return path


def monitor(tmp_path):
    from pet.codex_monitor import CodexMonitor
    root = tmp_path / 'sessions'
    root.mkdir()
    app = QApplication.instance() or QApplication([])
    mon = CodexMonitor('agent-codex', tmp_path / 'profile', root)
    return app, mon, root


def test_codex_is_detected_with_actual_session_source(tmp_path, monkeypatch):
    monkeypatch.delenv('CODEX_HOME', raising=False)
    root = tmp_path / '.codex' / 'sessions'
    session(root)
    program = RunningProgram(123, 'codex.exe', '/apps/codex.exe', '')
    sources = find_program_sources(program, home=tmp_path, opened_paths=[])
    assert [(item.path, item.adapter) for item in sources] == [(root, 'codex')]
    assert not validate_source(root, 'codex')
    assert validate_source(tmp_path / 'random-folder', 'codex')


def test_codex_home_override_is_used(tmp_path, monkeypatch):
    root = tmp_path / 'custom-home' / 'sessions'
    root.mkdir(parents=True)
    monkeypatch.setenv('CODEX_HOME', str(root.parent))
    program = RunningProgram(123, 'Codex.exe', '/apps/Codex.exe', '')
    assert find_program_sources(program, home=tmp_path, opened_paths=[])[0].path == root


def test_open_rollout_identifies_custom_codex_home(tmp_path, monkeypatch):
    monkeypatch.delenv('CODEX_HOME', raising=False)
    root = tmp_path / 'custom' / 'sessions'
    path = session(root)
    program = RunningProgram(123, 'renamed.exe', '/apps/renamed.exe', '')
    assert find_program_sources(program, home=tmp_path, opened_paths=[path])[0].adapter == 'codex'


def test_codex_adapter_survives_config_and_manager_creation(tmp_path):
    from pet.codex_monitor import CodexMonitor
    from pet.agent_link import AgentLinkManager
    app = QApplication.instance() or QApplication([])
    config = Config(base=tmp_path / 'profile')
    entry = {'key': 'agent-codex', 'name': 'Codex', 'path': '~/.codex/sessions', 'adapter': 'codex', 'process_names': ['codex.exe']}
    config.set('agent_link', {**config.get('agent_link'), 'custom_agents': [entry]})
    assert config.save()
    assert Config(base=tmp_path / 'profile').get('agent_link')['custom_agents'] == [entry]
    manager = AgentLinkManager(None, config)
    try:
        assert isinstance(manager.monitors['agent-codex'], CodexMonitor)
        assert manager.monitors['agent-codex'].sessions_dir == Path.home() / '.codex' / 'sessions'
    finally:
        manager.shutdown()


def test_real_rollout_working_thinking_completion_and_privacy(tmp_path):
    app, mon, root = monitor(tmp_path)
    path = session(root)
    states, tools = [], []
    mon.state_changed.connect(lambda agent, state: states.append(state))
    mon.activity.connect(lambda agent, tool: tools.append(tool))
    mon._poll()
    append(path, row('event_msg', {'type': 'task_started', 'turn_id': 'turn-1'}))
    mon._poll()
    assert states[-1] == 'thinking'
    append(path, row('response_item', {'type': 'custom_tool_call', 'name': 'functions.exec', 'input': 'PRIVATE-CODE', 'call_id': 'call-1'}))
    mon._poll()
    assert states[-1] == 'working'
    assert tools[-1] == 'bash'
    append(path, row('response_item', {'type': 'custom_tool_call_output', 'output': 'PRIVATE-OUTPUT', 'call_id': 'call-1'}))
    mon._poll()
    assert states[-1] == 'thinking'
    append(path, row('response_item', {'type': 'message', 'role': 'assistant', 'phase': 'commentary', 'content': 'PRIVATE-CHAT'}))
    mon._poll()
    assert states[-1] == 'thinking'
    append(path, row('event_msg', {'type': 'task_complete', 'turn_id': 'turn-1', 'last_agent_message': 'PRIVATE-ANSWER'}))
    mon._poll()
    assert states[-1] == 'idle'
    assert not (tmp_path / 'profile').exists()
    assert 'PRIVATE-' not in repr(mon._sessions)
    mon.stop()


def test_historical_work_is_not_replayed_and_new_files_are_not_skipped(tmp_path):
    app, mon, root = monitor(tmp_path)
    old = session(root, 'old')
    historical = '2020-01-01T00:00:00Z'
    append(old, row('event_msg', {'type': 'task_started', 'turn_id': 'old'}, timestamp=historical))
    states = []
    mon.state_changed.connect(lambda agent, state: states.append(state))
    mon._poll()
    assert not states
    new = session(root, 'new')
    append(new, row('event_msg', {'type': 'task_started', 'turn_id': 'new'}))
    mon.scan_interval = 0
    mon._poll()
    assert states[-1] == 'thinking'
    append(new, row('event_msg', {'type': 'task_complete', 'turn_id': 'new'}))
    mon._poll()
    assert states[-1] == 'idle'
    mon.stop()


def test_parallel_turns_and_subagents_do_not_emit_false_completion(tmp_path):
    app, mon, root = monitor(tmp_path)
    first, second = session(root, 'first'), session(root, 'second')
    child = session(root, 'child', source={'subagent': {'thread_spawn': {'parent_thread_id': 'first'}}})
    states = []
    mon.state_changed.connect(lambda agent, state: states.append(state))
    mon._poll()
    for path in (first, second, child):
        append(path, row('event_msg', {'type': 'task_started', 'turn_id': path.stem}))
    mon._poll()
    assert states[-1] == 'thinking'
    append(first, row('event_msg', {'type': 'task_complete', 'turn_id': first.stem}))
    append(child, row('event_msg', {'type': 'task_complete', 'turn_id': child.stem}))
    mon._poll()
    assert 'idle' not in states
    append(second, row('event_msg', {'type': 'turn_aborted', 'turn_id': second.stem}))
    mon._poll()
    assert states[-1] == 'idle'
    mon.stop()


def test_late_completion_cannot_end_the_newer_turn(tmp_path):
    app, mon, root = monitor(tmp_path)
    path = session(root)
    states = []
    mon.state_changed.connect(lambda agent, state: states.append(state))
    mon._poll()
    append(path, row('event_msg', {'type': 'task_started', 'turn_id': 'new'}),
           row('event_msg', {'type': 'task_complete', 'turn_id': 'old'}))
    mon._poll()
    assert states == ['thinking']
    mon.stop()


def test_partial_records_and_rollout_replacement_are_handled(tmp_path):
    app, mon, root = monitor(tmp_path)
    path = session(root)
    states = []
    mon.state_changed.connect(lambda agent, state: states.append(state))
    mon._poll()
    encoded = json.dumps(row('event_msg', {'type': 'task_started', 'turn_id': 'first'}))
    with path.open('a', encoding='utf-8') as stream:
        stream.write(encoded[:30])
    mon._poll()
    assert not states
    with path.open('a', encoding='utf-8') as stream:
        stream.write(encoded[30:] + '\n')
    mon._poll()
    assert states == ['thinking']
    replacement = path.with_suffix('.new')
    append(replacement, row('session_meta', {'id': 'root', 'source': 'cli'}),
           row('event_msg', {'type': 'task_started', 'turn_id': 'replacement'}),
           row('response_item', {'type': 'function_call', 'name': 'apply_patch', 'arguments': 'PRIVATE'}))
    replacement.replace(path)
    mon._poll()
    assert states[-1] == 'working'
    append(path, row('event_msg', {'type': 'task_complete', 'turn_id': 'replacement'}))
    mon._poll()
    assert states[-1] == 'idle'
    mon.stop()


def test_removing_active_rollout_releases_busy_state(tmp_path):
    app, mon, root = monitor(tmp_path)
    path = session(root)
    states = []
    mon.state_changed.connect(lambda agent, state: states.append(state))
    mon._poll()
    append(path, row('event_msg', {'type': 'task_started', 'turn_id': 'first'}))
    mon._poll()
    path.unlink()
    mon.scan_interval = 0
    mon._poll()
    assert states[-1] == 'idle'
    mon.stop()


def test_dialog_selects_and_persists_codex_adapter(tmp_path):
    from pet.running_agents_dialog import RunningAgentsDialog
    app = QApplication.instance() or QApplication([])
    config = Config(base=tmp_path / 'profile')
    dialog = RunningAgentsDialog(config, scan_on_open=False)
    try:
        root = tmp_path / 'sessions'
        root.mkdir()
        index = dialog.adapter.findData('codex')
        assert index >= 0
        dialog.adapter.setCurrentIndex(index)
        dialog.name_edit.setText('Codex')
        dialog.source_edit.setText(str(root))
        dialog.add_binding()
        entry = config.get('agent_link')['custom_agents'][0]
        assert entry['adapter'] == 'codex'
        assert 'Codex' in dialog.status.text()
        dialog.tabs.setCurrentIndex(1)
        dialog.bindings.setCurrentItem(dialog.bindings.topLevelItem(0))
        assert dialog.adapter.currentData() == 'codex'
        assert '目录' in dialog.browse_button.text()
    finally:
        dialog.close()


def test_real_worker_observes_external_writer_and_shuts_down(tmp_path):
    import subprocess
    app, mon, root = monitor(tmp_path)
    path = session(root)
    states = []
    mon.state_changed.connect(lambda agent, state: states.append(state), Qt.ConnectionType.QueuedConnection)
    mon._POLL_INTERVAL_S = 0.03
    assert mon.start()
    writer = subprocess.Popen([sys.executable, '-c',
        'import json,sys; from datetime import datetime,timezone; '
        'f=open(sys.argv[1],"a",encoding="utf-8"); '
        'f.write(json.dumps({"timestamp":datetime.now(timezone.utc).isoformat(),"type":"event_msg",'
        '"payload":{"type":"task_started","turn_id":"real"}})+"\\n"); f.close()', str(path)])
    try:
        assert writer.wait(timeout=12) == 0
        deadline = time.monotonic() + 12
        while 'thinking' not in states and time.monotonic() < deadline:
            app.processEvents()
            mon._worker_stop.wait(0.005)
        assert 'thinking' in states
    finally:
        mon.stop()
        assert not mon._worker.is_alive()
