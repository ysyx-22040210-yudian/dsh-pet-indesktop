"""On-demand local process discovery and portable Agent source bindings."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from string import Template


@dataclass(frozen=True)
class RunningProgram:
    pid: int
    name: str
    executable: str
    cwd: str


@dataclass(frozen=True)
class AgentSource:
    path: Path
    adapter: str


def expand_agent_path(value: str | Path) -> Path:
    return Path(os.path.expandvars(str(value))).expanduser()


def portable_path(path: str | Path, *, home: Path | None = None) -> str:
    path = expand_agent_path(path).absolute()
    try:
        return '~/' + path.relative_to(home or Path.home()).as_posix()
    except ValueError:
        return str(path)


def is_shared_runtime(name: str) -> bool:
    name = name.lower()
    return name in {'node', 'node.exe', 'bun', 'bun.exe', 'electron', 'electron.exe', 'deno', 'deno.exe'} \
        or re.fullmatch(r'pythonw?(?:\d+(?:\.\d+)*)?(?:\.exe)?', name) is not None


def discover_programs(*, cancelled=lambda: False) -> list[RunningProgram]:
    """Return current-user executables, including renamed forks, without command text."""
    import psutil
    username = psutil.Process().username()
    programs = {}
    for process in psutil.process_iter(attrs=['pid', 'name', 'exe', 'cwd', 'username'], ad_value=''):
        if cancelled():
            break
        try:
            info = process.info
            if info.get('username') and info['username'].casefold() != username.casefold():
                continue
            executable, name = info.get('exe') or '', info.get('name') or ''
            if not executable or not name:
                continue
            program = RunningProgram(int(info['pid']), name, executable, info.get('cwd') or '')
            key = executable.casefold() if os.name == 'nt' else executable
            if is_shared_runtime(name):
                key = (key, program.pid)
            if key not in programs or program.pid < programs[key].pid:
                programs[key] = program
        except (psutil.Error, OSError, ValueError, KeyError):
            continue
    return sorted(programs.values(), key=lambda item: ('opencode' not in item.name.lower(), item.name.casefold()))


def validate_source(path: str | Path, adapter: str) -> str:
    source = expand_agent_path(path)
    if adapter == 'codex':
        if not source.is_dir() or source.name != 'sessions':
            return '请选择 Codex 的 sessions 文件夹（通常在 ~/.codex/sessions），不能选择通用事件文件。'
        return ''
    if adapter == 'jsonl':
        if source.exists() and not source.is_file():
            return '请选择事件文件，不能选择文件夹。'
        if source.suffix.lower() != '.jsonl':
            return '事件文件需要使用 .jsonl 扩展名；尚未创建的文件也可以绑定。'
        if source.is_file():
            try:
                size = source.stat().st_size
                if not size:
                    return ''
                with source.open('rb') as stream:
                    stream.seek(max(0, size - 65536))
                    lines = stream.read(65536).decode('utf-8-sig', 'replace').splitlines()
                for line in lines:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(record, dict):
                        state, event = record.get('state'), record.get('event')
                        if (
                            isinstance(state, str) and state in {'working', 'thinking', 'attention', 'error', 'idle', 'sleeping'}
                            or isinstance(event, str) and event in {'SessionStart', 'SessionEnd', 'UserPromptSubmit', 'PreToolUse',
                                                                  'PostToolUse', 'PostToolUseFailure', 'Stop', 'StopFailure', 'SubagentStop'}
                        ):
                            return ''
                return '这个文件没有兼容的任务事件。请选择事件文件，或新建通道并导出插件。'
            except OSError as exc:
                return f'无法读取事件文件：{exc}'
        return ''
    if adapter != 'opencode':
        return '不支持的联动方式。'
    if not source.is_file():
        return '请选择已经存在的 OpenCode 兼容数据库。'
    try:
        with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True, timeout=0.2)) as database:
            columns = {row[1] for row in database.execute('PRAGMA table_info(event)')}
        if {'type', 'data'} <= columns:
            return ''
        return '这个数据库没有兼容的事件表。请使用事件文件，并导出 OpenCode 插件接入。'
    except (sqlite3.Error, OSError) as exc:
        return f'无法只读打开数据库：{exc}'


def find_program_sources(program: RunningProgram, *, home: Path | None = None,
                         opened_paths=None, cancelled=lambda: False) -> list[AgentSource]:
    """Probe selected process handles and a bounded set of nearby data directories."""
    home = home or Path.home()
    if opened_paths is None:
        import psutil
        try:
            opened_paths = [item.path for item in psutil.Process(program.pid).open_files()]
        except (psutil.Error, OSError):
            opened_paths = []
    candidates = [Path(path) for path in opened_paths if Path(path).suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.jsonl'}]
    stem = Path(program.name).stem
    slugs = {stem, stem.lower()}
    if 'opencode' in program.name.lower() or 'opencode' in program.executable.lower():
        slugs.add('opencode')
    roots = [Path(program.executable).parent]
    if program.cwd:
        roots.append(Path(program.cwd))
    for slug in slugs:
        roots.extend([home / '.local' / 'share' / slug, home / '.config' / slug])
        for variable in ('APPDATA', 'LOCALAPPDATA', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME'):
            if os.environ.get(variable):
                roots.append(Path(os.environ[variable]) / slug)
    for root in dict.fromkeys(roots):
        if str(root).startswith('\\\\') or cancelled():
            continue
        for folder in (root, root / 'data', root / '.data', root / 'storage'):
            candidates.extend(folder / name for name in ('opencode.db', f'{stem}.db', 'pet-events.jsonl'))
    result, seen = [], set()
    codex_roots = []
    if Path(program.name).stem.casefold() == 'codex' or 'openai' in program.executable.casefold() and 'codex' in program.executable.casefold():
        codex_roots.append(expand_agent_path(os.environ.get('CODEX_HOME') or home / '.codex') / 'sessions')
    for path in candidates:
        if path.name.startswith('rollout-') and path.suffix.lower() == '.jsonl':
            root = next((parent for parent in path.parents if parent.name == 'sessions'), None)
            if root:
                codex_roots.append(root)
    for root in dict.fromkeys(codex_roots):
        if not cancelled() and not validate_source(root, 'codex'):
            result.append(AgentSource(root, 'codex'))
    for path in candidates[:256]:
        if cancelled():
            break
        identity = os.path.normcase(os.path.abspath(path))
        if identity in seen or not path.is_file():
            continue
        seen.add(identity)
        if any(root in path.parents for root in codex_roots):
            continue
        adapter = 'jsonl' if path.suffix.lower() == '.jsonl' else 'opencode'
        if not validate_source(path, adapter):
            result.append(AgentSource(path, adapter))
    return result


def binding_key(name: str, existing) -> str:
    stem = re.sub(r'[^a-z0-9_-]+', '-', name.lower()).strip('-')[:18] or 'agent'
    stem = 'agent-' + stem
    key, number = stem, 2
    while key in existing:
        key = f'{stem}-{number}'
        number += 1
    return key


def render_opencode_plugin(events_path: str | Path, agent_key: str) -> str:
    """Export a zero-dependency hook; user chooses its installation destination."""
    destination = json.dumps(portable_path(events_path), ensure_ascii=False)
    agent = json.dumps(agent_key)
    return Template('''// Qilin pet OpenCode-compatible bridge. Only task metadata is recorded.
import { appendFile, mkdir, stat, rename } from "node:fs/promises";
import { dirname, join } from "node:path";
import { homedir } from "node:os";

export const QilinPetBridge = async () => {
  const destination = ${destination};
  const file = destination.startsWith("~/") ? join(homedir(), destination.slice(2)) : destination;
  let pending = Promise.resolve();
  const children = new Set();
  const write = (state, tool = "", sessionID = "") => {
    if (children.has(sessionID)) return Promise.resolve();
    pending = pending.then(async () => {
      await mkdir(dirname(file), { recursive: true });
      const size = await stat(file).then(s => s.size).catch(() => 0);
      if (size > 1024 * 1024) await rename(file, file + ".1").catch(() => {});
      await appendFile(file, JSON.stringify({ ts: Date.now() / 1000, agent: ${agent}, state, tool, session_id: sessionID }) + "\\n", "utf8");
    }).catch(() => {});
    return pending;
  };
  return {
    event: async ({ event }) => {
      const p = event.properties || {};
      const sessionID = p.sessionID || p.info?.id || "";
      if (event.type === "session.created" && p.info?.parentID) children.add(p.info.id);
      if (event.type === "session.status") {
        const state = { busy: "working", idle: "idle", retry: "thinking" }[p.status?.type];
        if (state) await write(state, "", sessionID);
      } else if (event.type === "session.idle") await write("idle", "", sessionID);
      else if (event.type === "session.error") await write("error", "", sessionID);
      else if (event.type === "permission.asked") await write("attention", "", sessionID);
    },
    "tool.execute.before": async (input) => write("working", input.tool || "", input.sessionID || ""),
    "tool.execute.after": async (input) => write("working", input.tool || "", input.sessionID || ""),
  };
};
''').substitute(destination=destination, agent=agent)
