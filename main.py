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


# ============== KivyMD 现代化前端 ==============

class NovelDownloader(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.md_bg_color = BG_PRIMARY

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

        # 标题装饰条
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
            text='v1.3.1 | 桀桀桀桀桀',
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
            height=dp(180),
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

        self.download_btn = MDRaisedButton(
            text='开始下载',
            md_bg_color=ACCENT,
            text_color=TEXT_WHITE,
            font_size='16sp',
            size_hint=(1, None),
            height=dp(48)
        )
        self.download_btn.bind(on_press=self.start_download)

        input_card.add_widget(input_hint)
        input_card.add_widget(self.book_id_input)
        input_card.add_widget(self.download_btn)

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

        # 日志头部
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

        # 进度条
        self.progress_bar = MDProgressBar(
            value=0,
            color=ACCENT,
            size_hint_y=None,
            height=dp(4)
        )

        # 输出文本标签
        self.output_label = MDLabel(
            text = '[color=666688]book id获取方法：\n1.点击小说界面右上角分享，选择复制链接\n2.在浏览器打开该链接，然后复制加载后的地址\n3.地址前几行book id=后的数字即为该书id[/color]',
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

        # 滚动容器
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

    # ============== 交互逻辑（完全未修改） ==============

    def start_download(self, instance):
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._append_output("[color=e94545]请输入有效的book id[/color]\n")
            return
        self.download_btn.disabled = True
        self.download_btn.text = '下载中...'
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
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{safe_title}.txt")

            self._append_output(f"[color=666688]保存路径: {output_dir}[/color]\n")

            with open(output_file, 'w', encoding='utf-8') as f:
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
                        info = chap_dict.get(idx)
                        orig = next((ch for ch in chapters if ch.get('index') == idx), None)
                        chap_title = orig['title'] if orig else info.get('chapter_title', f'第{idx}章')
                        percent = (idx / total) * 100

                        def _upd(dt, p=percent, i=idx, t=total):
                            self._set_output(
                                f"[color=4da6e8]下载进度[/color]  "
                                f"[b][color=4de8a2]{p:.1f}%[/color][/b]\n"
                                f"[color=888899]正在处理: {i}/{t}[/color]"
                            )
                            self.progress_bar.value = p

                        Clock.schedule_once(_upd, 0)

                        if info:
                            content = clean_content(info.get('content', ''))
                            if content.lstrip().startswith(chap_title):
                                content = content.lstrip()[len(chap_title):].strip()
                            f.write(f"{chap_title}\n{content}\n\n")
                        else:
                            f.write(f"{chap_title}\n[内容缺失]\n\n")

                self._append_output(
                    f"\n[color=33e87a]下载完成！[/color]\n"
                    f"[color=666688]文件: {output_file}[/color]\n"
                )
        except Exception as e:
            self._append_output(f"[color=e94545]下载失败: {str(e)}[/color]\n")
        finally:
            def enable_btn(dt):
                self.download_btn.disabled = False
                self.download_btn.text = '开始下载'
                self.status_label.text = '就绪'
                self.status_label.text_color = SUCCESS
                self.progress_bar.value = 100
                self.progress_bar.color = SUCCESS
            Clock.schedule_once(enable_btn, 0)


# ============== 应用入口 ==============

class TomatoNovelApp(MDApp):
    def build(self):
        # KivyMD 主题配置
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.accent_palette = "Teal"

        try:
            LabelBase.register(name='Roboto', fn_regular='font.ttf')
        except:
            pass

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