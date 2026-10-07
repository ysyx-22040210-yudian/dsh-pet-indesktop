"""Execution boundaries for the local companion; no GUI or account rewrites."""
from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from .companion_store import TEXT_LIMIT, TaskOutcome

RESULT_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'message': {'type': 'string'},
        'status': {'type': 'string', 'enum': ['completed', 'waiting', 'followup']},
        'wake_at': {'type': ['string', 'null']},
        'memory_suggestions': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['message', 'status', 'wake_at', 'memory_suggestions'],
}


class RunnerError(RuntimeError):
    pass


class RunCancelled(RuntimeError):
    pass


def discover_codex_command():
    """Resolve installed native CLI without evaluating shell wrappers or tokens."""
    if os.name != 'nt':
        path = shutil.which('codex')
        return [path] if path else []
    executable = shutil.which('codex.exe')
    if executable:
        return [executable]
    wrapper = shutil.which('codex.cmd') or shutil.which('codex') or shutil.which('codex.ps1')
    if not wrapper:
        return []
    package = Path(wrapper).parent / 'node_modules' / '@openai' / 'codex'
    candidates = []
    for pattern in ('node_modules/@openai/codex-*/vendor/*/bin/codex.exe',
                    'node_modules/@openai/codex-*/vendor/*/codex/codex.exe',
                    'vendor/*/bin/codex.exe', 'vendor/*/codex/codex.exe'):
        candidates.extend(package.glob(pattern))
    return [str(candidates[0])] if candidates else []


def codex_command(executable, task, schema):
    mode = 'workspace-write' if task.get('write_access') else 'read-only'
    command = [*executable, '--cd', str(task['workspace']), '--sandbox', mode, 'exec']
    thread_id = str(task.get('thread_id') or '')
    if thread_id:
        try:
            thread_id = str(uuid.UUID(thread_id))
        except ValueError as exc:
            raise RunnerError('保存的任务会话标识无效。') from exc
        command.append('resume')
    command.extend(['--json', '--color', 'never'] if not thread_id else ['--json'])
    command.extend(['--skip-git-repo-check', '--output-schema', str(schema)])
    if thread_id:
        command.append(thread_id)
    command.append('-')
    return command


def parse_outcome(text, thread_id='', *, strict=True):
    text = str(text).strip()
    if not text or len(text) > TEXT_LIMIT:
        raise RunnerError('模型没有返回有效结果，任务不能判为完成。')
    candidate = text
    if candidate.startswith('```') and candidate.endswith('```'):
        candidate = candidate.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        data = json.loads(candidate)
        if (not isinstance(data, dict) or not isinstance(data.get('message'), str)
                or not data['message'].strip() or data.get('status') not in ('completed', 'waiting', 'followup')
                or not isinstance(data.get('memory_suggestions', []), list)):
            raise ValueError('结果结构无效')
    except (ValueError, TypeError):
        if strict:
            raise RunnerError('执行结果不符合任务协议，请检查结果后再继续。') from None
        return TaskOutcome(text, thread_id=thread_id)
    wake_at = None
    if data.get('wake_at'):
        try:
            stamp = datetime.fromisoformat(str(data['wake_at']).replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('时区缺失')
            wake_at = stamp.timestamp()
        except (ValueError, OverflowError, OSError):
            pass
    return TaskOutcome(data['message'].strip(), data['status'], wake_at, thread_id,
                       tuple(str(x)[:1000] for x in data.get('memory_suggestions', [])[:5]))


class _ProcessScope:
    """An independent kill-on-close job/group containing only this spawned task."""
    def __init__(self, process):
        self.process = process
        self.handle = None
        if os.name == 'nt':
            import ctypes
            from . import win_job

            api = win_job._api()
            handle = api.CreateJobObjectW(None, None)
            if handle:
                info = win_job._JOBOBJECT_EXTENDED_LIMIT_INFORMATION_STRUCT()
                info.BasicLimitInformation.LimitFlags = win_job._JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                if (api.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info))
                        and api.AssignProcessToJobObject(handle, int(process._handle))):
                    self.handle = handle
                else:
                    api.CloseHandle(handle)
            if self.handle is None and process.poll() is None:
                process.terminate()
                raise RunnerError('无法建立任务子进程回收边界，本次没有继续执行。')

    def close(self):
        if os.name == 'nt':
            if self.handle is not None:
                from . import win_job
                win_job._api().CloseHandle(self.handle)
                self.handle = None
        else:
            try:
                if os.getpgid(self.process.pid) == self.process.pid:
                    os.killpg(self.process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


class CodexRunner:
    def __init__(self, executable=None, *, timeout=3600):
        self.executable = executable if executable is not None else discover_codex_command()
        self.timeout = timeout
        self._scope = None
        self._guard = threading.Lock()

    def cancel(self):
        with self._guard:
            if self._scope is not None:
                self._scope.close()

    def run(self, task, prompt, cancel, progress, output_root):
        if cancel.is_set():
            raise RunCancelled()
        if not self.executable:
            raise RunnerError('未找到本机 Codex CLI，请先安装并登录，或选择当前聊天模型执行文字任务。')
        output_root = Path(output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        schema = output_root / 'result-schema.json'
        schema.write_text(json.dumps(RESULT_SCHEMA), encoding='utf-8')
        directory = Path(task['workspace'])
        if not directory.is_dir():
            raise RunnerError('工作目录不存在，请重新选择工作目录。')
        command = codex_command(self.executable, task, schema)
        kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
        try:
            process = subprocess.Popen(command, cwd=directory, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        except OSError as exc:
            raise RunnerError('任务执行器无法启动，请检查 CLI 和工作目录。') from exc
        events = queue.Queue(maxsize=128)
        errors = []

        def read_output():
            try:
                while True:
                    line = process.stdout.readline(1024 * 1024 + 1)
                    if not line:
                        break
                    if len(line) > 1024 * 1024:
                        errors.append('执行器事件超出大小上限。')
                        break
                    while not cancel.is_set():
                        try:
                            events.put(line, timeout=.1)
                            break
                        except queue.Full:
                            continue
            except (OSError, ValueError):
                pass

        def drain_errors():
            try:
                while process.stderr.read(4096):
                    pass
            except (OSError, ValueError):
                pass

        reader = threading.Thread(target=read_output, name='companion-cli-output', daemon=True)
        error_reader = threading.Thread(target=drain_errors, name='companion-cli-stderr', daemon=True)
        final, completed, thread_id = '', False, str(task.get('thread_id') or '')
        started = time.monotonic()
        last_progress = ''
        try:
            with self._guard:
                self._scope = _ProcessScope(process)
            reader.start()
            error_reader.start()
            if cancel.is_set():
                raise RunCancelled()
            try:
                process.stdin.write(prompt.encode('utf-8'))
                process.stdin.close()
            except (OSError, BrokenPipeError):
                pass
            while reader.is_alive() or not events.empty() or process.poll() is None:
                if cancel.is_set():
                    raise RunCancelled()
                if time.monotonic() - started > self.timeout:
                    raise RunnerError('本轮执行超过一小时，已停止；可以检查结果后继续。')
                if errors:
                    raise RunnerError(errors[0])
                try:
                    line = events.get(timeout=.05)
                except queue.Empty:
                    continue
                try:
                    event = json.loads(line.decode('utf-8'))
                except (ValueError, UnicodeError):
                    continue
                if not isinstance(event, dict):
                    continue
                kind = event.get('type')
                if kind == 'thread.started':
                    try:
                        thread_id = str(uuid.UUID(str(event.get('thread_id'))))
                    except ValueError:
                        raise RunnerError('执行器返回了无效会话标识。') from None
                    progress({'text': '已连接本机任务会话', 'thread_id': thread_id})
                elif kind == 'turn.failed':
                    raise RunnerError('本轮任务执行失败，请检查登录、网络或模型配置后继续。')
                elif kind == 'turn.completed':
                    completed = True
                elif kind in ('item.started', 'item.completed'):
                    item = event.get('item')
                    if not isinstance(item, dict):
                        continue
                    item_type = str(item.get('type', '')).replace('_', '').casefold()
                    if item_type == 'agentmessage' and kind == 'item.completed' and item.get('phase') != 'commentary':
                        final = str(item.get('text') or '')
                    label = {'commandexecution': '正在执行本机步骤', 'filechange': '正在处理工作目录文件',
                             'websearch': '正在检索资料', 'mcptoolcall': '正在使用已连接工具',
                             'reasoning': '正在分析任务', 'plan': '正在更新执行计划'}.get(item_type, '')
                    if label and kind == 'item.started' and label != last_progress:
                        progress({'text': label, 'thread_id': thread_id})
                        last_progress = label
            if cancel.is_set():
                raise RunCancelled()
            if process.wait(timeout=2) != 0 or not completed:
                raise RunnerError('执行进程未确认本轮完成，任务结果需要检查。')
            return parse_outcome(final, thread_id)
        finally:
            self.cancel()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            reader.join(timeout=1) if reader.ident is not None else None
            error_reader.join(timeout=1) if error_reader.ident is not None else None
            for stream in (process.stdin, process.stdout, process.stderr):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass


class ChatRunner:
    """Text responsibilities use the already selected provider, model and secrets."""
    def __init__(self, config, provider=None):
        from .chat.providers import OpenAICompatibleProvider
        self.config = config
        self.provider = provider or OpenAICompatibleProvider()
        self._responses = []

    def cancel(self):
        for response in list(self._responses):
            try:
                response.close()
            except Exception:
                pass

    def run(self, task, prompt, cancel, progress, output_root):
        progress({'text': '正在使用当前聊天模型整理文字任务'})
        messages = [{'role': 'system', 'content': '你负责文字分析和整理，不具备文件、联网或电脑操作工具。'
                     '只能报告根据已提供内容实际得出的结果，需要更多资料时返回 waiting。'},
                    {'role': 'user', 'content': prompt}]
        parts, size = [], 0
        for part in self.provider.stream(messages, self.config, cancel, response_holder=self._responses):
            if cancel.is_set():
                raise RunCancelled()
            size += len(part)
            if size > TEXT_LIMIT:
                self.cancel()
                raise RunnerError('本轮回复过长，请缩小任务范围后继续。')
            parts.append(part)
        if cancel.is_set():
            raise RunCancelled()
        return parse_outcome(''.join(parts))
