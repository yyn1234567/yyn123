#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
番茄小说下载器 - Kivy APP 版
Termux 风格输出 + Kivy 进度条
"""

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
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.graphics import Color, Rectangle
from kivy.utils import platform, get_color_from_hex

# ══════════════════════════════════════════════════════════════
#  API 配置
# ══════════════════════════════════════════════════════════════
BASE_URL = "https://oiapi.net/api/FqRead"
API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"
MAX_RETRIES = 3
RETRY_DELAY = 2
TIMEOUT = 30
BATCH_SIZE = 30          # 每批下载章节数
PROGRESS_BAR_LENGTH = 24 # 终端风格进度条长度

# ══════════════════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════════════════
def clean_filename(name):
    """清理文件名中的非法字符"""
    return re.sub(r"[\/\\\:\*\?\"\<\>\|]", "_", name)

def api_request(url_params):
    """发送 API 请求，带重试机制"""
    url = f"{BASE_URL}?{url_params}&key={API_KEY}"
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=TIMEOUT, verify=False)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(f"API请求失败，已重试{MAX_RETRIES}次")

def get_book_info(book_id):
    """获取书籍信息"""
    result = api_request(f"method=ids&id={book_id}")
    if result.get('code') == 1:
        return result['data']
    raise Exception(f"获取书籍信息失败: {result.get('message', '未知错误')}")

def get_chapter_list(book_id):
    """获取章节列表"""
    result = api_request(f"method=chapters&id={book_id}")
    if result.get('code') == 1:
        return result['data']
    raise Exception(f"获取章节列表失败: {result.get('message', '未知错误')}")

def get_chapter_contents_batch(book_id, start, end):
    """批量获取章节内容"""
    result = api_request(f"method=chapter&id={book_id}&chapter={start}-{end}")
    if result.get('code') == 1:
        return result['data']
    raise Exception(f"批量获取章节失败: {result.get('message', '未知错误')}")

def clean_content(content):
    """清理章节内容，去掉 HTML 标签"""
    content = content.replace('</p><p>', '\n').replace('<p>', '').replace('</p>', '\n')
    content = re.sub(re.compile('<.*?>'), '', content)
    content = re.sub(r'\n+', '\n', content).strip()
    return content

def format_progress_bar(current, total, length=PROGRESS_BAR_LENGTH):
    """
    生成终端风格的进度条字符串
    返回: "[████████░░░░░░░░░░░░] 45.2% 136/300"
    """
    percent = (current / total) * 100 if total > 0 else 0
    filled = int(length * current // total) if total > 0 else 0
    bar = '█' * filled + '░' * (length - filled)
    return f"[{bar}] {percent:5.1f}% {current}/{total}"

def get_download_dir():
    """
    获取下载目录，兼容不同 Android 版本及 scoped storage
    优先级: 公共Download/novels → 应用私有目录
    """
    # 桌面端
    if platform not in ('android', 'ios'):
        downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
        return os.path.join(downloads, 'novels')

    # Android 端
    try:
        from jnius import autoclass
        Environment = autoclass('android.os.Environment')

        if Environment.getExternalStorageState() == Environment.MEDIA_MOUNTED:
            external = Environment.getExternalStorageDirectory().getAbsolutePath()
            download_dir = os.path.join(external, 'Download', 'novels')
            os.makedirs(download_dir, exist_ok=True)
            # 测试可写性
            test_file = os.path.join(download_dir, '.write_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                return download_dir
            except (OSError, PermissionError):
                pass
    except Exception:
        pass

    # 回退到应用私有目录
    try:
        private_dir = os.path.join(App.get_running_app().user_data_dir, 'novels')
    except Exception:
        private_dir = os.path.join(os.getcwd(), 'novels')

    os.makedirs(private_dir, exist_ok=True)
    return private_dir

# ══════════════════════════════════════════════════════════════
#  主界面
# ══════════════════════════════════════════════════════════════
class NovelDownloader(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=12, spacing=8, **kwargs)

        # ── 深色终端背景 ──
        with self.canvas.before:
            Color(*get_color_from_hex('#1a1a2e'))  # 深蓝黑色背景
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # ── 等宽字体注册 ──
        self._register_mono_font()

        # ── 标题 ──
        self.title_label = Label(
            text='fq v1.2.0\n桀桀桀桀桀～',
            size_hint_y=None, height=56,
            font_size='16sp', bold=True,
            color=get_color_from_hex('#00ff88'),  # 终端绿
            halign='center', valign='middle'
        )
        self.add_widget(self.title_label)

        # ── 输入行 ──
        input_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=44, spacing=8)
        self.book_id_input = TextInput(
            hint_text='请输入 book id...',
            multiline=False,
            font_size='14sp',
            background_color=get_color_from_hex('#16213e'),
            foreground_color=get_color_from_hex('#e0e0e0'),
            hint_text_color=get_color_from_hex('#555555'),
            cursor_color=get_color_from_hex('#00ff88')
        )
        input_row.add_widget(self.book_id_input)

        self.download_btn = Button(
            text='▶ 开始下载',
            size_hint_x=0.35,
            font_size='13sp',
            background_normal='',
            background_color=get_color_from_hex('#00ff88'),
            color=get_color_from_hex('#000000'),
            bold=True
        )
        self.download_btn.bind(on_press=self.start_download)
        input_row.add_widget(self.download_btn)

        self.cancel_btn = Button(
            text='■ 取消',
            size_hint_x=0.2,
            font_size='12sp',
            background_normal='',
            background_color=get_color_from_hex('#444444'),
            color=get_color_from_hex('#cccccc'),
            disabled=True
        )
        self.cancel_btn.bind(on_press=self.cancel_download)
        input_row.add_widget(self.cancel_btn)

        self.add_widget(input_row)

        # ── 进度条区域 ──
        self.progress_bar = ProgressBar(
            max=100, value=0,
            size_hint_y=None, height=8,
            background_color=get_color_from_hex('#333333')
        )
        self.add_widget(self.progress_bar)

        # ── 状态标签（模拟原地更新） ──
        self.status_label = Label(
            text='就绪，等待输入 book id',
            size_hint_y=None, height=22,
            font_size='11sp',
            color=get_color_from_hex('#aaaaaa'),
            halign='left', valign='middle',
            font_name='Mono'  # 等宽字体
        )
        self.add_widget(self.status_label)

        # ── 日志输出区域 ──
        self.log_label = Label(
            text='',
            size_hint_y=None,
            font_size='12sp',
            color=get_color_from_hex('#c0c0c0'),
            halign='left', valign='top',
            font_name='Mono',  # 等宽字体让进度条对齐
            markup=False
        )
        self.log_label.bind(texture_size=self._update_log_height)

        self.scroll_view = ScrollView(
            size_hint=(1, 1),
            bar_width=6,
            bar_color=get_color_from_hex('#444444'),
            bar_inactive_color=get_color_from_hex('#222222'),
            scroll_type=['bars', 'content']
        )
        self.scroll_view.add_widget(self.log_label)
        self.add_widget(self.scroll_view)

        # ── 底栏信息 ──
        self.footer_label = Label(
            text='保存路径: 等待下载...',
            size_hint_y=None, height=20,
            font_size='10sp',
            color=get_color_from_hex('#666666'),
            halign='left', valign='middle'
        )
        self.add_widget(self.footer_label)

        # ── 内部状态 ──
        self._cancel_event = threading.Event()
        self._download_thread = None

    # ── 背景自适应 ──
    def _update_bg(self, instance, value):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    # ── 等宽字体加载 ──
    def _register_mono_font(self):
        """尝试加载系统等宽字体（优先级从高到低）"""
        mono_paths = [
            # Android 系统等宽字体
            '/system/fonts/DroidSansMono.ttf',
            '/system/fonts/NotoMono-Regular.ttf',
            # Termux 常见字体
            '/data/data/com.termux/files/usr/share/fonts/DejaVuSansMono.ttf',
            # 项目自带字体
            'font.ttf',
            'mono.ttf',
        ]
        registered = False
        for path in mono_paths:
            if os.path.exists(path):
                try:
                    LabelBase.register(name='Mono', fn_regular=path)
                    registered = True
                    break
                except Exception:
                    continue

        if not registered:
            # 尝试用默认字体注册 Mono 名称（退化方案）
            try:
                LabelBase.register(name='Mono', fn_regular='DroidSans.ttf')
            except Exception:
                pass  # 将使用 Kivy 默认字体，进度条可能不对齐

    # ── 日志标签高度自适应 ──
    def _update_log_height(self, instance, value):
        instance.height = max(instance.texture_size[1], self.scroll_view.height)
        # 自动滚到底部
        self.scroll_view.scroll_y = 0

    # ── 线程安全的 UI 更新 ──
    def _append_log(self, text):
        """追加日志（终端风格输出）"""
        def _update(dt):
            self.log_label.text += text
            # 限制日志最大行数，避免性能问题
            lines = self.log_label.text.split('\n')
            if len(lines) > 500:
                self.log_label.text = '\n'.join(lines[-400:])
        Clock.schedule_once(_update, 0)

    def _set_status(self, text):
        """更新状态标签（模拟原地刷新）"""
        def _update(dt):
            self.status_label.text = text
        Clock.schedule_once(_update, 0)

    def _set_progress(self, value):
        """更新进度条（0-100）"""
        def _update(dt):
            self.progress_bar.value = value
        Clock.schedule_once(_update, 0)

    def _set_footer(self, text):
        """更新底栏信息"""
        def _update(dt):
            self.footer_label.text = text
        Clock.schedule_once(_update, 0)

    # ── 开始/取消下载 ──
    def start_download(self, instance):
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._set_status('⚠ 请输入有效的 book id')
            return

        self.download_btn.disabled = True
        self.cancel_btn.disabled = False
        self._cancel_event.clear()
        self.log_label.text = ''
        self.progress_bar.value = 0
        self._set_status('⏳ 正在获取书籍信息...')
        self._set_footer('保存路径: 获取中...')

        self._download_thread = threading.Thread(
            target=self._download_novel, args=(book_id,), daemon=True
        )
        self._download_thread.start()

    def cancel_download(self, instance):
        self._cancel_event.set()
        self._set_status('⏹ 正在取消...')
        self.cancel_btn.disabled = True
        self._append_log('\n⚠ 用户取消下载\n')

    # ── 核心下载逻辑 ──
    def _download_novel(self, book_id):
        start_time = time.time()
        try:
            # ── 获取书籍信息 ──
            info = get_book_info(book_id)
            title = info['title']
            author = info['author']
            intro = info.get('docs', '').replace('\n', ' ')

            self._append_log(f'书名: {title}\n')
            self._append_log(f'作者: {author}\n')
            self._append_log(f'简介: {intro[:120]}{"..." if len(intro) > 120 else ""}\n')

            if self._cancel_event.is_set():
                return

            # ── 获取章节列表 ──
            chapters_data = get_chapter_list(book_id)
            chapters = []
            for vol in chapters_data:
                if isinstance(vol, list):
                    chapters.extend(vol)
                elif isinstance(vol, dict):
                    chapters.append(vol)

            total = len(chapters)
            self._append_log(f'\n共 {total} 章，开始下载...\n')
            self._append_log('─' * 40 + '\n')

            safe_title = clean_filename(title)
            output_dir = get_download_dir()
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{safe_title}.txt")

            self._set_footer(f'保存路径: {output_dir}')

            if self._cancel_event.is_set():
                return

            # ── 写入文件头 ──
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{title}\n作者: {author}\n简介:\n{intro}\n\n")

                last_progress_line = 0  # 记录上一次追加进度条的百分比（避免过于频繁）

                for start in range(1, total + 1, BATCH_SIZE):
                    if self._cancel_event.is_set():
                        self._append_log('\n⚠ 已取消，文件已部分保存\n')
                        f.flush()
                        return

                    end = min(start + BATCH_SIZE - 1, total)

                    # 批量获取章节
                    try:
                        batch = get_chapter_contents_batch(book_id, start, end)
                    except Exception as e:
                        self._append_log(f'✗ 批量 {start}-{end} 失败: {e}\n')
                        # 失败时逐章跳过
                        for idx in range(start, end + 1):
                            if self._cancel_event.is_set():
                                return
                            orig = next((ch for ch in chapters if ch.get('index') == idx), None)
                            chap_title = orig['title'] if orig else f'第{idx}章'
                            f.write(f"{chap_title}\n[下载失败]\n\n")
                        continue

                    # 转为字典便于查找
                    chap_dict = {int(item['chapter']): item for item in batch if item.get('chapter')}

                    # 逐章写入
                    for idx in range(start, end + 1):
                        if self._cancel_event.is_set():
                            return

                        info_chap = chap_dict.get(idx)
                        orig = next((ch for ch in chapters if ch.get('index') == idx), None)
                        chap_title = orig['title'] if orig else (info_chap.get('chapter_title', f'第{idx}章') if info_chap else f'第{idx}章')

                        if info_chap:
                            content = clean_content(info_chap.get('content', ''))
                            # 如果内容开头重复了章节标题，去掉
                            if content.lstrip().startswith(chap_title):
                                content = content.lstrip()[len(chap_title):].strip()
                            f.write(f"{chap_title}\n{content}\n\n")
                        else:
                            f.write(f"{chap_title}\n[内容缺失]\n\n")

                    # ── 每完成一个 batch，追加一行终端风格进度条到日志 ──
                    current_percent = int((end / total) * 100)
                    if current_percent - last_progress_line >= 5 or end == total:
                        progress_line = format_progress_bar(end, total)
                        self._append_log(f'{progress_line}\n')
                        last_progress_line = current_percent

                    # ── 更新进度条和状态 ──
                    percent_val = (end / total) * 100
                    self._set_progress(percent_val)
                    self._set_status(format_progress_bar(end, total))

                # ── 完成 ──
                f.flush()

            elapsed = time.time() - start_time
            file_size = os.path.getsize(output_file)
            size_str = self._format_size(file_size)

            self._append_log('─' * 40 + '\n')
            self._append_log(f'✅ 下载完成！\n')
            self._append_log(f'   文件: {output_file}\n')
            self._append_log(f'   大小: {size_str}\n')
            self._append_log(f'   耗时: {elapsed:.1f} 秒\n')
            self._set_progress(100)
            self._set_status(f'✅ 完成 - {size_str} - {elapsed:.0f}s')
            self._set_footer(f'已保存: {output_file}')

        except Exception as e:
            self._append_log(f'\n❌ 下载失败: {str(e)}\n')
            self._set_status(f'❌ 失败: {str(e)[:40]}')
        finally:
            def enable_buttons(dt):
                self.download_btn.disabled = False
                self.cancel_btn.disabled = True
            Clock.schedule_once(enable_buttons, 0)

    @staticmethod
    def _format_size(size_bytes):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

# ══════════════════════════════════════════════════════════════
#  Kivy App
# ══════════════════════════════════════════════════════════════
class TomatoNovelApp(App):
    def build(self):
        # ── 尝试注册等宽字体（中英文混合） ──
        try:
            # 如果项目根目录有 font.ttf，优先使用
            LabelBase.register(name='Roboto', fn_regular='font.ttf')
        except Exception:
            pass

        # ── Android 权限请求 ──
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                permissions_needed = [
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE,
                ]
                # Android 13+ 媒体权限
                for perm_name in ('READ_MEDIA_IMAGES', 'READ_MEDIA_VIDEO', 'READ_MEDIA_AUDIO'):
                    try:
                        permissions_needed.append(getattr(Permission, perm_name))
                    except AttributeError:
                        pass
                request_permissions(permissions_needed)
            except Exception as e:
                print(f'权限请求失败: {e}')

        return NovelDownloader()

if __name__ == '__main__':
    TomatoNovelApp().run()