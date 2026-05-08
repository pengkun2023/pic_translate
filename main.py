import sys
import os
import subprocess
import threading
import requests
from PIL import Image
import pytesseract
from pynput import keyboard

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QObject

# ==========================================
# CONFIG: 配置项集中存放
# ==========================================
CONFIG = {
    "screenshot_cmd": ["scrot", "-s", "-o"],  # 使用 scrot 框选截图，-o 覆盖同名文件
    "screenshot_path": "/tmp/pic_translate_capture.png",
    "hotkey": "<ctrl>+<alt>+x",
    "ocr_lang": "eng+chi_sim",  # 确保系统已安装 tesseract-ocr-eng 和 tesseract-ocr-chi-sim
    "api_provider": "DeepSeek",
    "api_url": "https://api.deepseek.com",
    "api_key": "sk-906b97091638488f86988b15926e810b",
    "api_model": "deepseek-v4-flash",
    "win_width": 400,
    "win_height": 300,
}

# ==========================================
# 信号类：用于子线程与 GUI 主线程通信
# ==========================================
class WorkerSignals(QObject):
    update_text = pyqtSignal(str)
    show_window = pyqtSignal()
    error_occurred = pyqtSignal(str)

# ==========================================
# 后台工作逻辑
# ==========================================
def take_screenshot() -> bool:
    """调用系统工具进行截图，返回是否成功"""
    print("[Screenshot] 开始截图...")
    try:
        # 阻塞等待用户框选完成
        cmd = CONFIG["screenshot_cmd"] + [CONFIG["screenshot_path"]]
        subprocess.run(cmd, check=True)
        if os.path.exists(CONFIG["screenshot_path"]):
            print("[Screenshot] 截图成功")
            return True
        return False
    except subprocess.CalledProcessError as e:
        print(f"[Screenshot] 取消截图或发生错误: {e}")
        return False
    except Exception as e:
        print(f"[Screenshot] 发生未知错误: {e}")
        return False

def do_ocr() -> str:
    """读取截图文件进行 OCR 识别"""
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
    """调用大模型 API 进行翻译"""
    if not text:
        return ""
    
    print(f"[{CONFIG['api_provider']}] 开始翻译...")
    try:
        # 修复 httpx 不识别 socks:// 协议的问题（强制转换为 socks5://）
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
        )
        
        result = response.choices[0].message.content.strip()
        print(f"[{CONFIG['api_provider']}] 翻译成功")
        return result
    except Exception as e:
        print(f"[{CONFIG['api_provider']}] 翻译失败: {e}")
        raise RuntimeError(f"翻译失败: {e}")

def workflow_thread(signals: WorkerSignals):
    """完整的截图翻译工作流（在子线程运行）"""
    try:
        # 1. 截图
        success = take_screenshot()
        if not success:
            return
            
        # 2. 唤起窗口显示“识别中...”
        signals.show_window.emit()
        signals.update_text.emit("正在识别文字...")
        
        # 3. OCR 识别
        text = do_ocr()
        if not text:
            signals.update_text.emit("未识别到文字。")
            return
            
        signals.update_text.emit(f"【原文】\n{text}\n\n正在翻译...")
        
        # 4. 翻译
        translated = translate_text(text)
        signals.update_text.emit(f"【原文】\n{text}\n\n【翻译】\n{translated}")
        
    except Exception as e:
        signals.error_occurred.emit(str(e))

# ==========================================
# GUI 悬浮窗口
# ==========================================
class FloatingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        # 允许拖拽的内部状态
        self._is_tracking = False
        self._start_pos = None

    def init_ui(self):
        # 无边框 + 窗口置顶
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(CONFIG["win_width"], CONFIG["win_height"])
        
        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 文本框
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        # 简单的样式
        self.text_edit.setStyleSheet("font-size: 14px; background-color: #FAFAFA; border: 1px solid #CCC;")
        layout.addWidget(self.text_edit)
        
        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.copy_btn = QPushButton("一键复制")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        btn_layout.addWidget(self.copy_btn)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.hide)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)

    def set_text(self, text: str):
        self.text_edit.setPlainText(text)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        print("[GUI] 内容已复制到剪贴板")
        
    # --- 拖拽窗口实现 ---
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
        self.window = FloatingWindow()
        
        # 信号设置
        self.signals = WorkerSignals()
        self.signals.update_text.connect(self.window.set_text)
        self.signals.show_window.connect(self.window.show)
        self.signals.error_occurred.connect(self.handle_error)
        
        # 热键监听器
        self.listener = keyboard.GlobalHotKeys({
            CONFIG["hotkey"]: self.on_hotkey_pressed
        })
        self.listener.start()
        print(f"[System] 程序已启动，监听快捷键: {CONFIG['hotkey']}")

    def handle_error(self, err_msg: str):
        self.window.set_text(f"❌ 发生错误:\n{err_msg}")
        self.window.show()

    def on_hotkey_pressed(self):
        print(f"\n[System] 触发快捷键 {CONFIG['hotkey']}")
        # 启动子线程执行耗时任务，避免阻塞 GUI 主线程
        threading.Thread(target=workflow_thread, args=(self.signals,), daemon=True).start()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    controller = AppController()
    controller.run()
