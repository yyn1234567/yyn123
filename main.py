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


# ============== 后端逻辑 ==============

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
    raise Exception(f"批量获取章节失败: {str(e)}")


def clean_content(content):
    content = content.replace('</p><p>', '\n').replace('<p>', '').replace('</p>', '\n')
    content = re.sub(re.compile('<.*?>'), '', content)
    content = re.sub(r'\n+', '\n', content).strip()
    return content


def get_download_dir():
    """获取下载目录，兼容Android 11+ scoped storage"""
    try:
        if platform == 'android':
            from jnius import autoclass
            Environment = autoclass('android.os.Environment')
            Build = autoclass('android.os.Build')
            
            # Android 11+ 检查是否有文件管理权限
            has_manager_permission = False
            if Build.VERSION.SDK_INT >= 30:
                try:
                    has_manager_permission = Environment.isExternalStorageManager()
                except Exception as e:
                    print(f"检查MANAGE_EXTERNAL_STORAGE权限失败: {e}")
                    has_manager_permission = False
            
            # 检查外部存储是否可用
            if Environment.getExternalStorageState() == Environment.MEDIA_MOUNTED:
                external_storage = Environment.getExternalStorageDirectory().getAbsolutePath()
                download_dir = os.path.join(external_storage, 'Download', 'novels')
                
                # 尝试创建目录并测试写入权限
                try:
                    os.makedirs(download_dir, exist_ok=True)
                    test_file = os.path.join(download_dir, '.permission_test')
                    with open(test_file, 'w', encoding='utf-8') as f:
                        f.write('permission_test')
                    os.remove(test_file)
                    print(f"✅ 外部存储写入成功: {download_dir}")
                    return download_dir
                except OSError as e:
                    print(f"⚠️ 外部存储写入失败 (errno={e.errno}): {e}")
                    if Build.VERSION.SDK_INT >= 30 and not has_manager_permission:
                        print("💡 提示: Android 11+需要'所有文件访问'权限")
            
            # 回退到应用私有目录
            private_dir = os.path.join(App.get_running_app().user_data_dir, 'novels')
            os.makedirs(private_dir, exist_ok=True)
            print(f"✅ 使用私有目录: {private_dir}")
            return private_dir
            
        else:
            # 桌面端
            downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            return os.path.join(downloads, 'novels')
            
    except Exception as e:
        print(f"⚠️ 获取下载目录异常: {e}")
        try:
            private_dir = os.path.join(App.get_running_app().user_data_dir, 'novels')
            os.makedirs(private_dir, exist_ok=True)
            return private_dir
        except:
            return os.path.join(os.getcwd(), 'novels')


def request_manage_storage_permission():
    """请求MANAGE_EXTERNAL_STORAGE权限（Android 11+）"""
    if platform != 'android':
        return
    
    try:
        from jnius import autoclass
        Build = autoclass('android.os.Build')
        
        # 只在Android 11+执行
        if Build.VERSION.SDK_INT < 30:
            print("ℹ️ Android 11以下，跳过MANAGE_EXTERNAL_STORAGE检查")
            return
        
        Environment = autoclass('android.os.Environment')
        
        # 检查是否已有权限
        if Environment.isExternalStorageManager():
            print("✅ 已有MANAGE_EXTERNAL_STORAGE权限")
            return
        
        # 没有权限，引导用户到系统设置页面
        print("⚠️ 需要用户手动授予'所有文件访问'权限")
        Intent = autoclass('android.content.Intent')
        Settings = autoclass('android.provider.Settings')
        Uri = autoclass('android.net.Uri')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        
        intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
        uri = Uri.fromParts("package", PythonActivity.mActivity.getPackageName(), None)
        intent.setData(uri)
        PythonActivity.mActivity.startActivity(intent)
        
        print("📱 已打开系统设置页面，请手动开启'所有文件访问'权限")
        
    except Exception as e:
        print(f"⚠️ 请求MANAGE_EXTERNAL_STORAGE权限失败: {e}")


# ============== KivyMD 现代化前端 ==============

class NovelDownloader(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.md_bg_color = BG_PRIMARY
        self._is_downloading = False

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
            text='v1.3.3 | 桀桀桀桀桀',
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

    # ============== 交互逻辑 ==============

    def start_download(self, instance):
        if self._is_downloading:
            return
        
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._append_output("[color=e94545]请输入有效的book id[/color]\n")
            return
        self._is_downloading = True
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

            # 预先删除可能存在的旧文件（避免某些文件系统的怪异行为）
            try:
                if os.path.exists(output_file):
                    os.remove(output_file)
                    print(f"已删除旧文件: {output_file}")
            except Exception as e:
                print(f"删除旧文件失败: {e}")

            # 尝试打开文件写入
            file_handle = None
            try:
                file_handle = open(output_file, 'w', encoding='utf-8')
            except PermissionError as pe:
                self._append_output(
                    f"[color=e94545]权限不足，无法写入外部存储[/color]\n"
                    f"[color=e94545]错误: {pe}[/color]\n"
                    f"[color=4da6e8]正在尝试使用应用私有目录...[/color]\n"
                )
                # 回退到应用私有目录
                output_dir = os.path.join(App.get_running_app().user_data_dir, 'novels')
                os.makedirs(output_dir, exist_ok=True)
                output_file = os.path.join(output_dir, f"{safe_title}.txt")
                self._append_output(f"[color=666688]新保存路径: {output_dir}[/color]\n")
                file_handle = open(output_file, 'w', encoding='utf-8')
            except OSError as ose:
                self._append_output(
                    f"[color=e94545]文件系统错误: {ose}[/color]\n"
                    f"[color=4da6e8]正在尝试使用应用私有目录...[/color]\n"
                )
                # 回退到应用私有目录
                output_dir = os.path.join(App.get_running_app().user_data_dir, 'novels')
                os.makedirs(output_dir, exist_ok=True)
                output_file = os.path.join(output_dir, f"{safe_title}.txt")
                self._append_output(f"[color=666688]新保存路径: {output_dir}[/color]\n")
                file_handle = open(output_file, 'w', encoding='utf-8')

            with file_handle as f:
                f.write(f"{title}\n作者: {author}\n简介:\n{intro}\n\n")

                BATCH = 30
                failed_batches = []
                for start in range(1, total + 1, BATCH):
                    end = min(start + BATCH - 1, total)
                    try:
                        batch = get_chapter_contents_batch(book_id, start, end)
                    except Exception as e:
                        self._append_output(f"[color=e94545]批量 {start}-{end} 失败: {e}[/color]\n")
                        failed_batches.append((start, end))
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

                # 下载完成提示
                if failed_batches:
                    self._append_output(
                        f"\n[color=e9a545]下载完成（部分失败）[/color]\n"
                        f"[color=e94545]失败批次: {failed_batches}[/color]\n"
                        f"[color=666688]文件: {output_file}[/color]\n"
                    )
                else:
                    self._append_output(
                        f"\n[color=33e87a]下载完成！[/color]\n"
                        f"[color=666688]文件: {output_file}[/color]\n"
                    )

        except Exception as e:
            self._append_output(f"[color=e94545]下载失败: {str(e)}[/color]\n")
            import traceback
            print(f"下载异常详情:\n{traceback.format_exc()}")
        finally:
            def enable_btn(dt):
                self._is_downloading = False
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

        # 注册支持中文的字体覆盖默认 Roboto
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

        # 将所有 KivyMD 主题字体样式统一指向 'Roboto'
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
                print("✅ 基础存储权限已请求")
            except Exception as e:
                print(f"⚠️ 基础权限请求失败: {e}")
            
            # Android 11+ 请求 MANAGE_EXTERNAL_STORAGE 权限
            # 这个权限需要通过系统设置页面手动授予
            Clock.schedule_once(lambda dt: request_manage_storage_permission(), 2)

        return NovelDownloader()


if __name__ == '__main__':
    TomatoNovelApp().run()