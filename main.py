#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os, time, re, threading
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.utils import platform
from kivy.graphics import Color, Rectangle, Line, RoundedRectangle
from kivy.properties import NumericProperty

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


class GradientBoxLayout(BoxLayout):
    """带渐变背景的BoxLayout"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self.color1 = Color(rgba=(0.05, 0.12, 0.18, 1))
            self.rect1 = Rectangle(pos=self.pos, size=self.size)
            self.color2 = Color(rgba=(0.08, 0.18, 0.25, 0.7))
            self.rect2 = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_rect, size=self.update_rect)
    
    def update_rect(self, *args):
        self.rect1.pos = self.pos
        self.rect1.size = self.size
        self.rect2.pos = self.pos
        self.rect2.size = self.size


class CardBox(BoxLayout):
    """卡片式容器"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [20, 20, 20, 20]
        self.spacing = 15
        
        with self.canvas.before:
            Color(rgba=(0.97, 0.98, 1.0, 1))
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[15, 15, 15, 15])
            Color(rgba=(0.1, 0.15, 0.2, 0.1))
            self.shadow = RoundedRectangle(pos=(self.x-4, self.y-4), size=self.size, radius=[15, 15, 15, 15])
        self.bind(pos=self.update_rect, size=self.update_rect)
    
    def update_rect(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.shadow.pos = self.x-4, self.y-4
        self.shadow.size = self.size


class ModernTextInput(TextInput):
    """现代化输入框"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0.94, 0.96, 0.98, 1)
        self.foreground_color = (0.15, 0.25, 0.35, 1)
        self.cursor_color = (0.18, 0.55, 0.65, 1)
        self.hint_text_color = (0.5, 0.6, 0.7, 0.8)
        self.multiline = False
        self.padding = [15, 12, 15, 12]
        self.size_hint = (1, None)
        self.height = 50
        self.font_size = '15sp'
        
        with self.canvas.before:
            self.border_color = Color(rgba=(0.6, 0.8, 0.85, 0.8))
            self.border = Line(rectangle=(self.x, self.y, self.width, self.height), width=1.5)
        self.bind(pos=self.update_border, size=self.update_border, focus=self.on_focus)
    
    def update_border(self, *args):
        self.border.rectangle = (self.x, self.y, self.width, self.height)
    
    def on_focus(self, instance, value):
        if value:
            self.border_color.rgba = (0.15, 0.5, 0.6, 1)
        else:
            self.border_color.rgba = (0.6, 0.8, 0.85, 0.8)


class ModernButton(Button):
    """现代化按钮"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.size_hint = (1, None)
        self.height = 52
        self.font_size = '16sp'
        self.bold = True
        self.color = (1, 1, 1, 1)
        
        with self.canvas.before:
            self.bg_color = Color(rgba=(0.18, 0.6, 0.7, 1))
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[26, 26, 26, 26])
        self.bind(pos=self.update_rect, size=self.update_rect, state=self.on_state)
    
    def update_rect(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
    
    def on_state(self, instance, value):
        if value == 'down':
            self.bg_color.rgba = (0.12, 0.5, 0.6, 1)
        elif value == 'normal':
            if self.disabled:
                self.bg_color.rgba = (0.4, 0.5, 0.6, 0.5)
            else:
                self.bg_color.rgba = (0.18, 0.6, 0.7, 1)


class OutputLabel(Label):
    """输出标签"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.color = (0.18, 0.28, 0.38, 1)
        self.halign = 'left'
        self.valign = 'top'
        self.text_size = (None, None)
        self.padding = [12, 10]
        self.size_hint_y = None
        self.font_size = '14sp'
        self.height = self.texture_size[1] if self.texture_size else 0
        self.bind(texture_size=self._update_height)
    
    def _update_height(self, instance, value):
        self.height = value[1]


class ModernScrollView(ScrollView):
    """现代化滚动视图"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, 1)
        self.do_scroll_x = False
        self.scroll_type = ['content', 'bars']
        self.bar_width = 6
        self.bar_color = (0.18, 0.5, 0.6, 0.8)
        self.bar_inactive_color = (0.3, 0.5, 0.6, 0.3)
        
        with self.canvas.before:
            Color(rgba=(0.93, 0.96, 1.0, 1))
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[12, 12, 12, 12])
        self.bind(pos=self.update_rect, size=self.update_rect)
    
    def update_rect(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size


class Separator(BoxLayout):
    """分隔线"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, None)
        self.height = 1
        
        with self.canvas.before:
            Color(rgba=(0.7, 0.8, 0.85, 0.5))
            self.line = Line(points=[0, 0, 0, 0], width=1)
        self.bind(pos=self.update_line, size=self.update_line)
    
    def update_line(self, *args):
        self.line.points = [self.x, self.centery, self.right, self.centery]


class NovelDownloader(GradientBoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=[15, 20, 15, 15], spacing=10, **kwargs)
        
        # 添加顶部标题区域
        header_layout = BoxLayout(orientation='vertical', size_hint=(1, None), height=75, spacing=5)
        self.add_widget(header_layout)
        
        self.title_label = Label(
            text='fq v1.2.1',
            size_hint=(1, None),
            height=40,
            bold=True,
            font_size='24sp',
            color=(0.2, 0.6, 0.7, 1),
            halign='center'
        )
        header_layout.add_widget(self.title_label)
        
        self.subtitle_label = Label(
            text='请输入book id',
            size_hint=(1, None),
            height=30,
            font_size='13sp',
            color=(0.5, 0.65, 0.75, 1),
            halign='center'
        )
        header_layout.add_widget(self.subtitle_label)
        
        # 创建卡片容器
        self.card = CardBox(size_hint=(1, None), height=200)
        self.add_widget(self.card)
        
        # 输入框标签
        input_label = Label(
            text='book id',
            size_hint=(1, None),
            height=25,
            font_size='13sp',
            color=(0.35, 0.5, 0.6, 1),
            halign='left',
            text_size=(None, None)
        )
        self.card.add_widget(input_label)
        
        # 添加输入框
        self.book_id_input = ModernTextInput(hint_text='请输入book id')
        self.card.add_widget(self.book_id_input)
        
        # 添加下载按钮
        self.download_btn = ModernButton(text='开始下载')
        self.download_btn.bind(on_press=self.start_download)
        self.card.add_widget(self.download_btn)
        
        # 添加输出区域标题
        output_header = BoxLayout(orientation='horizontal', size_hint=(1, None), height=35, spacing=10)
        self.add_widget(output_header)
        
        output_label = Label(
            text='下载进度',
            size_hint=(1, 1),
            font_size='14sp',
            color=(0.35, 0.5, 0.6, 1),
            halign='left',
            text_size=(None, None)
        )
        output_header.add_widget(output_label)
        
        # 添加状态指示
        self.status_label = Label(
            text='●',
            size_hint=(None, 1),
            width=20,
            font_size='12sp',
            color=(0.4, 0.8, 0.6, 1)
        )
        output_header.add_widget(self.status_label)
        
        # 添加分隔线
        self.add_widget(Separator())
        
        # 添加滚动视图
        self.output_label = OutputLabel(text='')
        self.scroll_view = ModernScrollView()
        self.scroll_view.add_widget(self.output_label)
        self.add_widget(self.scroll_view)
        
        self._update_event = None

    def start_download(self, instance):
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._append_output("请输入有效的book id\n")
            return
        self.download_btn.disabled = True
        self.status_label.color = (0.9, 0.6, 0.2, 1)
        self._append_output("正在获取书籍信息...\n")
        threading.Thread(target=self._download_novel, args=(book_id,), daemon=True).start()

    def _append_output(self, text):
        def _update(dt):
            self.output_label.text += text
            self.output_label.texture_update()
            self.output_label.height = max(self.output_label.texture_size[1], self.scroll_view.height - 20)
            self.scroll_view.scroll_y = 0
        Clock.schedule_once(_update, 0)

    def _set_output(self, text):
        def _update(dt):
            self.output_label.text = text
            self.output_label.texture_update()
            self.output_label.height = max(self.output_label.texture_size[1], self.scroll_view.height - 20)
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

            # 使用新的下载路径函数
            output_dir = get_download_dir()
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{safe_title}.txt")

            # 显示实际保存路径
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

                self._append_output(f"\n下载完成！\n文件: {output_file}\n")
        except Exception as e:
            self._append_output(f"\n下载失败: {str(e)}\n")
        finally:
            def enable_btn(dt):
                self.download_btn.disabled = False
                self.status_label.color = (0.4, 0.8, 0.6, 1)
            Clock.schedule_once(enable_btn, 0)

class TomatoNovelApp(App):
    def build(self):
        # 注册中文字体（确保 font.ttf 存在）
        try:
            LabelBase.register(name='Roboto', fn_regular='font.ttf')
        except:
            pass

        # Android平台请求权限
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission

                # 请求存储权限，兼容Android 15
                permissions_needed = [
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE
                ]

                # Android 13+ 需要新的媒体权限
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