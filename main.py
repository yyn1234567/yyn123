#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.utils import platform
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.core.window import Window

# ============== 配色方案 ==============
BG_PRIMARY    = (0.067, 0.067, 0.118, 1)   # 深蓝黑背景
BG_CARD       = (0.106, 0.114, 0.196, 1)   # 卡片背景
ACCENT        = (0.298, 0.643, 0.918, 1)   # 主题蓝
ACCENT_PRESS  = (0.200, 0.480, 0.780, 1)   # 按下蓝色
SUCCESS       = (0.298, 0.780, 0.549, 1)   # 成功绿
DANGER        = (0.914, 0.271, 0.271, 1)   # 警告红
TEXT_WHITE     = (0.957, 0.957, 0.973, 1)   # 主文字
TEXT_GRAY      = (0.580, 0.600, 0.675, 1)   # 辅助文字
INPUT_BG      = (0.125, 0.133, 0.231, 1)   # 输入框背景
INPUT_BORDER  = (0.220, 0.240, 0.360, 1)   # 输入框边框
SCROLL_BG     = (0.086, 0.090, 0.157, 1)   # 滚动区背景
DIVIDER       = (0.200, 0.220, 0.340, 1)   # 分隔线

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
            from android.permissions import check_permission, Permission
            if Environment.getExternalStorageState() == Environment.MEDIA_MOUNTED:
                external_storage = Environment.getExternalStorageDirectory().getAbsolutePath()
                download_dir = os.path.join(external_storage, 'Download', 'novels')
                test_file = os.path.join(download_dir, '.test')
                try:
                    os.makedirs(download_dir, exist_ok=True)
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    return download_dir
                except:
                    pass
            return os.path.join(App.get_running_app().user_data_dir, 'novels')
        else:
            downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            return os.path.join(downloads, 'novels')
    except Exception as e:
        try:
            return os.path.join(App.get_running_app().user_data_dir, 'novels')
        except:
            return os.path.join(os.getcwd(), 'novels')


class RoundedInput(TextInput):
    """自定义圆角输入框"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)  # 透明背景
        self.foreground_color = TEXT_WHITE
        self.cursor_color = ACCENT
        self.hint_text_color = (*TEXT_GRAY[:3], 0.6)
        self.font_size = '16sp'
        self.padding = [18, 14, 18, 14]
        self.multiline = False
        self.size_hint_y = None
        self.height = 52

    def on_size(self, *args):
        self._update_bg()

    def on_pos(self, *args):
        self._update_bg()

    def _update_bg(self):
        self.canvas.before.clear()
        with self.canvas.before:
            # 外边框
            Color(*INPUT_BORDER)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[10])
            # 内背景
            Color(*INPUT_BG)
            RoundedRectangle(
                pos=(self.x + 1, self.y + 1),
                size=(self.width - 2, self.height - 2),
                radius=[9]
            )


class RoundedButton(Button):
    """自定义圆角按钮"""
    def __init__(self, **kwargs):
        self.btn_color = kwargs.pop('btn_color', ACCENT)
        self.btn_color_press = kwargs.pop('btn_color_press', ACCENT_PRESS)
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.background_down = ''
        self.color = TEXT_WHITE
        self.font_size = '17sp'
        self.bold = True
        self.size_hint_y = None
        self.height = 52
        self._pressed = False

    def on_size(self, *args):
        self._update_bg()

    def on_pos(self, *args):
        self._update_bg()

    def on_press(self):
        self._pressed = True
        self._update_bg()

    def on_release(self):
        self._pressed = False
        self._update_bg()

    def _update_bg(self):
        self.canvas.before.clear()
        with self.canvas.before:
            c = self.btn_color_press if (self._pressed or self.disabled) else self.btn_color
            if self.disabled:
                c = (*c[:3], 0.5)
            Color(*c)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[10])


class CardBox(BoxLayout):
    """带圆角背景的卡片容器"""
    def __init__(self, **kwargs):
        card_color = kwargs.pop('card_color', BG_CARD)
        radius = kwargs.pop('radius', 12)
        self._card_color = card_color
        self._radius = radius
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*self._card_color)
            self._bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self._radius]
            )
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size


class OutputLabel(Label):
    """自定义输出标签"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.color = TEXT_WHITE
        self.font_size = '14sp'
        self.halign = 'left'
        self.valign = 'top'
        self.text_size = (None, None)
        self.markup = True
        self.line_height = 1.4


class NovelDownloader(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=0, spacing=0, **kwargs)

        # ====== 全局背景 ======
        with self.canvas.before:
            Color(*BG_PRIMARY)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

        # ====== 主内容区 ======
        main_layout = BoxLayout(
            orientation='vertical',
            padding=[16, 12, 16, 16],
            spacing=12
        )

        # ---- 顶部标题栏 ----
        header = CardBox(
            orientation='vertical',
            size_hint_y=None,
            height=90,
            padding=[20, 15, 20, 15],
            spacing=4,
            card_color=(0.114, 0.125, 0.216, 1)
        )

        # 标题装饰线
        accent_bar = Widget(size_hint_y=None, height=3)
        with accent_bar.canvas:
            Color(*ACCENT)
            RoundedRectangle(pos=accent_bar.pos, size=(0, 3), radius=[2])
        accent_bar.bind(pos=lambda w, *a: self._update_bar(w), size=lambda w, *a: self._update_bar(w))

        title_label = Label(
            text='📚  fq 小说下载器',
            font_size='22sp',
            bold=True,
            color=TEXT_WHITE,
            size_hint_y=None,
            height=36,
            halign='left',
            valign='middle'
        )
        title_label.bind(size=title_label.setter('text_size'))

        subtitle_label = Label(
            text='v1.2.6 · 输入 Book ID 即可开始下载',
            font_size='13sp',
            color=TEXT_GRAY,
            size_hint_y=None,
            height=22,
            halign='left',
            valign='middle'
        )
        subtitle_label.bind(size=subtitle_label.setter('text_size'))

        header.add_widget(accent_bar)
        header.add_widget(title_label)
        header.add_widget(subtitle_label)

        # ---- 输入区卡片 ----
        input_card = CardBox(
            orientation='vertical',
            size_hint_y=None,
            height=130,
            padding=[16, 14, 16, 14],
            spacing=10
        )

        input_label = Label(
            text='Book ID',
            font_size='13sp',
            color=TEXT_GRAY,
            size_hint_y=None,
            height=20,
            halign='left',
            valign='middle'
        )
        input_label.bind(size=input_label.setter('text_size'))

        self.book_id_input = RoundedInput(
            hint_text='请输入 Book ID ...'
        )

        self.download_btn = RoundedButton(
            text='🚀  开始下载',
            btn_color=ACCENT,
            btn_color_press=ACCENT_PRESS
        )
        self.download_btn.bind(on_press=self.start_download)

        input_card.add_widget(input_label)
        input_card.add_widget(self.book_id_input)
        input_card.add_widget(self.download_btn)

        # ---- 输出日志区 ----
        output_card = CardBox(
            orientation='vertical',
            padding=[14, 12, 14, 12],
            spacing=6,
            card_color=SCROLL_BG
        )

        output_header = BoxLayout(
            size_hint_y=None,
            height=28,
            spacing=8
        )

        output_icon = Label(
            text='📄',
            font_size='16sp',
            size_hint_x=None,
            width=30,
            halign='center'
        )
        output_icon.bind(size=output_icon.setter('text_size'))

        output_title = Label(
            text='下载日志',
            font_size='14sp',
            color=TEXT_GRAY,
            bold=True,
            halign='left',
            valign='middle'
        )
        output_title.bind(size=output_title.setter('text_size'))

        self.status_label = Label(
            text='就绪',
            font_size='12sp',
            color=SUCCESS,
            size_hint_x=None,
            width=60,
            halign='right',
            valign='middle'
        )
        self.status_label.bind(size=self.status_label.setter('text_size'))

        output_header.add_widget(output_icon)
        output_header.add_widget(output_title)
        output_header.add_widget(Widget())  # spacer
        output_header.add_widget(self.status_label)

        # 分隔线
        divider = Widget(size_hint_y=None, height=1)
        with divider.canvas:
            Color(*DIVIDER)
            self._divider_line = Rectangle(pos=divider.pos, size=(divider.width, 1))
        divider.bind(
            pos=lambda w, *a: setattr(self._divider_line, 'pos', w.pos),
            size=lambda w, *a: setattr(self._divider_line, 'size', (w.width, 1))
        )

        self.output_label = OutputLabel(
            text='[color=9999aa]欢迎使用 fq 小说下载器[/color]\n[color=666688]输入 Book ID 后点击"开始下载"[/color]',
            size_hint_y=None,
            height=200
        )

        self.scroll_view = ScrollView(
            size_hint=(1, 1),
            bar_color=(*ACCENT[:3], 0.4),
            bar_inactive_color=(*ACCENT[:3], 0.15),
            bar_width=4
        )
        self.scroll_view.add_widget(self.output_label)

        output_card.add_widget(output_header)
        output_card.add_widget(divider)
        output_card.add_widget(self.scroll_view)

        # ---- 组装主布局 ----
        main_layout.add_widget(header)
        main_layout.add_widget(input_card)
        main_layout.add_widget(output_card)

        self.add_widget(main_layout)
        self._update_event = None

    def _update_canvas(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _update_bar(self, widget):
        widget.canvas.clear()
        with widget.canvas:
            Color(*ACCENT)
            RoundedRectangle(
                pos=widget.pos,
                size=(min(widget.width, 60), 3),
                radius=[2]
            )

    def start_download(self, instance):
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._append_output("[color=e94545]⚠ 请输入有效的 Book ID[/color]\n")
            return
        self.download_btn.disabled = True
        self.download_btn.text = '⏳  下载中...'
        self.status_label.text = '下载中'
        self.status_label.color = ACCENT
        self._set_output('[color=9999aa]正在获取书籍信息...[/color]\n')
        threading.Thread(target=self._download_novel, args=(book_id,), daemon=True).start()

    def _append_output(self, text):
        def _update(dt):
            self.output_label.text += text
            self.output_label.texture_update()
            self.output_label.height = max(self.output_label.texture_size[1], 100)
            self.scroll_view.scroll_y = 0
        Clock.schedule_once(_update, 0)

    def _set_output(self, text):
        def _update(dt):
            self.output_label.text = text
            self.output_label.texture_update()
            self.output_label.height = max(self.output_label.texture_size[1], 100)
        Clock.schedule_once(_update, 0)

    def _download_novel(self, book_id):
        try:
            info = get_book_info(book_id)
            title = info['title']
            author = info['author']
            intro = info.get('docs', '').replace('\n', ' ')

            self._append_output(
                f"[color=4da6e8]📖 书名:[/color] [b]{title}[/b]\n"
                f"[color=4da6e8]✍ 作者:[/color] {author}\n"
                f"[color=4da6e8]📝 简介:[/color] {intro[:80]}...\n"
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
            self._append_output(f"[color=4da6e8]📚 共 {total} 章，开始下载...[/color]\n")

            safe_title = clean_filename(title)
            output_dir = get_download_dir()
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{safe_title}.txt")

            self._append_output(f"[color=666688]💾 保存路径: {output_dir}[/color]\n")

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{title}\n作者: {author}\n简介:\n{intro}\n\n")

                BATCH = 30
                for start in range(1, total + 1, BATCH):
                    end = min(start + BATCH - 1, total)
                    try:
                        batch = get_chapter_contents_batch(book_id, start, end)
                    except Exception as e:
                        self._append_output(f"[color=e94545]✗ 批量 {start}-{end} 失败: {e}[/color]\n")
                        continue

                    chap_dict = {int(item['chapter']): item for item in batch if item.get('chapter')}
                    for idx in range(start, end + 1):
                        info = chap_dict.get(idx)
                        orig = next((ch for ch in chapters if ch.get('index') == idx), None)
                        chap_title = orig['title'] if orig else info.get('chapter_title', f'第{idx}章')
                        percent = (idx / total) * 100

                        def _upd(dt, p=percent, i=idx, t=total):
                            self._set_output(
                                f"[color=4da6e8]⬇ 下载进度[/color]  "
                                f"[b][color=4de8a2]{p:.1f}%[/color][/b]\n"
                                f"[color=888899]正在处理: {i}/{t}[/color]"
                            )

                        Clock.schedule_once(_upd, 0)

                        if info:
                            content = clean_content(info.get('content', ''))
                            if content.lstrip().startswith(chap_title):
                                content = content.lstrip()[len(chap_title):].strip()
                            f.write(f"{chap_title}\n{content}\n\n")
                        else:
                            f.write(f"{chap_title}\n[内容缺失]\n\n")

                self._append_output(
                    f"\n[color=33e87a]✅ 下载完成！[/color]\n"
                    f"[color=666688]📁 文件: {output_file}[/color]\n"
                )
        except Exception as e:
            self._append_output(f"[color=e94545]✗ 下载失败: {str(e)}[/color]\n")
        finally:
            def enable_btn(dt):
                self.download_btn.disabled = False
                self.download_btn.text = '🚀  开始下载'
                self.status_label.text = '就绪'
                self.status_label.color = SUCCESS
            Clock.schedule_once(enable_btn, 0)


class TomatoNovelApp(App):
    def build(self):
        # 注册中文字体
        try:
            LabelBase.register(name='Roboto', fn_regular='font.ttf')
        except:
            pass

        # 设置窗口背景色
        Window.clearcolor = BG_PRIMARY

        # Android平台请求权限
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