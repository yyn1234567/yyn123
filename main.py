#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os, time, re, threading
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.text import LabelBase

# ----- KivyMD 组件 -----
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.toolbar import MDToolbar
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.card import MDCard
from kivymd.uix.snackbar import Snackbar

# ----------------------- 原有功能代码不变 -----------------------
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

# ------------------ 重构后的主界面 ------------------
class NovelDownloaderScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.save_dir = os.path.join(App.get_running_app().user_data_dir, "novels")
        # 文件管理器实例
        self.file_manager = None
        self._downloading = False

        # 主布局
        self.layout = MDBoxLayout(orientation='vertical', padding=dp(15), spacing=dp(12))

        # 顶部工具栏
        toolbar = MDToolbar(title="fq v2.0.6", pos_hint={'top': 1}, elevation=10)
        toolbar.md_bg_color = (0.12, 0.58, 0.95, 1)    # 蓝色主题
        self.add_widget(toolbar)

        # 内容卡片
        card = MDCard(
            size_hint=(1, None),
            height=dp(280),
            padding=dp(16),
            spacing=dp(12),
            elevation=2,
            radius=[15, 15, 15, 15]
        )

        # 输入 book ID
        self.book_id_input = MDTextField(
            hint_text="请输入 book id",
            mode="rectangle",
            size_hint=(1, None),
            height=dp(48)
        )

        # 保存路径显示与选择按钮
        path_box = MDBoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(48), spacing=dp(8))
        self.path_label = MDLabel(
            text=f"保存至: {self.save_dir}",
            theme_text_color="Hint",
            size_hint=(0.85, 1),
            shorten=True
        )
        choose_btn = MDIconButton(icon="folder", on_release=self.choose_save_dir)
        path_box.add_widget(self.path_label)
        path_box.add_widget(choose_btn)

        # 下载按钮
        self.download_btn = MDRaisedButton(
            text="开始下载",
            size_hint=(1, None),
            height=dp(48),
            md_bg_color=(0.12, 0.58, 0.95, 1),
            on_release=self.start_download
        )

        card.add_widget(self.book_id_input)
        card.add_widget(path_box)
        card.add_widget(self.download_btn)

        # 进度标签（百分比）
        self.progress_label = MDLabel(
            text="",
            halign="center",
            size_hint=(1, None),
            height=dp(30),
            theme_text_color="Primary"
        )

        # 日志输出区域（带滚动）
        self.output_label = MDLabel(
            text="",
            valign="top",
            size_hint_y=None,
            markup=True
        )
        self.output_label.bind(texture_size=self._update_output_height)
        self.scroll_view = MDScrollView(size_hint=(1, 1))
        self.scroll_view.add_widget(self.output_label)

        # 组装页面
        self.layout.add_widget(card)
        self.layout.add_widget(self.progress_label)
        self.layout.add_widget(self.scroll_view)
        self.add_widget(self.layout)

    def _update_output_height(self, instance, value):
        """让日志标签高度自适应内容"""
        self.output_label.height = self.output_label.texture_size[1]

    # ---------- 文件管理器 ----------
    def choose_save_dir(self, *args):
        """打开目录选择器"""
        if not self.file_manager:
            self.file_manager = MDFileManager(
                select_path=self.on_dir_select,
                exit_manager=self.on_manager_exit,
                preview=False,
                selector='folder'
            )
        # Android 可能需要先请求存储权限，这里简单起见假设已授权
        self.file_manager.show(self.save_dir)

    def on_dir_select(self, path):
        """用户选中目录后的回调"""
        self.save_dir = path
        self.path_label.text = f"保存至: {self.save_dir}"
        self.file_manager.close()

    def on_manager_exit(self, *args):
        """文件管理器退出"""
        self.file_manager.close()

    # ---------- 下载控制 ----------
    def start_download(self, instance):
        if self._downloading:
            return
        book_id = self.book_id_input.text.strip()
        if not book_id:
            Snackbar(text="请输入有效的 book id", snackbar_x="10dp", snackbar_y="10dp", size_hint_x=0.5).open()
            return
        self.download_btn.disabled = True
        self._downloading = True
        self.progress_label.text = "正在获取书籍信息..."
        threading.Thread(target=self._download_novel, args=(book_id,), daemon=True).start()

    def _append_output(self, text):
        """线程安全地将日志追加到界面"""
        def do_append(dt):
            self.output_label.text += text
            # 强制滚动到底部
            self.scroll_view.scroll_y = 0
        Clock.schedule_once(do_append, 0)

    def _set_progress(self, text):
        """线程安全地更新进度文字"""
        Clock.schedule_once(lambda dt: setattr(self.progress_label, 'text', text), 0)

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
            os.makedirs(self.save_dir, exist_ok=True)
            output_file = os.path.join(self.save_dir, f"{safe_title}.txt")

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
                        self._set_progress(f"[{percent:.1f}%] 正在下载 {idx}/{total}")

                        if info:
                            content = clean_content(info.get('content', ''))
                            if content.lstrip().startswith(chap_title):
                                content = content.lstrip()[len(chap_title):].strip()
                            f.write(f"{chap_title}\n{content}\n\n")
                        else:
                            f.write(f"{chap_title}\n[内容缺失]\n\n")

                self._append_output(f"\n下载完成！\n文件保存在: {output_file}\n")
        except Exception as e:
            self._append_output(f"\n下载失败: {str(e)}\n")
        finally:
            def reset_btn(dt):
                self.download_btn.disabled = False
                self._downloading = False
            Clock.schedule_once(reset_btn, 0)

# ---------- App 入口 ----------
class TomatoNovelApp(MDApp):
    def build(self):
        # 尝试注册中文字体（font.ttf 需要放在项目根目录）
        try:
            LabelBase.register(name='Roboto', fn_regular='font.ttf')
        except:
            pass

        # 请求存储权限（Android 6+ 运行时权限）
        if self._is_android():
            self.request_android_permissions()

        return NovelDownloaderScreen()

    def request_android_permissions(self):
        """简单的运行时权限请求"""
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])
        except ImportError:
            pass

    def _is_android(self):
        try:
            from android import mActivity
            return True
        except ImportError:
            return False

if __name__ == '__main__':
    TomatoNovelApp().run()