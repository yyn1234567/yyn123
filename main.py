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
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.progressbar import MDProgressBar

# ─── SAF 辅助模块 ───
from saf_helper import SAFHelper

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


def get_private_dir():
    """获取应用私有目录（回退方案）"""
    try:
        private_dir = os.path.join(App.get_running_app().user_data_dir, 'novels')
        os.makedirs(private_dir, exist_ok=True)
        return private_dir
    except Exception:
        return os.path.join(os.getcwd(), 'novels')


# ============== KivyMD 现代化前端 ==============

class NovelDownloader(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.md_bg_color = BG_PRIMARY
        self._is_downloading = False
        self._saf = SAFHelper()
        self._current_book_id = None  # 暂存当前下载的 book_id

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
            height=dp(250),  # 增加高度以容纳新按钮
            padding=[dp(18), dp(14), dp(18), dp(14)],
            spacing=dp(10),
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

        # ─── 保存路径显示行 ───
        path_row = MDBoxLayout(
            size_hint_y=None,
            height=dp(36),
            spacing=dp(8)
        )

        path_icon_label = MDLabel(
            text='📁',
            font_style='Body1',
            size_hint_x=None,
            width=dp(24),
            halign='center'
        )

        self.save_path_label = MDLabel(
            text='点击下方按钮选择保存目录',
            font_style='Caption',
            theme_text_color='Custom',
            text_color=TEXT_GRAY,
            halign='left',
            shorten=True,
            size_hint_x=0.65
        )
        self.save_path_label.bind(
            size=lambda i, v: setattr(i, 'text_size', (i.width, None))
        )

        self.select_dir_btn = MDFlatButton(
            text='选择目录',
            text_color=TEXT_WHITE,
            md_bg_color=[0.149, 0.161, 0.259, 1],
            font_size='12sp',
            size_hint_x=0.35,
            height=dp(36)
        )
        self.select_dir_btn.bind(on_press=self._on_select_dir)

        path_row.add_widget(path_icon_label)
        path_row.add_widget(self.save_path_label)
        path_row.add_widget(self.select_dir_btn)

        # ─── 下载按钮 ───
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
        input_card.add_widget(path_row)
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

        # 初始化保存路径显示
        self._update_save_path_display()

    # ============== 保存路径管理 ==============

    def _update_save_path_display(self):
        """更新保存路径标签"""
        if self._saf.has_valid_permission():
            uri = self._saf.get_saved_uri()
            # 尝试从 URI 中提取可读的路径信息
            self.save_path_label.text = f'SAF授权目录 (已就绪)'
            self.save_path_label.text_color = SUCCESS
        elif self._saf.get_saved_uri():
            self.save_path_label.text = 'SAF授权已过期，请重新选择'
            self.save_path_label.text_color = DANGER
        else:
            self.save_path_label.text = '未选择 → 将使用应用私有目录'
            self.save_path_label.text_color = TEXT_GRAY

    def _on_select_dir(self, instance):
        """点击「选择目录」按钮"""
        if self._is_downloading:
            return
        self._append_output('[color=4da6e8]正在打开系统文件管理器，请选择一个目录...[/color]\n')
        self._saf.request_directory_access(on_result=self._on_saf_dir_selected)

    def _on_saf_dir_selected(self, success, tree_uri_str):
        """SAF 目录选择完成后的回调（主线程）"""
        if success:
            self._append_output(
                f'[color=33e87a]✅ 目录已授权！[/color]\n'
                f'[color=666688]URI: {tree_uri_str}[/color]\n'
            )
        else:
            self._append_output(
                '[color=e9a545]⚠️ 未选择目录或授权被取消，将使用应用私有目录[/color]\n'
            )
        self._update_save_path_display()

        # 如果之前有等待中的下载，现在继续
        if self._current_book_id is not None:
            bid = self._current_book_id
            self._current_book_id = None
            # 短暂延迟确保 UI 更新后再开始下载
            Clock.schedule_once(lambda dt: self._execute_download(bid), 0.3)

    # ============== 交互逻辑 ==============

    def start_download(self, instance):
        if self._is_downloading:
            return

        book_id = self.book_id_input.text.strip()
        if not book_id:
            self._append_output("[color=e94545]请输入有效的book id[/color]\n")
            return

        # 检查是否有有效的 SAF 目录权限
        if self._saf.has_valid_permission():
            # 已有权限，直接下载
            self._execute_download(book_id)
        elif self._saf.get_saved_uri():
            # 有保存的 URI 但权限已失效，提示重新选择
            self._append_output(
                '[color=e9a545]SAF目录权限已过期，请重新选择保存目录[/color]\n'
            )
            self._current_book_id = book_id
            self._on_select_dir(None)
        else:
            # 没有任何 SAF 授权，使用私有目录（自动回退）
            self._append_output(
                '[color=666688]未设置SAF目录，使用应用私有目录[/color]\n'
            )
            self._execute_download(book_id)

    def _execute_download(self, book_id):
        """实际执行下载（已确定保存路径）"""
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
        """后台下载线程"""
        use_saf = self._saf.has_valid_permission()
        saf_tree_uri = self._saf.get_saved_uri() if use_saf else None
        output_dir = None
        output_file = None
        file_handle = None

        try:
            # ── 获取书籍信息 ──
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
            safe_title = clean_filename(title)
            file_name = f"{safe_title}.txt"

            self._append_output(f"[color=4da6e8]共 {total} 章，开始下载...[/color]\n")

            if use_saf and saf_tree_uri:
                self._append_output(f"[color=666688]保存方式: SAF 授权目录[/color]\n")
            else:
                output_dir = get_private_dir()
                output_file = os.path.join(output_dir, file_name)
                self._append_output(f"[color=666688]保存路径: {output_dir}[/color]\n")
                # 删除旧文件
                try:
                    if os.path.exists(output_file):
                        os.remove(output_file)
                except Exception:
                    pass
                file_handle = open(output_file, 'w', encoding='utf-8')

            # ── 下载章节 ──
            BATCH = 30
            failed_batches = []
            content_buffer = []  # SAF 模式下先缓冲所有内容
            header_text = f"{title}\n作者: {author}\n简介:\n{intro}\n\n"

            if use_saf and saf_tree_uri:
                content_buffer.append(header_text)
            else:
                file_handle.write(header_text)

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
                    info_chap = chap_dict.get(idx)
                    orig = next((ch for ch in chapters if ch.get('index') == idx), None)
                    chap_title = orig['title'] if orig else (
                        info_chap.get('chapter_title', f'第{idx}章') if info_chap else f'第{idx}章'
                    )
                    percent = (idx / total) * 100

                    def _upd(dt, p=percent, i=idx, t=total):
                        self._set_output(
                            f"[color=4da6e8]下载进度[/color]  "
                            f"[b][color=4de8a2]{p:.1f}%[/color][/b]\n"
                            f"[color=888899]正在处理: {i}/{t}[/color]"
                        )
                        self.progress_bar.value = p

                    Clock.schedule_once(_upd, 0)

                    if info_chap:
                        content = clean_content(info_chap.get('content', ''))
                        if content.lstrip().startswith(chap_title):
                            content = content.lstrip()[len(chap_title):].strip()
                        chapter_text = f"{chap_title}\n{content}\n\n"
                    else:
                        chapter_text = f"{chap_title}\n[内容缺失]\n\n"

                    if use_saf and saf_tree_uri:
                        content_buffer.append(chapter_text)
                    else:
                        file_handle.write(chapter_text)

            # ── 完成写入 ──
            if use_saf and saf_tree_uri:
                full_content = ''.join(content_buffer)
                success = self._saf.write_file(saf_tree_uri, file_name, full_content)
                if success:
                    output_file = f"SAF目录/{file_name}"
                else:
                    # SAF 写入失败，回退到私有目录
                    self._append_output(
                        '[color=e9a545]SAF写入失败，回退到应用私有目录...[/color]\n'
                    )
                    output_dir = get_private_dir()
                    output_file = os.path.join(output_dir, file_name)
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(full_content)
            else:
                # 普通文件模式已完成写入（在循环中）
                pass

            if file_handle:
                file_handle.close()
                file_handle = None

            # ── 下载完成提示 ──
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
            if file_handle:
                try:
                    file_handle.close()
                except Exception:
                    pass

            def enable_btn(dt):
                self._is_downloading = False
                self.download_btn.disabled = False
                self.download_btn.text = '开始下载'
                self.status_label.text = '就绪'
                self.status_label.text_color = SUCCESS
                self.progress_bar.value = 100
                self.progress_bar.color = SUCCESS
                self._current_book_id = None
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

        # Android 权限请求（SAF 不需要存储权限，但保留以兼容旧设备）
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                permissions_needed = [
                    Permission.INTERNET,
                ]
                try:
                    permissions_needed.extend([
                        Permission.WRITE_EXTERNAL_STORAGE,
                        Permission.READ_EXTERNAL_STORAGE,
                    ])
                except Exception:
                    pass
                request_permissions(permissions_needed)
                print("✅ 基础权限已请求")
            except Exception as e:
                print(f"⚠️ 基础权限请求失败: {e}")

            # 不再需要 MANAGE_EXTERNAL_STORAGE，SAF 取代之
            # 但可以提示用户使用 SAF 选择目录
            Clock.schedule_once(lambda dt: self._init_saf_check(), 2)

        return NovelDownloader()

    def _init_saf_check(self):
        """启动时检查 SAF 权限状态"""
        saf = SAFHelper()
        if saf.has_valid_permission():
            print("✅ SAF 目录权限有效")
        elif saf.get_saved_uri():
            print("⚠️ SAF 目录权限已过期，需要重新授权")
        else:
            print("ℹ️ 未设置 SAF 目录，将使用应用私有目录")


if __name__ == '__main__':
    TomatoNovelApp().run()