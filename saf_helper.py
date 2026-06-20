#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SAF (Storage Access Framework) Helper —— Kivy Android 应用专用
通过系统文件管理器获取用户选择的目录写入权限，无需 MANAGE_EXTERNAL_STORAGE
兼容 Android 5.0 (API 21) 及以上；非 Android 平台自动回退到普通文件操作

使用方式：
    from saf_helper import SAFHelper

    saf = SAFHelper()

    # 1) 启动系统目录选择器（用户选择后自动回调 _on_dir_selected）
    saf.request_directory_access(on_result=_on_dir_selected)

    # 2) 在回调中获得 tree_uri 后写入文件
    saf.write_file(tree_uri, "小说名.txt", content_bytes)

    # 3) 下次启动时可恢复已持久化的 URI
    saved_uri = saf.get_saved_uri()
"""

import os
import json
import threading
from kivy.utils import platform
from kivy.clock import Clock

# ──────────────────── 平台相关导入 ────────────────────
_IS_ANDROID = (platform == 'android')

if _IS_ANDROID:
    from jnius import autoclass, cast, PythonJavaClass
    from android import activity as android_activity

    # Java 类缓存
    _Intent = autoclass('android.content.Intent')
    _Uri = autoclass('android.net.Uri')
    _Activity = autoclass('android.app.Activity')
    _PythonActivity = autoclass('org.kivy.android.PythonActivity')
    _Build = autoclass('android.os.Build')
    _DocumentsContract = autoclass('android.provider.DocumentsContract')
    _FileOutputStream = autoclass('java.io.FileOutputStream')

    # 尝试加载 DocumentFile（AndroidX 支持库，可选）
    try:
        _DocumentFile = autoclass('androidx.documentfile.provider.DocumentFile')
        _HAS_DOCUMENT_FILE = True
    except Exception:
        _DocumentFile = None
        _HAS_DOCUMENT_FILE = False

    # 常量
    REQUEST_CODE_SAF_DIR = 9527
    _RESULT_OK = -1  # Activity.RESULT_OK
else:
    # 桌面端桩代码
    _Intent = None
    _Uri = None
    _Activity = None
    _PythonActivity = None
    _Build = None
    _DocumentsContract = None
    _FileOutputStream = None
    _DocumentFile = None
    _HAS_DOCUMENT_FILE = False
    REQUEST_CODE_SAF_DIR = 9527
    _RESULT_OK = -1
    android_activity = None


# ──────────────────── 持久化存储（JSON 文件） ────────────────────
def _get_config_path():
    """获取 SAF 配置文件的路径（存放在应用私有目录）"""
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app:
            return os.path.join(app.user_data_dir, 'saf_config.json')
    except Exception:
        pass
    return os.path.join(os.path.expanduser('~'), '.saf_config.json')


def _load_config():
    try:
        with open(_get_config_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(data):
    os.makedirs(os.path.dirname(_get_config_path()), exist_ok=True)
    with open(_get_config_path(), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ──────────────────── onActivityResult 回调处理 ────────────────────
class _SAFResultListener:
    """
    统一管理 SAF 目录选择器的回调。
    通过设置 PythonActivity 的 ActivityResultListener 实现。
    """
    _instance = None
    _pending_callback = None
    _lock = threading.Lock()

    def __init__(self):
        if not _IS_ANDROID:
            return
        self._registered = False
        self._activity_bound = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_callback(self, callback):
        """设置在收到结果时执行的回调函数 callback(request_code, result_code, data)"""
        with self._lock:
            self._pending_callback = callback

    def clear_callback(self):
        with self._lock:
            self._pending_callback = None

    def _handle_result(self, request_code, result_code, data):
        """内部：处理从 Activity 返回的结果"""
        cb = None
        with self._lock:
            cb = self._pending_callback
            self._pending_callback = None
        if cb is not None:
            try:
                cb(request_code, result_code, data)
            except Exception as e:
                print(f"[SAF] 回调执行异常: {e}")

    def _ensure_registered(self):
        """确保已注册 onActivityResult 监听器"""
        if self._registered:
            return
        self._registered = True

        # 方法 1：使用 android.activity.bind（推荐）
        try:
            if android_activity is not None:
                android_activity.bind(on_activity_result=self._on_activity_result_v1)
                self._activity_bound = True
                print("[SAF] 已通过 android.activity.bind 注册回调")
                return
        except Exception as e:
            print(f"[SAF] android.activity.bind 失败: {e}")

        # 方法 2：使用 pyjnius 设置 ActivityResultListener（回退）
        try:
            # PythonActivity 内部接口 ActivityResultListener
            _Listener = PythonJavaClass(
                'org.kivy.android.PythonActivity$ActivityResultListener'
            )

            class _ListenerImpl(_Listener):
                def __init__(self, handler):
                    super().__init__()
                    self._handler = handler

                def onActivityResult(self, requestCode, resultCode, intent):
                    self._handler(requestCode, resultCode, intent)

            listener = _ListenerImpl(self._handle_result)
            # 尝试注册到 PythonActivity
            mActivity = _PythonActivity.mActivity
            # 不同的 p4a 版本可能用不同的方法名
            for method_name in [
                'registerActivityResultListener',
                'setActivityResultListener',
                'setOnActivityResultListener',
            ]:
                try:
                    method = getattr(mActivity, method_name, None)
                    if method:
                        method(listener)
                        print(f"[SAF] 已通过 {method_name} 注册回调")
                        return
                except Exception:
                    continue

            # 最后一招：直接设字段（部分版本支持）
            try:
                mActivity.mActivityResultListener = listener
                print("[SAF] 已通过 mActivityResultListener 字段注册回调")
                return
            except Exception:
                pass
        except Exception as e:
            print(f"[SAF] pyjnius 注册回调失败: {e}")

        print("[SAF] ⚠️ 无法注册 onActivityResult 监听器，SAF 可能不可用")

    def _on_activity_result_v1(self, request_code, result_code, data):
        """android.activity.bind 回调版本"""
        self._handle_result(request_code, result_code, data)


# ──────────────────── SAF 辅助类 ────────────────────
class SAFHelper:
    """
    提供 SAF 目录选择和文件写入功能。
    """

    def __init__(self):
        self._listener = _SAFResultListener.get_instance()
        self._pending_book_id = None  # 在等待 SAF 选择时暂存的 book_id
        self._pending_on_complete = None  # 下载完成后的回调

    # ── 公开 API ──────────────────────────────────────────

    def is_available(self):
        """检查 SAF 是否可用（Android 5.0+ 且非桌面端）"""
        if not _IS_ANDROID:
            return False
        try:
            sdk = _Build.VERSION.SDK_INT
            return sdk >= 21  # Android 5.0
        except Exception:
            return False

    def get_saved_uri(self):
        """获取已持久化的 SAF 目录 URI 字符串（可能为 None 或已失效）"""
        config = _load_config()
        return config.get('saf_tree_uri', None)

    def has_valid_permission(self):
        """
        检查已保存的 URI 是否仍然有效（拥有持久化权限）
        """
        uri_str = self.get_saved_uri()
        if not uri_str or not _IS_ANDROID:
            return False
        try:
            uri = _Uri.parse(uri_str)
            # 检查持久化权限列表中是否包含此 URI
            content_resolver = _PythonActivity.mActivity.getContentResolver()
            persisted = content_resolver.getPersistedUriPermissions()
            for perm in persisted:
                if perm.getUri().equals(uri) and perm.isWritePermission():
                    return True
            return False
        except Exception as e:
            print(f"[SAF] 检查权限异常: {e}")
            return False

    def request_directory_access(self, on_result=None):
        """
        启动系统文件管理器，让用户选择一个目录并授权。

        参数:
            on_result: 回调函数 (success: bool, tree_uri_str: str | None)
                       当用户选择完成后在主线程调用
        """
        if not self.is_available():
            print("[SAF] 设备不支持 SAF")
            if on_result:
                Clock.schedule_once(lambda dt: on_result(False, None), 0)
            return

        # 注册回调
        self._listener._ensure_registered()
        self._listener.set_callback(
            lambda rc, res, data: self._on_saf_result(rc, res, data, on_result)
        )

        # 构建 Intent
        intent = _Intent(_Intent.ACTION_OPEN_DOCUMENT_TREE)
        # Android 8.0+ 可指定初始目录
        if _Build.VERSION.SDK_INT >= 26:
            try:
                # 尝试以已保存的 URI 作为初始位置
                saved = self.get_saved_uri()
                if saved:
                    initial_uri = _Uri.parse(saved)
                    intent.putExtra(_DocumentsContract.EXTRA_INITIAL_URI, initial_uri)
            except Exception as e:
                print(f"[SAF] 设置初始 URI 失败: {e}")

        try:
            _PythonActivity.mActivity.startActivityForResult(intent, REQUEST_CODE_SAF_DIR)
            print("[SAF] 已启动目录选择器")
        except Exception as e:
            print(f"[SAF] 启动选择器失败: {e}")
            self._listener.clear_callback()
            if on_result:
                Clock.schedule_once(lambda dt: on_result(False, None), 0)

    def write_file(self, tree_uri_str, file_name, content):
        """
        在 SAF 授权的目录中创建/覆盖文件并写入内容。

        参数:
            tree_uri_str: SAF 目录 URI 字符串
            file_name: 文件名（如 "小说名.txt"）
            content: 字节内容 (bytes) 或字符串 (str)

        返回:
            bool: 写入是否成功
        """
        if not _IS_ANDROID:
            return self._write_file_fallback(file_name, content)

        if isinstance(content, str):
            content = content.encode('utf-8')

        try:
            tree_uri = _Uri.parse(tree_uri_str)
            context = _PythonActivity.mActivity
            content_resolver = context.getContentResolver()

            # 先尝试删除已存在的同名文件
            self._delete_if_exists(content_resolver, tree_uri, file_name)

            if _HAS_DOCUMENT_FILE:
                # 使用 DocumentFile API（更简洁）
                return self._write_via_documentfile(
                    context, content_resolver, tree_uri, file_name, content
                )
            else:
                # 使用 DocumentsContract 直接操作
                return self._write_via_contract(
                    content_resolver, tree_uri, file_name, content
                )

        except Exception as e:
            print(f"[SAF] 写入文件异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _delete_if_exists(self, content_resolver, tree_uri, file_name):
        """尝试删除已存在的同名文件"""
        try:
            tree_doc_id = _DocumentsContract.getTreeDocumentId(tree_uri)
            children_uri = _DocumentsContract.buildChildDocumentsUriUsingTree(
                tree_uri, tree_doc_id
            )
            # 查询子文档
            cursor = None
            try:
                cursor = content_resolver.query(
                    children_uri,
                    [_DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                     _DocumentsContract.Document.COLUMN_DISPLAY_NAME],
                    None, None, None
                )
                if cursor:
                    while cursor.moveToNext():
                        name = cursor.getString(1)
                        if name == file_name:
                            doc_id = cursor.getString(0)
                            doc_uri = _DocumentsContract.buildDocumentUriUsingTree(
                                tree_uri, doc_id
                            )
                            _DocumentsContract.deleteDocument(content_resolver, doc_uri)
                            print(f"[SAF] 已删除旧文件: {file_name}")
                            break
            finally:
                if cursor:
                    cursor.close()
        except Exception as e:
            print(f"[SAF] 删除旧文件时出错（可忽略）: {e}")

    def _write_via_documentfile(self, context, content_resolver, tree_uri,
                                 file_name, content):
        """通过 DocumentFile API 创建文件并写入"""
        root_doc = _DocumentFile.fromTreeUri(context, tree_uri)
        if root_doc is None or not root_doc.canWrite():
            print("[SAF] 目录不可写")
            return False

        # 创建新文件
        mime_type = 'text/plain'
        new_file = root_doc.createFile(mime_type, file_name)
        if new_file is None:
            print(f"[SAF] 创建文件失败: {file_name}")
            return False

        # 写入内容
        output_stream = content_resolver.openOutputStream(new_file.getUri(), 'wt')
        if output_stream is None:
            print("[SAF] 无法打开输出流")
            return False
        try:
            output_stream.write(content)
            output_stream.flush()
            print(f"[SAF] ✅ 文件写入成功 (DocumentFile): {file_name}")
            return True
        finally:
            output_stream.close()

    def _write_via_contract(self, content_resolver, tree_uri, file_name, content):
        """通过 DocumentsContract API 创建文件并写入（无需 DocumentFile）"""
        tree_doc_id = _DocumentsContract.getTreeDocumentId(tree_uri)
        children_uri = _DocumentsContract.buildChildDocumentsUriUsingTree(
            tree_uri, tree_doc_id
        )

        # 创建新文档
        mime_type = 'text/plain'
        new_doc_uri = _DocumentsContract.createDocument(
            content_resolver, children_uri, mime_type, file_name
        )
        if new_doc_uri is None:
            print(f"[SAF] 创建文档失败: {file_name}")
            return False

        # 写入内容
        output_stream = content_resolver.openOutputStream(new_doc_uri, 'wt')
        if output_stream is None:
            print("[SAF] 无法打开输出流")
            return False
        try:
            output_stream.write(content)
            output_stream.flush()
            print(f"[SAF] ✅ 文件写入成功 (DocumentsContract): {file_name}")
            return True
        finally:
            output_stream.close()

    def _write_file_fallback(self, file_name, content):
        """桌面端回退：直接写入文件系统"""
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        try:
            download_dir = os.path.join(os.path.expanduser('~'), 'Downloads', 'novels')
            os.makedirs(download_dir, exist_ok=True)
            file_path = os.path.join(download_dir, file_name)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[SAF-Fallback] ✅ 文件已保存到: {file_path}")
            return True
        except Exception as e:
            print(f"[SAF-Fallback] ❌ 写入失败: {e}")
            return False

    # ── 内部回调处理 ──────────────────────────────────────

    def _on_saf_result(self, request_code, result_code, data, on_result):
        """处理 SAF 目录选择器的返回结果"""
        self._listener.clear_callback()

        if request_code != REQUEST_CODE_SAF_DIR:
            # 不是我们的请求，重新设置回调并忽略
            if on_result:
                self._listener.set_callback(
                    lambda rc, res, d: self._on_saf_result(rc, res, d, on_result)
                )
            return

        if result_code != _RESULT_OK or data is None:
            print("[SAF] 用户取消了目录选择")
            if on_result:
                on_result(False, None)
            return

        try:
            tree_uri = data.getData()
            if tree_uri is None:
                print("[SAF] 未获取到 URI")
                if on_result:
                    on_result(False, None)
                return

            # 获取持久化权限
            flags = data.getFlags() & (
                _Intent.FLAG_GRANT_READ_URI_PERMISSION |
                _Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            )
            content_resolver = _PythonActivity.mActivity.getContentResolver()
            content_resolver.takePersistableUriPermission(tree_uri, flags)

            # 保存 URI 到配置文件
            uri_str = tree_uri.toString()
            config = _load_config()
            config['saf_tree_uri'] = uri_str
            _save_config(config)

            print(f"[SAF] ✅ 目录权限已获取并持久化: {uri_str}")
            if on_result:
                on_result(True, uri_str)

        except Exception as e:
            print(f"[SAF] 处理 SAF 结果异常: {e}")
            import traceback
            traceback.print_exc()
            if on_result:
                on_result(False, None)