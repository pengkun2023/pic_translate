import sys
import os
import subprocess
import threading
import json
from pathlib import Path

import requests
from PIL import Image
import pytesseract
from pynput import keyboard

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTextEdit, 
                             QPushButton, QHBoxLayout, QSystemTrayIcon, QMenu,
                             QDialog, QLabel, QLineEdit, QMessageBox, QComboBox, QSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRect, QPoint
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QPen

# ==========================================
# CONFIG: 配置项集中存放与本地持久化
# ==========================================
DEFAULT_CONFIG = {
    "screenshot_path": "/tmp/pic_translate_capture.png",
    "hotkey": "<ctrl>+<alt>+x",
    "ocr_lang": "eng+chi_sim",
    "api_provider": "DeepSeek",
    "api_url": "https://api.deepseek.com",
    "api_key": "",
    "api_model": "deepseek-v4-pro",
    "win_width": 400,
    "win_height": 300,
    "font_size": 14,
    "text_color": "#000000",
    "bg_color": "#FAFAFA",
    "display_mode": "in_place" # 'in_place' (原位覆盖) 或 'floating' (悬浮窗)
}

CONFIG = DEFAULT_CONFIG.copy()

def get_config_path() -> Path:
    config_dir = Path.home() / ".config" / "pic-translate"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"

def load_config():
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                CONFIG.update(user_config)
        except Exception as e:
            print(f"[System] 读取配置文件失败: {e}")

def save_config():
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(CONFIG, f, indent=4, ensure_ascii=False)
        print("[System] 配置已持久化保存")
    except Exception as e:
        print(f"[System] 保存配置文件失败: {e}")

load_config()

# ==========================================
# 信号类
# ==========================================
class WorkerSignals(QObject):
    update_text = pyqtSignal(str)
    show_window = pyqtSignal()
    error_occurred = pyqtSignal(str)

class ControllerSignals(QObject):
    start_snipper = pyqtSignal()

# ==========================================
# 后台工作逻辑
# ==========================================
def do_ocr() -> str:
    print("[OCR] 开始识别文字...")
    try:
        img = Image.open(CONFIG["screenshot_path"])
        text = pytesseract.image_to_string(img, lang=CONFIG["ocr_lang"])
        res_text = text.strip()
        print(f"[OCR] 识别结果: {res_text[:20]}...")
        return res_text
    except Exception as e:
        print(f"[OCR] 识别失败: {e}")
        raise RuntimeError(f"OCR 识别失败: {e}")

def translate_text(text: str) -> str:
    if not text:
        return ""
    
    if not CONFIG.get('api_key') or not str(CONFIG.get('api_key')).strip():
        raise RuntimeError("尚未配置 API Key！请右键点击系统托盘图标，选择「设置」进行配置。")
    
    print(f"[{CONFIG['api_provider']}] 开始翻译...")
    try:
        # 修复 httpx 不识别 socks:// 的问题
        for key in ['all_proxy', 'ALL_PROXY', 'http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']:
            if key in os.environ and os.environ[key].startswith('socks://'):
                os.environ[key] = os.environ[key].replace('socks://', 'socks5://')
                
        from openai import OpenAI
        client = OpenAI(
            api_key=CONFIG['api_key'],
            base_url=CONFIG['api_url']
        )

        response = client.chat.completions.create(
            model=CONFIG["api_model"],
            messages=[
                {"role": "system", "content": "你是一个专业的翻译助手。请将以下内容翻译为流畅的中文（如果是中文则翻译为英文）。只返回翻译结果，不要任何解释。"},
                {"role": "user", "content": text}
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}}
        )
        
        result = response.choices[0].message.content.strip()
        print(f"[{CONFIG['api_provider']}] 翻译成功")
        return result
    except Exception as e:
        print(f"[{CONFIG['api_provider']}] 翻译失败: {e}")
        raise RuntimeError(f"翻译失败: {e}")

def workflow_thread(signals: WorkerSignals):
    """翻译工作流（在子线程运行，截图已经在主线程完成了）"""
    try:
        signals.show_window.emit()
        signals.update_text.emit("正在识别文字...")
        
        text = do_ocr()
        if not text:
            signals.update_text.emit("未识别到文字。")
            return
            
        signals.update_text.emit(f"【原文】\n{text}\n\n正在翻译...")
        
        translated = translate_text(text)
        signals.update_text.emit(f"【原文】\n{text}\n\n【翻译】\n{translated}")
        
    except Exception as e:
        signals.error_occurred.emit(str(e))

# ==========================================
# GUI: 截图选框 (Snipper)
# ==========================================
class Snipper(QWidget):
    capture_complete = pyqtSignal(QRect)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        self.begin = QPoint()
        self.end = QPoint()
        self.is_drawing = False

    def start_capture(self):
        # 计算所有显示器合并后的虚拟桌面大区域
        virtual_rect = QRect()
        for s in QApplication.screens():
            virtual_rect = virtual_rect.united(s.geometry())
            
        self.setGeometry(virtual_rect)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.show()
        self.activateWindow()

    def paintEvent(self, event):
        painter = QPainter(self)
        # 绘制全屏半透明遮罩
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        if self.is_drawing:
            selection_rect = QRect(self.begin, self.end).normalized()
            # 挖空选区，让其完全透明以显示底层真实的桌面
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(selection_rect, Qt.GlobalColor.transparent)
            
            # 画一个边框
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(97, 175, 239), 2))
            painter.drawRect(selection_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin = event.position().toPoint()
            self.end = self.begin
            self.is_drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False
            self.end = event.position().toPoint()
            self.update()
            
            selection_rect = QRect(self.begin, self.end).normalized()
            self.hide()
            
            if selection_rect.width() > 10 and selection_rect.height() > 10:
                global_rect = QRect(
                    self.mapToGlobal(selection_rect.topLeft()),
                    self.mapToGlobal(selection_rect.bottomRight())
                )
                # 延迟一小段，等待遮罩窗口完全消失后再截图
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(100, lambda: self.perform_capture(global_rect))
            else:
                print("[Screenshot] 选区太小，已取消")

    def perform_capture(self, global_rect):
        screen = QApplication.screenAt(global_rect.center())
        if not screen:
            screen = QApplication.primaryScreen()
            
        # 抓取选区所在屏幕的全屏画面
        pixmap = screen.grabWindow(0)
        
        # 将全局坐标转换为当前屏幕的局部坐标
        screen_geom = screen.geometry()
        local_rect = global_rect.translated(-screen_geom.x(), -screen_geom.y())
        
        # 乘以 DPI 缩放率转换为物理像素坐标
        dpr = screen.devicePixelRatio()
        physical_rect = QRect(
            int(local_rect.x() * dpr),
            int(local_rect.y() * dpr),
            int(local_rect.width() * dpr),
            int(local_rect.height() * dpr)
        )
        
        cropped = pixmap.copy(physical_rect)
        cropped.save(CONFIG["screenshot_path"])
        print("[Screenshot] 自定义截图完成")
        self.capture_complete.emit(global_rect)

    def keyPressEvent(self, event):
        # 按 ESC 取消截图
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            print("[Screenshot] 用户取消截图")

# ==========================================
# GUI: 设置窗口
# ==========================================
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedWidth(400)
        
        layout = QVBoxLayout(self)
        
        # API Key
        layout.addWidget(QLabel("DeepSeek API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        layout.addWidget(self.api_key_input)
        
        # 显示模式
        layout.addWidget(QLabel("呈现模式:"))
        self.display_mode_combo = QComboBox()
        self.display_mode_combo.addItem("原位覆盖显示", "in_place")
        self.display_mode_combo.addItem("居中悬浮显示", "floating")
        layout.addWidget(self.display_mode_combo)
        
        # 字体大小
        layout.addWidget(QLabel("字体大小 (px):"))
        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(8, 72)
        layout.addWidget(self.font_size_input)
        
        # 文本颜色
        layout.addWidget(QLabel("文字颜色 (十六进制):"))
        self.text_color_input = QLineEdit()
        layout.addWidget(self.text_color_input)
        
        # 背景颜色
        layout.addWidget(QLabel("背景颜色 (十六进制/RGBA):"))
        self.bg_color_input = QLineEdit()
        layout.addWidget(self.bg_color_input)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        self.load_ui_data()

    def load_ui_data(self):
        self.api_key_input.setText(CONFIG.get("api_key", ""))
        self.font_size_input.setValue(CONFIG.get("font_size", 14))
        self.text_color_input.setText(CONFIG.get("text_color", "#000000"))
        self.bg_color_input.setText(CONFIG.get("bg_color", "#FAFAFA"))
        
        mode = CONFIG.get("display_mode", "in_place")
        idx = self.display_mode_combo.findData(mode)
        if idx >= 0:
            self.display_mode_combo.setCurrentIndex(idx)

    def save_settings(self):
        CONFIG["api_key"] = self.api_key_input.text().strip()
        CONFIG["font_size"] = self.font_size_input.value()
        CONFIG["text_color"] = self.text_color_input.text().strip()
        CONFIG["bg_color"] = self.bg_color_input.text().strip()
        CONFIG["display_mode"] = self.display_mode_combo.currentData()
        
        save_config()
        QMessageBox.information(self, "保存成功", "设置已保存，下次翻译时生效！")
        self.accept()

# ==========================================
# GUI: 悬浮结果窗口
# ==========================================
class FloatingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self._is_tracking = False
        self._start_pos = None

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.copy_btn = QPushButton("复制")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        btn_layout.addWidget(self.copy_btn)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.hide)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        self.apply_styles()

    def apply_styles(self):
        font_size = CONFIG.get("font_size", 14)
        text_color = CONFIG.get("text_color", "#000000")
        bg_color = CONFIG.get("bg_color", "#FAFAFA")
        
        # 外部窗口背景可以完全透明或带点边框，这里将背景色赋给文本框
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 1px solid #999;
                border-radius: 5px;
            }}
            QTextEdit {{
                font-size: {font_size}px;
                color: {text_color};
                background-color: transparent;
                border: none;
            }}
            QPushButton {{
                background-color: #E0E0E0;
                color: #333;
                border: 1px solid #CCC;
                padding: 4px 10px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: #D0D0D0;
            }}
        """)

    def set_text(self, text: str):
        self.text_edit.setPlainText(text)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        print("[GUI] 内容已复制到剪贴板")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_tracking = True
            self._start_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._is_tracking:
            delta = event.globalPosition().toPoint() - self._start_pos
            self.move(self.pos() + delta)
            self._start_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_tracking = False

# ==========================================
# 主控制器
# ==========================================
class AppController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.window = FloatingWindow()
        self.settings_dlg = None
        self.snipper = Snipper()
        
        # --- 信号绑定 ---
        self.controller_signals = ControllerSignals()
        self.controller_signals.start_snipper.connect(self.show_snipper)
        self.snipper.capture_complete.connect(self.on_capture_complete)
        
        self.signals = WorkerSignals()
        self.signals.update_text.connect(self.window.set_text)
        self.signals.show_window.connect(self.window.show)
        self.signals.error_occurred.connect(self.handle_error)

        # --- 托盘图标设置 ---
        self.tray_icon = QSystemTrayIcon(self.app)
        
        if hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        icon_path = os.path.join(base_dir, "assets", "icon.png")
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.app.setWindowIcon(app_icon)
            self.tray_icon.setIcon(app_icon)
        else:
            fallback_icon = self.app.style().standardIcon(self.app.style().StandardPixmap.SP_ComputerIcon)
            self.app.setWindowIcon(fallback_icon)
            self.tray_icon.setIcon(fallback_icon)
            
        tray_menu = QMenu()
        
        translate_action = QAction("截屏翻译", self.app)
        translate_action.triggered.connect(self.controller_signals.start_snipper.emit)
        tray_menu.addAction(translate_action)
        
        settings_action = QAction("设置", self.app)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("退出程序", self.app)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # --- 热键监听器 ---
        self.listener = keyboard.GlobalHotKeys({
            CONFIG["hotkey"]: self.on_hotkey_pressed
        })
        self.listener.start()
        print(f"[System] 程序已启动，监听快捷键: {CONFIG['hotkey']}")

    def handle_error(self, err_msg: str):
        self.window.set_text(f"❌ 发生错误:\n{err_msg}")
        self.window.show()

    def show_settings(self):
        if not self.settings_dlg:
            self.settings_dlg = SettingsDialog()
        self.settings_dlg.load_ui_data()
        self.settings_dlg.show()
        self.settings_dlg.raise_()
        self.settings_dlg.activateWindow()

    def on_hotkey_pressed(self):
        print(f"\n[System] 触发快捷键 {CONFIG['hotkey']}")
        # 必须通过信号触发 GUI 组件，因为当前处于 pynput 的后台线程
        self.controller_signals.start_snipper.emit()
        
    def show_snipper(self):
        self.snipper.start_capture()
        
    def on_capture_complete(self, rect: QRect):
        # 截图完毕，应用样式并调整窗口位置
        self.window.apply_styles()
        
        if CONFIG.get("display_mode") == "in_place":
            # 精确覆盖在截图的坐标上
            self.window.setGeometry(rect)
        else:
            # 居中悬浮模式
            self.window.resize(CONFIG["win_width"], CONFIG["win_height"])
            # 简单计算让它在屏幕中间偏上的位置
            screen_geom = QApplication.primaryScreen().geometry()
            x = (screen_geom.width() - CONFIG["win_width"]) // 2
            y = (screen_geom.height() - CONFIG["win_height"]) // 3
            self.window.move(x, y)
            
        # 启动翻译线程
        threading.Thread(target=workflow_thread, args=(self.signals,), daemon=True).start()

    def quit_app(self):
        print("[System] 正在退出程序...")
        self.listener.stop()
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    controller = AppController()
    controller.run()
