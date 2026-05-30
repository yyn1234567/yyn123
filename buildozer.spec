[app]
title = s丶ky书包
package.name = fq
package.domain = com.yyn123.fq
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.2.1
requirements = python3,kivy,requests,pyjnius,android
icon.filename = icon.png
presplash.filename = presplash.png
fullscreen = 0
orientation = portrait
entrypoint = main.py

# Android 配置（保持不变）
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

# Android 权限
android.permissions = INTERNET,WAKE_LOCK,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO,MANAGE_EXTERNAL_STORAGE
android.add_src = android/src/main/java/com/yyn123/fq/FileProvider.java

# 输出APK（非AAB）
android.aab = False

# Android manifest 补充
android.manifest_placeholders = [:]
android.manifest = <manifest><uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE"/></manifest>

[buildozer]
log_level = 2
warn_on_root = 1