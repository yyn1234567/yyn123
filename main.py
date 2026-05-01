# main.py
import os
import re
import json
import threading
import time
import urllib.request
import urllib.error

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.clock import mainthread
from kivy.core.clipboard import Clipboard
from kivy.utils import platform

# ---------- 原始下载逻辑（稍作调整） ----------
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
            with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise Exception(f"API请求失败: {str(e)}")
            time.sleep(RETRY_DELAY)

def get_book_info(book_id):
    result = api_request(f"method=ids&id={book_id}")
    if result.get('code') == 1:
        return result['data']
    raise Exception(result.get('message', '获取书籍信息失败'))

def get_chapter_list(book_id):
    result = api_request(f"method=chapters&id={book_id}")
    if result.get('code') == 1:
        return result['data']
    raise Exception(result.get('message', '获取章节列表失败'))

def get_chapter_contents_batch(book_id, start, end):
    result = api_request(f"method=chapter&id={book_id}&chapter={start}-{end}")
    if result.get('code') == 1:
        # 转换为字典，key为章节号
        chapter_dict = {}
        for item in result['data']:
            if 'chapter' in item:
                chapter_dict[int(item['chapter'])] = item
        return chapter_dict
    raise Exception(result.get('message', '批量获取失败'))

def clean_content(content):
    content = content.replace('</p><p>', '\n')
    content = content.replace('<p>', '')
    content = content.replace('</p>', '\n')
    content = re.sub(r'<[^>]*>', '', content)
    return re.sub(r'\n+', '\n', content).strip()

# ---------- Kivy GUI ----------
class DownloaderLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=20, spacing=10, **kwargs)

        self.add_widget(Label(text='番茄小说下载器', font_size='20sp', size_hint_y=0.1))

        self.input = TextInput(hint_text='请输入 book_id', multiline=False, size_hint_y=0.1)
        self.add_widget(self.input)

        self.btn = Button(text='开始下载', size_hint_y=0.15)
        self.btn.bind(on_press=self.start_download)
        self.add_widget(self.btn)

        self.status = Label(text='等待输入...', size_hint_y=0.3, halign='left', valign='top')
        self.status.bind(size=self.status.setter('text_size'))
        self.add_widget(self.status)

        self.progress = ProgressBar(max=100, size_hint_y=0.1)
        self.add_widget(self.progress)

    def start_download(self, instance):
        book_id = self.input.text.strip()
        if not book_id:
            self.status.text = '书籍ID不能为空'
            return
        self.btn.disabled = True
        self.status.text = '正在获取书籍信息...'
        self.progress.value = 0
        threading.Thread(target=self.download_thread, args=(book_id,), daemon=True).start()

    @mainthread
    def update_status(self, text):
        self.status.text = text

    @mainthread
    def update_progress(self, value):
        self.progress.value = value

    @mainthread
    def download_finished(self, file_path, message):
        self.btn.disabled = False
        self.status.text = message

    def download_thread(self, book_id):
        try:
            # 获取输出目录（安卓上写到应用外部存储文件夹，用户易找）
            if platform == 'android':
                from android.storage import primary_external_storage_path
                base_dir = primary_external_storage_path()
                output_dir = os.path.join(base_dir, 'Novels')
            else:
                output_dir = os.path.join(os.getcwd(), 'novels')
            os.makedirs(output_dir, exist_ok=True)

            self.update_status('获取书籍信息...')
            book_info = get_book_info(book_id)
            book_title = book_info['title']
            author = book_info['author']
            intro = book_info.get('docs', '').replace('\n', ' ')

            chapters_data = get_chapter_list(book_id)
            # 展平卷结构
            chapters = []
            for vol in chapters_data:
                if isinstance(vol, list):
                    chapters.extend(vol)
                elif isinstance(vol, dict):
                    chapters.append(vol)
            total = len(chapters)

            safe_title = clean_filename(book_title)
            output_file = os.path.join(output_dir, f"{safe_title}.txt")

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{book_title}\n作者: {author}\n简介:\n{intro}\n\n")
                BATCH_SIZE = 30
                for start in range(1, total + 1, BATCH_SIZE):
                    end = min(start + BATCH_SIZE - 1, total)
                    try:
                        batch = get_chapter_contents_batch(book_id, start, end)
                    except Exception as e:
                        self.update_status(f'批量下载失败: {e}')
                        # 标记缺失章节
                        for i in range(start, end + 1):
                            perc = i / total * 100
                            self.update_progress(perc)
                            f.write(f"第{i}章\n[下载失败]\n\n")
                        continue

                    for i in range(start, end + 1):
                        perc = i / total * 100
                        self.update_progress(perc)
                        chapter_info = batch.get(i)
                        # 获取章节标题
                        original_ch = next((ch for ch in chapters if ch.get('index') == i), None)
                        title = original_ch['title'] if original_ch else (chapter_info.get('chapter_title') if chapter_info else f'第{i}章')

                        if chapter_info:
                            content = clean_content(chapter_info.get('content', ''))
                            if content.lstrip().startswith(title):
                                content = content.lstrip()[len(title):].strip()
                            f.write(f"{title}\n{content}\n\n")
                        else:
                            f.write(f"{title}\n[内容缺失]\n\n")

            self.download_finished(output_file, f'下载完成！\n文件保存至:\n{output_file}')
        except Exception as e:
            self.download_finished('', f'下载失败: {str(e)}')

class TomatoApp(App):
    def build(self):
        return DownloaderLayout()

if __name__ == '__main__':
    TomatoApp().run()