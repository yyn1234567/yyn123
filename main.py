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

# --- KivyMD 导入 ---
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

# --- 原有业务逻辑保持不变 ---
BASE_URL = "https://oiapi.net/api/FqRead"
API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"
MAX_RETRIES = 3
RETRY_DELAY = 2
TIMEOUT = 30

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
            from jnius import autoclass
            Environment = autoclass('android.os.Environment')
            if Environment.getExternalStorageState() == Environment.MEDIA_MOUNTED:
                external_storage = Environment.getExternalStorageDirectory().getAbsolutePath()
                download_dir = os.path.join(external_storage, 'Download', 'novels')
                try:
                    os.makedirs(download_dir, exist_ok=True)
                    test_file = os.path.join(download_dir, '.test')
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    return download_dir
                except:
                    pass
            return os.path.join(MDApp.get_running_app().user_data_dir, 'novels')
        else:
            downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            return os.path.join(downloads, 'novels')
    except Exception as e:
        try:
            return os.path.join(MDApp.get_running_app().user_data_dir, 'novels')
        except:
            return os.path.join(os.getcwd(), 'novels')

# --- KivyMD UI 代码 ---
KV = '''
MDScreen:
    name: "main"
    md_bg_color: self.theme_cls.backgroundColor

    MDBoxLayout:
        orientation: "vertical"
        padding: "20dp"
        spacing: "15dp"

        MDLabel:
            text: "fq v1.2.2"
            halign: "center"
            font_style: "DisplayLarge"
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
            MDBoxLayout:
                id: output_box
                orientation: "vertical"
                adaptive_height: True
                padding: "10dp"
                spacing: "5dp"

        MDProgressBar:
            id: progress_bar
            determinate: False
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

    def _add_log(self, text, color="primary"):
        label = MDLabel(
            text=text,
            theme_text_color="Custom",
            text_color=getattr(self.theme_cls, f"{color}Color"),
            size_hint_y=None,
            height="30dp",
            markup=True
        )
        self.output_box.add_widget(label)
        # 自动滚动到底部
        Clock.schedule_once(lambda dt: setattr(self.children[0], 'scroll_y', 0), 0.1)

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
        
        # 禁用按钮防止重复点击
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
            output_dir = get_download_dir()
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{safe_title}.txt")
            
            Clock.schedule_once(lambda dt: self._add_log(f"保存路径: {output_dir}", "success"))

            BATCH = 30
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{title}\n作者: {author}\n简介:\n{intro}\n\n")
                
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
                            if content.lstrip().startswith(chap_title):
                                content = content.lstrip()[len(chap_title):].strip()
                            f.write(f"{chap_title}\n{content}\n\n")
                        else:
                            f.write(f"{chap_title}\n[内容缺失]\n\n")
                            
                        # 更新进度
                        percent = (idx / total) * 100
                        Clock.schedule_once(lambda dt, p=percent: self._add_log(f"[{p:.1f}%] 下载完成: {idx}/{total}", "primary"))

            Clock.schedule_once(lambda dt: self._add_log(f"下载成功！文件已保存。", "success"))
            
        except Exception as e:
            Clock.schedule_once(lambda dt: self._show_error(f"下载失败: {str(e)}"))
        finally:
            Clock.schedule_once(lambda dt: setattr(self.progress_bar, 'opacity', 0))
            Clock.schedule_once(lambda dt: setattr(button, 'disabled', False))

    def _show_error(self, message):
        snackbar = Snackbar(
            text=message,
            duration=3,
            snackbar_x="10dp",
            snackbar_y="10dp",
        )
        snackbar.open()

class TomatoNovelApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"  # 可选 "Light"
        self.theme_cls.primary_palette = "BlueGray" # 更柔和的配色
        
        # Android 权限请求
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                permissions_needed = [
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE
                ]
                try:
                    permissions_needed.extend([
                        Permission.READ_MEDIA_IMAGES,
                        Permission.READ_MEDIA_VIDEO,
                        Permission.READ_MEDIA_AUDIO
                    ])
                except:
                    pass
                request_permissions(permissions_needed)
            except Exception as e:
                print(f"权限请求失败: {e}")
        
        return Builder.load_string(KV)

if __name__ == '__main__':
    TomatoNovelApp().run()
