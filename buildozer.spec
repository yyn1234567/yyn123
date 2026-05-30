[app]

# (str) 应用程序标题
title = s丶ky书包

# (str) 包名（必须唯一，建议用你自己的域名风格）
package.name = fq

# (str) 包域名（用于Java包名生成）
package.domain = com.yyn123.fq

# (str) 主程序入口文件
source.dir = .

# (list) 包含的源文件
source.include_exts = py,png,jpg,kv,atlas,ttf

# (list) 排除的源文件模式
source.exclude_exts = spec

# (str) 应用版本号
version = 1.2.2

# (str) 应用版本名
version.regex = __version__ = ['"](.*)['"]
version.filename = %(source.dir)s/main.py

# (list) 构建要求
# 对于 Kivy 应用，buildozer 会自动包含 kivy
requirements = python3,kivy

# (str) 支持的Android最低API等级
android.minapi = 24

# (str) 目标API等级（建议 >= 33）
android.api = 34

# (str) 编译SDK等级
android.ndk = 25b

# (str) Android SDK版本
android.sdk = 34

# (list) Android 权限
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# (list) Android 功能
android.features = android.hardware.screen_portrait

# (bool) 允许代码混淆（减小体积）
android.release = False

# (str) 默认横竖屏
orientation = portrait

# (list) 支持的横竖屏
android.allow_backup = True

# (str) 图标路径（你需要准备一个 512x512 的 PNG）
icon.filename = %(source.dir)s/icon.png

# (str) 启动画面（可选）
presplash.filename = %(source.dir)s/presplash.png

# (list) 需要包含的额外文件/目录
source.include_patterns = 

# (bool) 是否使用Gradle构建
android.gradle_dependencies = 

# (bool) Kivy 应用专用
osx.kivy_version = 2.3.0

# (str) 构建日志级别: trace, debug( verbose), info, warning, error, critical
log_level = 1

# (bool) 允许调试模式
android.enable_androidx = True