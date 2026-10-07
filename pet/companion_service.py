"""One GUI-owned coordinator; work and network I/O run outside the GUI thread."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QLockFile, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication

from .companion_runner import ChatRunner, CodexRunner, RunCancelled
from .companion_store import StoreError, TaskStore, build_task_prompt


class _Bridge(QObject):
    progress = Signal(str, str, object)
    result = Signal(str, str, object, str)


class CompanionService(QObject):
    changed = Signal()
    notification = Signal(object)

    def __init__(self, root, *, config=None, runner_factory=None, parent=None):
        super().__init__(parent)
        self.available = False
        self.unavailable_reason = ''
        self.store = None
        self.config = config
        self._runner_factory = runner_factory
        self._jobs = {}
        self._stopped = False
        self._about_connected = False
        self._last_progress = {}
        self._bridge = _Bridge(self)
        self._bridge.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self._bridge.result.connect(self._on_result, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self.tick)
        root = Path(root)
        self._lock = QLockFile(str(root / 'coordinator.lock'))
        self._lock.setStaleLockTime(0)
        try:
            root.mkdir(parents=True, exist_ok=True)
            if not self._lock.tryLock(0):
                self.unavailable_reason = '长期助手已在另一个桌宠进程中运行，请在该桌宠打开。'
                return
            self.store = TaskStore(root)
            self.store.recover_interrupted()
        except (OSError, StoreError) as exc:
            self.unavailable_reason = str(exc)
            self._lock.unlock()
            return
        self.available = True
        if any(t['status'] in ('queued', 'scheduled') for t in self.store.tasks()):
            self._timer.start()
            QTimer.singleShot(0, self.tick)
        application = QApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.stop)
            self._about_connected = True

    def _ensure_available(self):
        if not self.available or self._stopped:
            raise StoreError(self.unavailable_reason or '长期助手已经停止。')

    def create_task(self, instruction, **options):
        self._ensure_available()
        task = self.store.create_task(instruction, **options)
        self._timer.start()
        self.changed.emit()
        QTimer.singleShot(0, self.tick)
        return task

    def pause(self, task_id, *, cancel=False):
        self._ensure_available()
        task = self.store.pause(task_id, cancel=cancel)
        job = self._jobs.get(task_id)
        if job:
            job['cancel'].set()
            job['runner'].cancel()
        self.changed.emit()
        return task

    def resume(self, task_id, answer=''):
        self._ensure_available()
        if task_id in self._jobs:
            raise ValueError('上一轮还在结束，请稍后继续。')
        task = self.store.resume(task_id, answer)
        self._timer.start()
        self.changed.emit()
        QTimer.singleShot(0, self.tick)
        return task

    def delete_task(self, task_id):
        self._ensure_available()
        if task_id in self._jobs:
            raise ValueError('上一轮还在结束，请稍后移除。')
        self.store.delete_task(task_id)
        self.changed.emit()

    def put_memory(self, text, memory_id=None):
        self._ensure_available()
        result = self.store.put_memory(text, memory_id)
        self.changed.emit()
        return result

    def delete_memory(self, memory_id):
        self._ensure_available()
        self.store.delete_memory(memory_id)
        self.changed.emit()

    def _make_runner(self, task):
        if self._runner_factory:
            return self._runner_factory(task)
        if task['engine'] == 'codex':
            return CodexRunner()
        if self.config is None:
            raise StoreError('请先在 AI 设置配置当前聊天模型。')
        from .chat.models import ProviderConfig, SecretStore
        settings = self.config.chat_settings()
        provider = ProviderConfig.from_dict(settings.active_provider, settings.active_config.to_dict())
        if not provider.api_key:
            provider.api_key = SecretStore().get(provider.api_key_ref)
        return ChatRunner(provider)

    def tick(self):
        if not self.available or self._stopped:
            return
        capacity = 2 - len(self._jobs)
        try:
            tasks = self.store.claim_due(time.time(), limit=capacity,
                                         active_tasks=[job['task'] for job in self._jobs.values()])
        except (StoreError, OSError) as exc:
            self._storage_failed(exc)
            return
        for task in tasks:
            try:
                if Path(task['workspace']).is_relative_to(self.store.root / 'workspaces'):
                    Path(task['workspace']).mkdir(parents=True, exist_ok=True)
                runner = self._make_runner(task)
            except Exception as exc:
                try:
                    failed = self.store.fail(task['id'], task['run_id'], str(exc))
                except StoreError as save_error:
                    self._storage_failed(save_error)
                    return
                self.notification.emit(failed)
                self.changed.emit()
                continue
            cancel = threading.Event()
            prompt = build_task_prompt(task, self.store.memories())
            bridge = self._bridge
            output_root = self.store.root / 'run-data' / task['run_id']

            def work(task=task, runner=runner, cancel=cancel, prompt=prompt, output_root=output_root):
                result, error = None, ''
                try:
                    result = runner.run(task, prompt, cancel,
                                        lambda event: bridge.progress.emit(task['id'], task['run_id'], event), output_root)
                except RunCancelled:
                    pass
                except Exception as exc:
                    error = str(exc)[:1000]
                try:
                    bridge.result.emit(task['id'], task['run_id'], result, error)
                except RuntimeError:
                    pass  # The application already quit; no GUI object is touched.

            thread = threading.Thread(target=work, name='qilin-responsibility', daemon=True)
            self._jobs[task['id']] = {'thread': thread, 'cancel': cancel, 'runner': runner, 'task': task}
            thread.start()
            self.changed.emit()
        if not self._jobs and not any(t['status'] in ('queued', 'scheduled') for t in self.store.tasks()):
            self._timer.stop()

    def _on_progress(self, task_id, run_id, event):
        if self._stopped or not self.available or not isinstance(event, dict):
            return
        key = (task_id, run_id)
        text = str(event.get('text') or '')[:500]
        thread_id = str(event.get('thread_id') or '')
        previous = self._last_progress.get(key)
        now = time.monotonic()
        if previous and thread_id == previous[2] and (text == previous[0] or now - previous[1] < 2):
            return
        self._last_progress[key] = (text, now, thread_id)
        try:
            self.store.record_progress(task_id, run_id, text, thread_id=thread_id)
        except StoreError as exc:
            self._storage_failed(exc)
            return
        self.changed.emit()

    def _on_result(self, task_id, run_id, result, error):
        job = self._jobs.get(task_id)
        if job and job['task']['run_id'] == run_id:
            del self._jobs[task_id]
        self._last_progress.pop((task_id, run_id), None)
        if self._stopped or not self.available:
            return
        try:
            task = (self.store.fail(task_id, run_id, error) if error
                    else self.store.finish(task_id, run_id, result) if result is not None else None)
            if task is not None:
                if task.get('notify', True):
                    self.notification.emit(task)
        except StoreError as exc:
            self._storage_failed(exc)
            return
        self.changed.emit()
        QTimer.singleShot(0, self.tick)

    def _storage_failed(self, error):
        self.available = False
        self.unavailable_reason = str(error) + ' 请检查存储后重启桌宠，未完成任务会暂停。'
        self._timer.stop()
        for job in self._jobs.values():
            job['cancel'].set()
            job['runner'].cancel()
        self.changed.emit()

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        self._timer.stop()
        for task_id, job in list(self._jobs.items()):
            job['cancel'].set()
            job['runner'].cancel()
            if self.store:
                try:
                    self.store.pause(task_id)
                except StoreError:
                    pass
        deadline = time.monotonic() + 1.5
        for job in list(self._jobs.values()):
            job['thread'].join(max(0, deadline - time.monotonic()))
        if self._lock.isLocked():
            self._lock.unlock()
        self.available = False
        application = QApplication.instance()
        if application is not None and self._about_connected:
            try:
                application.aboutToQuit.disconnect(self.stop)
                self._about_connected = False
            except (RuntimeError, TypeError):
                pass
