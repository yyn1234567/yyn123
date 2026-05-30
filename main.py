#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s丶ky书包
"""

import json
import urllib.request
import urllib.error
import os
import re
import time
import threading

# ── Kivy 导入 ──────────────────────────────────────────
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.properties import StringProperty, NumericProperty, BooleanProperty

# ── 跨平台存储路径 ─────────────────────────────────────
try:
    from android.storage import primary_external_storage_path
    _ANDROID = True
except ImportError:
    _ANDROID = False

try:
    from android.permissions import request_permissions, Permission, check_permission
    _ANDROID_PERM = True
except ImportError:
    _ANDROID_PERM = False


# ═══════════════════════════════════════════════════════════
#  API 配置（与原脚本一致）
# ═══════════════════════════════════════════════════════════
BASE_URL = "https://oiapi.net/api/FqRead"
API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"
MAX_RETRIES = 3
RETRY_DELAY = 2
TIMEOUT = 30
BATCH_SIZE = 30


# ═══════════════════════════════════════════════════════════
#  工具函数（与原脚本一致）
# ═══════════════════════════════════════════════════════════
def clean_filename(name):
    """清理文件名中的非法字符"""
    return re.sub(r'[\/\\\:\*\?\"\<\>\|]', '_', name)


def api_request(url_params):
    """发送API请求，带重试机制"""
    url = f"{BASE_URL}?{url_params}&key={API_KEY}"
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                data = response.read().decode('utf-8')
                return json.loads(data)
        except (urllib.error.URLError, json.JSONDecodeError, Exception) as e:
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


def get_chapter_contents_batch(book_id, start_index, end_index):
    chapter_range = f"{start_index}-{end_index}"
    result = api_request(f"method=chapter&id={book_id}&chapter={chapter_range}")
    if result.get('code') == 1:
        return result['data']
    raise Exception(f"批量获取章节内容失败: {result.get('message', '未知错误')}")


def clean_content(content):
    """清理章节内容，去掉HTML标签"""
    content = content.replace('</p><p>', '\n')
    content = content.replace('<p>', '')
    content = content.replace('</p>', '\n')
    content = re.sub(r'<.*?>', '', content)
    content = re.sub(r'\n+', '\n', content).strip()
    return content


def get_save_dir():
    """
    获取小说保存目录
    Android: 优先外部存储/Novels，否则应用私有目录
    桌面: ./novels
    """
    if _ANDROID:
        try:
            ext = primary_external_storage_path()
            d = os.path.join(ext, 'Novels')
            os.makedirs(d, exist_ok=True)
            return d
        except Exception:
            pass
    d = os.path.join(os.getcwd(), 'novels')
    os.makedirs(d, exist_ok=True)
    return d


# ═══════════════════════════════════════════════════════════
#  Kivy UI 组件
# ═══════════════════════════════════════════════════════════

class LogScrollView(ScrollView):
    """可滚动的日志区域"""
    pass


class MainLayout(BoxLayout):
    """主界面布局"""
    pass


class NovelDownloaderApp(App):
    """s丶ky书包"""

    # ── 绑定到UI的属性 ──
    status_text = StringProperty("就绪")
    chapter_progress = StringProperty("")
    progress_value = NumericProperty(0)        # 0 ~ 100
    progress_max = NumericProperty(100)
    log_text = StringProperty("")
    is_downloading = BooleanProperty(False)
    book_title_text = StringProperty("")
    book_author_text = StringProperty("")
    save_path_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._download_thread = None
        self._cancel_flag = False

    def build(self):
        """构建界面"""
        # 设置窗口颜色
        Window.clearcolor = (0.12, 0.12, 0.14, 1)  # 深色背景

        self.root = MainLayout(orientation='vertical', padding=12, spacing=8)

        # ── 顶部：标题 ──
        title_bar = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=48
        )
        title_label = Label(
            text="[b]s丶ky书包[/b]  v2.1.2",
            markup=True,
            font_size=20,
            color=(1, 0.85, 0.4, 1),  # 金色
            halign='left',
            valign='middle'
        )
        title_label.bind(size=title_label.setter('text_size'))
        title_bar.add_widget(title_label)
        self.root.add_widget(title_bar)

        # ── 书籍信息卡片 ──
        info_card = GridLayout(
            cols=1,
            size_hint_y=None,
            height=100,
            spacing=4,
            padding=[8, 6]
        )
        self._info_title = Label(
            text="书名: --",
            font_size=15,
            color=(0.9, 0.9, 0.9, 1),
            halign='left',
            valign='top',
            text_size=(Window.width - 40, None)
        )
        self._info_author = Label(
            text="作者: --",
            font_size=13,
            color=(0.7, 0.7, 0.7, 1),
            halign='left',
            valign='top',
            text_size=(Window.width - 40, None)
        )
        self._info_save = Label(
            text="保存位置: --",
            font_size=11,
            color=(0.5, 0.8, 0.5, 1),
            halign='left',
            valign='top',
            text_size=(Window.width - 40, None)
        )
        info_card.add_widget(self._info_title)
        info_card.add_widget(self._info_author)
        info_card.add_widget(self._info_save)
        self.root.add_widget(info_card)

        # ── 输入区域 ──
        input_box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=50,
            spacing=8
        )
        self._book_id_input = TextInput(
            hint_text="请输入book id",
            multiline=False,
            font_size=16,
            background_color=(0.2, 0.2, 0.22, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 0.85, 0.4, 1),
            padding=[10, 14]
        )
        self._download_btn = Button(
            text="开始下载",
            font_size=16,
            size_hint_x=0.35,
            background_color=(0.25, 0.6, 0.3, 1),
            color=(1, 1, 1, 1)
        )
        self._download_btn.bind(on_press=self.on_download_pressed)
        input_box.add_widget(self._book_id_input)
        input_box.add_widget(self._download_btn)
        self.root.add_widget(input_box)

        # ── 进度区域 ──
        progress_box = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=55,
            spacing=2
        )
        self._progress_bar = ProgressBar(
            max=100,
            value=0,
            size_hint_y=None,
            height=18
        )
        self._progress_label = Label(
            text="等待下载...",
            font_size=12,
            color=(0.7, 0.7, 0.7, 1),
            halign='center',
            valign='middle'
        )
        self._progress_label.bind(size=self._progress_label.setter('text_size'))
        progress_box.add_widget(self._progress_bar)
        progress_box.add_widget(self._progress_label)
        self.root.add_widget(progress_box)

        # ── 日志区域（可滚动）──
        log_label = Label(
            text="运行日志",
            font_size=12,
            color=(0.5, 0.5, 0.6, 1),
            size_hint_y=None,
            height=20,
            halign='left',
            valign='middle'
        )
        log_label.bind(size=log_label.setter('text_size'))
        self.root.add_widget(log_label)

        self._log_scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False
        )
        self._log_content = Label(
            text="",
            font_size=11,
            color=(0.8, 0.8, 0.8, 1),
            halign='left',
            valign='top',
            markup=True,
            padding=[6, 4]
        )
        self._log_content.bind(
            size=lambda s, v: setattr(s, 'text_size', (v[0], None))
        )
        self._log_scroll.add_widget(self._log_content)
        self.root.add_widget(self._log_scroll)

        # ── 底部按钮 ──
        bottom_box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=44,
            spacing=8
        )
        self._cancel_btn = Button(
            text="取消下载",
            font_size=14,
            background_color=(0.7, 0.25, 0.2, 1),
            color=(1, 1, 1, 1),
            disabled=True
        )
        self._cancel_btn.bind(on_press=self.on_cancel_pressed)

        self._open_dir_btn = Button(
            text="打开下载目录",
            font_size=14,
            background_color=(0.2, 0.35, 0.6, 1),
            color=(1, 1, 1, 1)
        )
        self._open_dir_btn.bind(on_press=self.on_open_dir_pressed)

        bottom_box.add_widget(self._cancel_btn)
        bottom_box.add_widget(self._open_dir_btn)
        self.root.add_widget(bottom_box)

        return self.root

    def on_start(self):
        """App启动后的初始化"""
        if _ANDROID and _ANDROID_PERM:
            # 请求存储权限
            request_permissions([
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
            ])
        # 显示保存路径
        save_dir = get_save_dir()
        self._info_save.text = f"保存位置: {save_dir}"

    # ── 事件处理 ──

    def on_download_pressed(self, instance):
        """按下「开始下载」按钮"""
        if self.is_downloading:
            return

        book_id = self._book_id_input.text.strip()
        if not book_id:
            self._show_popup("提示", "请输入 book id")
            return

        if not book_id.isdigit():
            self._show_popup("提示", "book id必须是数字")
            return

        # 重置状态
        self._cancel_flag = False
        self.is_downloading = True
        self._download_btn.disabled = True
        self._cancel_btn.disabled = False
        self._log_content.text = ""
        self._progress_bar.value = 0
        self._progress_label.text = "正在获取书籍信息..."
        self._info_title.text = "书名: --"
        self._info_author.text = "作者: --"

        # 启动后台下载线程
        self._download_thread = threading.Thread(
            target=self._do_download,
            args=(book_id,),
            daemon=True
        )
        self._download_thread.start()

    def on_cancel_pressed(self, instance):
        """按下「取消下载」按钮"""
        self._cancel_flag = True
        self._append_log("\n[color=#FF6644]正在取消...[/color]")

    def on_open_dir_pressed(self, instance):
        """按下「打开下载目录」按钮"""
        save_dir = get_save_dir()
        if _ANDROID:
            try:
                from android.content import Intent
                from android.os import Environment
                from jnius import cast
                import android.activity
                # 简单做法：显示路径
                self._show_popup(
                    "下载目录",
                    f"文件保存在:\n{save_dir}\n\n请使用文件管理器查看。"
                )
            except Exception:
                self._show_popup("下载目录", f"路径: {save_dir}")
        else:
            # 桌面端：尝试用系统文件管理器打开
            import platform
            import subprocess
            try:
                system = platform.system()
                if system == 'Windows':
                    os.startfile(save_dir)
                elif system == 'Darwin':
                    subprocess.run(['open', save_dir])
                else:
                    subprocess.run(['xdg-open', save_dir])
            except Exception:
                self._show_popup("下载目录", f"路径: {save_dir}")

    # ── 后台下载逻辑 ──

    def _do_download(self, book_id):
        """在后台线程中执行下载"""
        try:
            book_id_int = int(book_id)

            # 1. 获取书籍信息
            self._update_ui_log("获取书籍信息...")
            book_info = get_book_info(book_id_int)
            book_title = book_info['title']
            author = book_info.get('author', '未知')
            intro = book_info.get('docs', '').replace('\n', ' ')

            self._update_ui_info(book_title, author)
            self._update_ui_log(f"  书名: [b]{book_title}[/b]")
            self._update_ui_log(f"  作者: {author}")
            self._update_ui_log(f"  简介: {intro[:80]}{'...' if len(intro) > 80 else ''}")

            # 2. 获取章节列表
            self._update_ui_log("获取章节列表...")
            self._update_ui_progress_label("正在获取章节列表...")
            chapters_data = get_chapter_list(book_id_int)

            # 展平章节列表
            chapters = []
            for volume in chapters_data:
                if isinstance(volume, list):
                    chapters.extend(volume)
                elif isinstance(volume, dict):
                    chapters.append(volume)

            total_chapters = len(chapters)
            self._update_ui_log(f"  共 [b]{total_chapters}[/b] 章")

            # 3. 准备保存
            safe_title = clean_filename(book_title)
            save_dir = get_save_dir()
            output_file = os.path.join(save_dir, f"{safe_title}.txt")

            self._update_ui_progress_max(total_chapters)

            # 4. 写入文件头
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{book_title}\n")
                f.write(f"作者: {author}\n")
                f.write(f"简介:\n{intro}\n\n")

                # 5. 批量下载章节
                for start in range(1, total_chapters + 1, BATCH_SIZE):
                    if self._cancel_flag:
                        self._update_ui_log("[color=#FF6644]用户取消下载[/color]")
                        break

                    end = min(start + BATCH_SIZE - 1, total_chapters)

                    try:
                        batch_data = get_chapter_contents_batch(book_id_int, start, end)
                    except Exception as e:
                        self._update_ui_log(f"[color=#FF6644]批量下载失败 ({start}-{end}): {e}[/color]")
                        # 逐章重试
                        for chap_idx in range(start, end + 1):
                            if self._cancel_flag:
                                break
                            self._update_ui_progress(chap_idx, total_chapters)
                            f.write(f"第{chap_idx}章\n\n[下载失败]\n\n")
                        continue

                    # 将返回列表转为字典
                    chapter_dict = {}
                    for item in batch_data:
                        cn = item.get('chapter')
                        if cn is not None:
                            chapter_dict[int(cn)] = item

                    # 按顺序写入
                    for chap_idx in range(start, end + 1):
                        if self._cancel_flag:
                            break

                        chapter_info = chapter_dict.get(chap_idx)
                        original_chapter = next(
                            (ch for ch in chapters if ch.get('index') == chap_idx),
                            None
                        )
                        title = (
                            original_chapter['title']
                            if original_chapter
                            else chapter_info.get('chapter_title', f'第{chap_idx}章')
                        )

                        self._update_ui_progress(chap_idx, total_chapters)

                        if chapter_info:
                            content = chapter_info.get('content', '')
                            content = clean_content(content)
                            # 如果内容以标题开头，去掉重复的标题
                            if content.lstrip().startswith(title):
                                content = content.lstrip()[len(title):].strip()
                            f.write(f"{title}\n{content}\n\n")
                        else:
                            f.write(f"{title}\n[内容缺失]\n\n")

            # 6. 完成
            if not self._cancel_flag:
                self._update_ui_progress(total_chapters, total_chapters)
                self._update_ui_log(f"\n[b]下载完成！[/b]")
                self._update_ui_log(f"文件: {output_file}")
                self._update_ui_progress_label("下载完成！")
            else:
                self._update_ui_progress_label("已取消")

        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            self._update_ui_log(f"\n[color=#FF4444]下载失败: {str(e)}[/color]")
            self._update_ui_log(f"[color=#666666]{err_msg[-500:]}[/color]")
            self._update_ui_progress_label(f"失败: {str(e)[:50]}")

        finally:
            # 恢复UI状态
            self._on_download_finished()

    # ── UI更新方法（线程安全）──

    @mainthread
    def _update_ui_log(self, message):
        """往日志追加一行"""
        current = self._log_content.text
        if current:
            current += "\n" + message
        else:
            current = message
        self._log_content.text = current
        # 自动滚动到底部
        if self._log_scroll:
            self._log_scroll.scroll_y = 0

    @mainthread
    def _update_ui_info(self, title, author):
        """更新书名和作者"""
        self._info_title.text = f"书名: {title}"
        self._info_author.text = f"作者: {author}"

    @mainthread
    def _update_ui_progress(self, current, total):
        """更新进度条"""
        if total > 0:
            self._progress_bar.max = total
            self._progress_bar.value = current
            percent = (current / total) * 100
            self._progress_label.text = f"下载中: {current}/{total} ({percent:.1f}%)"

    @mainthread
    def _update_ui_progress_max(self, total):
        self._progress_bar.max = total
        self._progress_bar.value = 0

    @mainthread
    def _update_ui_progress_label(self, text):
        self._progress_label.text = text

    @mainthread
    def _on_download_finished(self):
        """下载结束后的UI恢复"""
        self.is_downloading = False
        self._download_btn.disabled = False
        self._cancel_btn.disabled = True

    @mainthread
    def _show_popup(self, title, message):
        """显示弹窗"""
        from kivy.uix.popup import Popup
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        msg_label = Label(
            text=message,
            font_size=14,
            color=(1, 1, 1, 1),
            halign='left',
            valign='top'
        )
        msg_label.bind(size=msg_label.setter('text_size'))
        btn = Button(
            text="确定",
            size_hint_y=None,
            height=40,
            background_color=(0.25, 0.6, 0.3, 1)
        )
        content.add_widget(msg_label)
        content.add_widget(btn)

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.82, 0.45),
            auto_dismiss=True,
            title_color=(1, 0.85, 0.4, 1),
            separator_color=(1, 0.85, 0.4, 0.5)
        )
        btn.bind(on_press=popup.dismiss)
        popup.open()


# ═══════════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════════
if __name__ == '__main__':
    NovelDownloaderApp().run()