[app]
title = s丶ky书包
package.name = fq
package.domain = com.yyn123.fq
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
version = 1.2.7
requirements = python3,kivy,requests,libiconv,libffi,pyjnius,android
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

# Android permissions - Updated for Android 15 compatibility
android.permissions = INTERNET,WAKE_LOCK,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO,MANAGE_EXTERNAL_STORAGE

# Android 11+ scoped storage compatibility
android.add_src = android/src/main/java/com/yyn123/fq/FileProvider.java

# Following is required for release mode
android.aab = False

# Signature configuration (uncomment and configure for release builds)
#android.keystore = /home/runner/work/yyn123/AndAgain/com.yyn123.fq.keystore
#android.keystore_storepass = android
#android.keystore_keypass = android
#android.keystore_alias = com.yyn123.fq

# Android manifest additions
android.manifest_placeholders = [:]
android.manifest = <manifest><uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE"/></manifest>

[buildozer]
log_level = 2
warn_on_root = 1
