# Linux 桌面截屏翻译小工具 (Pic-Translate)

这是一个基于 Python 和 PyQt6 开发的轻量级 Linux 桌面应用。它允许用户通过全局快捷键快速框选屏幕上的任何内容，利用本地 OCR 技术识别文字，并通过 DeepSeek 大模型（或兼容 OpenAI 格式的其他大语言模型）将其翻译为流畅的中文/英文，最终在一个可拖拽、置顶的悬浮窗中展示结果。

## ✨ 核心特性

- 🎯 **全局快捷键触发**: 默认快捷键 `<ctrl>+<alt>+x`，随时随地呼出截屏框。
- 🖼️ **高效本地 OCR**: 使用 `Tesseract-OCR` 进行离线图像文字识别，保护隐私，速度极快。
- 🧠 **AI 智能翻译**: 原生接入 DeepSeek v4 Flash 官方 Python SDK，利用大模型的强大推理能力进行语境翻译。
- 🔧 **可视化配置**: 拥有系统托盘 (System Tray) 图标，支持通过 GUI 设置界面直接填写和修改 API Key，配置自动持久化保存。
- 🪟 **悬浮窗结果展示**: 翻译结果显示在无边框、半透明的置顶窗口中，支持自由拖拽和“一键复制”。
- 📦 **开箱即用**: 提供一键打包的 `.deb` 安装包，自动生成桌面图标和应用菜单入口。

## 🛠️ 环境要求 (依赖)

如果在非打包的源码环境下运行，请确保系统安装了以下依赖：

### 1. 系统级依赖项 (Ubuntu/Debian)
```bash
sudo apt update
# scrot 用于截图; tesseract 用于 OCR 识别; libxcb-cursor0 用于解决 PyQt6 鼠标指针库缺失问题
sudo apt install scrot tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim libxcb-cursor0
```

### 2. Python 环境
推荐使用 Conda 创建独立环境：
```bash
conda create -n pic_work python=3.10 -y
conda activate pic_work
pip install -r requirements.txt
```

## 🚀 安装与使用

### 方式一：使用 `.deb` 安装包 (推荐)
如果你已经通过打包脚本生成了 `.deb` 文件，可以直接在 Ubuntu 等 Debian 系系统中双击安装，或者在终端执行：

```bash
sudo apt install ./pic-translate_1.0.0_amd64.deb
```
安装后，在系统的“应用抽屉 / 所有程序”中搜索 `截屏翻译` 并启动。

### 方式二：源码运行
在安装好上述系统依赖和 Python 库之后：
```bash
conda activate pic_work
python main.py
```

### 使用指南
1. **启动程序**: 启动后程序会在后台静默运行。请留意屏幕顶部或底部的系统托盘，会出现一个 `A/文` 图标。
2. **配置 API Key**: 第一次使用时，请**右键点击托盘图标 -> 设置**，填入你的 DeepSeek API Key（以 `sk-` 开头）。配置会自动保存在 `~/.config/pic-translate/config.json` 中，重启不丢失。
3. **开始翻译**: 按下 `<ctrl>+<alt>+x`，鼠标变成十字光标后，框选需要翻译的屏幕区域。
4. **查看与复制**: 稍等片刻，屏幕上会弹出悬浮窗展示原文和翻译结果，点击“一键复制”即可将结果拷入剪贴板。

*(注意：如果使用的是较新的 Wayland 桌面协议，`scrot` 和全局快捷键可能会受到系统级权限拦截。建议切换到 Xorg 会话，或修改代码中的截图命令为系统自带的 `gnome-screenshot`。)*

## 📦 如何打包应用？

本项目自带了自动化构建脚本 `build_deb.sh`。只需在终端中运行它，它就会自动下载 `PyInstaller`，将项目静态编译为一个独立的单文件二进制程序，并打包成一个标准的 Debian 包结构。

```bash
chmod +x build_deb.sh
./build_deb.sh
```

生成的安装包将保存在当前目录下（例如：`pic-translate_1.0.0_amd64.deb`）。

## 🔧 自定义高级配置

如果你想更改默认的模型或替换成 OpenAI、代理地址等，可以直接修改 `main.py` 顶部的 `DEFAULT_CONFIG` 字典，或者在你的用户目录配置文件中添加相应的键值对：

- `~/.config/pic-translate/config.json`

例如，想切换到快速的对话模型，可以将 `"api_model"` 的值从 `"deepseek-v4-pro"` 改为 `"deepseek-v4-flash"`。

## 📜 License
MIT License
