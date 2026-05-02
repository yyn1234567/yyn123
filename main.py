#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
番茄小说下载器 - Kivy 安卓版
"""

import json
import urllib.request
import urllib.error
import os
import time
import re
import threading

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock

# ========== 原 API 配置 ==========
BASE_URL = "https://oiapi.net/api/FqRead"
API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"
MAX_RETRIES = 3
RETRY_DELAY = 2
TIMEOUT = 30

# ========== 工具函数（同原脚本）==========
def clean_filename(name):
    return re.sub(r"[\/\\\:\*\?\"\<\>\|]", "_", name)

def api_request(url_params):
    url = f"{BASE_URL}?{url_params}&key={API_KEY}"
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
                data = response.read().decode('utf-8')
                return json.loads(data)
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(f"API请求失败: {str(e)}")
        except json.JSONDecodeError:
            raise Exception("API返回的数据格式错误")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(f"请求失败: {str(e)}")

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

def get_chapter_contents_batch(book_id, start_index, end_index):
    chapter_range = f"{start_index}-{end_index}"
    result = api_request(f"method=chapter&id={book_id}&chapter={chapter_range}")
    if result.get('code') == 1:
        return result['data']
    raise Exception(f"批量获取章节内容失败: {result.get('message', '未知错误')}")

def clean_content(content):
    content = content.replace('</p><p>', '\n')
    content = content.replace('<p>', '')
    content = content.replace('</p>', '\n')
    content = re.sub(re.compile('<.*?>'), '', content)
    content = re.sub(r'\n+', '\n', content).strip()
    return content

# ========== Kivy 界面 ==========
class NovelDownloader(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)

        # 标题
        self.add_widget(Label(
            text='fq v2.0.3',
            size_hint=(1, 0.1),
            bold=True,
            font_size='20sp'
        ))

        # 输入框
        self.book_id_input = TextInput(
            hint_text='请输入book id',
            size_hint=(1, 0.1),
            multiline=False
        )
        self.add_widget(self.book_id_input)

        # 下载按钮
        self.download_btn = Button(
            text='开始下载',
            size_hint=(1, 0.1)
        )
        self.download_btn.bind(on_press=self.start_download)
        self.add_widget(self.download_btn)

        # 输出区域（滚动）
        self.output_label = Label(
            text='',
            size_hint_y=None,
            halign='left',
            valign='top',
            text_size=(None, None)  # 宽度会在绑定后设置
        )
        self.output_label.bind(texture_size=self._update_label_height)
        self.scroll_view = ScrollView(size_hint=(1, 0.7))
        self.scroll_view.add_widget(self.output_label)
        self.add_widget(self.scroll_view)

        # 用于线程安全更新输出
        self._update_event = None

    def _update_label_height(self, instance, size):
        """根据内容自动调整 Label 高度，以便滚动"""
        instance.size_hint_y = None
        instance.height = size[1]
        # 设置 text_size 宽度为滚动视图宽度
        instance.text_size = (self.scroll_view.width, None)

    def start_download(self, instance):
        """点击按钮后启动下载线程"""
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._append_output("请输入有效的book id\n")
            return

        self.download_btn.disabled = True
        self._append_output(f"正在获取书籍信息...\n")
        thread = threading.Thread(target=self._download_novel, args=(book_id,), daemon=True)
        thread.start()

    def _append_output(self, text):
        """线程安全地追加输出文本"""
        def _update(dt):
            self.output_label.text += text
            # 自动滚动到底部
            if self.scroll_view.scroll_y != 0:
                self.scroll_view.scroll_y = 0
        Clock.schedule_once(_update, 0)

    def _set_output(self, text):
        """线程安全地设置输出文本（覆盖）"""
        def _update(dt):
            self.output_label.text = text
        Clock.schedule_once(_update, 0)

    def _download_novel(self, book_id):
        """下载逻辑（在子线程中运行）"""
        try:
            # 获取书籍信息
            book_info = get_book_info(book_id)
            book_title = book_info['title']
            author = book_info['author']
            intro = book_info.get('docs', '').replace('\n', ' ')

            self._append_output(f"书名: {book_title}\n作者: {author}\n")
            self._append_output(f"简介: {intro[:100]}{'...' if len(intro)>100 else ''}\n\n")

            # 获取章节列表
            chapters_data = get_chapter_list(book_id)
            chapters = []
            for volume in chapters_data:
                if isinstance(volume, list):
                    chapters.extend(volume)
                elif isinstance(volume, dict):
                    chapters.append(volume)

            total_chapters = len(chapters)
            self._append_output(f"共 {total_chapters} 章，开始下载...\n")

            # 准备输出文件（保存在应用私有目录）
            safe_title = clean_filename(book_title)
            # Android 上建议使用 App 的 user_data_dir
            output_dir = os.path.join(App.get_running_app().user_data_dir, "novels")
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{safe_title}.txt")

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{book_title}\n作者: {author}\n简介:\n{intro}\n\n")

                BATCH_SIZE = 30
                for start in range(1, total_chapters + 1, BATCH_SIZE):
                    end = min(start + BATCH_SIZE - 1, total_chapters)
                    try:
                        batch_data = get_chapter_contents_batch(book_id, start, end)
                    except Exception as e:
                        self._append_output(f"批量下载 {start}-{end} 失败: {e}\n")
                        for chap_idx in range(start, end + 1):
                            f.write(f"第{chap_idx}章\n\n[下载失败]\n\n")
                        continue

                    # 转为字典
                    chapter_dict = {}
                    for item in batch_data:
                        chap_num = item.get('chapter')
                        if chap_num is not None:
                            chapter_dict[int(chap_num)] = item

                    for chap_idx in range(start, end + 1):
                        chapter_info = chapter_dict.get(chap_idx)
                        original_chapter = next((ch for ch in chapters if ch.get('index') == chap_idx), None)
                        title = original_chapter['title'] if original_chapter else chapter_info.get('chapter_title', f'第{chap_idx}章')

                        # 更新进度
                        percent = (chap_idx / total_chapters) * 100
                        self._set_output(
                            self.output_label.text.strip().rsplit('\n', 1)[0] +  # 移除上一次的进度行
                            f"\n[{percent:.1f}%] 正在下载 {chap_idx}/{total_chapters}"
                        )

                        if chapter_info:
                            content = clean_content(chapter_info.get('content', ''))
                            if content.lstrip().startswith(title):
                                content = content.lstrip()[len(title):].strip()
                            f.write(f"{title}\n{content}\n\n")
                        else:
                            f.write(f"{title}\n[内容缺失]\n\n")

                # 完成
                self._append_output(f"\n下载完成！\n文件已保存至:\n{output_file}\n")

        except Exception as e:
            self._append_output(f"\n下载失败: {str(e)}\n")
        finally:
            # 恢复按钮
            def enable_btn(dt):
                self.download_btn.disabled = False
            Clock.schedule_once(enable_btn, 0)


class TomatoNovelApp(App):
    def build(self):
        return NovelDownloader()

if __name__ == '__main__':
    TomatoNovelApp().run()