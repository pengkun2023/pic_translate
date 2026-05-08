#!/bin/bash
set -e

APP_NAME="pic-translate"
VERSION="0.0.2"
ARCH="amd64"
DEB_DIR="${APP_NAME}_${VERSION}_${ARCH}"

echo ">>> 安装打包依赖 PyInstaller..."
conda run -n pic_work pip install pyinstaller

echo ">>> 开始使用 PyInstaller 编译项目..."
# 使用 --windowed 隐藏控制台，--add-data 打包静态资源
conda run -n pic_work pyinstaller --clean --name "${APP_NAME}" \
    --windowed \
    --onefile \
    --icon "assets/icon.png" \
    --add-data "assets/icon.png:assets" \
    main.py

echo ">>> 创建 Debian 包目录结构..."
rm -rf "${DEB_DIR}"
mkdir -p "${DEB_DIR}/DEBIAN"
mkdir -p "${DEB_DIR}/usr/bin"
mkdir -p "${DEB_DIR}/usr/share/applications"
mkdir -p "${DEB_DIR}/usr/share/pixmaps"

echo ">>> 编写 control 文件..."
cat << EOF > "${DEB_DIR}/DEBIAN/control"
Package: ${APP_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: scrot, tesseract-ocr, tesseract-ocr-eng, tesseract-ocr-chi-sim, libxcb-cursor0
Maintainer: Byte <byte@example.com>
Description: A desktop screenshot translation tool powered by DeepSeek AI.
 Global hotkey triggers a screenshot and translates the text using OCR and LLM.
EOF

echo ">>> 拷贝编译产物与资源..."
# 拷贝二进制文件
cp "dist/${APP_NAME}" "${DEB_DIR}/usr/bin/"
chmod 755 "${DEB_DIR}/usr/bin/${APP_NAME}"

# 拷贝桌面快捷方式
cp "${APP_NAME}.desktop" "${DEB_DIR}/usr/share/applications/"
chmod 644 "${DEB_DIR}/usr/share/applications/${APP_NAME}.desktop"

# 拷贝图标
cp "assets/icon.png" "${DEB_DIR}/usr/share/pixmaps/${APP_NAME}.png"
chmod 644 "${DEB_DIR}/usr/share/pixmaps/${APP_NAME}.png"

echo ">>> 生成 .deb 包..."
dpkg-deb --build "${DEB_DIR}"

echo ">>> 打包完成！"
echo "你可以使用以下命令安装: sudo apt install ./${DEB_DIR}.deb"
