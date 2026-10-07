"""Read local Codex rollout metadata without changing Codex settings or history."""
from __future__ import annotations

import heapq
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .agent_link import BaseAgentMonitor, ByteOffsetTailer

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CodexEvent:
    state: str = ''
    tool: str = ''
    turn: str = ''
    terminal: bool = False
    requires_active: bool = False


def codex_event(record: dict) -> CodexEvent:
    """Extract only lifecycle, item type and tool name; never retain transcript text."""
    payload = record.get('payload')
    if not isinstance(payload, dict):
        return CodexEvent()
    kind, event = record.get('type'), payload.get('type')
    turn = str(payload.get('turn_id') or '')
    if kind == 'event_msg':
        if event == 'task_started':
            return CodexEvent('thinking', turn=turn)
        if event in ('task_complete', 'turn_aborted'):
            return CodexEvent('idle', turn=turn, terminal=True)
        if event in ('exec_approval_request', 'apply_patch_approval_request'):
            return CodexEvent('attention', turn=turn)
        if event in ('agent_reasoning', 'agent_reasoning_raw_content'):
            return CodexEvent('thinking')
        if event in ('exec_command_begin', 'apply_patch_begin', 'mcp_tool_call_begin'):
            tool = {'exec_command_begin': 'bash', 'apply_patch_begin': 'edit', 'mcp_tool_call_begin': 'mcp'}[event]
            return CodexEvent('working', tool, turn)
        if event in ('exec_command_end', 'apply_patch_end', 'mcp_tool_call_end'):
            return CodexEvent('thinking', turn=turn, requires_active=True)
        if event not in ('item_started', 'item_completed'):
            return CodexEvent()
        item = payload.get('item')
        if not isinstance(item, dict):
            return CodexEvent()
        # Current Desktop persists PascalCase items; other clients use camelCase.
        item_type = str(item.get('type') or '').casefold()
        if item_type in ('reasoning', 'contextcompaction', 'usermessage'):
            return CodexEvent('thinking', turn=turn)
        tools = {'commandexecution': 'bash', 'filechange': 'edit', 'mcptoolcall': 'mcp',
                 'dynamictoolcall': 'tool', 'websearch': 'search', 'imageview': 'read', 'collabtoolcall': 'task'}
        if item_type in tools:
            return CodexEvent('working' if event == 'item_started' else 'thinking', tools[item_type], turn,
                              requires_active=event == 'item_completed')
        return CodexEvent()
    if kind != 'response_item':
        return CodexEvent()
    if event == 'reasoning':
        return CodexEvent('thinking')
    if event in ('function_call', 'custom_tool_call'):
        name = str(payload.get('name') or '').rsplit('.', 1)[-1]
        tool = {'exec': 'bash', 'exec_command': 'bash', 'write_stdin': 'bash', 'apply_patch': 'edit',
                'web__run': 'search', 'view_image': 'read'}.get(name, 'tool')
        return CodexEvent('working', tool)
    if event in ('function_call_output', 'custom_tool_call_output'):
        return CodexEvent('thinking', requires_active=True)
    # Commentary and final text are not authoritative task completion events.
    return CodexEvent()


class CodexMonitor(BaseAgentMonitor):
    """Aggregate live root turns from a selected CODEX_HOME/sessions directory."""

    def __init__(self, agent_key: str, config_dir: Path, sessions_dir: Path, parent=None):
        super().__init__(agent_key, config_dir, parent)
        self.sessions_dir = Path(sessions_dir)
        self._mkdir_on_start = False
        self.scan_interval = 30.0
        self.max_files = 64
        self._reset_sessions()

    def _reset_sessions(self):
        self._since = time.time()
        self._last_scan = None
        self._tailers = {}
        self._sessions = {}
        self._last_state = ''

    def _worker_started(self):
        self._reset_sessions()

    def _add_file(self, path):
        try:
            with path.open('rb') as stream:
                meta = json.loads(stream.readline(262144))
            payload = meta.get('payload') if isinstance(meta, dict) else None
            if not isinstance(payload, dict) or meta.get('type') != 'session_meta':
                return
            source = payload.get('source')
            thread_source = payload.get('thread_source')
            child = any(isinstance(value, dict) and any('subagent' in str(key).casefold() for key in value)
                        for value in (source, thread_source))
            stat = path.stat()
            tailer = ByteOffsetTailer(path)
            # A bounded initial tail catches events written since activation,
            # including newly created sessions; older records are filtered below.
            tailer._initial_backfill_done = True
            tailer.offset = stat.st_size if stat.st_mtime < self._since else max(0, stat.st_size - 262144)
            tailer._discard_until_newline = 0 < tailer.offset < stat.st_size
            self._tailers[str(path)] = tailer
            self._sessions[str(path)] = {'active': False, 'state': '', 'turn': '', 'child': child}
        except (OSError, ValueError):
            return

    def _scan(self, now):
        full_scan = self._last_scan is None or now - self._last_scan >= self.scan_interval
        if full_scan:
            self._last_scan = now

        def paths_to_probe():
            if full_scan:
                yield from self.sessions_dir.glob('**/rollout-*.jsonl')
                return
            paths = {key: tailer.file_path for key, tailer in self._tailers.items()}
            # New local turns use dated folders. Probe these every poll, while
            # discovery of resumed older files pays a full scan only every 30s.
            for delta in (-1, 0, 1):
                day = datetime.now() + timedelta(days=delta)
                directory = self.sessions_dir / day.strftime('%Y') / day.strftime('%m') / day.strftime('%d')
                paths.update((str(path), path) for path in directory.glob('rollout-*.jsonl'))
            yield from paths.values()

        def candidates():
            for path in paths_to_probe():
                if self._worker_stop.is_set():
                    return
                try:
                    active = self._sessions.get(str(path), {}).get('active', False)
                    yield active, path.stat().st_mtime, str(path), path
                except OSError:
                    continue

        paths = {str(item[3]): item[3] for item in heapq.nlargest(self.max_files, candidates())}
        removed_active = False
        for key in self._tailers.keys() - paths.keys():
            removed_active |= self._sessions[key]['active']
            del self._tailers[key]
            del self._sessions[key]
        for key, path in paths.items():
            if key not in self._tailers:
                self._add_file(path)
        return removed_active

    def _poll(self, gen=None):
        emit_gen = self._emit_gen if gen is None else gen
        changed = bool(self._scan(time.monotonic()))
        for key, tailer in self._tailers.items():
            session = self._sessions[key]
            for line in tailer.read_new_lines():
                if self._worker_stop.is_set() and self._running:
                    return
                if session['child']:
                    continue
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        continue
                    stamp = datetime.fromisoformat(str(record.get('timestamp') or '').replace('Z', '+00:00')).timestamp()
                    if stamp < self._since:
                        continue
                    event = codex_event(record)
                except (ValueError, TypeError, OverflowError):
                    continue
                if not event.state or event.requires_active and not session['active']:
                    continue
                if event.terminal and event.turn and session['turn'] and event.turn != session['turn']:
                    continue
                session['active'] = not event.terminal
                session['state'] = event.state
                if event.turn:
                    session['turn'] = event.turn
                changed = True
                if event.tool:
                    self._emit_tool(event.tool, emit_gen)
        if changed:
            active = {session['state'] for session in self._sessions.values() if session['active']}
            state = next((value for value in ('attention', 'error', 'working', 'thinking') if value in active), 'idle')
            if state != self._last_state:
                self._last_state = state
                self._emit_state(state, emit_gen)
                log.info('Codex 任务状态 [%s]: %s', self.agent_key, state)
