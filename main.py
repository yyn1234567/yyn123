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
from kivy.core.window import Window
from kivy.utils import platform
from kivy.graphics import Color, RoundedRectangle, Rectangle

# ============================================================
# 颜色主题常量（温暖阅读风 / Warm Reading）
# ============================================================
COLOR_BG = (0.961, 0.941, 0.922, 1)  # 暖米色背景 #F5F0EB
COLOR_CARD = (1, 1, 1, 1)  # 白色卡片
COLOR_PRIMARY = (0.784, 0.475, 0.255, 1)  # 主按钮陶土色 #C87941
COLOR_PRIMARY_DOWN = (0.659, 0.365, 0.180, 1)  # 按下加深 #A85D2E
COLOR_PRIMARY_DISABLED = (0.82, 0.78, 0.75, 1)  # 禁用灰 #D1C7BF
COLOR_TITLE = (0.290, 0.188, 0.157, 1)  # 标题深棕 #4A3028
COLOR_BODY = (0.361, 0.251, 0.200, 1)  # 正文棕 #5C4033
COLOR_SUBTLE = (0.549, 0.482, 0.459, 1)  # 次要文字 #8C7B75
COLOR_INPUT_BORDER = (0.867, 0.831, 0.800, 1)  # 输入框边框 #DDD4CC
COLOR_INPUT_FOCUS = (0.784, 0.475, 0.255, 1)  # 焦点边框（同主色）
COLOR_OUTPUT_BG = (0.980, 0.976, 0.969, 1)  # 输出区背景 #FBFAF8
COLOR_SUCCESS = (0.357, 0.549, 0.353, 1)  # 成功绿 #5B8C5A
COLOR_ERROR = (0.753, 0.224, 0.169, 1)  # 错误红 #C0392B
COLOR_WHITE = (1, 1, 1, 1)
COLOR_SEPARATOR = (0.89, 0.86, 0.83, 1)  # 分隔线 #E3DBD4

# ============================================================
# 后端函数（完全保持不变）
# ============================================================
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


# ============================================================
# 自定义UI组件（前端美化）
# ============================================================

class RoundedButton(Button):
    """圆角按钮，支持按压反馈与禁用态"""

    def __init__(self, bg_color=COLOR_PRIMARY, text_color=COLOR_WHITE,
                 radius=14, **kwargs):
        super().__init__(**kwargs)
        self._bg_normal = bg_color
        self._bg_down = COLOR_PRIMARY_DOWN
        self._bg_disabled = COLOR_PRIMARY_DISABLED
        self._radius = radius
        self._text_color = text_color

        # 移除原生背景
        self.background_normal = ''
        self.background_down = ''
        self.background_disabled_normal = ''
        self.background_color = (0, 0, 0, 0)

        self.color = self._text_color
        self.bold = True

        with self.canvas.before:
            self._btn_color = Color(*self._bg_normal)
            self._btn_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self._radius]
            )
        self.bind(pos=self._update_rect, size=self._update_rect,
                  state=self._on_state_change,
                  disabled=self._on_disabled_change)

    def _update_rect(self, *args):
        self._btn_rect.pos = self.pos
        self._btn_rect.size = self.size

    def _on_state_change(self, instance, state):
        if self.disabled:
            return
        if state == 'down':
            self._btn_color.rgba = self._bg_down
        else:
            self._btn_color.rgba = self._bg_normal

    def _on_disabled_change(self, instance, disabled):
        if disabled:
            self._btn_color.rgba = self._bg_disabled
            self.color = (0.75, 0.72, 0.70, 1)
        else:
            self._btn_color.rgba = self._bg_normal
            self.color = self._text_color


class RoundedTextInput(TextInput):
    """圆角输入框，支持焦点边框变色"""

    def __init__(self, radius=12, **kwargs):
        super().__init__(**kwargs)
        self._radius = radius
        self._border_color = COLOR_INPUT_BORDER
        self._focus_color = COLOR_INPUT_FOCUS

        # 移除原生背景
        self.background_normal = ''
        self.background_active = ''
        self.background_color = (0, 0, 0, 0)
        self.foreground_color = COLOR_BODY
        self.cursor_color = COLOR_PRIMARY
        self.padding = [14, 12, 14, 12]
        self.font_size = '15sp'

        with self.canvas.before:
            # 白色背景
            self._bg_color = Color(*COLOR_CARD)
            self._bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self._radius]
            )
            # 边框
            self._border_color_inst = Color(*self._border_color)
            self._border_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self._radius]
            )
            # 内部填充（通过绘制稍小的矩形来模拟边框效果）
            # 实际上用双层圆角矩形：底层为边框色，上层为填充色（略小）

        self.bind(pos=self._update_rects, size=self._update_rects,
                  focus=self._on_focus_change)

    def _update_rects(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._border_rect.pos = self.pos
        self._border_rect.size = self.size

    def _on_focus_change(self, instance, focused):
        if focused:
            self._border_color_inst.rgba = self._focus_color
        else:
            self._border_color_inst.rgba = self._border_color

    def _refresh_border_thickness(self):
        """通过重绘实现细边框：先画边框色大矩形，再画填充色略小矩形"""
        pass  # 简化处理，使用单层圆角矩形 + 后续优化


class StyledScrollView(ScrollView):
    """带浅色背景的滚动视图"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bar_width = 8
        self.bar_color = COLOR_SUBTLE[:3] + (0.5,)
        self.bar_inactive_color = COLOR_SUBTLE[:3] + (0.25,)
        self.scroll_type = ['bars', 'content']

        with self.canvas.before:
            self._sv_bg_color = Color(*COLOR_OUTPUT_BG)
            self._sv_bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *args):
        self._sv_bg_rect.pos = self.pos
        self._sv_bg_rect.size = self.size


# ============================================================
# 主界面（UI 美化，后端逻辑完全不变）
# ============================================================

class NovelDownloader(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=18, spacing=10, **kwargs)

        # ---------- 主背景 ----------
        with self.canvas.before:
            Color(*COLOR_BG)
            self._main_bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_main_bg, size=self._update_main_bg)

        # ---------- 标题区 ----------
        title_box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=56,
            spacing=10
        )
        # 图标
        icon_label = Label(
            text='📖',
            font_size='26sp',
            size_hint_x=None, width=44,
            bold=True,
            color=COLOR_TITLE
        )
        title_box.add_widget(icon_label)
        # 标题文字（垂直排列）
        title_text_box = BoxLayout(orientation='vertical', spacing=0)
        title_text_box.add_widget(Label(
            text='s丶ky书包',
            font_size='20sp',
            bold=True,
            color=COLOR_TITLE,
            halign='left', valign='bottom',
            size_hint_y=0.6
        ))
        title_text_box.add_widget(Label(
            text='桀桀桀',
            font_size='12sp',
            color=COLOR_SUBTLE,
            halign='left', valign='top',
            size_hint_y=0.4
        ))
        title_box.add_widget(title_text_box)
        self.add_widget(title_box)

        # ---------- 细分隔线 ----------
        sep = Widget(size_hint_y=None, height=1)
        with sep.canvas:
            Color(*COLOR_SEPARATOR)
            Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda s, v: s.canvas.children[-1].__setattr__('pos', v),
                 size=lambda s, v: s.canvas.children[-1].__setattr__('size', v))
        self.add_widget(sep)

        # ---------- 输入区域 ----------
        input_box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=52,
            spacing=10
        )
        self.book_id_input = RoundedTextInput(
            hint_text='请输入 book id...',
            multiline=False,
            size_hint_x=0.68
        )
        input_box.add_widget(self.book_id_input)

        self.download_btn = RoundedButton(
            text='开始下载',
            size_hint_x=0.32,
            font_size='16sp'
        )
        self.download_btn.bind(on_press=self.start_download)
        input_box.add_widget(self.download_btn)
        self.add_widget(input_box)

        # ---------- 状态提示 ----------
        self.status_label = Label(
            text='● 等待输入',
            font_size='13sp',
            color=COLOR_SUBTLE,
            size_hint_y=None, height=28,
            halign='left', valign='middle'
        )
        self.add_widget(self.status_label)

        # ---------- 输出区域 ----------
        self.output_label = Label(
            text='',
            size_hint_y=None,
            halign='left', valign='top',
            color=COLOR_BODY,
            font_size='14sp',
            padding=(14, 12),
            markup=False
        )
        self.output_label.bind(
            texture_size=lambda instance, value:
            setattr(instance, 'height', instance.texture_size[1] + 24)
        )

        self.scroll_view = StyledScrollView(size_hint=(1, 1))
        self.scroll_view.add_widget(self.output_label)
        self.add_widget(self.scroll_view)

        # ---------- 底部版本信息 ----------
        version_label = Label(
            text='fq v1.2.3  ·  powered by oiapi',
            font_size='10sp',
            color=COLOR_SUBTLE[:3] + (0.55,),
            size_hint_y=None, height=22,
            halign='center', valign='middle'
        )
        self.add_widget(version_label)

        self._update_event = None

    def _update_main_bg(self, *args):
        self._main_bg.pos = self.pos
        self._main_bg.size = self.size

    # ========== 以下方法逻辑完全不变 ==========

    def start_download(self, instance):
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._append_output("⚠️ 请输入有效的 book id\n")
            self.status_label.text = '⚠️ 请输入有效的 book id'
            self.status_label.color = COLOR_ERROR
            return
        self.download_btn.disabled = True
        self.status_label.text = '⏳ 正在获取书籍信息...'
        self.status_label.color = COLOR_PRIMARY
        self._append_output("正在获取书籍信息...\n")
        threading.Thread(target=self._download_novel, args=(book_id,), daemon=True).start()

    def _append_output(self, text):
        def _update(dt):
            self.output_label.text += text
            self.output_label.texture_update()
            self.output_label.height = self.output_label.texture_size[1] + 24
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
            output_dir = get_download_dir()
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{safe_title}.txt")
            self._append_output(f"保存路径: {output_dir}\n")

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
                            f.write(f"{chap_title}\n{content}\n\n")
                        else:
                            f.write(f"{chap_title}\n[内容缺失]\n\n")

            self._append_output(f"\n✅ 下载完成！\n📁 文件: {output_file}\n")
            Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', '✅ 下载完成！'), 0)
            Clock.schedule_once(lambda dt: setattr(self.status_label, 'color', COLOR_SUCCESS), 0)
        except Exception as e:
            self._append_output(f"\n❌ 下载失败: {str(e)}\n")
            Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', f'❌ 下载失败: {str(e)[:40]}'), 0)
            Clock.schedule_once(lambda dt: setattr(self.status_label, 'color', COLOR_ERROR), 0)
        finally:
            def enable_btn(dt):
                self.download_btn.disabled = False
            Clock.schedule_once(enable_btn, 0)


# ============================================================
# App 入口
# ============================================================

class TomatoNovelApp(App):
    def build(self):
        # 设置窗口背景色
        Window.clearcolor = COLOR_BG

        # 注册中文字体（确保 font.ttf 存在）
        try:
            LabelBase.register(name='Roboto', fn_regular='font.ttf')
        except:
            pass

        # Android 平台请求权限
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