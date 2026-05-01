# -*- coding: utf-8 -*-
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.progressbar import ProgressBar
from kivy.clock import mainthread
import threading
import json
import urllib.request
import urllib.error
import os
import time
import re

# API配置
BASE_URL = "https://oiapi.net/api/FqRead"
API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"

# 请求重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2

# 超时配置
TIMEOUT = 30


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


def print_progress(current, total, final=False):
    """打印进度条"""
    percent = (current / total) * 100
    bar_length = 30
    filled = int(bar_length * current // total)
    bar = '█' * filled + '-' * (bar_length - filled)
    
    if final:
        sys.stdout.write(f'\r[{bar}] {percent:.1f}% {current}/{total} 下载完成\n')
    else:
        sys.stdout.write(f'\r[{bar}] {percent:.1f}% 正在下载{current}/{total}')
    sys.stdout.flush()


def clean_content(content):
    """清理章节内容，去掉HTML标签"""
    content = content.replace('</p><p>', '\n')
    content = content.replace('<p>', '')
    content = content.replace('</p>', '\n')
    content = re.sub(re.compile('<.*?>'), '', content)
    content = re.sub(r'\n+', '\n', content).strip()
    return content

def download_novel(book_id, update_callback):
    """
    下载小说的核心函数
    :param book_id: 书籍ID (str)
    :param update_callback: 回调函数，用于更新UI进度和日志
                          调用方式: update_callback(progress=0-100, status="消息", log="日志内容")
    """
    try:
        # --- 步骤1：获取书籍信息 ---
        update_callback(status="获取书籍信息...", log=f"[INFO] 开始获取书籍ID: {book_id}")
        try:
            book_info = get_book_info(book_id)
            if not book_info:
                raise Exception("返回数据为空")
            book_title = book_info['title']
            author = book_info['author']
            intro = book_info.get('docs', '').replace('\n', ' ')
            
            # 清理文件名
            safe_title = clean_filename(book_title)
            update_callback(log=f"[SUCCESS] 书籍信息获取成功: 《{book_title}》 作者: {author}")
            
        except Exception as e:
            error_msg = f"获取书籍信息失败: {str(e)}"
            update_callback(status="错误", log=f"[ERROR] {error_msg}")
            return False

        # --- 步骤2：获取章节列表 ---
        update_callback(status="获取章节列表...", log="[INFO] 正在获取章节列表...")
        try:
            chapters_data = get_chapter_list(book_id)
            chapters = []
            for volume in chapters_data:
                if isinstance(volume, list):
                    chapters.extend(volume)
                elif isinstance(volume, dict):
                    chapters.append(volume)
            total_chapters = len(chapters)
            if total_chapters == 0:
                raise Exception("无章节数据")
                
            update_callback(log=f"[SUCCESS] 共获取到 {total_chapters} 章节")
            
        except Exception as e:
            error_msg = f"获取章节列表失败: {str(e)}"
            update_callback(status="错误", log=f"[ERROR] {error_msg}")
            return False

        # --- 步骤3：准备保存文件 ---
        # 尝试适配Android环境保存到Download目录，否则回退到应用目录
        try:
            if hasattr(sys, '_MEIPASS'): # PyInstaller打包环境(测试用)
                download_dir = os.path.expanduser("~/Downloads")
            else:
                # Android 环境检测
                # 尝试使用 Android API (需要 python-for-android 支持，此处简化为直接路径)
                # 常见路径: /storage/emulated/0/Download 或 /sdcard/Download
                possible_paths = [
                    os.path.expanduser("~/Download"), # Linux/Mac 风格
                    os.path.expanduser("~/Downloads"),
                    "/storage/emulated/0/Download",
                    "/sdcard/Download",
                    os.path.join(os.getcwd(), "novels") # 最后的保底：应用同级目录
                ]
                
                output_dir = None
                for path in possible_paths:
                    if os.path.exists(path) or path == possible_paths[-1]: # 如果路径存在或者是最有一个保底路径
                        output_dir = path
                        try:
                            os.makedirs(output_dir, exist_ok=True)
                            # 尝试写入测试文件以检测权限
                            test_file = os.path.join(output_dir, ".test_permission")
                            with open(test_file, 'w') as f:
                                f.write("test")
                            os.remove(test_file)
                            break
                        except:
                            output_dir = None
                            continue
                
                if not output_dir:
                    output_dir = os.path.join(os.getcwd(), "novels")
                    os.makedirs(output_dir, exist_ok=True)
                    
        except Exception as e:
            # 如果路径检测出错，强制使用应用目录
            output_dir = os.path.join(os.getcwd(), "novels")
            os.makedirs(output_dir, exist_ok=True)
            update_callback(log=f"[WARN] 使用默认目录: {output_dir}")

        output_file = os.path.join(output_dir, f"{safe_title}.txt")

        # --- 步骤4：开始下载循环 ---
        BATCH_SIZE = 30 # 批量下载大小
        update_callback(status="开始下载", log=f"[INFO] 开始下载正文，预计 {total_chapters} 章...")
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                # 写入头部信息
                f.write(f"书名: {book_title}\n")
                f.write(f"作者: {author}\n")
                f.write(f"来源: 番茄小说\n")
                f.write(f"简介:\n{intro}\n")
                f.write("-" * 50 + "\n\n")
                
                # 遍历章节进行下载
                for start_idx in range(1, total_chapters + 1, BATCH_SIZE):
                    end_idx = min(start_idx + BATCH_SIZE - 1, total_chapters)
                    
                    # --- 批量获取数据 ---
                    try:
                        batch_data = get_chapter_contents_batch(book_id, start_idx, end_idx)
                        # 将列表转为字典方便查找
                        chapter_dict = {}
                        for item in batch_data:
                            chapter_num = item.get('chapter')
                            if chapter_num is not None:
                                chapter_dict[int(chapter_num)] = item
                    except Exception as e:
                        update_callback(log=f"[WARN] 批量获取失败 (第{start_idx}-{end_idx}章): {str(e)}，尝试单章下载...")
                        # 如果批量失败，这里简单跳过或进行单章重试（为了逻辑简洁，此处仅记录日志）
                        batch_data = []
                        chapter_dict = {}

                    # --- 处理单章数据 ---
                    for chap_idx in range(start_idx, end_idx + 1):
                        # 更新进度 (0-100)
                        progress_val = int((chap_idx / total_chapters) * 100)
                        update_callback(progress=progress_val, status=f"下载中... {chap_idx}/{total_chapters}")
                        
                        chapter_info = chapter_dict.get(chap_idx)
                        original_chapter = next((ch for ch in chapters if ch.get('index') == chap_idx), None)
                        
                        title = original_chapter['title'] if original_chapter else f"第{chap_idx}章"
                        
                        if chapter_info and chapter_info.get('content'):
                            content = clean_content(chapter_info['content'])
                            # 简单的防重复标题处理
                            if content.lstrip().startswith(title):
                                content = content.lstrip()[len(title):].strip()
                            f.write(f"第{chap_idx}章: {title}\n")
                            f.write(f"{content}\n\n")
                            update_callback(log=f"[OK] {title}")
                        else:
                            f.write(f"第{chap_idx}章: {title} [内容获取失败]\n\n")
                            update_callback(log=f"[SKIP] {title} (内容为空)")

                # --- 下载完成 ---
                update_callback(
                    progress=100, 
                    status="下载完成", 
                    log=f"[SUCCESS] 下载成功！文件已保存至:\n{output_file}"
                )
                return True
                
        except Exception as e:
            error_msg = f"文件写入错误: {str(e)}"
            update_callback(status="错误", log=f"[ERROR] {error_msg}")
            return False

    except Exception as e:
        # 捕获顶层异常
        error_msg = f"未知错误: {str(e)}"
        update_callback(status="错误", log=f"[CRITICAL] {error_msg}")
        return False


# --- Kivy UI 部分 ---
class NovelDownloaderUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = 20
        self.spacing = 10

        # 标题
        title = Label(
            text="[b]番茄小说下载器[/b]",
            size_hint_y=None,
            height=50,
            markup=True,
            font_size=24
        )
        self.add_widget(title)

        # ID输入框
        self.input_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
        self.id_input = TextInput(
            hint_text="请输入Book ID",
            multiline=False,
            font_size=18,
            padding=[10, 10]
        )
        self.input_layout.add_widget(self.id_input)
        self.add_widget(self.input_layout)

        # 操作按钮
        self.btn_layout = BoxLayout(size_hint_y=None, height=60, spacing=10)
        self.start_btn = Button(text="开始下载", font_size=18)
        self.start_btn.bind(on_press=self.start_download)
        self.btn_layout.add_widget(self.start_btn)
        self.add_widget(self.btn_layout)

        # 进度条
        self.progress_bar = ProgressBar(max=100, height=20, size_hint_y=None)
        self.add_widget(self.progress_bar)
        
        self.progress_label = Label(text="准备就绪", size_hint_y=None, height=30)
        self.add_widget(self.progress_label)

        # 日志显示 (ScrollView 包裹 Label)
        self.log_scroll = ScrollView(size_hint_y=0.7)
        self.log_label = Label(text="欢迎使用...\n", size_hint_y=None, text_size=(App.get_running_app().root.width - 40, None))
        self.log_label.bind(width=lambda *x: self.log_label.setter('text_size')(self.log_label, (x[1] - 40, None)))
        self.log_scroll.add_widget(self.log_label)
        self.add_widget(self.log_scroll)

    def log(self, message):
        """向日志框添加信息"""
        self.log_label.text += f"{message}\n"
        # 自动滚动到底部
        self.log_label.height = len(self.log_label.text.split('\n')) * 20
        self.log_scroll.scroll_y = 0

    def update_progress(self, current, total):
        """更新进度条和标签"""
        if total > 0:
            percent = (current / total) * 100
            self.progress_bar.value = percent
            self.progress_label.text = f"下载中... {current}/{total} ({percent:.1f}%)"

    def start_download(self, instance):
        book_id = self.id_input.text.strip()
        if not book_id:
            self.log("错误：书籍ID不能为空")
            return
        
        self.log(f"开始下载书籍 ID: {book_id}")
        self.start_btn.disabled = True
        
        # 在后台线程运行下载，避免阻塞UI
        def run_download():
            success = download_novel(book_id, update_callback=self.update_progress_callback)
            mainthread(lambda: self.on_download_complete(success))()
        
        threading.Thread(target=run_download, daemon=True).start()

    def update_progress_callback(self, current=None, total=None, error=None):
        """供下载线程调用的回调"""
        if error:
            self.log(f"下载错误: {error}")
        else:
            self.update_progress(current, total)

    def on_download_complete(self, success):
        if success:
            self.log("下载完成！文件已保存。")
            self.progress_bar.value = 100
        else:
            self.log("下载失败，请重试。")
        self.start_btn.disabled = False

class NovelApp(App):
    def build(self):
        return NovelDownloaderUI()

if __name__ == '__main__':
    NovelApp().run()
