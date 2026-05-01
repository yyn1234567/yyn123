[app]

# (str) 应用标题 (显示在手机桌面上)
title = 番茄小说下载器

# (str) 包名 (必须是唯一的，建议反向域名格式)
package.name = com.example.fanqienovel

# (str) 包域名 (生成最终的包名: org.example.fanqienovel)
package.domain = org.example

# (str) 你的应用版本号 (修复了刚才报错的地方)
version = 0.1

# (list) 源代码目录
source.dir = .

# (list) 包含的文件扩展名
source.include_exts = py,png,jpg,kv,atlas,txt

# (list) 需要的 Python 包
# Kivy 是必须的，urllib3 和 certifi 有助于 Android 上的 HTTPS 请求
requirements = python3, kivy, urllib3, certifi

# (str) 应用图标 (如果没有，使用默认)
# icon.filename = %(source.dir)s/icon.png

# (str) 启动屏背景颜色
# bootstrap.default_bg = #FFFFFF

# (list) Android 权限 (非常重要：下载需要网络和写入存储)
# 注意：Android 10+ 以上版本写入公共目录可能需要特殊处理，但权限必须先声明
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# Android SDK 设置
[android]
# (int) 编译 SDK 版本
android.api = 30
# (int) 最低支持的 Android 版本 (Android 5.0+)
android.minapi = 21
# (str) NDK 版本 (Buildozer 会自动下载)
# ndk = 25b
# (int) NDK API 版本 (通常与 minapi 一致)
# ndk_api = 21

# 编译模式
[buildozer]
# (int) 日志级别 (2 为正常输出)
log_level = 2
# (str) 虚拟机/容器选择 (默认为 docker)
# bin_dir = 
# (str) 虚拟机镜像名称 (默认为 kivy/buildozer)
# docker_image = kivy/buildozer

# (str) 生成的 APK 文件名
# android.numeric_version = 1

# (list) 服务配置 (如果需要后台服务)
# android.services = 

# (list) 签名配置 (Debug 模式不需要)
# android.sign.debug = 
# android.keystore = 
# android.keyalias = 
# android.keypass = 
# android.storepass = 
