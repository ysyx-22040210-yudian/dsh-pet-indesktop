import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import shutil
import subprocess
import sys
import threading

import pytest

from pet.agent_discovery import (
    RunningProgram, discover_programs, find_program_sources, portable_path, validate_source, render_opencode_plugin,
)
from PySide6.QtWidgets import QApplication, QMenu
from pet.agent_link import AgentLinkManager, OpenCodeMonitor
from pet.config import Config, _clean_custom_agents


def event_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE event (type TEXT, data TEXT)')
    return path


def test_renamed_fork_is_found_by_compatible_database(tmp_path):
    database = event_database(tmp_path / 'fork' / 'data' / 'opencode.db')
    program = RunningProgram(123, 'MyWorkbench.exe', str(tmp_path / 'fork' / 'MyWorkbench.exe'), str(tmp_path / 'fork'))
    sources = find_program_sources(program, home=tmp_path, opened_paths=[])
    assert [source.path for source in sources] == [database]
    assert sources[0].adapter == 'opencode'


def test_selected_process_open_file_is_probed_regardless_of_name(tmp_path):
    database = event_database(tmp_path / 'different place' / 'renamed.db')
    program = RunningProgram(123, 'fork.exe', '/apps/fork.exe', '')
    assert find_program_sources(program, home=tmp_path, opened_paths=[database])[0].path == database


def test_unrelated_database_is_not_claimed_as_an_agent(tmp_path):
    database = tmp_path / 'unrelated.db'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE password (data TEXT)')
    assert validate_source(database, 'opencode')
    assert not database.with_name(database.name + '-journal').exists()


def test_jsonl_channel_can_be_bound_before_agent_creates_it(tmp_path):
    missing = tmp_path / 'events.jsonl'
    assert validate_source(missing, 'jsonl') == ''
    assert not missing.exists()


def test_non_event_jsonl_is_not_automatically_claimed(tmp_path):
    path = tmp_path / 'chat-history.jsonl'
    path.write_text('{"role":"user","content":"private"}\n', encoding='utf-8')
    assert validate_source(path, 'jsonl')
    path.write_text('{"state":"working","tool":"read"}\n', encoding='utf-8')
    assert not validate_source(path, 'jsonl')


def test_malformed_event_metadata_is_rejected_without_raising(tmp_path):
    path = tmp_path / 'events.jsonl'
    path.write_text('{"state":[],"event":{}}\n', encoding='utf-8')
    assert validate_source(path, 'jsonl')


def test_home_path_moves_to_another_device(tmp_path):
    assert portable_path(tmp_path / '.local' / 'share' / 'fork' / 'events.jsonl', home=tmp_path) == '~/.local/share/fork/events.jsonl'


def test_discovery_deduplicates_children_and_keeps_unknown_forks(monkeypatch):
    import psutil
    username = psutil.Process().username()
    snapshots = [SimpleNamespace(info={'pid': pid, 'name': name, 'exe': exe, 'cwd': '', 'username': username}) for pid, name, exe in [
        (5, 'MyFork.exe', '/apps/MyFork.exe'), (6, 'MyFork.exe', '/apps/MyFork.exe'),
        (7, 'opencode.exe', '/apps/opencode.exe'),
    ]]
    monkeypatch.setattr(psutil, 'process_iter', lambda **kwargs: iter(snapshots))
    programs = discover_programs()
    assert sorted(program.pid for program in programs) == [5, 7]


@pytest.mark.parametrize('name', ['node.exe', 'python3', 'pythonw.exe', 'electron', 'bun.exe'])
def test_two_agents_using_same_runtime_remain_selectable(monkeypatch, name):
    import psutil
    username = psutil.Process().username()
    snapshots = [SimpleNamespace(info={'pid': pid, 'name': name, 'exe': '/apps/runtime', 'cwd': f'/fork-{pid}', 'username': username}) for pid in (5, 6)]
    monkeypatch.setattr(psutil, 'process_iter', lambda **kwargs: iter(snapshots))
    assert [program.pid for program in discover_programs()] == [5, 6]


def test_new_adapter_metadata_survives_round_trip_and_legacy_shape(tmp_path):
    old = {'key': 'old', 'name': 'Old', 'path': '~/events.jsonl'}
    new = {'key': 'fork', 'name': 'Fork', 'path': '~/opencode.db', 'adapter': 'opencode', 'process_names': ['MyFork.exe']}
    assert _clean_custom_agents([old])[0] == old
    config = Config(base=tmp_path)
    config.set('agent_link', {**config.get('agent_link'), 'custom_agents': [old, new]})
    assert config.save()
    restored = Config(base=tmp_path)
    assert restored.get('agent_link')['custom_agents'][1] == new


def test_manager_registers_fork_and_hot_reloads_its_source(tmp_path):
    app = QApplication.instance() or QApplication([])
    config = Config(base=tmp_path / 'profile')
    manager = AgentLinkManager(None, config)
    try:
        database = event_database(tmp_path / 'opencode.db')
        entry = {'key': 'fork', 'name': 'Renamed Fork', 'path': str(database), 'adapter': 'opencode', 'process_names': ['fork.exe']}
        config.set('agent_link', {**config.get('agent_link'), 'custom_agents': [entry]})
        manager.apply_config()
        assert isinstance(manager.monitors['fork'], OpenCodeMonitor)
        assert manager.monitors['fork'].agent_key == 'fork'
        assert manager.monitors['fork'].db_path == database
        manager._last_raw['fork'] = 'working'
        config.set('agent_link', {**config.get('agent_link'), 'fork': True})
        assert manager.busy_agent_owns_process('fork.exe')
        changed = {**entry, 'path': str(event_database(tmp_path / 'next.db'))}
        config.set('agent_link', {**config.get('agent_link'), 'custom_agents': [changed]})
        manager.apply_config()
        assert manager.monitors['fork'].db_path == tmp_path / 'next.db'
        config.set('agent_link', {**config.get('agent_link'), 'custom_agents': []})
        manager.apply_config()
        assert 'fork' not in manager.monitors
        assert not manager.busy_agent_owns_process('fork.exe')
    finally:
        manager.shutdown()


def test_source_replacement_ignores_queued_events_from_previous_binding(tmp_path):
    from pet.agent_link import AgentEvent
    app = QApplication.instance() or QApplication([])
    config = Config(base=tmp_path / 'profile')
    entry = {'key': 'fork', 'name': 'Fork', 'path': str(tmp_path / 'first.jsonl')}
    config.set('agent_link', {**config.get('agent_link'), 'custom_agents': [entry], 'fork': True})
    manager = AgentLinkManager(None, config)
    try:
        manager.apply_config()
        previous = manager.monitors['fork']
        event = AgentEvent(agent='fork', kind='state', state='working', gen=previous._emit_gen)
        writer = threading.Thread(target=lambda: previous.state_event.emit(event))
        writer.start()
        writer.join(timeout=12)
        assert not writer.is_alive()
        config.set('agent_link', {**config.get('agent_link'), 'custom_agents': [{**entry, 'path': str(tmp_path / 'second.jsonl')}]})
        manager.apply_config()
        app.processEvents()
        assert 'fork' not in manager._last_raw
    finally:
        manager.shutdown()


def test_custom_database_binding_does_not_mix_in_previous_jsonl_channel(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    config = Config(base=tmp_path / 'profile')
    database = event_database(tmp_path / 'fork.db')
    config.set('agent_link', {**config.get('agent_link'), 'custom_agents': [
        {'key': 'fork', 'name': 'Fork', 'path': str(database), 'adapter': 'opencode'}]})
    manager = AgentLinkManager(None, config)
    try:
        monitor = manager.monitors['fork']
        monitor.events_file.parent.mkdir(parents=True, exist_ok=True)
        monitor.events_file.touch()
        states = []
        monkeypatch.setattr(monitor, '_emit_state', lambda state, gen: states.append(state))
        monitor._poll()
        monitor.events_file.write_text('{"state":"working"}\n', encoding='utf-8')
        monitor._poll()
        assert not states
    finally:
        manager.shutdown()


def test_agent_menu_exposes_running_program_discovery():
    from pet.context_menus.shared import add_agent_link_menu
    app = QApplication.instance() or QApplication([])
    menu = QMenu()
    pet = SimpleNamespace(cfg=SimpleNamespace(get=lambda *args: {}), toggle_agent_link=lambda *args: None, set_agent_link_option=lambda *args: None)
    add_agent_link_menu(menu, pet)
    assert '识别运行中的 Agent…' in [action.text() for action in menu.actions()[0].menu().actions()]


def test_dialog_saves_portable_binding_without_overwriting_chat(tmp_path):
    from pet.running_agents_dialog import RunningAgentsDialog
    app = QApplication.instance() or QApplication([])
    config = Config(base=tmp_path / 'profile')
    chat_before = json.loads(json.dumps(config.get('chat')))
    dialog = RunningAgentsDialog(config, scan_on_open=False)
    try:
        dialog.name_edit.setText('My Fork')
        dialog.source_edit.setText(str(tmp_path / 'not-created-yet.jsonl'))
        dialog.add_binding()
        items = config.get('agent_link')['custom_agents']
        assert len(items) == 1
        assert config.get('agent_link')[items[0]['key']] is True
        assert config.get('chat') == chat_before
        dialog.add_binding()
        assert len(config.get('agent_link')['custom_agents']) == 1
        assert dialog.name_edit.accessibleName()
        assert dialog.source_edit.accessibleName()
    finally:
        dialog.close()


def test_escape_closes_discovery_and_stops_background_updates(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from pet.running_agents_dialog import RunningAgentsDialog
    app = QApplication.instance() or QApplication([])
    dialog = RunningAgentsDialog(Config(base=tmp_path), scan_on_open=False)
    try:
        dialog.show()
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        assert not dialog.isVisible()
        assert not dialog._timer.isActive()
        assert dialog._cancel.is_set()
    finally:
        dialog.close()


@pytest.mark.skipif(not shutil.which('node'), reason='Node is required for the actual plugin process test')
def test_exported_plugin_emits_only_metadata_from_real_node_process(tmp_path):
    event_file = tmp_path / 'AGENT DESTINATION events.jsonl'
    plugin = tmp_path / 'bridge.mjs'
    plugin.write_text(render_opencode_plugin(event_file, 'fork'), encoding='utf-8')
    script = f'''const {{QilinPetBridge}} = await import({json.dumps(plugin.as_uri())});
const hooks = await QilinPetBridge();
await hooks.event({{event:{{type:'session.status',properties:{{sessionID:'root',status:{{type:'busy'}}}}}}}});
await hooks['tool.execute.before']({{tool:'read',sessionID:'root',args:{{content:'PRIVATE-CODE'}}}});
await hooks.event({{event:{{type:'session.created',properties:{{info:{{id:'child',parentID:'root'}}}}}}}});
await hooks.event({{event:{{type:'session.idle',properties:{{sessionID:'child'}}}}}});
await hooks.event({{event:{{type:'session.idle',properties:{{sessionID:'root'}}}}}});'''
    subprocess.run([shutil.which('node'), '--input-type=module', '-e', script], check=True, timeout=20)
    text = event_file.read_text(encoding='utf-8')
    records = [json.loads(line) for line in text.splitlines()]
    assert [record['state'] for record in records] == ['working', 'working', 'idle']
    assert records[1]['tool'] == 'read'
    assert 'PRIVATE-CODE' not in text


def test_renamed_database_writer_reaches_real_monitor_event_loop(tmp_path):
    from PySide6.QtCore import QEventLoop, QTimer
    app = QApplication.instance() or QApplication([])
    database = event_database(tmp_path / 'renamed # database.db')
    monitor = OpenCodeMonitor(tmp_path / 'cfg', db_path=database, agent_key='renamed')
    events = []
    monitor.state_changed.connect(lambda key, state: events.append((key, state)))

    def wait_for(predicate):
        loop = QEventLoop()
        poll, deadline = QTimer(), QTimer()
        poll.setInterval(20)
        poll.timeout.connect(lambda: loop.quit() if predicate() else None)
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        poll.start()
        deadline.start(12000)
        loop.exec()
        poll.stop()
        deadline.stop()
        assert predicate(), events
    try:
        monitor.start()
        wait_for(lambda: monitor._db_ready)
        script = '''import sqlite3,sys,json
with sqlite3.connect(sys.argv[1]) as db:
    db.execute('INSERT INTO event VALUES (?,?)', ('message.part.updated.1',json.dumps({'part':{'type':'step-start'}})))
    db.execute('INSERT INTO event VALUES (?,?)', ('message.part.updated.1',json.dumps({'part':{'type':'step-finish','reason':'stop'}})))
'''
        subprocess.run([sys.executable, '-c', script, str(database)], check=True, timeout=20)
        wait_for(lambda: ('renamed', 'idle') in events)
        assert ('renamed', 'working') in events
    finally:
        monitor.stop()
