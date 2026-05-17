#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import time
import re
import threading
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- KivyMD 导入 (兼容 1.2.0) ---
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.progressbar import MDProgressBar
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.utils import platform
from kivy.lang import Builder
# --- 修复点 1: 2026年安全导入 android.permissions ---
try:
    from android.permissions import Permission, request_permissions
except ImportError:
    Permission = None
    request_permissions = None

# --- 全局配置 ---
BASE_URL = "https://oiapi.net/api/FqRead"
API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"
MAX_RETRIES = 3
RETRY_DELAY = 2
TIMEOUT = 30

# --- 工具函数 ---
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

def get_download_dir():
    """获取系统Download/novels目录，兼容不同Android版本"""
    try:
        if platform == 'android':
            # 尝试使用pyjnius访问Environment类
            from jnius import autoclass
            Environment = autoclass('android.os.Environment')
            
            # --- 修复点 2: 检查权限是否存在 ---
            if Permission is not None:
                # 检查存储状态
                if Environment.getExternalStorageState() == Environment.MEDIA_MOUNTED:
                    external_storage = Environment.getExternalStorageDirectory().getAbsolutePath()
                    download_dir = os.path.join(external_storage, 'Download', 'novels')
                    
                    # 确保目录可写
                    try:
                        os.makedirs(download_dir, exist_ok=True)
                        test_file = os.path.join(download_dir, '.test')
                        with open(test_file, 'w') as f:
                            f.write('test')
                        os.remove(test_file)
                        return download_dir
                    except:
                        pass
            
            # 如果无法访问外部存储，返回应用私有目录下的novels文件夹
            return os.path.join(MDApp.get_running_app().user_data_dir, 'novels')
        else:
            # 桌面端使用用户主目录的Downloads文件夹
            downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            return os.path.join(downloads, 'novels')
    except Exception as e:
        # 出错时回退到应用私有目录
        try:
            return os.path.join(MDApp.get_running_app().user_data_dir, 'novels')
        except:
            return os.path.join(os.getcwd(), 'novels')

# --- KV UI 字符串 ---
KV = '''
MDScreen:
    name: "main"
    md_bg_color: app.theme_cls.bg_dark if app.theme_cls.theme_style == "Dark" else app.theme_cls.bg_light

    MDBoxLayout:
        orientation: "vertical"
        padding: "20dp"
        spacing: "15dp"

        MDLabel:
            text: "fq v1.2.2"
            halign: "center"
            font_style: "DisplayLarge" # KivyMD 1.2.0 兼容写法
            theme_text_color: "Primary"
            size_hint_y: None
            height: "60dp"

        MDLabel:
            text: "请输入book id"
            halign: "center"
            theme_text_color: "Hint"
            size_hint_y: None
            height: "20dp"

        MDTextField:
            id: book_id_input
            hint_text: "book id"
            helper_text: "获取方法另见视频"
            helper_text_mode: "on_focus"
            mode: "rectangle"
            on_text_validate: app.root.start_download()

        MDRaisedButton:
            text: "开始下载"
            on_press: app.root.start_download()
            pos_hint: {"center_x": 0.5}
            size_hint_x: 0.8

        MDLabel:
            text: "状态"
            halign: "left"
            font_style: "LabelLarge"
            padding: [0, "10dp", 0, 0]

        MDSeparator:

        ScrollView:
            id: scroll_view

            MDBoxLayout:
                id: output_box
                orientation: "vertical"
                adaptive_height: True
                padding: "10dp"
                spacing: "5dp"

        MDProgressBar:
            id: progress_bar
            opacity: 0
            size_hint_y: None
            height: "10dp"
'''

class NovelDownloader(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.output_box = self.ids.output_box
        self.progress_bar = self.ids.progress_bar
        self.book_id_input = self.ids.book_id_input
        self.progress_bar.determinate = False # 兼容 1.2.0
        
        # 修复：ScrollView 自适应高度监听 (针对 Kivy 2.3.0)
        Clock.schedule_once(self._setup_scroll_view)

    def _setup_scroll_view(self, dt):
        # 确保 ScrollView 内容高度变化时能正确滚动
        self.ids.scroll_view.bind(
            height=lambda *x: self.ids.output_box.setter('height')(self.ids.output_box, self.ids.output_box.minimum_height)
        )

    def _add_log(self, text, color="primary"):
        label = MDLabel(
            text=text,
            theme_text_color="Custom",
            text_color=getattr(self.theme_cls, f"{color}Color", (1, 1, 1, 1)),
            size_hint_y=None,
            height="30dp",
            markup=True
        )
        self.output_box.add_widget(label)
        
        # 修复：使用更稳健的滚动到底部方法
        Clock.schedule_once(lambda dt: setattr(self.ids.scroll_view, 'scroll_y', 0), 0.1)

    def _clear_logs(self):
        self.output_box.clear_widgets()

    def start_download(self, *args):
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._show_error("请输入有效的book id")
            return
        self._clear_logs()
        self._add_log("正在获取书籍信息...", "secondary")
        self.progress_bar.opacity = 1
        btn = self.children[1]
        btn.disabled = True
        threading.Thread(target=self._download_novel, args=(book_id, btn), daemon=True).start()

    def _download_novel(self, book_id, button):
        try:
            info = get_book_info(book_id)
            title = info['title']
            author = info['author']
            intro = info.get('docs', '').replace('\n', ' ')
            Clock.schedule_once(lambda dt: self._add_log(f"书名: {title}", "primary"))
            Clock.schedule_once(lambda dt: self._add_log(f"作者: {author}", "primary"))
            Clock.schedule_once(lambda dt: self._add_log(f"简介: {intro[:50]}...", "hint"))
            
            chapters_data = get_chapter_list(book_id)
            chapters = []
            for vol in chapters_data:
                if isinstance(vol, list):
                    chapters.extend(vol)
                elif isinstance(vol, dict):
                    chapters.append(vol)
            total = len(chapters)
            Clock.schedule_once(lambda dt: self._add_log(f"共 {total} 章，开始下载...", "secondary"))
            
            safe_title = clean_filename(title)
            output_dir = get_download_dir() # 原错误：get_download _dir()
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{safe_title}.txt")
            Clock.schedule_once(lambda dt: self._add_log(f"保存路径: {output_dir}", "success"))
            
            BATCH = 30
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{title}\n作者: {author}\n简介:\n{intro}\n\n")
            
            with open(output_file, 'a', encoding='utf-8') as f:
                for start in range(1, total + 1, BATCH):
                    end = min(start + BATCH - 1, total)
                    try:
                        batch = get_chapter_contents_batch(book_id, start, end)
                    except Exception as e:
                        Clock.schedule_once(lambda dt, e=e: self._add_log(f"批量 {start}-{end} 失败: {e}", "error"))
                        continue
                    
                    chap_dict = {int(item['chapter']): item for item in batch if item.get('chapter')}
                    for idx in range(start, end + 1):
                        info = chap_dict.get(idx)
                        orig = next((ch for ch in chapters if ch.get('index') == idx), None)
                        chap_title = orig['title'] if orig else info.get('chapter_title', f'第{idx}章')
                        
                        if info:
                            content = clean_content(info.get('content', ''))
                            # --- 确认点：防重复标题逻辑在此 ---
                            if content.lstrip().startswith(chap_title):
                                content = content.lstrip()[len(chap_title):].strip()
                            f.write(f"{chap_title}\n{content}\n\n")
                        else:
                            f.write(f"{chap_title}\n[内容缺失]\n\n")
                        
                        percent = (idx / total) * 100
                        Clock.schedule_once(lambda dt, p=percent: self._add_log(f"[{p:.1f}%] 下载完成: {idx}/{total}", "primary"))
            
            Clock.schedule_once(lambda dt: self._add_log(f"下载成功！文件已保存。", "success"))
            
        except Exception as e:
            Clock.schedule_once(lambda dt: self._show_error(f"下载失败: {str(e)}"))
        finally:
            Clock.schedule_once(lambda dt: setattr(self.progress_bar, 'opacity', 0))
            Clock.schedule_once(lambda dt: setattr(button, 'disabled', False))

    def _show_error(self, message):
        # 优化 Snackbar 兼容性
        try:
            snackbar = Snackbar(
                text=message,
                duration=3,
                md_bg_color=self.theme_cls.primary_dark
            )
            snackbar.open()
        except:
            # 极简回退方案
            snackbar = Snackbar(text=message)
            snackbar.open()

class TomatoNovelApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "BlueGray"
        self.theme_cls.material_style = "M2" # 锁定 M2
        
        # --- 修复点 3: 2026年安全权限请求 ---
        if platform == 'android':
            if request_permissions is not None:
                permissions = [Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE]
                # Android 13+ 需要 READ_MEDIA_IMAGES
                try:
                    # 检查是否存在该属性，防止旧版Android报错
                    if hasattr(Permission, 'READ_MEDIA_IMAGES'):
                        permissions.append(Permission.READ_MEDIA_IMAGES)
                except:
                    pass
                try:
                    request_permissions(permissions)
                except Exception as e:
                    print(f"请求权限时发生错误: {e}")
            else:
                print("android.permissions 模块不可用，请检查打包环境")
                
        return Builder.load_string(KV)

if __name__ == '__main__':
    TomatoNovelApp().run()
