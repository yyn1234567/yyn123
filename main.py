import flet as ft
import json
import os
import re
import asyncio
import aiohttp
import traceback
import logging
from datetime import datetime
import sys

# 配置日志系统
class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        record.name = f"{log_color}{record.name}{self.RESET}"
        return super().format(record)

# 配置日志
def setup_logging():
    """配置日志系统"""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # 日志格式
    formatter = ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 同时输出到文件
    try:
        file_handler = logging.FileHandler('app.log', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logging.warning(f"无法创建日志文件: {e}")
    
    return logger

# 初始化日志
logger = setup_logging()

class NovelDownloader:
    """小说下载器类"""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.output_dir = os.path.join(os.path.dirname(__file__), "novels")
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"初始化下载器，输出目录: {self.output_dir}")

    def clean_filename(self, name):
        """清理文件名"""
        clean_name = re.sub(r"[\/\\\:\*\?\"\<\>\|]", "_", name)
        logger.debug(f"清理文件名: '{name}' -> '{clean_name}'")
        return clean_name

    def clean_content(self, content):
        """清理章节内容"""
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
        TIMEOUT = aiohttp.ClientTimeout(total=10)
        
        url = f"{BASE_URL}?{url_params}&key={API_KEY}"
        logger.info(f"开始API请求: {url}")
        request_start = datetime.now()
        
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            for attempt in range(MAX_RETRIES):
                try:
                    logger.debug(f"尝试第 {attempt + 1}/{MAX_RETRIES} 次请求")
                    async with session.get(url) as response:
                        logger.debug(f"收到响应状态码: {response.status}")
                        
                        if response.status == 200:
                            data = await response.text()
                            logger.debug(f"成功获取数据，长度: {len(data)} 字节")
                            result = json.loads(data)
                            elapsed = (datetime.now() - request_start).total_seconds()
                            logger.info(f"API请求成功，耗时: {elapsed:.2f}秒")
                            return result
                        else:
                            error_msg = f"HTTP错误: {response.status}"
                            logger.error(error_msg)
                            raise Exception(error_msg)
                            
                except asyncio.TimeoutError as e:
                    elapsed = (datetime.now() - request_start).total_seconds()
                    logger.warning(f"请求超时 (尝试 {attempt + 1}/{MAX_RETRIES})，耗时: {elapsed:.2f}秒")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(1)
                    else:
                        logger.error(f"所有重试均超时，总耗时: {elapsed:.2f}秒")
                        raise Exception(f"网络请求超时: {str(e)}")
                        
                except aiohttp.ClientError as e:
                    elapsed = (datetime.now() - request_start).total_seconds()
                    logger.warning(f"网络连接错误 (尝试 {attempt + 1}/{MAX_RETRIES}): {str(e)}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(1)
                    else:
                        logger.error(f"所有重试均失败，总耗时: {elapsed:.2f}秒")
                        raise Exception(f"网络连接失败: {str(e)}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {str(e)}")
                    raise Exception(f"JSON解析失败: {str(e)}")
                    
                except Exception as e:
                    logger.error(f"未知错误: {str(e)}\n{traceback.format_exc()}")
                    raise Exception(f"未知错误: {str(e)}")
        
        logger.error("API请求失败，返回None")
        return None

    async def get_book_info(self, book_id):
        """获取书籍信息"""
        logger.info(f"获取书籍信息，Book ID: {book_id}")
        try:
            result = await self.api_request(f"method=ids&id={book_id}")
            if result and result.get('code') == 1:
                data = result['data']
                logger.info(f"成功获取书籍信息: {data.get('title', 'N/A')}")
                return data
            error_msg = result.get('message', '获取书籍信息失败')
            logger.error(f"获取书籍信息失败: {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"获取书籍信息异常: {str(e)}\n{traceback.format_exc()}")
            raise

    async def get_chapter_list(self, book_id):
        """获取章节列表"""
        logger.info(f"获取章节列表，Book ID: {book_id}")
        try:
            result = await self.api_request(f"method=chapters&id={book_id}")
            if result and result.get('code') == 1:
                chapters = result['data']
                total = sum(len(item) if isinstance(item, list) else 1 for item in chapters)
                logger.info(f"成功获取章节列表，共 {total} 章")
                return chapters
            error_msg = result.get('message', '获取章节列表失败')
            logger.error(f"获取章节列表失败: {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"获取章节列表异常: {str(e)}\n{traceback.format_exc()}")
            raise

    async def get_chapter_contents_batch(self, book_id, start_index, end_index):
        """批量获取章节内容"""
        logger.debug(f"获取章节内容批次: {start_index}-{end_index}")
        try:
            chapter_range = f"{start_index}-{end_index}"
            result = await self.api_request(f"method=chapter&id={book_id}&chapter={chapter_range}")
            if result and result.get('code') == 1:
                data = result['data']
                logger.debug(f"成功获取批次数据，章节数: {len(data)}")
                return data
            error_msg = result.get('message', '批量获取章节内容失败')
            logger.error(f"批量获取章节内容失败: {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"批量获取章节内容异常: {str(e)}\n{traceback.format_exc()}")
            raise

    async def download_novel(self, book_id, update_status):
        """异步下载小说，通过 update_status 回调更新 UI"""
        logger.info(f"开始下载小说，Book ID: {book_id}")
        download_start = datetime.now()
        
        try:
            # 1. 获取书籍信息
            update_status("正在连接服务器...", 0)
            await asyncio.sleep(0.1)  # 确保UI更新
            logger.info("步骤1: 获取书籍信息")
            
            book_info = await self.get_book_info(book_id)
            book_title = book_info['title']
            author = book_info['author']
            intro = book_info.get('docs', '').replace('\n', ' ')
            
            logger.info(f"书籍信息 - 标题: {book_title}, 作者: {author}")

            # 2. 获取章节列表
            update_status("正在获取章节列表...", 5)
            await asyncio.sleep(0.1)  # 确保UI更新
            logger.info("步骤2: 获取章节列表")
            
            chapters_data = await self.get_chapter_list(book_id)
            chapters = []
            for volume in chapters_data:
                if isinstance(volume, list):
                    chapters.extend(volume)
                elif isinstance(volume, dict):
                    chapters.append(volume)
            total_chapters = len(chapters)
            
            if total_chapters == 0:
                logger.error("未找到章节")
                raise Exception("未找到章节")
            
            logger.info(f"总共 {total_chapters} 个章节")

            # 3. 准备文件
            update_status("正在准备文件...", 10)
            await asyncio.sleep(0.1)  # 确保UI更新
            logger.info("步骤3: 准备输出文件")
            
            safe_title = self.clean_filename(book_title)
            output_file = os.path.join(self.output_dir, f"{safe_title}.txt")
            logger.info(f"输出文件路径: {output_file}")

            # 写入基本信息
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"{book_title}\n")
                    f.write(f"作者: {author}\n")
                    f.write(f"简介:\n{intro}\n\n")
                logger.info("成功写入书籍基本信息")
            except IOError as e:
                logger.error(f"无法创建文件: {str(e)}")
                raise Exception(f"无法创建文件: {str(e)}")

            # 4. 下载章节
            logger.info("步骤4: 开始下载章节内容")
            BATCH_SIZE = 30
            success_count = 0
            error_count = 0
            
            for start in range(1, total_chapters + 1, BATCH_SIZE):
                if start > total_chapters:
                    break
                end = min(start + BATCH_SIZE - 1, total_chapters)

                try:
                    update_status(f"正在下载章节 {start}-{end}...", 10 + (start/total_chapters)*80)
                    await asyncio.sleep(0.05)  # 减少等待时间
                    
                    logger.debug(f"请求批次 {start}-{end}")
                    batch_data = await self.get_chapter_contents_batch(book_id, start, end)
                    
                    # 转为字典
                    chapter_dict = {}
                    for item in batch_data:
                        chapter_num = item.get('chapter')
                        if chapter_num is not None:
                            chapter_dict[int(chapter_num)] = item
                            logger.debug(f"已获取章节 {chapter_num}")

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
                                logger.debug(f"成功写入章节: {title}")
                                success_count += 1
                            except IOError as e:
                                logger.error(f"写入文件失败: {str(e)}")
                                raise Exception(f"写入文件失败: {str(e)}")
                        else:
                            with open(output_file, 'a', encoding='utf-8') as f:
                                f.write(f"{title}\n[内容缺失]\n\n")
                            logger.warning(f"章节内容缺失: {title}")
                            error_count += 1

                except Exception as e:
                    # 批量失败则单章重试（简化版，直接记录错误）
                    error_msg = f"章节 {start}-{end} 下载失败: {str(e)}"
                    logger.error(error_msg)
                    update_status(error_msg, 10 + (start/total_chapters)*90)
                    try:
                        for chap_idx in range(start, end + 1):
                            with open(output_file, 'a', encoding='utf-8') as f:
                                f.write(f"第{chap_idx}章\n[下载失败]\n\n")
                            error_count += 1
                    except IOError:
                        pass  # 忽略写入错误，避免级联失败

            # 下载完成
            elapsed = (datetime.now() - download_start).total_seconds()
            logger.info(f"下载完成! 成功: {success_count}, 失败: {error_count}, 总耗时: {elapsed:.2f}秒")
            update_status("下载完成!", 100)
            return output_file

        except Exception as e:
            elapsed = (datetime.now() - download_start).total_seconds()
            logger.error(f"下载过程异常，耗时: {elapsed:.2f}秒")
            logger.error(f"错误详情: {str(e)}\n{traceback.format_exc()}")
            error_msg = f"错误: {str(e)}"
            update_status(error_msg, 0)
            return None

async def main(page: ft.Page):
    """主程序入口"""
    logger.info("=" * 60)
    logger.info("应用启动")
    logger.info("=" * 60)
    
    page.title = "番茄小说下载器"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.theme_mode = ft.ThemeMode.LIGHT
    
    # 初始化下载器
    logger.info("初始化下载器...")
    downloader = NovelDownloader(page)

    # UI 控件
    book_id_field = ft.TextField(label="请输入 Book ID", width=300)
    status_text = ft.Text(value="就绪", color="blue")
    progress_bar = ft.ProgressBar(width=300, value=0, visible=False)
    result_text = ft.Text("", size=12, selectable=True)

    # 权限请求标志
    permissions_granted = False
    logger.info("UI初始化完成")

    async def check_and_request_permissions():
        """检查并请求必要的Android权限"""
        nonlocal permissions_granted
        logger.info("开始检查和请求权限")
        
        required_permissions = [
            "android.permission.INTERNET",
            "android.permission.WRITE_EXTERNAL_STORAGE",
            "android.permission.READ_EXTERNAL_STORAGE"
        ]
        logger.debug(f"需要请求的权限: {', '.join(required_permissions)}")
        
        try:
            # 尝试请求权限
            logger.debug("调用权限请求API...")
            permissions_result = await page.request_permission(*required_permissions)
            logger.debug(f"权限请求结果: {permissions_result}")
            
            permissions_granted = all(permissions_result.values())
            logger.info(f"权限状态: {'已授予' if permissions_granted else '部分或全部拒绝'}")
            
            if not permissions_granted:
                denied = [p for p, granted in permissions_result.items() if not granted]
                logger.warning(f"被拒绝的权限: {', '.join(denied)}")
            
            return permissions_granted
            
        except Exception as e:
            logger.warning(f"权限请求失败: {str(e)}，可能在不支持权限请求的平台上运行")
            logger.debug(traceback.format_exc())
            return True  # 如果平台不支持权限请求，默认返回True

    async def on_download_click(e):
        """下载按钮点击事件处理器"""
        nonlocal permissions_granted
        
        logger.info("=" * 60)
        logger.info("【按钮点击】下载按钮被点击")
        logger.info("=" * 60)
        
        book_id = book_id_field.value.strip()
        logger.info(f"输入的Book ID: '{book_id}'")
        
        if not book_id:
            logger.warning("Book ID为空")
            status_text.value = "错误：请输入 Book ID"
            status_text.color = "red"
            await page.update_async()
            return

        # 立即更新UI状态
        logger.info("更新UI状态: 开始下载...")
        status_text.value = "正在准备下载..."
        status_text.color = "blue"
        progress_bar.value = 0
        progress_bar.visible = True
        result_text.value = ""
        await page.update_async()
        logger.debug("UI状态已更新")

        # 定义更新函数（闭包）
        def update_status(text, progress):
            """更新UI状态的回调函数"""
            logger.debug(f"UI更新: {text} (进度: {progress:.1f}%)")
            status_text.value = text
            if progress >= 0:
                progress_bar.value = progress / 100

        # 在异步任务中运行下载（防止阻塞 UI）
        try:
            # 检查和请求权限
            if not permissions_granted:
                logger.info("需要请求权限...")
                update_status("正在请求权限...", 0)
                await page.update_async()
                
                if not await check_and_request_permissions():
                    logger.error("权限被拒绝，无法继续下载")
                    update_status("权限被拒绝，无法下载", 0)
                    await page.update_async()
                    result_text.value = "请授予应用存储和网络权限后重试。"
                    logger.error("显示权限拒绝提示")
                    await page.update_async()
                    return
                
                logger.info("权限已获取，继续下载...")
                update_status("权限已获取，正在准备...", 0)
                await page.update_async()

            # 直接调用异步的download_novel
            logger.info("开始执行下载任务...")
            file_path = await downloader.download_novel(book_id, update_status)

            # 更新UI显示结果
            logger.debug("下载任务完成，更新UI...")
            await page.update_async()

            if file_path:
                result_text.value = f"文件已保存至:\n{file_path}\n\n注意：在 Android 上，文件通常位于应用沙盒内，可通过文件管理器查找 Flet 相关目录。"
                logger.info(f"下载成功，文件路径: {file_path}")
            else:
                logger.error("下载失败")
                status_text.value = "下载失败"
                status_text.color = "red"
                result_text.value = "下载过程中出现错误，请检查网络连接后重试。"
                
        except Exception as ex:
            logger.error(f"系统异常: {str(ex)}")
            logger.error(traceback.format_exc())
            status_text.value = f"系统错误: {str(ex)}"
            status_text.color = "red"
            result_text.value = "发生系统错误，请稍后重试。"
            
        finally:
            progress_bar.visible = False
            await page.update_async()
            logger.info("下载流程结束")

    # 构建页面布局
    logger.info("构建页面布局...")
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
    logger.info("页面构建完成")

# 如果直接运行此文件
if __name__ == "__main__":
    logger.info("启动应用...")
    ft.app(target=main)