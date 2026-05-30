#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s丶ky书包 v1.2.1
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
from kivy.utils import platform, get_color_from_hex
from kivy.graphics import Color, Rectangle

# ===================== 常量 =====================
BASE_URL = "https://oiapi.net/api/FqRead"
API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"
MAX_RETRIES = 3
RETRY_DELAY = 2
TIMEOUT = 30
SETTINGS_FILE = "novel_settings.json"

# ===================== 配色主题 =====================
COLORS = {
    'bg':          (0.13, 0.13, 0.15, 1),    # 深色背景
    'surface':     (0.18, 0.18, 0.20, 1),    # 卡片/输入框背景
    'primary':     (0.35, 0.55, 0.75, 1),    # 主色调（柔和蓝）
    'primary_dim': (0.25, 0.40, 0.55, 1),    # 按钮按下态
    'accent':      (0.90, 0.55, 0.30, 1),    # 强调色（暖橙）
    'text_primary':(0.92, 0.92, 0.92, 1),    # 主文字
    'text_secondary':(0.60, 0.60, 0.65, 1),  # 次要文字
    'success':     (0.30, 0.75, 0.45, 1),    # 成功绿
    'error':       (0.85, 0.30, 0.30, 1),    # 错误红
    'divider':     (0.25, 0.25, 0.28, 1),    # 分割线
}

# ===================== 字体查找（不打包字体！）=====================
def _find_system_chinese_font():
    """按平台查找系统中文字体，找不到则回退默认"""
    if platform == 'android':
        candidates = [
            '/system/fonts/NotoSansCJK-Regular.ttc',
            '/system/fonts/DroidSansFallback.ttf',
            '/system/fonts/NotoSansSC-Regular.otf',
            '/system/fonts/FallbackFont.ttf',
        ]
    elif platform == 'linux':
        candidates = [
            '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        ]
    elif platform == 'macosx':
        candidates = [
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/STHeiti Light.ttc',
            '/Library/Fonts/Arial Unicode.ttf',
        ]
    elif platform == 'win':
        candidates = [
            'C:/Windows/Fonts/msyh.ttc',
            'C:/Windows/Fonts/msyhbd.ttc',
            'C:/Windows/Fonts/simsun.ttc',
        ]
    else:
        candidates = []

    for path in candidates:
        if os.path.exists(path):
            return path
    return None

# ===================== 配置管理 =====================
def get_settings_dir():
    """获取设置文件存储目录"""
    try:
        return App.get_running_app().user_data_dir
    except Exception:
        return os.getcwd()

def load_settings():
    """加载设置（记住上次book_id等）"""
    path = os.path.join(get_settings_dir(), SETTINGS_FILE)
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_settings(settings):
    """保存设置"""
    path = os.path.join(get_settings_dir(), SETTINGS_FILE)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ===================== API 层（不变）=====================
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
    """获取下载目录"""
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
                except Exception:
                    pass
            return os.path.join(App.get_running_app().user_data_dir, 'novels')
        else:
            downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            return os.path.join(downloads, 'novels')
    except Exception:
        try:
            return os.path.join(App.get_running_app().user_data_dir, 'novels')
        except Exception:
            return os.path.join(os.getcwd(), 'novels')

# ===================== UI 组件 =====================
class StyledButton(Button):
    """统一样式的按钮"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = COLORS['primary']
        self.color = (1, 1, 1, 1)
        self.font_size = '16sp'
        self.bold = True
        self.size_hint_y = None
        self.height = 52
        # 圆角效果通过 canvas 实现
        with self.canvas.before:
            Color(*COLORS['primary'])
            self._bg_rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def on_state(self, widget, value):
        if value == 'down':
            self.background_color = COLORS['primary_dim']
        else:
            self.background_color = COLORS['primary']


class NovelDownloader(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation='vertical',
            padding=[20, 16, 20, 16],
            spacing=12,
            **kwargs
        )

        # 背景色
        with self.canvas.before:
            Color(*COLORS['bg'])
            self._bg_rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # ---- 标题栏 ----
        title_box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=56,
            spacing=10
        )
        title_label = Label(
            text='s丶ky书包',
            font_size='22sp',
            bold=True,
            color=COLORS['text_primary'],
            size_hint_x=0.7,
            halign='left',
            valign='middle'
        )
        title_label.bind(size=title_label.setter('text_size'))
        version_label = Label(
            text='v1.2.1',
            font_size='12sp',
            color=COLORS['text_secondary'],
            size_hint_x=0.3,
            halign='right',
            valign='middle'
        )
        version_label.bind(size=version_label.setter('text_size'))
        title_box.add_widget(title_label)
        title_box.add_widget(version_label)
        self.add_widget(title_box)

        # ---- 分割线 ----
        self.add_widget(self._divider())

        # ---- 输入区域 ----
        input_label = Label(
            text='输入book id',
            font_size='14sp',
            color=COLORS['text_secondary'],
            size_hint_y=None,
            height=24,
            halign='left',
            valign='bottom'
        )
        input_label.bind(size=input_label.setter('text_size'))
        self.add_widget(input_label)

        self.book_id_input = TextInput(
            hint_text='例如: 7499553647647263806',
            font_size='16sp',
            size_hint_y=None,
            height=50,
            multiline=False,
            background_color=COLORS['surface'],
            foreground_color=COLORS['text_primary'],
            cursor_color=COLORS['accent'],
            padding=[14, 12, 14, 12],
            hint_text_color=COLORS['text_secondary'],
        )
        self.add_widget(self.book_id_input)

        # ---- 按钮行 ----
        btn_row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=52,
            spacing=12
        )
        self.download_btn = StyledButton(text='下载')
        self.download_btn.bind(on_press=self.start_download)
        self.clear_btn = Button(
            text='清空日志',
            font_size='14sp',
            size_hint_y=None,
            height=52,
            background_normal='',
            background_color=COLORS['surface'],
            color=COLORS['text_secondary'],
        )
        self.clear_btn.bind(on_press=self._clear_output)
        btn_row.add_widget(self.download_btn)
        btn_row.add_widget(self.clear_btn)
        self.add_widget(btn_row)

        # ---- 进度条 ----
        self.progress_bar = ProgressBar(
            max=100,
            value=0,
            size_hint_y=None,
            height=8,
            background_color=COLORS['surface'],
        )
        self.add_widget(self.progress_bar)

        # ---- 状态标签 ----
        self.status_label = Label(
            text='就绪',
            font_size='13sp',
            color=COLORS['text_secondary'],
            size_hint_y=None,
            height=28,
            halign='left',
            valign='middle'
        )
        self.status_label.bind(size=self.status_label.setter('text_size'))
        self.add_widget(self.status_label)

        # ---- 输出区域 ----
        self.output_label = Label(
            text='',
            font_size='14sp',
            color=COLORS['text_primary'],
            size_hint_y=None,
            halign='left',
            valign='top',
            markup=True,
        )
        self.output_label.bind(
            texture_size=self._on_texture_size,
            size=self._on_label_size
        )
        self.scroll_view = ScrollView(
            size_hint=(1, 1),
            bar_color=COLORS['primary'],
            bar_width=6,
        )
        self.scroll_view.add_widget(self.output_label)
        self.add_widget(self.scroll_view)

        # ---- 设置加载 ----
        self._settings = load_settings()
        last_id = self._settings.get('last_book_id', '')
        if last_id:
            self.book_id_input.text = last_id
            self._append_output(f'[color=#999]上次的book id: {last_id}[/color]\n')

        self._update_event = None

    # ---------- 辅助方法 ----------
    def _divider(self):
        """创建分割线"""
        d = BoxLayout(size_hint_y=None, height=1)
        with d.canvas.before:
            Color(*COLORS['divider'])
            Rectangle(size=d.size, pos=d.pos)
        d.bind(pos=lambda w, v: w.canvas.before.children[0].pos.__setitem__(slice(None), v),
               size=lambda w, v: w.canvas.before.children[0].size.__setitem__(slice(None), v))
        return d

    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _on_texture_size(self, instance, value):
        instance.size = value

    def _on_label_size(self, instance, value):
        instance.text_size = (instance.width, None)

    def _clear_output(self, instance):
        self.output_label.text = ''
        self.progress_bar.value = 0
        self.status_label.text = '日志已清空'

    # ---------- 输出方法 ----------
    def _append_output(self, text):
        def _update(dt):
            self.output_label.text += text
            self.output_label.texture_update()
            self.output_label.height = self.output_label.texture_size[1]
            # 滚动到底部
            self.scroll_view.scroll_y = 0
        Clock.schedule_once(_update, 0)

    def _set_output(self, text):
        def _update(dt):
            self.output_label.text = text
            self.output_label.texture_update()
            self.output_label.height = self.output_label.texture_size[1]
        Clock.schedule_once(_update, 0)

    def _update_progress(self, value):
        def _update(dt):
            self.progress_bar.value = value
        Clock.schedule_once(_update, 0)

    def _set_status(self, text, color=None):
        def _update(dt):
            self.status_label.text = text
            if color:
                self.status_label.color = color
        Clock.schedule_once(_update, 0)

    # ---------- 下载逻辑 ----------
    def start_download(self, instance):
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._set_status('请输入有效的book id', COLORS['error'])
            return

        # 记住book_id
        self._settings['last_book_id'] = book_id
        save_settings(self._settings)

        self.download_btn.disabled = True
        self.progress_bar.value = 0
        self._set_status('正在获取书籍信息...', COLORS['accent'])
        self._append_output(f'\n[color=#5a8ab5]━━━ 开始下载book id: {book_id} ━━━[/color]\n')
        threading.Thread(target=self._download_novel, args=(book_id,), daemon=True).start()

    def _download_novel(self, book_id):
        try:
            # 获取书籍信息
            info = get_book_info(book_id)
            title = info['title']
            author = info['author']
            intro = info.get('docs', '').replace('\n', ' ')
            self._append_output(
                f'[b]书名:[/b] {title}\n'
                f'[b]作者:[/b] {author}\n'
                f'[b]简介:[/b] {intro[:120]}{"..." if len(intro) > 120 else ""}\n'
            )

            # 获取章节列表
            chapters_data = get_chapter_list(book_id)
            chapters = []
            for vol in chapters_data:
                if isinstance(vol, list):
                    chapters.extend(vol)
                elif isinstance(vol, dict):
                    chapters.append(vol)

            total = len(chapters)
            self._append_output(f'[b]共 {total} 章[/b]，开始下载...\n\n')
            self._set_status(f'第0/{total} 章', COLORS['accent'])

            safe_title = clean_filename(title)
            output_dir = get_download_dir()
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{safe_title}.txt")

            self._append_output(f'[b]保存路径:[/b] {output_dir}\n\n')

            # 写文件头
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{title}\n作者: {author}\n简介:\n{intro}\n\n")

                BATCH = 30
                for start in range(1, total + 1, BATCH):
                    end = min(start + BATCH - 1, total)
                    try:
                        batch = get_chapter_contents_batch(book_id, start, end)
                    except Exception as e:
                        self._append_output(f'[color=#cc4444]批量 {start}-{end} 失败: {e}[/color]\n')
                        continue

                    chap_dict = {int(item['chapter']): item for item in batch if item.get('chapter')}
                    for idx in range(start, end + 1):
                        info_chap = chap_dict.get(idx)
                        orig = next((ch for ch in chapters if ch.get('index') == idx), None)
                        chap_title = orig['title'] if orig else (
                            info_chap.get('chapter_title', f'第{idx}章') if info_chap else f'第{idx}章'
                        )
                        percent = (idx / total) * 100
                        self._set_status(f'⬇ {idx}/{total} ({percent:.1f}%)', COLORS['accent'])
                        self._update_progress(percent)

                        if info_chap:
                            content = clean_content(info_chap.get('content', ''))
                            if content.lstrip().startswith(chap_title):
                                content = content.lstrip()[len(chap_title):].strip()
                            f.write(f"{chap_title}\n{content}\n\n")
                        else:
                            f.write(f"{chap_title}\n[内容缺失]\n\n")

            self._update_progress(100)
            self._set_status(f'下载了{total}章', COLORS['success'])
            self._append_output(
                f'\n[color=#4db86b]下载完成！[/color]\n'
                f'[b]文件:[/b] {output_file}\n'
                f'[b]章节:[/b] {total}\n'
                f'[b]目录:[/b] {output_dir}\n\n'
            )
        except Exception as e:
            self._update_progress(0)
            self._set_status(f'下载失败', COLORS['error'])
            self._append_output(f'\n[color=#cc4444]下载失败: {str(e)}[/color]\n\n')
        finally:
            def enable_btn(dt):
                self.download_btn.disabled = False
            Clock.schedule_once(enable_btn, 0)


class TomatoNovelApp(App):
    def build(self):
        self.title = 's丶ky书包'

        # ---- 注册中文字体（使用系统字体，零体积） ----
        font_path = _find_system_chinese_font()
        if font_path:
            try:
                LabelBase.register(name='Roboto', fn_regular=font_path)
                print(f'[Font] 注册了字体: {font_path}')
            except Exception as e:
                print(f'[Font] 字体注册失败: {e}')
        else:
            print('[Font] 未找到中文字体')

        # ---- Android 权限请求 ----
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                permissions_needed = [
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE,
                ]
                try:
                    permissions_needed.extend([
                        Permission.READ_MEDIA_IMAGES,
                        Permission.READ_MEDIA_VIDEO,
                        Permission.READ_MEDIA_AUDIO,
                    ])
                except Exception:
                    pass
                request_permissions(permissions_needed)
            except Exception as e:
                print(f'[Perm] 权限请求失败: {e}')

        return NovelDownloader()


if __name__ == '__main__':
    TomatoNovelApp().run()