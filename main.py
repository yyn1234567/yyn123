import flet as ft
import json
import os
import re
import asyncio
import aiohttp
import traceback

# --- 原有业务逻辑重构 (保持核心逻辑不变) ---
class NovelDownloader:
    def __init__(self, page: ft.Page):
        self.page = page
        self.output_dir = os.path.join(os.path.dirname(__file__), "novels")
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

    async def api_request(self, url_params):
        """异步API请求，使用aiohttp"""
        BASE_URL = "https://oiapi.net/api/FqRead"
        API_KEY = "oiapi-b27b0c8d-8984-7cd0-ecaf-0c209ad109d2"
        MAX_RETRIES = 3
        TIMEOUT = aiohttp.ClientTimeout(total=10)  # 缩短超时时间到10秒

        url = f"{BASE_URL}?{url_params}&key={API_KEY}"
        
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            for attempt in range(MAX_RETRIES):
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.text()
                            return json.loads(data)
                        else:
                            raise Exception(f"HTTP错误: {response.status}")
                except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(1)  # 缩短重试等待时间到1秒
                    else:
                        raise Exception(f"网络请求失败: {str(e)}")
                except json.JSONDecodeError as e:
                    raise Exception(f"JSON解析失败: {str(e)}")
                except Exception as e:
                    raise Exception(f"未知错误: {str(e)}")
        return None

    async def get_book_info(self, book_id):
        result = await self.api_request(f"method=ids&id={book_id}")
        if result and result.get('code') == 1:
            return result['data']
        raise Exception(result.get('message', '获取书籍信息失败'))

    async def get_chapter_list(self, book_id):
        result = await self.api_request(f"method=chapters&id={book_id}")
        if result and result.get('code') == 1:
            return result['data']
        raise Exception(result.get('message', '获取章节列表失败'))

    async def get_chapter_contents_batch(self, book_id, start_index, end_index):
        chapter_range = f"{start_index}-{end_index}"
        result = await self.api_request(f"method=chapter&id={book_id}&chapter={chapter_range}")
        if result and result.get('code') == 1:
            return result['data']
        raise Exception(result.get('message', '批量获取章节内容失败'))

    async def download_novel(self, book_id, update_status):
        """异步下载小说，通过 update_status 回调更新 UI"""
        try:
            # 1. 获取书籍信息
            update_status("正在连接服务器...", 0)
            await asyncio.sleep(0.1)  # 确保UI更新
            book_info = await self.get_book_info(book_id)
            book_title = book_info['title']
            author = book_info['author']
            intro = book_info.get('docs', '').replace('\n', ' ')

            # 2. 获取章节列表
            update_status("正在获取章节列表...", 5)
            await asyncio.sleep(0.1)  # 确保UI更新
            chapters_data = await self.get_chapter_list(book_id)
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
            update_status("正在准备文件...", 10)
            await asyncio.sleep(0.1)  # 确保UI更新
            safe_title = self.clean_filename(book_title)
            output_file = os.path.join(self.output_dir, f"{safe_title}.txt")

            # 写入基本信息
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"{book_title}\n")
                    f.write(f"作者: {author}\n")
                    f.write(f"简介:\n{intro}\n\n")
            except IOError as e:
                raise Exception(f"无法创建文件: {str(e)}")

            # 4. 下载章节
            BATCH_SIZE = 30
            for start in range(1, total_chapters + 1, BATCH_SIZE):
                if start > total_chapters:
                    break
                end = min(start + BATCH_SIZE - 1, total_chapters)

                try:
                    update_status(f"正在下载章节 {start}-{end}...", 10 + (start/total_chapters)*80)
                    await asyncio.sleep(0.05)  # 减少等待时间
                    batch_data = await self.get_chapter_contents_batch(book_id, start, end)
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

                        progress = 10 + (chap_idx / total_chapters) * 90
                        update_status(f"下载中: {title}", progress)

                        if chapter_info:
                            content = self.clean_content(chapter_info.get('content', ''))
                            if content.lstrip().startswith(title):
                                content = content.lstrip()[len(title):].strip()
                            try:
                                with open(output_file, 'a', encoding='utf-8') as f:
                                    f.write(f"{title}\n{content}\n\n")
                            except IOError as e:
                                raise Exception(f"写入文件失败: {str(e)}")
                        else:
                            with open(output_file, 'a', encoding='utf-8') as f:
                                f.write(f"{title}\n[内容缺失]\n\n")

                except Exception as e:
                    # 批量失败则单章重试（简化版，直接记录错误）
                    update_status(f"章节 {start}-{end} 下载失败: {str(e)}", 10 + (start/total_chapters)*90)
                    try:
                        for chap_idx in range(start, end + 1):
                            with open(output_file, 'a', encoding='utf-8') as f:
                                f.write(f"第{chap_idx}章\n[下载失败]\n\n")
                    except IOError:
                        pass  # 忽略写入错误，避免级联失败

            update_status("下载完成!", 100)
            return output_file

        except Exception as e:
            error_msg = f"错误: {str(e)}\n{traceback.format_exc()}"
            update_status(error_msg.split('\n')[0], 0)
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

    # 权限请求标志
    permissions_granted = False

    async def check_and_request_permissions():
        """检查并请求必要的Android权限"""
        nonlocal permissions_granted
        
        # 定义需要的权限
        required_permissions = [
            "android.permission.INTERNET",
            "android.permission.WRITE_EXTERNAL_STORAGE",
            "android.permission.READ_EXTERNAL_STORAGE"
        ]
        
        try:
            # 尝试请求权限
            permissions_result = await page.request_permission(*required_permissions)
            permissions_granted = all(permissions_result.values())
            return permissions_granted
        except Exception as e:
            # 如果平台不支持权限请求，默认返回True
            return True

    async def on_download_click(e):
        """下载按钮点击事件处理器"""
        nonlocal permissions_granted
        
        book_id = book_id_field.value.strip()
        if not book_id:
            status_text.value = "错误：请输入 Book ID"
            status_text.color = "red"
            await page.update_async()
            return

        # 立即更新UI状态
        status_text.value = "正在准备下载..."
        status_text.color = "blue"
        progress_bar.value = 0
        progress_bar.visible = True
        result_text.value = ""
        await page.update_async()

        # 定义更新函数（闭包）
        def update_status(text, progress):
            """更新UI状态的回调函数"""
            status_text.value = text
            if progress >= 0:
                progress_bar.value = progress / 100

        # 在异步任务中运行下载（防止阻塞 UI）
        try:
            # 检查和请求权限
            if not permissions_granted:
                update_status("正在请求权限...", 0)
                await page.update_async()
                
                if not await check_and_request_permissions():
                    update_status("权限被拒绝，无法下载", 0)
                    await page.update_async()
                    result_text.value = "请授予应用存储和网络权限后重试。"
                    await page.update_async()
                    return
                
                update_status("权限已获取，正在准备...", 0)
                await page.update_async()

            # 直接调用异步的download_novel
            file_path = await downloader.download_novel(book_id, update_status)

            # 更新UI显示结果
            await page.update_async()

            if file_path:
                result_text.value = f"文件已保存至:\n{file_path}\n\n注意：在 Android 上，文件通常位于应用沙盒内，可通过文件管理器查找 Flet 相关目录。"
            else:
                status_text.value = "下载失败"
                status_text.color = "red"
                result_text.value = "下载过程中出现错误，请检查网络连接后重试。"
        except Exception as ex:
            status_text.value = f"系统错误: {str(ex)}"
            status_text.color = "red"
            result_text.value = "发生系统错误，请稍后重试。"
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