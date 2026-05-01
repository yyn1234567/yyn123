#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
番茄小说下载器 - Android版本
使用Kivy GUI界面
"""

import json
import urllib.request
import urllib.error
import os
import time
import sys
import re
from threading import Thread

# Kivy imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.progressbar import ProgressBar

# API配置
BASE_URL = "https://oiapi.net/api/FqRead"
API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"

# 请求重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2

# 超时配置
TIMEOUT = 30

# Android存储路径配置
try:
    from android.storage import primary_external_storage_path
    STORAGE_PATH = os.path.join(primary_external_storage_path(), "Download", "novels")
except ImportError:
    # 非Android环境的备用路径
    STORAGE_PATH = os.path.join(os.getcwd(), "downloads", "novels")


class NovelDownloaderApp(App):
    """番茄小说下载器主应用类"""
    
    def build(self):
        """构建UI界面"""
        self.title = '番茄小说下载器'
        
        # 主布局
        root = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 标题
        title_label = Label(
            text='[b]番茄小说下载器[/b]',
            size_hint_y=None,
            height=50,
            font_size=20,
            markup=True
        )
        root.add_widget(title_label)
        
        # 书籍ID输入框
        id_label = Label(
            text='请输入书籍ID:',
            size_hint_y=None,
            height=30,
            halign='left'
        )
        root.add_widget(id_label)
        
        self.book_id_input = TextInput(
            size_hint_y=None,
            height=40,
            multiline=False,
            hint_text='输入番茄小说ID'
        )
        root.add_widget(self.book_id_input)
        
        # 下载按钮
        download_button = Button(
            text='开始下载',
            size_hint_y=None,
            height=50,
            background_color=(0.2, 0.6, 0.9, 1)
        )
        download_button.bind(on_press=self.start_download)
        root.add_widget(download_button)
        
        # 进度条
        self.progress_bar = ProgressBar(
            size_hint_y=None,
            height=30,
            max=100,
            value=0
        )
        root.add_widget(self.progress_bar)
        
        # 状态标签
        self.status_label = Label(
            text='准备就绪',
            size_hint_y=None,
            height=30,
            halign='center'
        )
        root.add_widget(self.status_label)
        
        # 下载信息显示区域
        info_scroll = ScrollView(size_hint=(1, 0.4))
        self.info_label = Label(
            text='',
            size_hint_y=None,
            halign='left',
            valign='top',
            markup=True,
            text_size=(Window.width - 20, None)
        )
        self.info_label.bind(texture_size=self.info_label.setter('size'))
        info_scroll.add_widget(self.info_label)
        root.add_widget(info_scroll)
        
        # 获取存储权限
        Clock.schedule_once(self.request_permissions, 1)
        
        return root
    
    def request_permissions(self, dt):
        """请求Android存储权限"""
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.INTERNET
            ])
            self.update_info("已请求存储权限")
        except ImportError:
            self.update_info("非Android环境，跳过权限请求")
    
    def update_info(self, text):
        """更新信息显示"""
        self.info_label.text = text
    
    def update_status(self, status):
        """更新状态显示"""
        self.status_label.text = status
    
    def update_progress(self, value):
        """更新进度条"""
        self.progress_bar.value = value
    
    def start_download(self, instance):
        """启动下载线程"""
        book_id = self.book_id_input.text.strip()
        if not book_id:
            self.show_popup("错误", "请输入书籍ID")
            return
        
        # 禁用按钮防止重复点击
        instance.disabled = True
        self.update_status("准备下载...")
        self.update_progress(0)
        
        # 创建下载线程
        download_thread = Thread(
            target=self.download_novel,
            args=(book_id, instance),
            daemon=True
        )
        download_thread.start()
    
    def download_novel(self, book_id, button):
        """下载小说（在后台线程中运行）"""
        try:
            Clock.schedule_once(lambda dt: self.update_info("获取书籍信息..."))
            
            # 获取书籍信息
            book_info = get_book_info(book_id)
            book_title = book_info['title']
            author = book_info['author']
            intro = book_info.get('docs', '').replace('\n', ' ')
            
            info_text = f"书名: {book_title}\n作者: {author}\n简介: {intro[:200]}{'...' if len(intro) > 200 else ''}\n\n"
            Clock.schedule_once(lambda dt: self.update_info(info_text))
            
            # 获取章节列表
            Clock.schedule_once(lambda dt: self.update_status("获取章节列表..."))
            chapters_data = get_chapter_list(book_id)
            
            # 展平章节列表（处理卷）
            chapters = []
            for volume in chapters_data:
                if isinstance(volume, list):
                    chapters.extend(volume)
                elif isinstance(volume, dict):
                    chapters.append(volume)
            
            total_chapters = len(chapters)
            Clock.schedule_once(lambda dt: self.update_status(f"共{total_chapters}章，开始下载..."))
            
            # 准备保存
            safe_title = clean_filename(book_title)
            os.makedirs(STORAGE_PATH, exist_ok=True)
            output_file = os.path.join(STORAGE_PATH, f"{safe_title}.txt")
            
            Clock.schedule_once(lambda dt: self.update_info(info_text + f"保存路径: {output_file}\n\n"))
            
            # 开始下载
            BATCH_SIZE = 30
            for start in range(1, total_chapters + 1, BATCH_SIZE):
                end = min(start + BATCH_SIZE - 1, total_chapters)
                
                try:
                    batch_data = get_chapter_contents_batch(book_id, start, end)
                except Exception as e:
                    error_text = f"批量下载失败: {str(e)}\n"
                    Clock.schedule_once(lambda dt: self.update_info(info_text + error_text))
                    for chap_idx in range(start, end + 1):
                        # 更新进度
                        progress = (chap_idx / total_chapters) * 100
                        Clock.schedule_once(lambda dt, p=progress: self.update_progress(p))
                        Clock.schedule_once(lambda dt, c=chap_idx: self.update_status(f"第{c}章（跳过）"))
                    continue
                
                # 将返回列表转为字典，键为章节号
                chapter_dict = {}
                for item in batch_data:
                    chapter_num = item.get('chapter')
                    if chapter_num is not None:
                        chapter_dict[int(chapter_num)] = item
                
                # 写入文件
                with open(output_file, 'a', encoding='utf-8') as f:
                    for chap_idx in range(start, end + 1):
                        chapter_info = chapter_dict.get(chap_idx)
                        original_chapter = next((ch for ch in chapters if ch.get('index') == chap_idx), None)
                        title = original_chapter['title'] if original_chapter else chapter_info.get('chapter_title', f'第{chap_idx}章')
                        
                        # 更新进度
                        progress = (chap_idx / total_chapters) * 100
                        Clock.schedule_once(lambda dt, p=progress: self.update_progress(p))
                        Clock.schedule_once(lambda dt, c=chap_idx: self.update_status(f"正在下载第{c}章"))
                        
                        if chapter_info:
                            content = chapter_info.get('content', '')
                            content = clean_content(content)
                            if content.lstrip().startswith(title):
                                content = content.lstrip()[len(title):].strip()
                            f.write(f"{title}\n{content}\n\n")
                        else:
                            f.write(f"{title}\n[内容缺失]\n\n")
            
            # 下载完成
            Clock.schedule_once(lambda dt: self.update_progress(100))
            Clock.schedule_once(lambda dt: self.update_status("下载完成！"))
            Clock.schedule_once(lambda dt: self.show_popup("成功", f"下载完成！\n文件已保存到:\n{output_file}"))
            
        except Exception as e:
            error_msg = f"\n下载失败: {str(e)}"
            Clock.schedule_once(lambda dt: self.update_status("下载失败"))
            Clock.schedule_once(lambda dt: self.show_popup("错误", f"下载失败:\n{str(e)}"))
        finally:
            # 重新启用按钮
            Clock.schedule_once(lambda dt: setattr(button, 'disabled', False))
    
    def show_popup(self, title, message):
        """显示弹出窗口"""
        popup = Popup(
            title=title,
            content=Label(text=message, text_size=(Window.width*0.8, None)),
            size_hint=(0.8, 0.4)
        )
        popup.open()


def clean_filename(name):
    """清理文件名中的非法字符"""
    return re.sub(r"[\/\\\:\*\?\"\<\>\|]", "_", name)


def api_request(url_params):
    """
    发送API请求，带重试机制（静默重试，不输出过程信息）
    """
    url = f"{BASE_URL}?{url_params}&key={API_KEY}"
    
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
                data = response.read().decode('utf-8')
                return json.loads(data)
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(f"API请求失败: {str(e)}")
        except json.JSONDecodeError:
            raise Exception("API返回的数据格式错误")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(f"请求失败: {str(e)}")


def get_book_info(book_id):
    """获取书籍信息"""
    try:
        result = api_request(f"method=ids&id={book_id}")
        if result.get('code') == 1:
            return result['data']
        else:
            raise Exception(f"获取书籍信息失败: {result.get('message', '未知错误')}")
    except Exception as e:
        raise Exception(f"获取书籍信息错误: {str(e)}")


def get_chapter_list(book_id):
    """获取章节列表"""
    try:
        result = api_request(f"method=chapters&id={book_id}")
        if result.get('code') == 1:
            return result['data']
        else:
            raise Exception(f"获取章节列表失败: {result.get('message', '未知错误')}")
    except Exception as e:
        raise Exception(f"获取章节列表错误: {str(e)}")


def get_chapter_content(book_id, chapter_id):
    """获取单个章节内容"""
    try:
        result = api_request(f"method=chapter&id={book_id}&chapter={chapter_id}")
        if result.get('code') == 1:
            return result['data']
        else:
            raise Exception(f"获取章节内容失败: {result.get('message', '未知错误')}")
    except Exception as e:
        raise Exception(f"获取章节内容错误: {str(e)}")


def get_chapter_contents_batch(book_id, start_index, end_index):
    """批量获取章节内容"""
    chapter_range = f"{start_index}-{end_index}"
    try:
        result = api_request(f"method=chapter&id={book_id}&chapter={chapter_range}")
        if result.get('code') == 1:
            return result['data']
        else:
            raise Exception(f"批量获取章节内容失败: {result.get('message', '未知错误')}")
    except Exception as e:
        raise Exception(f"批量获取章节内容错误: {str(e)}")


def clean_content(content):
    """清理章节内容，去掉HTML标签"""
    content = content.replace('</p><p>', '\n')
    content = content.replace('<p>', '')
    content = content.replace('</p>', '\n')
    content = re.sub(re.compile('<.*?>'), '', content)
    content = re.sub(r'\n+', '\n', content).strip()
    return content


if __name__ == '__main__':
    NovelDownloaderApp().run()