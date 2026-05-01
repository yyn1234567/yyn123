[app]

# (str) 应用标题
title = fq

# (str) 包名 (必须是唯一的域名格式)
package.name = com.example.noveldownloader

# (str) 包域名
package.domain = org.example

# (list) 源代码目录
source.dir = .

# (list) 源代码文件扩展名
source.include_exts = py,png,jpg,kv,atlas

# (list) 需要的Python包
# 注意：urllib 和 json 是标准库，不需要额外安装
requirements = python3, kivy, urllib3, certifi

# (str) 图标 (可选，如果没有则使用默认)
# icon.filename = %(source.dir)s/icon.png

# (int) 启动屏背景颜色 (十六进制)
# bootstrap.default_bg = #FFFFFF

# Android 配置
[android]
# (int) Android API 版本
android.api = 30
# (int) SDK 版本
android.minapi = 21
# (str) NDK 版本 (Buildozer会自动下载)
# ndk = 25b

# (list) 需要的权限
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE

# (str) 编译模式 (debug 或 release)
# production = 0

[buildozer]
# (int) 日志级别 (0 = 所有, 10 = INFO, 20 = WARNING, 30 = ERROR)
log_level = 20
