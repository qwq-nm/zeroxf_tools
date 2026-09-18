import sys
import os
import json
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QScrollArea, QFrame, QGridLayout,
    QMessageBox, QMenu, QMenuBar, QDialog, QFormLayout, QComboBox,
    QFileDialog, QSpacerItem, QSizePolicy, QToolButton, QToolTip
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QFont, QCursor, QIcon, QAction


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import run_tool as original_run_tool

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
TOOLS_FILE = os.path.join(CONFIG_DIR, "tools.json")
CATEGORIES_FILE = os.path.join(CONFIG_DIR, "categories.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")

CATEGORY_DISPLAY_NAMES = {
    "WebShell管理工具": "WebShell管理工具",
    "信息收集工具": "信息探测工具",
    "抓包与代理工具": "渗透利器工具",
    "漏洞扫描与利用工具": "综合漏洞探测利用工具",
    "框架漏洞利用工具": "框架漏洞利用工具",
    "爆破工具": "渗透利器工具",
    "免杀工具": "渗透利器工具",
    "后渗透工具": "渗透利器工具",
    "其他工具": "综合漏洞探测利用工具",
    "网页工具": "网页工具"
}

DISPLAY_CATEGORY_ORDER = [
    "WebShell管理工具",
    "渗透利器工具",
    "信息探测工具",
    "综合漏洞探测利用工具",
    "框架漏洞利用工具",
    "网页工具"
]


def load_json_file(filepath, default=None):
    if default is None:
        default = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


class ToolButton(QPushButton):
    def __init__(self, tool_data, parent=None):
        super().__init__(parent)
        self.tool_data = tool_data
        self.parent_window = parent
        self.abs_path = ""
        self.setText(tool_data.get("name", "未知"))
        self.setFixedSize(180, 28)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clicked.connect(self.run_tool)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        description = tool_data.get("description", "")
        if description:
            self.setToolTip(f"<p>{description}</p>")
        self._calc_abs_path()
        self.setToolTipDuration(2000)

    def _calc_abs_path(self):
        path = self.tool_data.get("path", "")
        if path:
            if path.startswith("/"):
                path = path[1:]
            path = path.replace("/", os.sep)
            if path.startswith("tools" + os.sep):
                path = path[6:]
            self.abs_path = os.path.join(BASE_DIR, "tools", path)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setObjectName("contextMenu")
        action_open_dir = menu.addAction("打开工具目录")
        action_open_dir.triggered.connect(self.open_tool_dir)
        menu.exec(self.mapToGlobal(pos))

    def open_tool_dir(self):
        if self.abs_path:
            dir_path = os.path.dirname(self.abs_path)
            if os.path.exists(dir_path):
                os.startfile(dir_path)
            else:
                QMessageBox.warning(self, "错误", f"目录不存在:\n{dir_path}")
        else:
            url = self.tool_data.get("url", "")
            if url:
                import webbrowser
                webbrowser.open(url)
            else:
                QMessageBox.information(self, "提示", "该工具没有关联的目录")

    def run_tool(self):
        tool_data = self.tool_data.copy()
        path = tool_data.get("path", "")
        if path:
            if path.startswith("/"):
                path = path[1:]
            path = path.replace("/", os.sep)
            if path.startswith("tools" + os.sep):
                path = path[6:]
            abs_path = os.path.join(BASE_DIR, "tools", path)
            tool_data["path"] = abs_path
        try:
            original_run_tool(tool_data, record_recent=True)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"启动工具失败: {e}")


class AddToolDialog(QDialog):
    def __init__(self, categories, parent=None):
        super().__init__(parent)
        self.categories = categories
        self.setWindowTitle("添加新工具")
        self.setFixedSize(450, 350)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("输入工具名称")
        layout.addRow("工具名称:", self.ed_name)

        self.cb_category = QComboBox()
        self.cb_category.addItems([c for c in self.categories if c not in ("最近启动", "我的收藏")])
        layout.addRow("所属分类:", self.cb_category)

        self.cb_type = QComboBox()
        self.cb_type.addItems(["GUI应用", "命令行", "Python", "JAVA8", "JAVA11", "批处理", "PowerShell", "网页"])
        layout.addRow("工具类型:", self.cb_type)

        self.ed_path = QLineEdit()
        self.ed_path.setPlaceholderText("工具路径或网址")
        layout.addRow("路径/网址:", self.ed_path)

        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self.browse_file)
        layout.addRow("", btn_browse)

        self.ed_params = QLineEdit()
        self.ed_params.setPlaceholderText("启动参数（可选）")
        layout.addRow("启动参数:", self.ed_params)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow("", btn_layout)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择工具文件", "",
            "可执行文件 (*.exe *.bat *.vbs *.ps1);;Java程序 (*.jar);;Python脚本 (*.py);;所有文件 (*.*)"
        )
        if file_path:
            self.ed_path.setText(file_path)

    def get_tool_data(self):
        return {
            "name": self.ed_name.text().strip(),
            "category": self.cb_category.currentText(),
            "type": self.cb_type.currentText(),
            "path": self.ed_path.text().strip(),
            "params": self.ed_params.text().strip(),
            "url": self.ed_path.text().strip() if self.cb_type.currentText() == "网页" else "",
            "weight": 0
        }


class CategorySection(QFrame):
    def __init__(self, title, tools, parent=None, expanded=True):
        super().__init__(parent)
        self.title = title
        self.tools = tools
        self.parent_window = parent
        self.is_expanded = expanded
        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("categorySection")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 15)
        main_layout.setSpacing(10)

        arrow = "▼" if self.is_expanded else "▶"
        self.title_label = QLabel(f"{arrow} {self.title}  (共 {len(self.tools)} 个工具)")
        self.title_label.setObjectName("sectionTitle")
        self.title_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.title_label.mousePressEvent = self.toggle_expand
        main_layout.addWidget(self.title_label)

        self.tools_widget = QWidget()
        self.tools_layout = QGridLayout(self.tools_widget)
        self.tools_layout.setContentsMargins(20, 5, 0, 5)
        self.tools_layout.setSpacing(8)
        self.tools_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        cols = 6
        for idx, tool in enumerate(self.tools):
            row = idx // cols
            col = idx % cols
            btn = ToolButton(tool, self.parent_window)
            self.tools_layout.addWidget(btn, row, col)

        main_layout.addWidget(self.tools_widget)
        self.tools_widget.setVisible(self.is_expanded)

    def toggle_expand(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_expanded = not self.is_expanded
            self.tools_widget.setVisible(self.is_expanded)
            arrow = "▼" if self.is_expanded else "▶"
            self.title_label.setText(f"{arrow} {self.title}  (共 {len(self.tools)} 个工具)")
            self.save_expand_state()

    def save_expand_state(self):
        settings = load_json_file(SETTINGS_FILE, {})
        collapsed = settings.get("collapsed_categories", [])
        if self.is_expanded:
            if self.title in collapsed:
                collapsed.remove(self.title)
        else:
            if self.title not in collapsed:
                collapsed.append(self.title)
        settings["collapsed_categories"] = collapsed
        save_json_file(SETTINGS_FILE, settings)


class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._stylesheet_applied = False
        self.tools = load_json_file(TOOLS_FILE, [])
        self.categories = load_json_file(CATEGORIES_FILE, [])
        self.settings = load_json_file(SETTINGS_FILE, {})
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("zeroxf 工具箱 - 启动器")
        self.setWindowIcon(QIcon(os.path.join(CONFIG_DIR, "fox.ico")))
        self.resize(1200, 750)
        self.setMinimumSize(1000, 600)

        self.setup_menubar()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setObjectName("mainScroll")

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(15, 10, 15, 10)
        self.content_layout.setSpacing(5)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(scroll_area, 1)

        self.refresh_tools()
        QTimer.singleShot(0, self.apply_stylesheet)

    def setup_menubar(self):
        menubar = self.menuBar()
        menubar.setObjectName("mainMenuBar")

        menu_file = menubar.addMenu("文件")
        action_refresh = QAction("刷新工具列表", self)
        action_refresh.triggered.connect(self.refresh_tools)
        menu_file.addAction(action_refresh)
        menu_file.addSeparator()
        action_exit = QAction("退出", self)
        action_exit.triggered.connect(self.close)
        menu_file.addAction(action_exit)

        menu_tools = menubar.addMenu("工具")
        action_search = QAction("搜索工具", self)
        action_search.triggered.connect(self.focus_search)
        menu_tools.addAction(action_search)

        menu_add = menubar.addMenu("自定义新增工具")
        action_add = QAction("添加新工具", self)
        action_add.triggered.connect(self.add_tool)
        menu_add.addAction(action_add)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        menubar.setCornerWidget(spacer)

        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(10, 0, 10, 0)
        search_layout.setSpacing(5)
        search_label = QLabel("搜索:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键词搜索工具...")
        self.search_input.setFixedWidth(200)
        self.search_input.setFixedHeight(24)
        self.search_input.textChanged.connect(self.on_search)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        menubar.setCornerWidget(search_widget)

    def get_display_categories(self):
        display_map = {}
        for tool in self.tools:
            orig_cat = tool.get("category", "")
            display_cat = CATEGORY_DISPLAY_NAMES.get(orig_cat, orig_cat)
            if display_cat not in display_map:
                display_map[display_cat] = []
            display_map[display_cat].append(tool)

        for cat in display_map:
            display_map[cat].sort(key=lambda x: x.get("weight", 0), reverse=True)

        return display_map

    def refresh_tools(self):
        self.tools = load_json_file(TOOLS_FILE, [])
        self.categories = load_json_file(CATEGORIES_FILE, [])
        self.settings = load_json_file(SETTINGS_FILE, {})
        collapsed = self.settings.get("collapsed_categories", [])

        for i in reversed(range(self.content_layout.count())):
            item = self.content_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        display_categories = self.get_display_categories()

        for display_cat in DISPLAY_CATEGORY_ORDER:
            if display_cat in display_categories and display_categories[display_cat]:
                expanded = display_cat not in collapsed
                section = CategorySection(display_cat, display_categories[display_cat], self, expanded)
                self.content_layout.addWidget(section)

        for display_cat, tools in display_categories.items():
            if display_cat not in DISPLAY_CATEGORY_ORDER and tools:
                expanded = display_cat not in collapsed
                section = CategorySection(display_cat, tools, self, expanded)
                self.content_layout.addWidget(section)

        self.content_layout.addStretch()

    def on_search(self, text):
        search_text = text.lower().strip()

        for i in range(self.content_layout.count()):
            item = self.content_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), CategorySection):
                section = item.widget()
                has_visible = False

                for j in range(section.tools_layout.count()):
                    btn = section.tools_layout.itemAt(j).widget()
                    if btn and isinstance(btn, ToolButton):
                        tool_name = btn.tool_data.get("name", "").lower()
                        tool_desc = btn.tool_data.get("description", "").lower()
                        tool_cat = btn.tool_data.get("category", "").lower()

                        if not search_text or search_text in tool_name or search_text in tool_desc or search_text in tool_cat:
                            btn.setVisible(True)
                            has_visible = True
                        else:
                            btn.setVisible(False)

                section.setVisible(has_visible)

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def add_tool(self):
        dialog = AddToolDialog(self.categories, self)
        if dialog.exec():
            tool_data = dialog.get_tool_data()
            if not tool_data["name"] or not tool_data["category"]:
                QMessageBox.warning(self, "错误", "请填写工具名称和分类")
                return

            if tool_data["type"] != "网页" and not tool_data["path"]:
                QMessageBox.warning(self, "错误", "请填写工具路径")
                return

            self.tools.append(tool_data)
            if save_json_file(TOOLS_FILE, self.tools):
                QMessageBox.information(self, "成功", "工具添加成功！")
                self.refresh_tools()
            else:
                QMessageBox.warning(self, "错误", "保存工具失败")

    def apply_stylesheet(self):
        if self._stylesheet_applied:
            return
        self._stylesheet_applied = True

        theme_name = str(self.settings.get("theme", "")).strip().lower()
        if theme_name == "performance":
            style = """
            QMainWindow {
                background: #0f172a;
            }
            QMenuBar {
                background: #111827;
                color: #e5e7eb;
                border-bottom: 1px solid #1f2937;
            }
            QMenuBar::item:selected {
                background: #1f2937;
            }
            QMenu {
                background: #111827;
                color: #e5e7eb;
                border: 1px solid #1f2937;
            }
            QMenu::item:selected {
                background: #1f2937;
            }
            QLineEdit, QComboBox {
                background: #111827;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QScrollArea#mainScroll {
                background: #0f172a;
                border: none;
            }
            QFrame#categorySection {
                background: #111827;
                border: 1px solid #1f2937;
                border-radius: 5px;
                margin: 2px;
            }
            QLabel#sectionTitle {
                color: #e5e7eb;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 15px;
                background: #172033;
                border-radius: 3px;
            }
            QPushButton {
                background: #111827;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #172033;
                border: 1px solid #3b82f6;
            }
            """
            self.setStyleSheet(style)
            return

        style = """
        QMainWindow {
            background: #f0f0f0;
        }
        QMenuBar {
            background: #e8e8e8;
            border-bottom: 1px solid #c0c0c0;
            padding: 2px;
            font-size: 13px;
        }
        QMenuBar::item {
            background: transparent;
            padding: 5px 12px;
            border-radius: 3px;
        }
        QMenuBar::item:selected {
            background: #d0d0d0;
        }
        QMenu {
            background: #ffffff;
            border: 1px solid #c0c0c0;
            padding: 3px;
        }
        QMenu::item {
            padding: 6px 30px;
            border-radius: 3px;
        }
        QMenu::item:selected {
            background: #0078d4;
            color: white;
        }
        QLineEdit {
            background: white;
            border: 1px solid #005a9e;
            border-radius: 3px;
            padding: 0 8px;
            font-size: 12px;
        }
        QLineEdit:focus {
            border: 2px solid #ffffff;
        }
        QScrollArea#mainScroll {
            background: #f5f5f5;
            border: none;
        }
        QScrollBar:vertical {
            background: #e0e0e0;
            width: 12px;
            border-radius: 6px;
        }
        QScrollBar::handle:vertical {
            background: #c0c0c0;
            border-radius: 6px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background: #a0a0a0;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QFrame#categorySection {
            background: white;
            border: 1px solid #d0d0d0;
            border-radius: 5px;
            margin: 2px;
        }
        QLabel#sectionTitle {
            color: #333333;
            font-size: 14px;
            font-weight: bold;
            padding: 8px 15px;
            background: #e8e8e8;
            border-radius: 3px;
        }
        QLabel#sectionTitle:hover {
            background: #d8d8d8;
        }
        QPushButton {
            background: #f8f8f8;
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            font-size: 12px;
            color: #333;
            text-align: center;
        }
        QPushButton:hover {
            background: #e5f3ff;
            border: 1px solid #0078d4;
            color: #0078d4;
        }
        QPushButton:pressed {
            background: #cce8ff;
        }
        QDialog {
            background: #f5f5f5;
        }
        QComboBox {
            background: white;
            border: 1px solid #c0c0c0;
            border-radius: 3px;
            padding: 5px 10px;
            min-width: 150px;
        }
        QComboBox:focus {
            border: 1px solid #0078d4;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox QAbstractItemView {
            background: white;
            border: 1px solid #c0c0c0;
            selection-background-color: #0078d4;
            selection-color: white;
        }
        """
        self.setStyleSheet(style)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
