import re
import os
import sys
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
import json

class LogAnalyzer:
    """日志分析器，用于分析应用运行日志"""
    
    def __init__(self, log_file: str = "app.log"):
        self.log_file = log_file
        self.log_entries = []
        self.events = defaultdict(list)
        self.errors = []
        self.warnings = []
        self.performance_stats = {}
        
    def parse_log_file(self):
        """解析日志文件"""
        if not os.path.exists(self.log_file):
            print(f"错误: 日志文件 {self.log_file} 不存在")
            return False
        
        print(f"正在读取日志文件: {self.log_file}")
        with open(self.log_file, 'r', encoding='utf-8') as f:
            self.log_entries = f.readlines()
        
        print(f"共读取 {len(self.log_entries)} 行日志")
        self._analyze_logs()
        return True
    
    def _analyze_logs(self):
        """分析日志内容"""
        for entry in self.log_entries:
            self._parse_log_entry(entry)
        
        self._calculate_performance_stats()
    
    def _parse_log_entry(self, entry: str):
        """解析单条日志"""
        # 匹配日志格式: YYYY-MM-DD HH:MM:SS | LEVEL | NAME | MESSAGE
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+) \| (\w+) \| (.+)'
        match = re.match(pattern, entry)
        
        if not match:
            return
        
        timestamp_str, level, name, message = match.groups()
        try:
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return
        
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'name': name,
            'message': message
        }
        
        # 分类存储
        if level == 'ERROR':
            self.errors.append(log_entry)
        elif level == 'WARNING':
            self.warnings.append(log_entry)
        
        # 提取关键事件
        self._extract_events(log_entry)
    
    def _extract_events(self, entry: Dict):
        """从日志条目中提取关键事件"""
        message = entry['message']
        
        # 按钮点击事件
        if '【按钮点击】' in message:
            self.events['button_click'].append(entry)
        
        # 权限相关事件
        if '权限' in message:
            if '开始检查和请求权限' in message:
                self.events['permission_request_start'].append(entry)
            elif '权限状态' in message:
                self.events['permission_granted' if '已授予' in message else 'permission_denied'].append(entry)
            elif '被拒绝' in message:
                self.events['permission_denied'].append(entry)
        
        # 网络请求事件
        if '开始API请求' in message:
            self.events['api_request_start'].append(entry)
        elif 'API请求成功' in message:
            self.events['api_request_success'].append(entry)
        elif '网络请求失败' in message or '网络连接失败' in message:
            self.events['api_request_failed'].append(entry)
        elif '超时' in message:
            self.events['api_timeout'].append(entry)
        
        # 下载相关事件
        if '开始下载小说' in message:
            self.events['download_start'].append(entry)
        elif '下载完成' in message:
            self.events['download_complete'].append(entry)
        elif '下载过程异常' in message:
            self.events['download_error'].append(entry)
        
        # UI更新事件
        if 'UI更新:' in message:
            self.events['ui_update'].append(entry)
    
    def _calculate_performance_stats(self):
        """计算性能统计"""
        # 计算平均请求时间
        request_times = []
        for entry in self.events['api_request_success']:
            match = re.search(r'耗时: ([\d.]+)秒', entry['message'])
            if match:
                request_times.append(float(match.group(1)))
        
        if request_times:
            self.performance_stats['avg_request_time'] = sum(request_times) / len(request_times)
            self.performance_stats['max_request_time'] = max(request_times)
            self.performance_stats['min_request_time'] = min(request_times)
        
        # 计算下载时间
        if self.events['download_complete']:
            last_download = self.events['download_complete'][-1]
            match = re.search(r'耗时: ([\d.]+)秒', last_download['message'])
            if match:
                self.performance_stats['last_download_time'] = float(match.group(1))
        
        # 计算总运行时间
        if self.log_entries:
            first_time = datetime.strptime(
                re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', self.log_entries[0]).group(1),
                '%Y-%m-%d %H:%M:%S'
            )
            last_time = datetime.strptime(
                re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', self.log_entries[-1]).group(1),
                '%Y-%m-%d %H:%M:%S'
            )
            self.performance_stats['total_runtime'] = (last_time - first_time).total_seconds()
    
    def print_summary(self):
        """打印日志摘要"""
        print("\n" + "="*80)
        print("日志分析摘要")
        print("="*80)
        
        # 基本信息
        print(f"\n📊 基本信息:")
        print(f"  日志文件: {self.log_file}")
        print(f"  总日志行数: {len(self.log_entries)}")
        print(f"  错误数量: {len(self.errors)}")
        print(f"  警告数量: {len(self.warnings)}")
        
        if self.performance_stats:
            print(f"\n⏱️  性能统计:")
            if 'total_runtime' in self.performance_stats:
                print(f"  总运行时间: {self.performance_stats['total_runtime']:.2f}秒")
            if 'avg_request_time' in self.performance_stats:
                print(f"  平均请求时间: {self.performance_stats['avg_request_time']:.2f}秒")
                print(f"  最大请求时间: {self.performance_stats['max_request_time']:.2f}秒")
                print(f"  最小请求时间: {self.performance_stats['min_request_time']:.2f}秒")
            if 'last_download_time' in self.performance_stats:
                print(f"  最近下载时间: {self.performance_stats['last_download_time']:.2f}秒")
        
        # 事件统计
        print(f"\n📝 事件统计:")
        event_names = {
            'button_click': '按钮点击',
            'permission_request_start': '权限请求开始',
            'permission_granted': '权限已授予',
            'permission_denied': '权限被拒绝',
            'api_request_start': 'API请求开始',
            'api_request_success': 'API请求成功',
            'api_request_failed': 'API请求失败',
            'api_timeout': 'API超时',
            'download_start': '下载开始',
            'download_complete': '下载完成',
            'download_error': '下载错误',
            'ui_update': 'UI更新'
        }
        
        for event_type, count in self.events.items():
            event_name = event_names.get(event_type, event_type)
            print(f"  {event_name}: {len(count)}次")
        
        # 错误详情
        if self.errors:
            print(f"\n❌ 错误详情 (最新5条):")
            for error in self.errors[-5:]:
                print(f"\n  时间: {error['timestamp']}")
                print(f"  模块: {error['name']}")
                print(f"  消息: {error['message'][:100]}...")
        
        # 警告详情
        if self.warnings:
            print(f"\n⚠️  警告详情 (最新5条):")
            for warning in self.warnings[-5:]:
                print(f"\n  时间: {warning['timestamp']}")
                print(f"  模块: {warning['name']}")
                print(f"  消息: {warning['message'][:100]}...")
    
    def search_logs(self, keyword: str, max_results: int = 10) -> List[Dict]:
        """搜索日志"""
        results = []
        pattern = re.compile(keyword, re.IGNORECASE)
        
        for entry in self.log_entries:
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+) \| (\w+) \| (.+)', entry)
            if match and pattern.search(entry):
                results.append({
                    'timestamp': match.group(1),
                    'level': match.group(2),
                    'name': match.group(3),
                    'message': match.group(4),
                    'full_entry': entry
                })
                if len(results) >= max_results:
                    break
        
        return results
    
    def generate_report(self, output_file: str = "log_report.json"):
        """生成JSON格式的分析报告"""
        report = {
            'summary': {
                'total_lines': len(self.log_entries),
                'total_errors': len(self.errors),
                'total_warnings': len(self.warnings),
                'total_runtime': self.performance_stats.get('total_runtime', 0)
            },
            'performance': self.performance_stats,
            'events': {k: len(v) for k, v in self.events.items()},
            'errors': [
                {
                    'timestamp': e['timestamp'].isoformat() if isinstance(e['timestamp'], datetime) else str(e['timestamp']),
                    'name': e['name'],
                    'message': e['message']
                }
                for e in self.errors
            ],
            'warnings': [
                {
                    'timestamp': w['timestamp'].isoformat() if isinstance(w['timestamp'], datetime) else str(w['timestamp']),
                    'name': w['name'],
                    'message': w['message']
                }
                for w in self.warnings
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 分析报告已保存到: {output_file}")
    
    def analyze_ui_performance(self):
        """分析UI性能"""
        if 'ui_update' not in self.events or not self.events['ui_update']:
            print("\n⚠️  未找到UI更新事件")
            return
        
        print("\n📱 UI性能分析:")
        ui_updates = self.events['ui_update']
        print(f"  总UI更新次数: {len(ui_updates)}")
        
        # 计算UI更新频率
        if len(ui_updates) > 1:
            intervals = []
            for i in range(1, len(ui_updates)):
                interval = (ui_updates[i]['timestamp'] - ui_updates[i-1]['timestamp']).total_seconds()
                intervals.append(interval)
            
            if intervals:
                print(f"  平均更新间隔: {sum(intervals)/len(intervals):.3f}秒")
                print(f"  最小更新间隔: {min(intervals):.3f}秒")
                print(f"  最大更新间隔: {max(intervals):.3f}秒")
                
                # 统计UI状态消息
                messages = [e['message'].replace('UI更新: ', '') for e in ui_updates]
                message_counts = Counter(messages)
                print(f"\n  UI状态统计:")
                for msg, count in message_counts.most_common(10):
                    print(f"    {msg}: {count}次")
    
    def analyze_network_issues(self):
        """分析网络问题"""
        print("\n🌐 网络问题分析:")
        
        # 超时统计
        timeouts = self.events.get('api_timeout', [])
        if timeouts:
            print(f"  API超时次数: {len(timeouts)}")
            print(f"  超时详情 (最新3次):")
            for timeout in timeouts[-3:]:
                print(f"    - {timeout['timestamp']}: {timeout['message'][:80]}...")
        else:
            print("  ✅ 无API超时记录")
        
        # 请求失败统计
        failures = self.events.get('api_request_failed', [])
        if failures:
            print(f"\n  API请求失败次数: {len(failures)}")
            print(f"  失败原因统计:")
            failure_reasons = Counter()
            for failure in failures:
                reason = re.search(r'网络请求失败: (.+)', failure['message'])
                if reason:
                    failure_reasons[reason.group(1)] += 1
            
            for reason, count in failure_reasons.most_common(5):
                print(f"    {reason}: {count}次")
        else:
            print("  ✅ 无API请求失败记录")
        
        # 成功率计算
        total_requests = (
            len(self.events.get('api_request_start', [])) or
            len(self.events.get('api_request_success', [])) +
            len(self.events.get('api_request_failed', [])) +
            len(self.events.get('api_timeout', []))
        )
        success_requests = len(self.events.get('api_request_success', []))
        
        if total_requests > 0:
            success_rate = (success_requests / total_requests) * 100
            print(f"\n  请求成功率: {success_rate:.1f}%")
            print(f"  成功请求: {success_requests}/{total_requests}")

def main():
    """主函数"""
    print("🔍 日志分析工具")
    print("="*80)
    
    # 获取日志文件路径
    log_file = "app.log"
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    
    # 创建分析器
    analyzer = LogAnalyzer(log_file)
    
    # 解析日志
    if not analyzer.parse_log_file():
        sys.exit(1)
    
    # 打印摘要
    analyzer.print_summary()
    
    # 详细分析
    analyzer.analyze_ui_performance()
    analyzer.analyze_network_issues()
    
    # 生成报告
    analyzer.generate_report()
    
    # 搜索功能示例
    print("\n🔎 搜索示例:")
    print("  输入关键词搜索日志 (输入 'q' 退出):")
    
    while True:
        keyword = input("\n关键词> ").strip()
        if keyword.lower() == 'q':
            break
        
        if keyword:
            results = analyzer.search_logs(keyword, 5)
            if results:
                print(f"\n找到 {len(results)} 条匹配记录:")
                for i, result in enumerate(results, 1):
                    print(f"\n  [{i}] {result['timestamp']} | {result['level']} | {result['name']}")
                    print(f"      {result['message'][:120]}...")
            else:
                print("  未找到匹配记录")

if __name__ == "__main__":
    main()