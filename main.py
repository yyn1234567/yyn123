#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os, time, re, threading
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.core.text import LabelBase

# === 安卓 SAf 支持 ===
from kivy.utils import platform
if platform == 'android':
    from android.storage import primary_external_storage_path
    from android import activity
    from jnius import autoclass, cast
    from android import mActivity

    # Java 类
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
    DocumentFile = autoclass('androidx.documentfile.provider.DocumentFile')
    FileOutputStream = autoclass('java.io.FileOutputStream')
    Environment = autoclass('android.os.Environment')
    Context = autoclass('android.content.Context')
    Activity = autoclass('android.app.Activity')

# 常量
BASE_URL = "https://oiapi.net/api/FqRead"
API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"
MAX_RETRIES = 3
RETRY_DELAY = 2
TIMEOUT = 30

# ---------- 原有工具函数保持不变 ----------
def clean_filename(name):
    return re.sub(r"[\/\\\:\*\?\"\<\>\|]", "_", name)

def api_request(url_params):
    url = f"{BASE_URL}?{url_params}&key={API_KEY}"
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=TIMEOUT, verify=False)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(f"API请求失败: {str(e)}")

def get_book_info(book_id):
    result = api_request(f"method=ids&id={book_id}")
    if result.get('code') == 1:
        return result['data']
    raise Exception(f"获取书籍信息失败: {result.get('message', '未知错误')}")

def get_chapter_list(book_id):
    result = api_request(f"method=chapters&id={book_id}")
    if result.get('code') == 1:
        return result['data']
    raise Exception(f"获取章节列表失败: {result.get('message', '未知错误')}")

def get_chapter_contents_batch(book_id, start, end):
    result = api_request(f"method=chapter&id={book_id}&chapter={start}-{end}")
    if result.get('code') == 1:
        return result['data']
    raise Exception(f"批量获取章节失败: {result.get('message', '未知错误')}")

def clean_content(content):
    content = content.replace('</p><p>', '\n').replace('<p>', '').replace('</p>', '\n')
    content = re.sub(re.compile('<.*?>'), '', content)
    content = re.sub(r'\n+', '\n', content).strip()
    return content

# ---------- 自定义目录相关 ----------
class CustomPathManager:
    """管理用户自定义保存目录 URI，使用 SharedPreferences 持久化"""
    def __init__(self):
        if platform == 'android':
            self.prefs = mActivity.getSharedPreferences("novel_prefs", Context.MODE_PRIVATE)
        else:
            self.prefs = None  # 桌面调试无此功能

    def get_saved_uri(self):
        """返回保存的目录树 URI 字符串，若无则返回 None"""
        if self.prefs:
            uri_str = self.prefs.getString("custom_save_uri", None)
            return uri_str
        return None

    def set_saved_uri(self, uri_str):
        """保存目录树 URI 字符串"""
        if self.prefs:
            editor = self.prefs.edit()
            editor.putString("custom_save_uri", uri_str)
            editor.apply()

    def choose_directory(self):
        """启动系统文件管理器，选择根目录"""
        if platform != 'android':
            print("当前平台不支持 SAF 选择目录")
            return

        # 构建 Intent
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
        intent.addFlags(
            Intent.FLAG_GRANT_READ_URI_PERMISSION |
            Intent.FLAG_GRANT_WRITE_URI_PERMISSION |
            Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION |
            Intent.FLAG_GRANT_PREFIX_URI_PERMISSION
        )
        mActivity.startActivityForResult(intent, 1001)  # 请求码 1001

        # 绑定结果回调（必须在方法内绑定，且只一次）
        activity.bind(on_activity_result=self.on_activity_result)

    def on_activity_result(self, request_code, result_code, data):
        if request_code == 1001 and result_code == Activity.RESULT_OK and data:
            tree_uri = data.getData()
            if tree_uri:
                # 获取持久化权限
                mActivity.getContentResolver().takePersistableUriPermission(
                    tree_uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                )
                self.set_saved_uri(tree_uri.toString())
                # 通知主线程更新显示
                Clock.schedule_once(lambda dt: self.update_ui_label(), 0)

    def update_ui_label(self):
        # 通过 App 实例找到 NovelDownloader 并更新标签
        app = App.get_running_app()
        if app and hasattr(app, 'root'):
            root = app.root
            if hasattr(root, 'path_label'):
                root.path_label.text = f"当前保存目录：自定义 (已选择)"

    def write_to_custom_uri(self, uri_str, filename, content):
        """
        通过 ContentResolver 在 SAF 目录树下写入文件。
        返回成功 True/失败 False
        """
        if platform != 'android':
            return False

        try:
            tree_uri = Uri.parse(uri_str)
            doc_file = DocumentFile.fromTreeUri(mActivity, tree_uri)
            # 创建或覆盖文件
            existing = doc_file.findFile(filename)
            if existing:
                existing.delete()
            new_file = doc_file.createFile("text/plain", filename)
            if new_file is None:
                raise Exception("无法创建文件")

            output_stream = mActivity.getContentResolver().openOutputStream(new_file.getUri())
            if output_stream is None:
                raise Exception("无法打开输出流")

            output_stream.write(content.encode('utf-8'))
            output_stream.close()
            return True
        except Exception as e:
            print(f"SAF 写入失败: {e}")
            return False

# ---------- 修改主界面，增加选择目录按钮 ----------
class NovelDownloader(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=15, spacing=10, **kwargs)

        self.path_manager = CustomPathManager()

        self.add_widget(Label(text='fq v2.0.6', size_hint_y=None, height=50, bold=True, font_size='18sp'))

        # 当前路径显示
        default_dir = os.path.join(App.get_running_app().user_data_dir, "novels")
        self.path_label = Label(
            text=f"当前保存目录：{default_dir}",
            size_hint_y=None,
            height=40,
            font_size='14sp',
            halign='left',
            valign='middle'
        )
        self.path_label.bind(size=self.path_label.setter('text_size'))
        self.add_widget(self.path_label)

        # 选择目录按钮
        self.choose_btn = Button(text='选择保存目录', size_hint_y=None, height=44)
        self.choose_btn.bind(on_press=self.ask_choose_directory)
        self.add_widget(self.choose_btn)

        self.book_id_input = TextInput(hint_text='请输入book id', size_hint_y=None, height=48, multiline=False)
        self.add_widget(self.book_id_input)

        self.download_btn = Button(text='开始下载', size_hint_y=None, height=48)
        self.download_btn.bind(on_press=self.start_download)
        self.add_widget(self.download_btn)

        self.output_label = Label(text='', size_hint_y=None, halign='left', valign='top')
        self.scroll_view = ScrollView(size_hint=(1, 1))
        self.scroll_view.add_widget(self.output_label)
        self.add_widget(self.scroll_view)

        self._update_event = None

    def ask_choose_directory(self, instance):
        """触发 SAF 目录选择"""
        if platform == 'android':
            self.path_manager.choose_directory()
            # 等待用户选择后，通过回调更新标签
        else:
            self._append_output("桌面端暂不支持自定义目录，文件将保存到默认位置。\n")

    def start_download(self, instance):
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._append_output("请输入有效的book id\n")
            return
        self.download_btn.disabled = True
        threading.Thread(target=self._download_novel, args=(book_id,), daemon=True).start()

    # 其余 _append_output, _set_output 不变...

    def _download_novel(self, book_id):
        try:
            info = get_book_info(book_id)
            title = info['title']
            author = info['author']
            intro = info.get('docs', '').replace('\n', ' ')
            self._append_output(f"书名: {title}\n作者: {author}\n简介: {intro[:100]}...\n")

            chapters_data = get_chapter_list(book_id)
            chapters = []
            for vol in chapters_data:
                if isinstance(vol, list):
                    chapters.extend(vol)
                elif isinstance(vol, dict):
                    chapters.append(vol)
            total = len(chapters)
            self._append_output(f"共 {total} 章，开始下载...\n")

            safe_title = clean_filename(title)

            # --- 决定保存路径 ---
            custom_uri = self.path_manager.get_saved_uri()
            if custom_uri:
                # 使用自定义目录
                output_file = None  # 不使用普通文件路径
                self._append_output(f"正在写入到自定义目录...\n")
            else:
                # 默认内部存储
                output_dir = os.path.join(App.get_running_app().user_data_dir, "novels")
                os.makedirs(output_dir, exist_ok=True)
                output_file = os.path.join(output_dir, f"{safe_title}.txt")
                f = open(output_file, 'w', encoding='utf-8')

            # --- 准备文件内容（先收集到内存，再一次性写入）---
            full_content = f"{title}\n作者: {author}\n简介:\n{intro}\n\n"
            BATCH = 30
            for start in range(1, total + 1, BATCH):
                end = min(start + BATCH - 1, total)
                try:
                    batch = get_chapter_contents_batch(book_id, start, end)
                except Exception as e:
                    self._append_output(f"批量 {start}-{end} 失败: {e}\n")
                    continue

                chap_dict = {int(item['chapter']): item for item in batch if item.get('chapter')}
                for idx in range(start, end + 1):
                    info = chap_dict.get(idx)
                    orig = next((ch for ch in chapters if ch.get('index') == idx), None)
                    chap_title = orig['title'] if orig else info.get('chapter_title', f'第{idx}章')
                    percent = (idx / total) * 100
                    self._set_output(f"[{percent:.1f}%] 正在下载 {idx}/{total}")

                    if info:
                        content = clean_content(info.get('content', ''))
                        if content.lstrip().startswith(chap_title):
                            content = content.lstrip()[len(chap_title):].strip()
                        full_content += f"{chap_title}\n{content}\n\n"
                    else:
                        full_content += f"{chap_title}\n[内容缺失]\n\n"

            # 根据路径写入
            if custom_uri:
                success = self.path_manager.write_to_custom_uri(
                    custom_uri, f"{safe_title}.txt", full_content
                )
                if success:
                    self._append_output(f"\n下载完成，文件已保存到自定义目录！\n")
                else:
                    self._append_output(f"\n写入自定义目录失败，请检查权限。\n")
            else:
                # 写入普通文件
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(full_content)
                self._append_output(f"\n下载完成！\n文件: {output_file}\n")

        except Exception as e:
            self._append_output(f"\n下载失败: {str(e)}\n")
        finally:
            def enable_btn(dt):
                self.download_btn.disabled = False
            Clock.schedule_once(enable_btn, 0)

# 应用入口不变
class TomatoNovelApp(App):
    def build(self):
        try:
            LabelBase.register(name='Roboto', fn_regular='font.ttf')
        except:
            pass
        return NovelDownloader()

if __name__ == '__main__':
    TomatoNovelApp().run()