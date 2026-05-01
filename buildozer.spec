[app]

# 应用名称（打包后的 APK 标题）
title = 番茄小说下载器

# 包名（必须唯一，不能与已有应用冲突）
package.name = com.tomatonovel.downloader

# 入口文件
source.include_exts = py
source.include_patterns = main.py

# 依赖（仅需 Kivy，其他标准库）
requirements = python3,kivy

# 权限（网络 + 存储）
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# 应用图标（可选，可后续替换）
# icon.filename = %(source.dir)s/icon.png

# 版本
version = 1.0
version.code = 1

# 避免打包不必要的文件，加快构建
source.exclude_dirs = .git, __pycache__, .buildozer
source.exclude_patterns = *.pyc, *.pyo, .DS_Store

# 安卓最小 / 目标 API（保持默认即可）
android.minapi = 21
android.ndk = 19b

# 着色样式（让状态栏与应用适配）
fullscreen = 0
android.statusbar_color = "#2196F3"