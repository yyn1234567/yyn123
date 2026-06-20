[app]
title = s丶ky书包
package.name = fq
package.domain = com.yyn123.fq
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
version = 1.3.4
requirements = python3,kivy,kivymd,pillow,requests,libiconv,libffi,pyjnius,android
icon.filename = icon.png
presplash.filename = presplash.png
fullscreen = 0
orientation = portrait
entrypoint = main.py

# Don't change these
android.accept_sdk_license = True
android.allow_api_min = 21
android.api = 35
android.minapi = 21
android.ndk = 25b
exclude_patterns = **/test/*, **/tests/*
android.gradle_download = https://services.gradle.org/distributions/gradle-7.6.4-all.zip
android.gradle_plugin = 7.4.2
android.sdk = 35
android.ndk_api = 21
p4a.gradle_dependencies = gradle:7.6.4
p4a.bootstrap = sdl2
p4a.gradle_options = -Dorg.gradle.java.home=/usr/lib/jvm/java-17-openjdk-amd64

# Android permissions
# SAF 不需要 MANAGE_EXTERNAL_STORAGE，保留基础存储权限仅用于兼容旧设备
android.permissions = INTERNET,WAKE_LOCK

# AndroidX DocumentFile 支持库（可选，但推荐）
# 如果构建失败可尝试注释掉下面这行
android.maven_repositories = https://dl.google.com/dl/android/maven2/

# Following is required for release mode
android.aab = False

# 移除以下行（不再需要）
# android.add_src = android/src/main/java/com/yyn123/fq/FileProvider.java

# Signature configuration (uncomment and configure for release builds)
#android.keystore = /home/runner/work/yyn123/AndAgain/com.yyn123.fq.keystore
#android.keystore_storepass = android
#android.keystore_keypass = android
#android.keystore_alias = com.yyn123.fq

# Android manifest 不再需要额外权限声明
# android.manifest = <manifest><uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE"/></manifest>

[buildozer]
log_level = 2
warn_on_root = 1