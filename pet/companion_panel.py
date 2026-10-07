"""Nonmodal command and result surface for the persistent local companion."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDateTime, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QDateTimeEdit, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from .companion_runner import discover_codex_command
from .settings_theme_qss import _settings_stylesheet
from .settings_widgets import BrowserSpinBox, ModernSelect, ResponsiveActionRow, SettingRow, SettingsSection, SettingsTabContainer, _system_dark

STATUS_LABELS = {'queued': '排队中', 'scheduled': '等待下次运行', 'running': '正在执行',
                 'waiting': '需要你的回答', 'paused': '已暂停', 'completed': '已完成',
                 'error': '执行失败', 'cancelled': '已停止'}


def _time(stamp):
    try:
        return datetime.fromtimestamp(float(stamp)).strftime('%m月%d日 %H:%M')
    except (OSError, ValueError, OverflowError):
        return ''


def companion_stylesheet(theme='system'):
    # Apply the shared editor tokens to the text/date controls used by this panel.
    style = _settings_stylesheet(theme).replace('QPlainTextEdit', 'QTextEdit').replace('QDoubleSpinBox', 'QDateTimeEdit')
    muted = '#7f7f89' if theme == 'dark' or (theme == 'system' and _system_dark()) else '#979ba2'
    return style + '\nQPushButton:disabled, QLineEdit:disabled { color: ' + muted + '; }'


class CompanionPanel(QDialog):
    def __init__(self, service, *, open_settings=None, parent=None):
        super().__init__(parent)
        self.service = service
        self._open_settings = open_settings
        self._selected_task = None
        self._selected_memory = None
        self.setWindowTitle('麒麟长期助手')
        self.setObjectName('companionPanel')
        self.setModal(False)
        self.resize(960, 760)
        self.setMinimumSize(680, 500)
        self.setStyleSheet(companion_stylesheet())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        title = QLabel('麒麟长期助手')
        title.setObjectName('pageTitle')
        layout.addWidget(title)
        self.summary = QLabel('交给我持续负责的事情；关闭这个面板后，任务仍会在桌宠中运行。')
        self.summary.setObjectName('settingHint')
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.tabs = SettingsTabContainer()
        self.tabs.addTab('new', '交给麒麟', self._new_page())
        self.tabs.addTab('tasks', '任务与结果', self._tasks_page())
        self.tabs.addTab('memory', '长期记忆', self._memory_page())
        self.tabs.addTab('activity', '活动记录', self._activity_page())
        layout.addWidget(self.tabs, 1)
        self.feedback = QLabel('')
        self.feedback.setWordWrap(True)
        self.feedback.setObjectName('settingHint')
        layout.addWidget(self.feedback)
        footer = QHBoxLayout()
        self.settings_button = QPushButton('AI 设置')
        self.settings_button.clicked.connect(self._settings)
        self.settings_button.setVisible(callable(open_settings))
        footer.addWidget(self.settings_button)
        footer.addStretch()
        footer.addWidget(self.submit)
        self.tabs.stack.currentChanged.connect(lambda _index: self.submit.setVisible(self.tabs.currentKey() == 'new'))
        close = QPushButton('收起面板')
        close.clicked.connect(self.close)
        footer.addWidget(close)
        layout.addLayout(footer)
        QShortcut(QKeySequence('Ctrl+Return'), self, activated=self.submit_task)
        self.service.changed.connect(self.refresh)
        self.refresh()

    def _scroll(self, sections):
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        for section in sections:
            layout.addWidget(section)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName('settingsScroll')
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        return scroll

    @staticmethod
    def _named(widget, name, description=''):
        widget.setAccessibleName(name)
        widget.setAccessibleDescription(description)
        return widget

    def _new_page(self):
        self.instruction = self._named(QTextEdit(), '任务内容', '说明需要的结果和持续负责的范围')
        self.instruction.setObjectName('companionInstruction')
        self.instruction.setAcceptRichText(False)
        self.instruction.setPlaceholderText('例如：阅读这个项目的文档，整理一份中文交付清单。')
        self.instruction.setMinimumHeight(100)
        self.instruction.setMaximumHeight(200)
        self.engine = self._named(ModernSelect(), '执行方式')
        self.engine.setMinimumWidth(0)
        self.engine.setMaximumWidth(16777215)
        self.engine.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.engine.addItem('Codex 本机任务：文件、工具和项目工作', 'codex')
        self.engine.addItem('当前聊天模型：文字分析与整理', 'chat')
        if not discover_codex_command():
            self.engine.setCurrentIndex(1)
        self.engine.currentIndexChanged.connect(self._sync_engine)
        self.workspace = self._named(QLineEdit(), '工作目录')
        self.workspace.setPlaceholderText('留空使用本任务的独立目录')
        browse = QPushButton('选择目录…')
        browse.clicked.connect(self._browse)
        directory = ResponsiveActionRow(self.workspace, [browse])
        self.write_access = self._named(QCheckBox('允许修改所选工作目录'), '允许修改工作目录')
        self.follow_up = self._named(QCheckBox('允许在等待变化时稍后跟进'), '允许稍后跟进')
        self.follow_up.setChecked(True)
        self.schedule = self._named(ModernSelect(), '运行时间')
        self.schedule.setMinimumWidth(0)
        self.schedule.setMaximumWidth(16777215)
        self.schedule.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for label, value in (('现在执行', 0), ('指定时间执行一次', -1), ('每小时', 60),
                             ('每24小时', 1440), ('自定义重复间隔', -2)):
            self.schedule.addItem(label, value)
        self.schedule.currentIndexChanged.connect(self._sync_schedule)
        self.first_run = self._named(QDateTimeEdit(), '首次运行时间', '使用本机时区')
        self.first_run.setCalendarPopup(True)
        self.first_run.setDisplayFormat('yyyy-MM-dd HH:mm')
        self.first_run.setDateTime(QDateTime.currentDateTime().addSecs(300))
        self.interval = self._named(BrowserSpinBox(), '重复间隔分钟')
        self.interval.setRange(1, 525600)
        self.interval.setValue(60)
        self.interval.setSuffix(' 分钟')
        self.time_row = SettingRow('companion.first_run', '首次运行', '按本机时区保存，重启后保留。', self.first_run)
        self.interval_row = SettingRow('companion.interval', '重复间隔', '每轮结束后只等待下一个未来时点。', self.interval)
        self.submit = QPushButton('交给麒麟')
        self.submit.setObjectName('companionSubmit')
        self.submit.setAccessibleName('创建并执行任务')
        self.submit.clicked.connect(self.submit_task)
        page = self._scroll([
            SettingsSection('需要我负责的事情', [
                SettingRow('companion.instruction', '任务内容', '可以随时补充指示，已有上下文会带入下一轮。', self.instruction, stacked=True),
                SettingRow('companion.engine', '执行方式', '本机任务沿用 Codex 当前模型和登录；文字任务使用 AI 设置中的聊天模型。', self.engine, stacked=True),
                SettingRow('companion.workspace', '工作目录', '本机任务只在明确选择的目录内工作。', directory, stacked=True),
                SettingRow('companion.write', '文件修改', '不勾选时使用只读环境。', self.write_access, stacked=True),
            ]),
            SettingsSection('什么时候跟进', [
                SettingRow('companion.schedule', '运行时间', '电脑在线且桌宠运行时执行；休眠后补做一轮，不重放所有错过时点。', self.schedule, stacked=True),
                self.time_row, self.interval_row,
                SettingRow('companion.followup', '后续跟进', '可保存下次检查时间；需要你的决定时会停下来等待回答。', self.follow_up, stacked=True),
            ]),
        ])
        self._sync_engine()
        self._sync_schedule()
        return page

    def _tasks_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.task_list = self._named(QListWidget(), '任务列表')
        self.task_list.setWordWrap(True)
        self.task_list.setMinimumHeight(90)
        self.task_list.currentItemChanged.connect(self._task_selected)
        self.result = self._named(QTextEdit(), '任务详情和结果')
        self.result.setReadOnly(True)
        self.result.setMinimumHeight(140)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.task_list)
        self.splitter.addWidget(self.result)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        layout.addWidget(self.splitter, 1)
        row = QHBoxLayout()
        self.pause_button = QPushButton('暂停')
        self.cancel_button = QPushButton('停止')
        self.remove_button = QPushButton('移除记录')
        self.output_button = QPushButton('打开结果')
        self.pause_button.clicked.connect(lambda: self._task_action('pause'))
        self.cancel_button.clicked.connect(lambda: self._task_action('cancel'))
        self.remove_button.clicked.connect(lambda: self._task_action('remove'))
        self.output_button.clicked.connect(self._open_output)
        for button in (self.pause_button, self.cancel_button, self.output_button, self.remove_button):
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        self.answer = self._named(QLineEdit(), '补充指示或回答')
        self.answer.setPlaceholderText('补充要求、回答问题，或留空继续原任务')
        self.answer.setMaxLength(4000)
        self.resume_button = QPushButton('继续任务')
        self.resume_button.clicked.connect(lambda: self._task_action('resume'))
        self.answer.returnPressed.connect(lambda: self._task_action('resume'))
        layout.addWidget(ResponsiveActionRow(self.answer, [self.resume_button]))
        return page

    def _memory_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel('保存你希望麒麟长期记住的偏好和事实。普通聊天与后续任务会使用这些记忆；可随时编辑或删除。')
        hint.setWordWrap(True)
        hint.setObjectName('settingHint')
        layout.addWidget(hint)
        self.memory_list = self._named(QListWidget(), '长期记忆列表')
        self.memory_list.setWordWrap(True)
        self.memory_list.currentItemChanged.connect(self._memory_selected)
        layout.addWidget(self.memory_list, 1)
        self.memory_text = self._named(QTextEdit(), '记忆内容')
        self.memory_text.setAcceptRichText(False)
        self.memory_text.setMaximumHeight(100)
        self.memory_text.setPlaceholderText('例如：项目报告使用中文，并附实际验证结果。')
        layout.addWidget(self.memory_text)
        row = QHBoxLayout()
        self.memory_save = QPushButton('保存记忆')
        self.memory_save.clicked.connect(self._save_memory)
        self.memory_delete = QPushButton('删除记忆')
        self.memory_delete.clicked.connect(self._delete_memory)
        fresh = QPushButton('新建记忆')
        fresh.clicked.connect(self._new_memory)
        for button in (self.memory_save, self.memory_delete, fresh):
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        return page

    def _activity_page(self):
        self.activity = self._named(QTextEdit(), '活动记录')
        self.activity.setReadOnly(True)
        return self.activity

    def _sync_engine(self):
        local = self.engine.currentData() == 'codex'
        self.write_access.setEnabled(local)
        self.workspace.setEnabled(local)
        if not local:
            self.write_access.setChecked(False)

    def _sync_schedule(self):
        choice = self.schedule.currentData()
        self.time_row.setVisible(choice != 0)
        self.interval_row.setVisible(choice == -2)

    def _browse(self):
        directory = QFileDialog.getExistingDirectory(self, '选择工作目录', self.workspace.text())
        if directory:
            self.workspace.setText(directory)

    def prefill(self, text):
        self.instruction.setPlainText(str(text))
        self.tabs.setCurrentKey('new')
        self.instruction.setFocus()

    def submit_task(self):
        if self.tabs.currentKey() != 'new':
            return
        choice = self.schedule.currentData()
        run_at = None if choice == 0 else self.first_run.dateTime().toSecsSinceEpoch()
        repeat = self.interval.value() if choice == -2 else max(0, choice)
        try:
            task = self.service.create_task(self.instruction.toPlainText(), engine=self.engine.currentData(),
                                            workspace=self.workspace.text().strip(), write_access=self.write_access.isChecked(),
                                            run_at=run_at, repeat_minutes=repeat, follow_up=self.follow_up.isChecked())
        except (ValueError, RuntimeError, OSError) as exc:
            self.feedback.setText(str(exc))
            return
        self.instruction.clear()
        self.feedback.setText('任务已保存，可以继续给其他任务或收起面板。')
        self.select_task(task['id'])

    def select_task(self, task_id):
        self._selected_task = task_id
        self.refresh()
        self.tabs.setCurrentKey('tasks')

    def _task_selected(self, current, previous=None):
        self._selected_task = current.data(Qt.ItemDataRole.UserRole) if current else None
        task = self.service.store.get_task(self._selected_task) if self.service.store and self._selected_task else None
        selected = bool(task) and self.service.available
        status = task['status'] if task else ''
        self.pause_button.setEnabled(selected and status in ('running', 'scheduled', 'queued'))
        self.cancel_button.setEnabled(selected and status not in ('cancelled', 'completed'))
        self.resume_button.setEnabled(selected and status not in ('running', 'queued'))
        self.remove_button.setEnabled(selected and status != 'running')
        self.output_button.setEnabled(selected and bool(task.get('output_path')))
        self.answer.setEnabled(selected and status != 'running')
        if not task:
            self.result.setPlainText('选择任务查看进展和结果。')
            return
        lines = [task['title'], STATUS_LABELS.get(status, status), '', '任务：', task['instruction']]
        if task['engine'] == 'codex':
            lines += ['', '工作目录：' + task['workspace'], '文件修改：' + ('允许' if task['write_access'] else '只读')]
        if status == 'scheduled':
            lines += ['', '下次运行：' + _time(task['next_run']) + '（本机时区）']
        if task['followups']:
            lines += ['', '最新指示：', task['followups'][-1]]
        if task['error']:
            lines += ['', '需要处理：', task['error']]
        if task['result']:
            lines += ['', '最近结果：', task['result']]
        if task['memory_suggestions']:
            lines += ['', '建议记住（可复制到长期记忆保存）：', *task['memory_suggestions']]
        self.result.setPlainText('\n'.join(lines))

    def _task_action(self, action):
        if not self._selected_task:
            return
        try:
            if action == 'pause':
                self.service.pause(self._selected_task)
            elif action == 'cancel':
                self.service.pause(self._selected_task, cancel=True)
            elif action == 'remove':
                self.service.delete_task(self._selected_task)
                self.feedback.setText('已移除任务记录，已有结果文件保留。')
            else:
                self.service.resume(self._selected_task, self.answer.text())
                self.answer.clear()
        except (ValueError, RuntimeError, OSError) as exc:
            self.feedback.setText(str(exc))

    def _open_output(self):
        task = self.service.store.get_task(self._selected_task) if self._selected_task else None
        if not task or not task.get('output_path'):
            return
        path = Path(task['output_path']).resolve()
        if path.is_relative_to(self.service.store.root / 'outputs') and path.suffix == '.md' and path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _memory_selected(self, current, previous=None):
        self._selected_memory = current.data(Qt.ItemDataRole.UserRole) if current else None
        memory = next((x for x in self.service.store.memories() if x['id'] == self._selected_memory), None) if self.service.store else None
        self.memory_text.setPlainText(memory['text'] if memory else '')

    def _new_memory(self):
        self.memory_list.setCurrentRow(-1)
        self._selected_memory = None
        self.memory_text.clear()
        self.memory_text.setFocus()

    def _save_memory(self):
        try:
            memory = self.service.put_memory(self.memory_text.toPlainText(), self._selected_memory)
            self._selected_memory = memory['id']
            self.refresh()
            self.feedback.setText('记忆已保存，下一次聊天和任务会使用。')
        except (ValueError, RuntimeError) as exc:
            self.feedback.setText(str(exc))

    def _delete_memory(self):
        if self._selected_memory:
            try:
                self.service.delete_memory(self._selected_memory)
            except (ValueError, RuntimeError, OSError) as exc:
                self.feedback.setText(str(exc))
                return
            self._new_memory()
            self.feedback.setText('这条长期记忆已删除。')

    def _settings(self):
        if callable(self._open_settings):
            self._open_settings()

    def refresh(self):
        self.submit.setEnabled(self.service.available)
        self.memory_save.setEnabled(self.service.available)
        self.memory_delete.setEnabled(self.service.available)
        if not self.service.available or self.service.unavailable_reason:
            self.summary.setText(self.service.unavailable_reason or '长期助手已停止。')
        if not self.service.store:
            self._task_selected(None)
            self.memory_delete.setEnabled(False)
            return
        self.task_list.blockSignals(True)
        self.task_list.clear()
        current = None
        for task in reversed(self.service.store.tasks()):
            item = QListWidgetItem(task['title'] + '\n' + STATUS_LABELS[task['status']])
            item.setData(Qt.ItemDataRole.UserRole, task['id'])
            self.task_list.addItem(item)
            if task['id'] == self._selected_task:
                current = item
        self.task_list.setCurrentItem(current)
        self.task_list.blockSignals(False)
        self._task_selected(current)
        self.memory_list.blockSignals(True)
        self.memory_list.clear()
        for memory in self.service.store.memories():
            item = QListWidgetItem(memory['text'])
            item.setData(Qt.ItemDataRole.UserRole, memory['id'])
            self.memory_list.addItem(item)
            if memory['id'] == self._selected_memory:
                self.memory_list.setCurrentItem(item)
        self.memory_list.blockSignals(False)
        self.activity.setPlainText('\n\n'.join(_time(x['at']) + '  ' + x['text'] for x in self.service.store.activity()))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, 'splitter'):
            self.splitter.setOrientation(Qt.Orientation.Vertical if self.width() < 850 else Qt.Orientation.Horizontal)

    def closeEvent(self, event):  # noqa: N802
        try:
            self.service.changed.disconnect(self.refresh)
        except (RuntimeError, TypeError):
            pass
        super().closeEvent(event)
