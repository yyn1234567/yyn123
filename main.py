#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import time
import re
import threading
import sys

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 新增：用于检测平台和调用安卓API ---
if sys.platform == 'android':
    try:
        from android.storage import primary_external_storage_path
        # 尝试获取安卓外部存储路径（通常是 /storage/emulated/0）
        download_dir = os.path.join(primary_external_storage_path(), 'Download', 'Novels')
    except Exception as e:
        # 如果失败，回退到旧版方法或默认路径
        download_dir = os.path.expanduser("~/Download/Novels")
else:
    # 桌面端默认路径
    download_dir = os.path.expanduser("~/Download/Novels")

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.core.text import LabelBase

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

class NovelDownloader(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=15, spacing=10, **kwargs)
        
        # --- 新增：显示当前保存路径 ---
        self.path_label = Label(
            text=f'💾 保存路径: {download_dir}', 
            size_hint_y=None, 
            height=40, 
            font_size='12sp',
            color=(0.5, 0.5, 0.5, 1)
        )
        self.add_widget(self.path_label)
        
        self.add_widget(Label(text='fq v2.0.5', size_hint_y=None, height=50, bold=True, font_size='18sp'))
        
        self.book_id_input = TextInput(hint_text='请输入book id', size_hint_y=None, height=48, multiline=False)
        self.add_widget(self.book_id_input)
        
        self.download_btn = Button(text='开始下载 (文件将保存在 Download/Novels)', size_hint_y=None, height=60)
        self.download_btn.bind(on_press=self.start_download)
        self.add_widget(self.download_btn)
        
        self.output_label = Label(text='等待输入...', size_hint_y=None, halign='left', valign='top')
        self.scroll_view = ScrollView(size_hint=(1, 1))
        self.scroll_view.add_widget(self.output_label)
        self.add_widget(self.scroll_view)
        
        self._update_event = None

    def start_download(self, instance):
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._append_output("请输入有效的book id\n")
            return
            
        self.download_btn.disabled = True
        self._append_output("正在获取书籍信息...\n")
        
        # --- 确保下载目录存在 ---
        try:
            os.makedirs(download_dir, exist_ok=True)
        except Exception as e:
            self._append_output(f"无法创建目录 {download_dir}: {e}\n")
            return
            
        threading.Thread(target=self._download_novel, args=(book_id,), daemon=True).start()

    def _append_output(self, text):
        def _update(dt):
            self.output_label.text += text
            self.output_label.texture_update()
            self.output_label.height = self.output_label.texture_size[1]
            self.scroll_view.scroll_y = 0
        Clock.schedule_once(_update, 0)

    def _set_output(self, text):
        def _update(dt):
            self.output_label.text = text
        Clock.schedule_once(_update, 0)

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
            
            # --- 修改核心：强制使用外部 Download 目录 ---
            # output_dir 已经在文件顶部定义为外部路径
            output_file = os.path.join(download_dir, f"{safe_title}.txt")

            # --- 调试：打印实际路径 ---
            self._append_output(f"尝试写入路径: {output_file}\n")

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{title}\n作者: {author}\n简介:\n{intro}\n\n")
                
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
                        # 追加模式写入
                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(f"{chap_title}\n{content}\n\n")
                    else:
                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(f"{chap_title}\n[内容缺失]\n\n")
                            
            self._append_output(f"\n下载完成！\n文件已保存至:\n{download_dir}\n")
            self._append_output(f"文件名: {safe_title}.txt\n")
            self._append_output(f"请在手机的文件管理器中找到 Download/Novels 文件夹查看。\n")

        except PermissionError:
            self._append_output(f"\n错误: 没有写入权限。请检查是否授予了存储权限。\n")
            self._append_output(f"尝试路径: {download_dir}\n")
        except Exception as e:
            self._append_output(f"\n下载失败: {str(e)}\n")
            import traceback
            self._append_output(f"Traceback: {traceback.format_exc()}\n")
        finally:
            def enable_btn(dt):
                self.download_btn.disabled = False
            Clock.schedule_once(enable_btn, 0)

class TomatoNovelApp(App):
    def build(self):
        try:
            LabelBase.register(name='Roboto', fn_regular='font.ttf')
        except:
            pass
        return NovelDownloader()

if __name__ == '__main__':
    TomatoNovelApp().run()
