import os

class FletBuildConfig:
    """Flet Android构建配置"""
    
    # 应用基本信息
    APP_TITLE = "煲汤-Tb"
    APP_BUNDLE_ID = "com.yyn123.fq"
    APP_ORG = "com.yyn123"
    APP_PRODUCT = "煲汤-Tb"
    BUILD_VERSION = "2.0.2"
    BUILD_NUMBER = "3"
    
    # Android权限配置
    ANDROID_PERMISSIONS = [
        "android.permission.INTERNET",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.ACCESS_NETWORK_STATE",
        "android.permission.ACCESS_WIFI_STATE"
    ]
    
    # Android特性配置
    ANDROID_FEATURES = {
        "android.hardware.camera": False,
        "android.hardware.location": False,
        "android.hardware.microphone": False
    }
    
    # 应用图标配置
    ICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    
    # 构建选项
    BUILD_OPTIONS = {
        "flutter": {
            "verbose": True,
            "obfuscate": False,
            "split-debug-info": None
        },
        "android": {
            "min_sdk_version": 21,
            "target_sdk_version": 33,
            "compile_sdk_version": 33
        }
    }
    
    @staticmethod
    def get_android_manifest():
        """生成AndroidManifest.xml内容"""
        permissions = "\n".join([f'    <uses-permission android:name="{perm}" />' 
                               for perm in FletBuildConfig.ANDROID_PERMISSIONS])
        
        features = "\n".join([f'    <uses-feature android:name="{feature}" android:required="{required}" />' 
                             for feature, required in FletBuildConfig.ANDROID_FEATURES.items()])
        
        return f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{FletBuildConfig.APP_BUNDLE_ID}">
{permissions}
{features}
    <application
        android:label="{FletBuildConfig.APP_TITLE}"
        android:icon="@mipmap/ic_launcher"
        android:requestLegacyExternalStorage="true">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:launchMode="singleTop"
            android:theme="@style/LaunchTheme"
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|smallestScreenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode"
            android:hardwareAccelerated="true"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>"""
    
    @staticmethod
    def get_build_args():
        """获取构建参数"""
        return [
            "--bundle-id", FletBuildConfig.APP_BUNDLE_ID,
            "--product", FletBuildConfig.APP_PRODUCT,
            "--org", FletBuildConfig.APP_ORG,
            "--build-version", FletBuildConfig.BUILD_VERSION,
            "--build-number", FletBuildConfig.BUILD_NUMBER
        ]
    
    @staticmethod
    def verify_config():
        """验证配置是否完整"""
        required_fields = [
            'APP_TITLE', 'APP_BUNDLE_ID', 'APP_ORG', 
            'APP_PRODUCT', 'BUILD_VERSION', 'BUILD_NUMBER'
        ]
        
        missing = [field for field in required_fields if not getattr(FletBuildConfig, field)]
        if missing:
            raise ValueError(f"缺少必要的配置字段: {', '.join(missing)}")
        
        return True

# 导出配置实例
config = FletBuildConfig()