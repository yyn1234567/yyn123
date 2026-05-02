import flet as ft
import json
import urllib.request
import urllib.error
import os
import time
import re
import asyncio

# --- 原有业务逻辑重构 (保持核心逻辑不变) ---
class NovelDownloader:
    def __init__(self, page: ft.Page):
        self.page = page
        self.output_dir = os.path.join(os.path.dirname(__file__), "novels") # Flet 打包后的工作目录处理
        os.makedirs(self.output_dir, exist_ok=True)

    def clean_filename(self, name):
        return re.sub(r"[\/\\\:\*\?\"\<\>\|]", "_", name)

    def clean_content(self, content):
        content = content.replace('</p><p>', '\n')
        content = content.replace('<p>', '')
        content = content.replace('</p>', '\n')
        content = re.sub(re.compile('<.*?>'), '', content)
        content = re.sub(r'\n+', '\n', content).strip()
        return content

    def api_request(self, url_params):
        # 注意：在 Flet 中，网络请求不能阻塞主线程，建议使用 aiohttp，但为了兼容原代码，这里保留同步并用线程池
        # 但在 Flet Desktop 中可能警告，Android 打包通常没问题
        BASE_URL = "https://oiapi.net/api/FqRead"
        API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"
        MAX_RETRIES = 3
        TIMEOUT = 30

        url = f"{BASE_URL}?{url_params}&key={API_KEY}"
        for attempt in range(MAX_RETRIES):
            try:
                with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
                    data = response.read().decode('utf-8')
                    return json.loads(data)
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)
                else:
                    raise e
        return None

    def get_book_info(self, book_id):
        result = self.api_request(f"method=ids&id={book_id}")
        if result and result.get('code') == 1:
            return result['data']
        raise Exception(result.get('message', '获取书籍信息失败'))

    def get_chapter_list(self, book_id):
        result = self.api_request(f"method=chapters&id={book_id}")
        if result and result.get('code') == 1:
            return result['data']
        raise Exception(result.get('message', '获取章节列表失败'))

    def get_chapter_contents_batch(self, book_id, start_index, end_index):
        chapter_range = f"{start_index}-{end_index}"
        result = self.api_request(f"method=chapter&id={book_id}&chapter={chapter_range}")
        if result and result.get('code') == 1:
            return result['data']
        raise Exception(result.get('message', '批量获取章节内容失败'))

    def download_novel(self, book_id, update_status):
        """下载小说，通过 update_status 回调更新 UI"""
        try:
            # 1. 获取书籍信息
            update_status("获取书籍信息...", 0)
            book_info = self.get_book_info(book_id)
            book_title = book_info['title']
            author = book_info['author']
            intro = book_info.get('docs', '').replace('\n', ' ')
            
            # 2. 获取章节列表
            chapters_data = self.get_chapter_list(book_id)
            chapters = []
            for volume in chapters_data:
                if isinstance(volume, list):
                    chapters.extend(volume)
                elif isinstance(volume, dict):
                    chapters.append(volume)
            total_chapters = len(chapters)
            if total_chapters == 0:
                raise Exception("未找到章节")

            # 3. 准备文件
            safe_title = self.clean_filename(book_title)
            output_file = os.path.join(self.output_dir, f"{safe_title}.txt")
            
            # 写入基本信息
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{book_title}\n")
                f.write(f"作者: {author}\n")
                f.write(f"简介:\n{intro}\n\n")

            # 4. 下载章节
            BATCH_SIZE = 30
            for start in range(1, total_chapters + 1, BATCH_SIZE):
                if start > total_chapters:
                    break
                end = min(start + BATCH_SIZE - 1, total_chapters)
                
                try:
                    batch_data = self.get_chapter_contents_batch(book_id, start, end)
                    # 转为字典
                    chapter_dict = {}
                    for item in batch_data:
                        chapter_num = item.get('chapter')
                        if chapter_num is not None:
                            chapter_dict[int(chapter_num)] = item

                    # 写入本批次
                    for chap_idx in range(start, end + 1):
                        chapter_info = chapter_dict.get(chap_idx)
                        original_chapter = next((ch for ch in chapters if ch.get('index') == chap_idx), None)
                        title = original_chapter['title'] if original_chapter else chapter_info.get('chapter_title', f'第{chap_idx}章')
                        
                        progress = (chap_idx / total_chapters) * 100
                        update_status(f"下载中: {title}", progress)

                        if chapter_info:
                            content = self.clean_content(chapter_info.get('content', ''))
                            if content.lstrip().startswith(title):
                                content = content.lstrip()[len(title):].strip()
                            f.write(f"{title}\n{content}\n\n")
                        else:
                            f.write(f"{title}\n[内容缺失]\n\n")

                except Exception as e:
                    # 批量失败则单章重试（简化版，直接记录错误）
                    update_status(f"章节 {start}-{end} 下载失败: {str(e)}", (start/total_chapters)*100)
                    for chap_idx in range(start, end + 1):
                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(f"第{chap_idx}章\n[下载失败]\n\n")

            update_status("下载完成!", 100)
            return output_file

        except Exception as e:
            update_status(f"错误: {str(e)}", 0)
            return None

# --- Flet UI 界面 ---
async def main(page: ft.Page):
    page.title = "番茄小说下载器"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.theme_mode = ft.ThemeMode.LIGHT

    # 初始化下载器
    downloader = NovelDownloader(page)

    # UI 控件
    book_id_field = ft.TextField(label="请输入 Book ID", width=300)
    status_text = ft.Text(value="就绪", color="blue")
    progress_bar = ft.ProgressBar(width=300, value=0, visible=False)
    
    # 用于存储下载结果的文本控件
    result_text = ft.Text("", size=12, selectable=True)

    async def on_download_click(e):
        book_id = book_id_field.value.strip()
        if not book_id:
            status_text.value = "错误：请输入 Book ID"
            status_text.color = "red"
            await page.update_async()
            return
    
        # 重置状态
        status_text.value = "开始下载..."
        status_text.color = "blue"
        progress_bar.value = 0
        progress_bar.visible = True
        result_text.value = ""
        await page.update_async()
    
        # --- 关键修改点：使用 Task 而不是直接 run_in_executor，防止阻塞 ---
        # 定义一个包装函数，用于在事件循环中运行
        async def run_download():
            loop = asyncio.get_event_loop()
            # 将耗时的同步函数丢到线程池
            file_path = await loop.run_in_executor(None, lambda: downloader.download_novel(book_id, update_status))
            return file_path
    
        # 启动任务
        download_task = asyncio.create_task(run_download())
    
        try:
            file_path = await download_task
            if file_path:
                result_text.value = f"文件已保存至:\n{file_path}\n\n注意：Android 10+ 可能需要通过“文件”App访问。"
            else:
                status_text.value = "下载失败"
                status_text.color = "red"
        except Exception as ex:
            status_text.value = f"系统错误: {str(ex)}"
            status_text.color = "red"
            # 打印详细错误到日志（在 Logcat 中可见）
            print(f"Download Exception: {ex}")
        finally:
            progress_bar.visible = False
            await page.update_async()


    # 构建页面布局
    page.add(
        ft.Column([
            ft.Text("番茄小说下载器", size=24, weight="bold"),
            ft.Divider(),
            book_id_field,
            ft.ElevatedButton("下载小说", on_click=on_download_click),
            ft.Divider(),
            status_text,
            progress_bar,
            ft.Divider(),
            result_text
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )

# 如果直接运行此文件
if __name__ == "__main__":
    ft.app(target=main)
