import sys
import sqlite3
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel, QLineEdit, QSystemTrayIcon, QMenu, QTextEdit
)
from PyQt6.QtCore import Qt, QPoint, QMimeData
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QIcon, QImage


class FloatingNoteApp(QWidget):
    windows = []  # 存储所有窗口的静态列表，避免被垃圾回收
    tray_icon = None

    def __init__(self):
        super().__init__()
        self.init_sqlite()
        # 设置窗口标题、大小、样式
        self.setWindowTitle("悬浮便签")
        self.resize(300, 300)
        if not FloatingNoteApp.tray_icon:
            FloatingNoteApp.tray_icon = QSystemTrayIcon(self)
            FloatingNoteApp.tray_icon.setIcon(QIcon("mini.ico"))
            self.setToolTip("悬浮便签")  # 托盘提示
            self.create_menu()
        self.create_time = time.time()
        self.setWindowIcon(QIcon("mini.ico"))
        self.setMinimumSize(150, 150)  # 设置最小窗口大小
        self.setWindowFlags(
            # Qt.WindowType.WindowStaysOnTopHint |   # 置顶
            Qt.WindowType.FramelessWindowHint
        )
        # 窗口拖动相关属性
        self.is_dragging = False
        self.start_pos = QPoint()
        self.is_resizing = False
        self.resize_start_pos = QPoint()
        self.painted = False
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True)  # 设置透明背景

        # 布局和控件
        layout = QVBoxLayout(self)

        # 顶部按钮栏
        button_layout = QHBoxLayout()
        self.delete_button = QPushButton("×", self)
        self.delete_button.setObjectName("delete")
        self.delete_button.clicked.connect(self.close)
        self.delete_button.setFixedSize(20, 20)

        # 添加窗口按钮
        self.add_button = QPushButton("+", self)
        self.add_button.clicked.connect(self.create_new_window)
        self.add_button.setFixedSize(20, 20)

        # 置顶按钮
        self.spin_button = QPushButton("o", self)
        self.spin_button.clicked.connect(self.set_top)
        self.spin_button.setFixedSize(20, 20)
        # 标题栏
        self.title_label = QLabel("双击修改窗口标题")
        # self.title_label.setFont(QFont("宋体", 12))
        self.title_label.setStyleSheet("color: #333;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.mouseDoubleClickEvent = self.change_title

        self.title_edit = QLineEdit()
        # self.title_edit.setFont(QFont("宋体", 12))
        self.title_edit.setStyleSheet("color: #333;")
        self.title_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_edit.setVisible(False)
        self.title_edit.editingFinished.connect(self.set_title)

        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.spin_button)
        button_layout.addWidget(self.title_label)
        button_layout.addWidget(self.title_edit)
        button_layout.addWidget(self.add_button)
        button_layout.setSpacing(5)  # 按钮间距
        layout.addLayout(button_layout)

        # 文本编辑框
        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setPlaceholderText("输入内容...")
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

    def init_sqlite(self):
        # 连接到数据库（自动创建数据库文件）
        conn = sqlite3.connect('note.db')
        cursor = conn.cursor()

        # 创建表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS note (
            time INTEGER PRIMARY KEY ,
            title TEXT ,
            note TEXT
        )
        ''')

    def create_menu(self):
        menu = QMenu()
        exit_action = menu.addAction("退出")
        exit_action.triggered.connect(QApplication.quit)  # 点击退出后退出程序
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def set_title(self):
        self.title_label.setText(self.title_edit.text())
        self.title_edit.setVisible(False)
        self.title_label.setVisible(True)
        self.setWindowTitle(self.title_label.text())

    def change_title(self, event):
        self.title_label.setVisible(False)
        self.title_edit.setText(self.title_label.text())
        self.title_edit.setVisible(True)
        self.title_edit.setFocus()

    def set_top(self):
        current_flags = self.windowHandle().flags()
        if (current_flags & Qt.WindowType.WindowStaysOnTopHint) == Qt.WindowType.WindowStaysOnTopHint:
            # 清除置顶标志，但保留无边框标志
            self.windowHandle().setFlags(current_flags & ~Qt.WindowType.WindowStaysOnTopHint)
            self.spin_button.setStyleSheet("""background-color: #aed581;""")
        else:
            # 设置置顶标志，并保留无边框标志
            self.windowHandle().setFlags(current_flags | Qt.WindowType.WindowStaysOnTopHint)
            self.spin_button.setStyleSheet("""background-color: #8bc34a;""")
        self.update()

    def exit_application(self):
        """退出程序"""
        QApplication.quit()

    def create_new_window(self):
        """创建新窗口"""
        new_window = FloatingNoteApp()
        FloatingNoteApp.windows.append(new_window)  # 保存新窗口的引用
        new_window.show()

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否在窗口边框拖动范围
            if self.is_in_resize_area(event.pos()):
                self.is_resizing = True
                self.resize_start_pos = event.globalPosition().toPoint()
            else:
                self.is_dragging = True
                self.start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.is_dragging:
            self.move(event.globalPosition().toPoint() - self.start_pos)
            event.accept()
        elif self.is_resizing:
            self.resize_window(event.globalPosition().toPoint())
            event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.is_resizing = False
            event.accept()

    def is_in_resize_area(self, pos):
        """判断鼠标是否在右下角的缩放区域"""
        margin = 10  # 缩放边界范围
        return (
            self.width() - margin <= pos.x() <= self.width() or
            self.height() - margin <= pos.y() <= self.height()
        )

    def resize_window(self, global_pos):
        """根据鼠标位置调整窗口大小"""
        delta = global_pos - self.resize_start_pos
        new_width = max(self.minimumWidth(), self.width() + delta.x())
        new_height = max(self.minimumHeight(), self.height() + delta.y())
        self.resize(new_width, new_height)
        self.resize_start_pos = global_pos

    def closeEvent(self, event):
        """移除窗口引用，防止内存泄漏"""
        FloatingNoteApp.windows.remove(self)
        super().closeEvent(event)

    def paintEvent(self, event):
        """自定义绘制窗口实现圆角矩形"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        color = QColor("#e8f5e9")  # 窗口背景颜色
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 8, 8)  # 圆角半径为15


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = FloatingNoteApp()
    with open("note.css", "r", encoding='utf-8') as f:
        app.setStyleSheet(f.read())
    FloatingNoteApp.windows.append(main_window)  # 保存主窗口的引用
    main_window.show()
    sys.exit(app.exec())
