"""Identify running programs and bind compatible local task-event sources."""
from __future__ import annotations

import queue
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHeaderView, QLabel, QLineEdit,
    QPushButton, QScrollArea, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from .agent_discovery import (
    binding_key, discover_programs, expand_agent_path, find_program_sources,
    portable_path, render_opencode_plugin, validate_source, is_shared_runtime,
)
from .settings_theme_qss import _settings_stylesheet
from .settings_widgets import ModernSelect, ResponsiveActionRow, SettingRow, SettingsSection


class RunningAgentsDialog(QDialog):
    bindings_changed = Signal()

    def __init__(self, config, parent=None, *, scan_on_open=True):
        super().__init__(parent)
        self.cfg = config
        self._program = None
        self._editing_key = ''
        self._source_generation = 0
        self._scan_generation = 0
        self._results = queue.Queue()
        self._cancel = threading.Event()
        self.setWindowTitle('识别与联动 Agent')
        self.setMinimumSize(720, 500)
        self.resize(900, 760)
        self.setStyleSheet(_settings_stylesheet())
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        title = QLabel('识别与联动 Agent')
        title.setObjectName('pageTitle')
        root.addWidget(title)
        hint = QLabel('选择正在运行的程序，再绑定它的数据源。改名或二次开发的 Agent 也可以添加。'
                      '任务状态来自数据库或事件文件；程序运行本身不会触发干活动画。')
        hint.setWordWrap(True)
        hint.setObjectName('settingHint')
        root.addWidget(hint)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        form = QVBoxLayout(content)
        form.setContentsMargins(0, 8, 0, 0)
        form.setSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText('筛选程序名称或路径…')
        self.search.setAccessibleName('筛选运行程序')
        self.refresh_button = QPushButton('重新识别')
        form.addWidget(ResponsiveActionRow(self.search, [self.refresh_button]))
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet('''
            QTabBar::tab { color: palette(window-text); background: palette(button);
                padding: 5px 10px; border: 1px solid palette(mid); }
            QTabBar::tab:selected { color: palette(text); background: palette(base); }
            QTabBar::tab:hover { background: palette(midlight); }
        ''')
        self.programs = QTreeWidget()
        self.programs.setAccessibleName('当前运行的程序')
        self.programs.setHeaderLabels(['程序', 'PID', '程序位置'])
        self.programs.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.programs.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.programs.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.bindings = QTreeWidget()
        self.bindings.setAccessibleName('已绑定的 Agent')
        self.bindings.setHeaderLabels(['Agent', '状态', '数据源'])
        self.bindings.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.programs, '运行中的程序')
        self.tabs.addTab(self.bindings, '已绑定 Agent')
        self.tabs.setMinimumHeight(160)
        self.tabs.setMaximumHeight(240)
        form.addWidget(self.tabs)
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(50)
        self.adapter = ModernSelect(width=210)
        self.adapter.addItem('通用事件文件（JSONL）', 'jsonl')
        self.adapter.addItem('OpenCode 兼容数据库', 'opencode')
        self.adapter.addItem('Codex 会话事件', 'codex')
        self.source_edit = QLineEdit()
        self.source_edit.setMinimumWidth(0)
        self.source_edit.setPlaceholderText('选择数据源；事件文件可以稍后由 Agent 创建')
        self.browse_button = QPushButton('选择文件…')
        source_control = ResponsiveActionRow(self.source_edit, [self.browse_button])
        form.addWidget(SettingsSection('联动来源', [
            SettingRow('agent_binding_name', '联动名称', '菜单和提醒中显示的名称。', self.name_edit),
            SettingRow('agent_binding_adapter', '联动方式', 'Codex 可直接读取会话事件；OpenCode 可读取兼容数据库或使用导出的插件。', self.adapter),
            SettingRow('agent_binding_source', '数据来源', '只读监听。用户目录内的路径保存为 ~，便于迁移到其他设备。', source_control, stacked=True),
        ], content))
        self.source_edit.setAccessibleName('Agent 数据来源')
        self.source_edit.setAccessibleDescription('Codex sessions 文件夹、OpenCode 兼容数据库或通用 JSONL 事件文件的路径')
        self.status = QLabel('正在识别程序…' if scan_on_open else '可从运行程序中选择，也可直接填写联动来源。')
        self.status.setWordWrap(True)
        self.status.setAccessibleName('Agent 识别状态')
        form.addWidget(self.status)
        self.remove_button = QPushButton('移除选中绑定')
        self.remove_button.setEnabled(False)
        form.addWidget(self.remove_button, alignment=Qt.AlignmentFlag.AlignLeft)
        form.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self.add_button = QPushButton('添加并启用联动')
        self.export_button = QPushButton('导出 OpenCode 插件…')
        close_button = QPushButton('关闭')
        root.addWidget(ResponsiveActionRow(self.add_button, [self.export_button, close_button]))
        self.refresh_button.clicked.connect(self.refresh_programs)
        self.search.textChanged.connect(self._filter_programs)
        self.programs.itemSelectionChanged.connect(self._select_program)
        self.bindings.itemSelectionChanged.connect(self._select_binding)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.browse_button.clicked.connect(self._browse)
        self.adapter.currentIndexChanged.connect(self._adapter_changed)
        self.add_button.clicked.connect(self.add_binding)
        self.export_button.clicked.connect(self.export_plugin)
        self.remove_button.clicked.connect(self.remove_binding)
        close_button.clicked.connect(self.close)
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._drain_results)
        self._timer.start()
        self._refresh_bindings()
        if scan_on_open:
            QTimer.singleShot(0, self.refresh_programs)

    def _background(self, kind, generation, job):
        results = self._results

        def run():
            try:
                results.put((kind, generation, job(), ''))
            except Exception as exc:
                results.put((kind, generation, None, str(exc)))
        threading.Thread(target=run, name='pet-agent-discovery', daemon=True).start()

    def refresh_programs(self):
        if not self.refresh_button.isEnabled():
            return
        self.refresh_button.setEnabled(False)
        self.status.setText('正在识别当前用户运行的程序…')
        self._scan_generation += 1
        cancel = self._cancel
        self._background('programs', self._scan_generation, lambda: discover_programs(cancelled=cancel.is_set))

    def _drain_results(self):
        while not self._results.empty():
            kind, generation, result, error = self._results.get_nowait()
            if self._cancel.is_set():
                return
            if kind == 'programs':
                if generation != self._scan_generation:
                    continue
                self.refresh_button.setEnabled(True)
                self.programs.clear()
                for program in result or []:
                    item = QTreeWidgetItem([program.name, str(program.pid), program.executable])
                    item.setData(0, Qt.ItemDataRole.UserRole, program)
                    item.setToolTip(2, program.executable)
                    self.programs.addTopLevelItem(item)
                self._filter_programs()
                self.status.setText(f'识别到 {len(result or [])} 个程序，请选择要联动的 Agent。' if not error else f'识别失败：{error}')
            elif generation == self._source_generation:
                if error:
                    self.status.setText(f'未能自动查找数据源：{error}。可以手动选择文件。')
                elif len(result) == 1 and self.source_edit.text() == self._probe_initial_path and self.adapter.currentData() == 'jsonl':
                    source = result[0]
                    self.source_edit.setText(portable_path(source.path))
                    self.adapter.setCurrentIndex(self.adapter.findData(source.adapter))
                    self.status.setText('已找到兼容的数据源。点击「添加并启用联动」即可接入。')
                elif result:
                    self.status.setText('找到多个可能的数据源，请选择文件：\n' + '\n'.join(str(source.path) for source in result))
                else:
                    self.status.setText('没有找到可直接读取的数据源。可以手动选择兼容数据库，或添加事件文件联动并导出 OpenCode 插件。')

    def _filter_programs(self):
        text = self.search.text().casefold()
        for index in range(self.programs.topLevelItemCount()):
            item = self.programs.topLevelItem(index)
            item.setHidden(text not in (item.text(0) + ' ' + item.text(2)).casefold())

    def _select_program(self):
        items = self.programs.selectedItems()
        if not items:
            return
        self._editing_key = ''
        self.remove_button.setEnabled(False)
        self.add_button.setText('添加并启用联动')
        self._program = items[0].data(0, Qt.ItemDataRole.UserRole)
        self.name_edit.setText(Path(self._program.name).stem)
        key = binding_key(self.name_edit.text(), self.cfg.get('agent_link', {}))
        self.source_edit.setText(portable_path(self.cfg.dir / 'agent-events' / f'{key}.jsonl'))
        self.adapter.setCurrentIndex(0)
        self._source_generation += 1
        self._probe_initial_path = self.source_edit.text()
        self.status.setText('正在查找这个程序的兼容数据源…')
        program, cancel = self._program, self._cancel
        self._background('sources', self._source_generation, lambda: find_program_sources(program, cancelled=cancel.is_set))

    def _refresh_bindings(self):
        self.bindings.clear()
        agent_cfg = self.cfg.get('agent_link', {})
        for entry in agent_cfg.get('custom_agents') or []:
            status = '已启用' if agent_cfg.get(entry['key']) else '已停用'
            if agent_cfg.get(entry['key']) and not expand_agent_path(entry['path']).exists():
                status = '等待数据源'
            item = QTreeWidgetItem([entry['name'], status, entry['path']])
            item.setData(0, Qt.ItemDataRole.UserRole, dict(entry))
            item.setToolTip(2, entry['path'])
            self.bindings.addTopLevelItem(item)

    def _select_binding(self):
        items = self.bindings.selectedItems()
        if not items:
            return
        entry = items[0].data(0, Qt.ItemDataRole.UserRole)
        self._editing_key = entry['key']
        self._program = None
        self._source_generation += 1
        self.name_edit.setText(entry['name'])
        self.source_edit.setText(entry['path'])
        self.adapter.setCurrentIndex(self.adapter.findData(entry.get('adapter') or 'jsonl'))
        self.add_button.setText('保存并启用联动')
        self.remove_button.setEnabled(True)

    def _tab_changed(self, index):
        if index == 0:
            self._editing_key = ''
            self.remove_button.setEnabled(False)
            self.add_button.setText('添加并启用联动')
            self._select_program()
        else:
            self._select_binding()

    def _browse(self):
        adapter = self.adapter.currentData()
        if adapter == 'codex':
            path = QFileDialog.getExistingDirectory(self, '选择 Codex sessions 文件夹', str(expand_agent_path(self.source_edit.text())))
            if path:
                self.source_edit.setText(portable_path(path))
            return
        filters = 'SQLite 数据库 (*.db *.sqlite *.sqlite3)' if adapter == 'opencode' else 'JSONL 事件文件 (*.jsonl)'
        path, _ = QFileDialog.getOpenFileName(self, '选择 Agent 数据来源', str(expand_agent_path(self.source_edit.text())), filters)
        if path:
            self.source_edit.setText(portable_path(path))

    def _adapter_changed(self):
        self.browse_button.setText('选择目录…' if self.adapter.currentData() == 'codex' else '选择文件…')
        self.export_button.setEnabled(self.adapter.currentData() == 'jsonl')

    def _commit(self, data):
        previous = dict(self.cfg.get('agent_link', {}))
        self.cfg.set('agent_link', data)
        if not self.cfg.save():
            self.cfg.set('agent_link', previous)
            self.status.setText('无法保存设置，请检查配置目录的写入权限。')
            return False
        self._refresh_bindings()
        self.bindings_changed.emit()
        return True

    def add_binding(self):
        name, source = self.name_edit.text().strip(), self.source_edit.text().strip()
        if not name or not source:
            self.status.setText('请填写联动名称和数据来源。')
            return
        adapter = self.adapter.currentData()
        error = validate_source(source, adapter)
        if error:
            self.status.setText(error)
            return
        data = dict(self.cfg.get('agent_link', {}))
        items = [dict(item) for item in data.get('custom_agents') or []]
        for item in items:
            if item['key'] != self._editing_key and expand_agent_path(item['path']).absolute() == expand_agent_path(source).absolute():
                self.status.setText(f'这个数据源已经绑定到「{item["name"]}」。请在已绑定 Agent 中修改。')
                return
        if len(items) >= 8 and not self._editing_key:
            self.status.setText('最多可绑定 8 个自定义 Agent，请先移除不再使用的绑定。')
            return
        key = self._editing_key or binding_key(name, data)
        entry = next((item for item in items if item['key'] == key), {'key': key})
        entry.update(name=name, path=portable_path(source))
        entry.pop('adapter', None)
        if adapter in ('opencode', 'codex'):
            entry['adapter'] = adapter
        if self._program and not is_shared_runtime(self._program.name):
            entry['process_names'] = [self._program.name]
        items = [item for item in items if item['key'] != key] + [entry]
        data.update(custom_agents=items)
        data[key] = True
        if self._commit(data):
            self._editing_key = key
            self.remove_button.setEnabled(True)
            self.add_button.setText('保存并启用联动')
            message = {'jsonl': '等待 Agent 写入事件；OpenCode 分支可点击导出插件。',
                       'opencode': '正在只读监听数据库中的新任务事件。',
                       'codex': '正在只读监听 Codex 的思考、工具执行、任务完成和中止事件。'}[adapter]
            self.status.setText(f'已启用「{name}」联动。' + message)

    def remove_binding(self):
        if not self._editing_key:
            return
        data = dict(self.cfg.get('agent_link', {}))
        data['custom_agents'] = [item for item in data.get('custom_agents') or [] if item['key'] != self._editing_key]
        data.pop(self._editing_key, None)
        if self._commit(data):
            self._editing_key = ''
            self.remove_button.setEnabled(False)
            self.add_button.setText('添加并启用联动')
            self.status.setText('已移除绑定，Agent 本身的数据文件保持原样。')

    def export_plugin(self):
        entry = next((item for item in self.cfg.get('agent_link', {}).get('custom_agents') or [] if item['key'] == self._editing_key), None)
        if not entry or entry.get('adapter') in ('opencode', 'codex'):
            self.status.setText('请先添加事件文件联动，再导出插件。')
            return
        path, _ = QFileDialog.getSaveFileName(self, '保存到 Agent 的 .opencode/plugins 目录，重启 Agent 后生效', 'qilin-pet-bridge.js', 'JavaScript 插件 (*.js)')
        if not path:
            return
        try:
            Path(path).write_text(render_opencode_plugin(entry['path'], entry['key']), encoding='utf-8')
            self.status.setText('插件已导出。放入这个 Agent 支持的插件目录并重启 Agent；桌宠会自动接收任务事件。')
        except OSError as exc:
            self.status.setText(f'无法导出插件：{exc}')

    def _stop_discovery(self):
        if self._cancel.is_set():
            return
        self._cancel.set()
        self._scan_generation += 1
        self._source_generation += 1
        self.refresh_button.setEnabled(True)
        self._timer.stop()

    def reject(self):
        self._stop_discovery()
        super().reject()

    def closeEvent(self, event):  # noqa: N802
        self._stop_discovery()
        super().closeEvent(event)


def open_running_agents(pet):
    dialog = getattr(pet, '_running_agents_dialog', None)
    if dialog is None:
        parent = pet if isinstance(pet, QWidget) else None
        dialog = RunningAgentsDialog(pet.cfg, parent)
        refresh = getattr(pet, 'refresh_pet_settings', None)
        if callable(refresh):
            dialog.bindings_changed.connect(refresh)
        pet._running_agents_dialog = dialog
    else:
        dialog._cancel = threading.Event()
        dialog._timer.start()
        dialog._refresh_bindings()
        dialog.refresh_programs()
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
