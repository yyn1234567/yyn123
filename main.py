#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os, time, re, threading
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.utils import platform
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.app import App

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.card import MDCard
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.progressbar import MDProgressBar

# ============== 配色方案 ==============
BG_PRIMARY    = [0.067, 0.067, 0.118, 1]
BG_CARD       = [0.106, 0.114, 0.196, 1]
ACCENT        = [0.298, 0.643, 0.918, 1]
ACCENT_PRESS  = [0.200, 0.480, 0.780, 1]
SUCCESS       = [0.298, 0.780, 0.549, 1]
DANGER        = [0.914, 0.271, 0.271, 1]
TEXT_WHITE     = [0.957, 0.957, 0.973, 1]
TEXT_GRAY      = [0.580, 0.600, 0.675, 1]
SCROLL_BG     = [0.086, 0.090, 0.157, 1]

BASE_URL = "https://oiapi.net/api/FqRead"
API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"
MAX_RETRIES = 3
RETRY_DELAY = 2
TIMEOUT = 30

REQUEST_CODE_OPEN_TREE = 1001


# ============== SAF 管理器（Android 专用） ==============

class SAFManager:
    """Storage Access Framework 管理器，用于 Android 11+ 的文件写入权限"""

    def __init__(self):
        self.saf_uri = None
        self.context = None
        self.content_resolver = None
        self._ready = False
        self._callback = None  # 回调函数，用于通知 UI

        if platform == 'android':
            self._init_android()

    def _init_android(self):
        try:
            from jnius import autoclass
            self.PythonActivity = autoclass('org.kivy.android.PythonActivity')
            self.Intent = autoclass('android.content.Intent')
            self.Uri = autoclass('android.net.Uri')
            self.DocumentsContract = autoclass('android.provider.DocumentsContract')
            self.Build = autoclass('android.os.Build')

            self.context = self.PythonActivity.mActivity
            self.content_resolver = self.context.getContentResolver()

            # 仅 Android 11+ (API 30) 需要 SAF
            if self.Build.VERSION.SDK_INT >= 30:
                self._load_uri()
                from android import activity
                activity.bind(on_activity_result=self._on_activity_result)
                self._ready = True
                print(f"[SAF] 初始化完成, 已有URI: {bool(self.saf_uri)}")
            else:
                print("[SAF] Android 版本 < 11, 不需要 SAF")
        except Exception as e:
            print(f"[SAF] 初始化失败: {e}")

    def _get_config_path(self):
        return os.path.join(App.get_running_app().user_data_dir, 'saf_uri.txt')

    def _load_uri(self):
        try:
            config = self._get_config_path()
            if os.path.exists(config):
                with open(config, 'r') as f:
                    uri_str = f.read().strip()
                if uri_str:
                    # 验证 URI 是否仍然有效
                    uri = self.Uri.parse(uri_str)
                    try:
                        # 检查是否仍有持久化权限
                        perms = self.content_resolver.getPersistedUriPermissions()
                        for i in range(perms.size()):
                            if perms.get(i).getUri().toString() == uri_str:
                                self.saf_uri = uri_str
                                print(f"[SAF] 已加载保存的 URI: {uri_str}")
                                return
                        print("[SAF] 保存的 URI 权限已失效")
                    except Exception:
                        # 无法检查权限，尝试直接使用
                        self.saf_uri = uri_str
        except Exception as e:
            print(f"[SAF] 加载 URI 失败: {e}")

    def _save_uri(self, uri_string):
        try:
            with open(self._get_config_path(), 'w') as f:
                f.write(uri_string)
            self.saf_uri = uri_string
            print(f"[SAF] URI 已保存: {uri_string}")
        except Exception as e:
            print(f"[SAF] 保存 URI 失败: {e}")

    def pick_directory(self, callback=None):
        """启动系统文件管理器让用户选择保存目录"""
        self._callback = callback
        if not self.context:
            if callback:
                callback(False, "SAF 未初始化")
            return

        try:
            intent = self.Intent(self.Intent.ACTION_OPEN_DOCUMENT_TREE)
            intent.addFlags(
                self.Intent.FLAG_GRANT_READ_URI_PERMISSION
                | self.Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                | self.Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
            )
            self.context.startActivityForResult(intent, REQUEST_CODE_OPEN_TREE)
        except Exception as e:
            print(f"[SAF] 启动选择器失败: {e}")
            if callback:
                callback(False, str(e))

    def _on_activity_result(self, request_code, result_code, intent):
        """处理 Activity 返回结果"""
        if request_code != REQUEST_CODE_OPEN_TREE:
            return

        if result_code == -1 and intent:  # Activity.RESULT_OK == -1
            uri = intent.getData()
            if uri:
                try:
                    # 获取持久化权限
                    flags = intent.getFlags()
                    read_write = 0x1 | 0x2  # FLAG_GRANT_READ | FLAG_GRANT_WRITE
                    take_flags = flags & read_write
                    if take_flags == 0:
                        take_flags = read_write
                    self.content_resolver.takePersistableUriPermission(uri, take_flags)
                    self._save_uri(uri.toString())
                    if self._callback:
                        self._callback(True, uri.toString())
                except Exception as e:
                    print(f"[SAF] 获取权限失败: {e}")
                    if self._callback:
                        self._callback(False, str(e))
        else:
            print("[SAF] 用户取消选择")
            if self._callback:
                self._callback(False, "用户取消")

    def create_file(self, filename, mime_type='text/plain'):
        """在 SAF 目录中创建文件，返回文件 URI 字符串"""
        if not self.saf_uri or not self.content_resolver:
            return None
        try:
            tree_uri = self.Uri.parse(self.saf_uri)
            new_uri = self.DocumentsContract.createDocument(
                self.content_resolver, tree_uri, mime_type, filename
            )
            if new_uri:
                return new_uri.toString()
        except Exception as e:
            print(f"[SAF] 创建文件失败: {e}")
        return None

    def needs_saf(self):
        """判断是否需要使用 SAF（Android 11+）"""
        if not self._ready:
            return False
        try:
            return self.Build.VERSION.SDK_INT >= 30
        except:
            return False


class SAFWriter:
    """将 SAF OutputStream 包装为 Python 文件风格的上下文管理器"""

    def __init__(self, uri_string, content_resolver):
        self._uri_string = uri_string
        self._content_resolver = content_resolver
        self._output_stream = None
        self._open()

    def _open(self):
        try:
            uri = SAFManager._parse_uri_static(self._uri_string)
            self._output_stream = self._content_resolver.openOutputStream(uri)
        except Exception as e:
            print(f"[SAF] 打开输出流失败: {e}")
            raise

    def write(self, text):
        if isinstance(text, str):
            data = bytearray(text.encode('utf-8'))
        else:
            data = bytearray(text)
        self._output_stream.write(data)

    def close(self):
        if self._output_stream:
            try:
                self._output_stream.flush()
                self._output_stream.close()
            except Exception:
                pass
            self._output_stream = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# 为 SAFWriter 添加静态 URI 解析方法
def _parse_uri_static(uri_string):
    from jnius import autoclass
    Uri = autoclass('android.net.Uri')
    return Uri.parse(uri_string)

SAFManager._parse_uri_static = staticmethod(_parse_uri_static)


# ============== 后端逻辑（完全未修改） ==============

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
    try:
        if platform == 'android':
            return os.path.join(App.get_running_app().user_data_dir, 'novels')
        else:
            downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            return os.path.join(downloads, 'novels')
    except Exception as e:
        try:
            return os.path.join(App.get_running_app().user_data_dir, 'novels')
        except:
            return os.path.join(os.getcwd(), 'novels')


# ============== KivyMD 现代化前端 ==============

class NovelDownloader(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.md_bg_color = BG_PRIMARY
        self.saf_manager = None

        # 初始化 SAF 管理器
        if platform == 'android':
            self.saf_manager = SAFManager()

        # 主内容容器
        main = MDBoxLayout(
            orientation='vertical',
            padding=[dp(16), dp(16), dp(16), dp(16)],
            spacing=dp(14)
        )

        # ───────────── 顶部标题栏 ─────────────
        header = MDCard(
            elevation=3,
            radius=[dp(16)],
            md_bg_color=[0.114, 0.125, 0.216, 1],
            size_hint_y=None,
            height=dp(88),
            padding=[dp(20), dp(14), dp(20), dp(12)],
            orientation='vertical',
            spacing=dp(4),
            ripple_behavior=False
        )

        accent_bar = MDBoxLayout(
            size_hint_y=None,
            height=dp(3),
            size_hint_x=None,
            width=dp(48),
            md_bg_color=ACCENT,
            radius=[dp(2)]
        )

        title_label = MDLabel(
            text='[b]s丶ky书包[/b]',
            font_style='H6',
            theme_text_color='Custom',
            text_color=TEXT_WHITE,
            markup=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        )
        title_label.bind(size=lambda i, v: setattr(i, 'text_size', (i.width, None)))

        subtitle_label = MDLabel(
            text='v1.3.4 | 桀桀桀桀桀',
            font_style='Caption',
            theme_text_color='Custom',
            text_color=TEXT_GRAY,
            size_hint_y=None,
            height=dp(18),
            halign='left'
        )
        subtitle_label.bind(size=lambda i, v: setattr(i, 'text_size', (i.width, None)))

        header.add_widget(accent_bar)
        header.add_widget(title_label)
        header.add_widget(subtitle_label)

        # ───────────── 输入区卡片 ─────────────
        input_card = MDCard(
            elevation=2,
            radius=[dp(16)],
            md_bg_color=BG_CARD,
            size_hint_y=None,
            height=dp(230),
            padding=[dp(18), dp(14), dp(18), dp(14)],
            spacing=dp(12),
            orientation='vertical',
            ripple_behavior=False
        )

        input_hint = MDLabel(
            text='请输入book id',
            font_style='Caption',
            theme_text_color='Custom',
            text_color=TEXT_GRAY,
            size_hint_y=None,
            height=dp(18),
            halign='left'
        )
        input_hint.bind(size=lambda i, v: setattr(i, 'text_size', (i.width, None)))

        self.book_id_input = MDTextField(
            hint_text='book id',
            mode='round',
            size_hint_y=None,
            height=dp(48)
        )

        # 按钮区域：下载按钮 + 选择目录按钮
        btn_row = MDBoxLayout(
            size_hint_y=None,
            height=dp(48),
            spacing=dp(8)
        )

        self.download_btn = MDRaisedButton(
            text='开始下载',
            md_bg_color=ACCENT,
            text_color=TEXT_WHITE,
            font_size='16sp',
            size_hint=(0.65, None),
            height=dp(48)
        )
        self.download_btn.bind(on_press=self.start_download)

        self.select_dir_btn = MDRaisedButton(
            text='选择保存目录',
            md_bg_color=[0.18, 0.20, 0.30, 1],
            text_color=TEXT_WHITE,
            font_size='14sp',
            size_hint=(0.35, None),
            height=dp(48)
        )
        self.select_dir_btn.bind(on_press=self.select_save_dir)

        btn_row.add_widget(self.download_btn)
        btn_row.add_widget(self.select_dir_btn)

        # 保存路径显示
        self.path_label = MDLabel(
            text='[color=666688]保存路径: 点击"选择保存目录"授权写入[/color]',
            font_style='Caption',
            theme_text_color='Custom',
            text_color=TEXT_GRAY,
            size_hint_y=None,
            height=dp(18),
            halign='left',
            markup=True
        )
        self.path_label.bind(size=lambda i, v: setattr(i, 'text_size', (i.width, None)))

        # 更新路径显示
        self._update_path_display()

        input_card.add_widget(input_hint)
        input_card.add_widget(self.book_id_input)
        input_card.add_widget(btn_row)
        input_card.add_widget(self.path_label)

        # ───────────── 日志输出卡片 ─────────────
        output_card = MDCard(
            elevation=2,
            radius=[dp(16)],
            md_bg_color=SCROLL_BG,
            padding=[dp(16), dp(12), dp(16), dp(12)],
            spacing=dp(8),
            orientation='vertical',
            ripple_behavior=False
        )

        log_header = MDBoxLayout(
            size_hint_y=None,
            height=dp(28),
            spacing=dp(8)
        )

        log_title = MDLabel(
            text='输出',
            font_style='Subtitle2',
            theme_text_color='Custom',
            text_color=TEXT_GRAY,
            bold=True,
            halign='left'
        )
        log_title.bind(size=lambda i, v: setattr(i, 'text_size', (i.width, None)))

        self.status_label = MDLabel(
            text='就绪',
            font_style='Caption',
            theme_text_color='Custom',
            text_color=SUCCESS,
            size_hint_x=None,
            width=dp(60),
            halign='right'
        )
        self.status_label.bind(size=lambda i, v: setattr(i, 'text_size', (i.width, None)))

        log_header.add_widget(log_title)
        log_header.add_widget(Widget())
        log_header.add_widget(self.status_label)

        self.progress_bar = MDProgressBar(
            value=0,
            color=ACCENT,
            size_hint_y=None,
            height=dp(4)
        )

        self.output_label = MDLabel(
            text='[color=666688]book id获取方法：\n1.点击小说界面右上角分享，选择复制链接\n2.在浏览器打开该链接，然后复制加载后的地址\n3.地址前几行book id=后的数字即为该书id[/color]',
            font_style='Body2',
            theme_text_color='Custom',
            text_color=TEXT_WHITE,
            markup=True,
            halign='left',
            valign='top',
            size_hint_y=None,
            height=dp(200),
            line_height=1.4
        )
        self.output_label.bind(
            width=lambda i, v: setattr(i, 'text_size', (i.width, None))
        )

        self.scroll_view = ScrollView(
            size_hint=(1, 1),
            bar_color=[*ACCENT[:3], 0.4],
            bar_inactive_color=[*ACCENT[:3], 0.15],
            bar_width=dp(4)
        )
        self.scroll_view.add_widget(self.output_label)

        output_card.add_widget(log_header)
        output_card.add_widget(self.progress_bar)
        output_card.add_widget(self.scroll_view)

        # ───────────── 组装 ─────────────
        main.add_widget(header)
        main.add_widget(input_card)
        main.add_widget(output_card)
        self.add_widget(main)

    def _update_path_display(self):
        """更新路径显示标签"""
        if self.saf_manager and self.saf_manager.saf_uri:
            self.path_label.text = '[color=33e87a]保存路径: 已授权 SAF 目录 ✓[/color]'
        else:
            output_dir = get_download_dir()
            self.path_label.text = f'[color=666688]保存路径: {output_dir}[/color]'

    def select_save_dir(self, instance):
        """让用户选择保存目录"""
        if not self.saf_manager:
            self._append_output("[color=e94545]SAF 不可用，当前平台不支持[/color]\n")
            return

        if not self.saf_manager.needs_saf():
            self._append_output("[color=4da6e8]当前 Android 版本无需 SAF 授权[/color]\n")
            return

        self.select_dir_btn.disabled = True
        self.select_dir_btn.text = '选择中...'
        self._append_output("[color=4da6e8]正在打开系统文件管理器...[/color]\n")

        def on_saf_result(success, msg):
            def _update(dt):
                self.select_dir_btn.disabled = False
                self.select_dir_btn.text = '选择保存目录'
                if success:
                    self._append_output(
                        f"[color=33e87a]✓ 目录授权成功！[/color]\n"
                        f"[color=666688]URI: {msg}[/color]\n"
                    )
                    self._update_path_display()
                else:
                    self._append_output(f"[color=e94545]✗ 授权失败: {msg}[/color]\n")
            Clock.schedule_once(_update, 0)

        self.saf_manager.pick_directory(callback=on_saf_result)

    # ============== 交互逻辑 ==============

    def start_download(self, instance):
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._append_output("[color=e94545]请输入有效的book id[/color]\n")
            return

        # Android 11+ 检查 SAF 权限
        if self.saf_manager and self.saf_manager.needs_saf() and not self.saf_manager.saf_uri:
            self._append_output(
                "[color=e94545]请先点击"选择保存目录"授权写入权限！[/color]\n"
            )
            return

        self.download_btn.disabled = True
        self.download_btn.text = '下载中...'
        self.select_dir_btn.disabled = True
        self.status_label.text = '下载中'
        self.status_label.text_color = ACCENT
        self.progress_bar.value = 0
        self.progress_bar.color = ACCENT
        self._set_output('[color=9999aa]正在获取书籍信息...[/color]\n')
        threading.Thread(target=self._download_novel, args=(book_id,), daemon=True).start()

    def _append_output(self, text):
        def _update(dt):
            self.output_label.text += text
            self.output_label.texture_update()
            self.output_label.height = max(self.output_label.texture_size[1], dp(100))
            self.scroll_view.scroll_y = 0
        Clock.schedule_once(_update, 0)

    def _set_output(self, text):
        def _update(dt):
            self.output_label.text = text
            self.output_label.texture_update()
            self.output_label.height = max(self.output_label.texture_size[1], dp(100))
        Clock.schedule_once(_update, 0)

    def _open_output_file(self, safe_title, output_dir):
        """
        打开输出文件，优先使用 SAF，否则使用普通文件写入。
        返回 (file_handle, path_description)
        """
        # 尝试 SAF 写入
        if self.saf_manager and self.saf_manager.saf_uri:
            file_uri = self.saf_manager.create_file(f"{safe_title}.txt")
            if file_uri:
                try:
                    writer = SAFWriter(file_uri, self.saf_manager.content_resolver)
                    return writer, f"SAF: {file_uri}"
                except Exception as e:
                    print(f"[SAF] 创建 SAFWriter 失败: {e}")

        # 回退到普通文件写入
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{safe_title}.txt")
        f = open(output_file, 'w', encoding='utf-8')
        return f, output_file

    def _download_novel(self, book_id):
        try:
            info = get_book_info(book_id)
            title = info['title']
            author = info['author']
            intro = info.get('docs', '').replace('\n', ' ')

            self._append_output(
                f"[color=4da6e8]书名:[/color] [b]{title}[/b]\n"
                f"[color=4da6e8]作者:[/color] {author}\n"
                f"[color=4da6e8]简介:[/color] {intro[:80]}...\n"
                f"[color=333355]─────────────────────────[/color]\n"
            )

            chapters_data = get_chapter_list(book_id)
            chapters = []
            for vol in chapters_data:
                if isinstance(vol, list):
                    chapters.extend(vol)
                elif isinstance(vol, dict):
                    chapters.append(vol)

            total = len(chapters)
            self._append_output(f"[color=4da6e8]共 {total} 章，开始下载...[/color]\n")

            safe_title = clean_filename(title)
            output_dir = get_download_dir()

            # 使用统一的文件打开方法（SAF 或普通文件）
            f, path_desc = self._open_output_file(safe_title, output_dir)
            self._append_output(f"[color=666688]保存方式: {path_desc}[/color]\n")

            try:
                f.write(f"{title}\n作者: {author}\n简介:\n{intro}\n\n")

                BATCH = 30
                for start in range(1, total + 1, BATCH):
                    end = min(start + BATCH - 1, total)
                    try:
                        batch = get_chapter_contents_batch(book_id, start, end)
                    except Exception as e:
                        self._append_output(f"[color=e94545]批量 {start}-{end} 失败: {e}[/color]\n")
                        continue

                    chap_dict = {int(item['chapter']): item for item in batch if item.get('chapter')}
                    for idx in range(start, end + 1):
                        chap_info = chap_dict.get(idx)
                        orig = next((ch for ch in chapters if ch.get('index') == idx), None)
                        chap_title = orig['title'] if orig else chap_info.get('chapter_title', f'第{idx}章')
                        percent = (idx / total) * 100

                        def _upd(dt, p=percent, i=idx, t=total):
                            self._set_output(
                                f"[color=4da6e8]下载进度[/color]  "
                                f"[b][color=4de8a2]{p:.1f}%[/color][/b]\n"
                                f"[color=888899]正在处理: {i}/{t}[/color]"
                            )
                            self.progress_bar.value = p

                        Clock.schedule_once(_upd, 0)

                        if chap_info:
                            content = clean_content(chap_info.get('content', ''))
                            if content.lstrip().startswith(chap_title):
                                content = content.lstrip()[len(chap_title):].strip()
                            f.write(f"{chap_title}\n{content}\n\n")
                        else:
                            f.write(f"{chap_title}\n[内容缺失]\n\n")

                self._append_output(
                    f"\n[color=33e87a]下载完成！[/color]\n"
                    f"[color=666688]文件: {path_desc}[/color]\n"
                )
            finally:
                f.close()

        except Exception as e:
            self._append_output(f"[color=e94545]下载失败: {str(e)}[/color]\n")
        finally:
            def enable_btn(dt):
                self.download_btn.disabled = False
                self.download_btn.text = '开始下载'
                self.select_dir_btn.disabled = False
                self.status_label.text = '就绪'
                self.status_label.text_color = SUCCESS
                self.progress_bar.value = 100
                self.progress_bar.color = SUCCESS
            Clock.schedule_once(enable_btn, 0)


# ============== 应用入口 ==============

class TomatoNovelApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.accent_palette = "Teal"

        try:
            LabelBase.register(
                name='Roboto',
                fn_regular='font.ttf',
                fn_bold='font.ttf',
                fn_italic='font.ttf',
                fn_bolditalic='font.ttf'
            )
            print("✅ 自定义字体注册成功")
        except Exception as e:
            print(f"⚠️ 字体注册失败: {e}")

        try:
            new_styles = {}
            for style_name, style_value in self.theme_cls.font_styles.items():
                if isinstance(style_value, (list, tuple)):
                    new_style = list(style_value)
                    new_style[0] = 'Roboto'
                    new_styles[style_name] = new_style
                else:
                    new_styles[style_name] = style_value
            self.theme_cls.font_styles = new_styles
            print("✅ 主题字体样式已统一为 Roboto")
        except Exception as e:
            print(f"⚠️ 字体样式覆盖失败: {e}")

        Window.clearcolor = BG_PRIMARY

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

        return NovelDownloader()


if __name__ == '__main__':
    TomatoNovelApp().run()