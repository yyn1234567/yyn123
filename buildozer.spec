[app]
title = 煲汤-Tb
package.name = com.yyn123.fq
package.domain = com.yyn123.fq
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
version = 2.0.4
requirements = python3,kivy,certifi,libiconv,libffi
icon.filename = icon.png
#presplash.filename = presplash.png
fullscreen = 0
orientation = portrait
entrypoint = main.py

#这些不要改 Don't change these
android.accept_sdk_license = True
android.allow_api_min = 21
android.api = 33
android.minapi = 21
android.ndk = 25b
exclude_patterns = **/test/*, **/tests/*
android.gradle_download = https://services.gradle.org/distributions/gradle-7.6.4-all.zip
android.gradle_plugin = 7.4.2
android.sdk = 33
android.ndk_api = 21
p4a.gradle_dependencies = gradle:7.6.4
p4a.bootstrap = sdl2
p4a.gradle_options = -Dorg.gradle.java.home=/usr/lib/jvm/java-17-openjdk-amd64
android.permissions = INTERNET

#以下为release模式需要 Following is required for release mode

#强制构建APK而不是AAB,但没用 Why does it build .aab instead of .apk?
#android.aab = False

#签名配置 signature configuration
#android.keystore = /home/runner/work/yyn123/AndAgain/com.yyn123.fq.keystore
#android.keystore_storepass = android
#android.keystore_keypass = android
#android.keystore_alias = com.yyn123.fq

[buildozer]
log_level = 2
warn_on_root = 1