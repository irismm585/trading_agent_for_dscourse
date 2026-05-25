#!/usr/bin/env python3
"""
自动测试脚本：运行多次股票搜索并提取失败记录
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

# 导入日志记录器
from backend.data_layer.stock_data import DataFetchLogger
from backend.data_layer.fundamental_data import FundamentalDataLogger


# 测试股票列表
TEST_STOCKS_CN = [
    {"symbol": "600519", "name": "贵州茅台"},
    {"symbol": "000001", "name": "平安银行"},
    {"symbol": "601318", "name": "中国平安"},
    {"symbol": "000858", "name": "五粮液"},
    {"symbol": "600036", "name": "招商银行"},
]

TEST_STOCKS_US = [
    {"symbol": "AAPL", "name": "苹果"},
    {"symbol": "MSFT", "name": "微软"},
    {"symbol": "GOOGL", "name": "谷歌"},
]

# 后端 API 地址
BACKEND_URL = "http://localhost:8000"


def create_session(symbol: str, market: str = "cn") -> Dict[str, Any]:
    """创建会话（触发数据获取）"""
    trade_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    url = f"{BACKEND_URL}/api/session"
    payload = {
        "symbol": symbol,
        "trade_date": trade_date,
        "market": market,
        "max_debate_rounds": 1,
        "llm_provider": "openai",
        "deep_think_llm": "Qwen/Qwen2.5-7B-Instruct",
        "quick_think_llm": "Qwen/Qwen2.5-7B-Instruct",
        "backend_url": "https://api.siliconflow.cn/v1"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ 创建会话失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ 创建会话异常: {e}")
        return None


def get_session_status(session_id: str) -> Dict[str, Any]:
    """获取会话状态"""
    url = f"{BACKEND_URL}/api/session/{session_id}"
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"❌ 获取会话状态异常: {e}")
        return None


def run_test(stocks: List[Dict[str, str]], market: str, test_name: str) -> Dict[str, Any]:
    """运行一组测试"""
    print(f"\n{'='*60}")
    print(f"开始测试: {test_name}")
    print(f"市场: {'A 股' if market == 'cn' else '美股'}")
    print(f"股票数量: {len(stocks)}")
    print(f"{'='*60}\n")
    
    results = {
        "test_name": test_name,
        "market": market,
        "stocks_tested": [],
        "sessions_created": 0,
        "sessions_failed": 0,
        "start_time": datetime.now().isoformat(),
    }
    
    for i, stock in enumerate(stocks, 1):
        symbol = stock["symbol"]
        name = stock["name"]
        
        print(f"[{i}/{len(stocks)}] 测试 {symbol} ({name})...")
        
        # 创建会话
        session = create_session(symbol, market)
        
        if session:
            results["sessions_created"] += 1
            results["stocks_tested"].append({
                "symbol": symbol,
                "name": name,
                "session_id": session.get("session_id"),
                "status": "success"
            })
            print(f"  ✅ 会话创建成功: {session.get('session_id')}")
        else:
            results["sessions_failed"] += 1
            results["stocks_tested"].append({
                "symbol": symbol,
                "name": name,
                "session_id": None,
                "status": "failed"
            })
            print(f"  ❌ 会话创建失败")
        
        # 等待一下，避免请求过快
        time.sleep(2)
    
    results["end_time"] = datetime.now().isoformat()
    return results


def collect_failed_logs() -> Dict[str, Any]:
    """收集所有失败的日志记录"""
    print(f"\n{'='*60}")
    print("收集失败日志记录")
    print(f"{'='*60}\n")
    
    # 获取行情数据失败日志
    stock_failed = DataFetchLogger.get_failed_logs()
    print(f"行情数据失败记录: {len(stock_failed)} 条")
    
    # 获取基本面数据失败日志
    fundamental_failed = FundamentalDataLogger.get_failed_logs()
    print(f"基本面数据失败记录: {len(fundamental_failed)} 条")
    
    # 按数据源分组
    stock_by_source = {}
    for log in stock_failed:
        source = log["source"]
        if source not in stock_by_source:
            stock_by_source[source] = []
        stock_by_source[source].append(log)
    
    fundamental_by_source = {}
    for log in fundamental_failed:
        source = log["source"]
        if source not in fundamental_by_source:
            fundamental_by_source[source] = []
        fundamental_by_source[source].append(log)
    
    return {
        "stock_data": {
            "total": len(stock_failed),
            "by_source": stock_by_source,
            "logs": stock_failed
        },
        "fundamental_data": {
            "total": len(fundamental_failed),
            "by_source": fundamental_by_source,
            "logs": fundamental_failed
        }
    }


def generate_report(test_results: List[Dict[str, Any]], failed_logs: Dict[str, Any]) -> str:
    """生成详细的测试报告"""
    report = []
    report.append("="*80)
    report.append("数据获取测试报告")
    report.append("="*80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 测试结果摘要
    report.append("一、测试结果摘要")
    report.append("-"*80)
    
    total_sessions = sum(r["sessions_created"] + r["sessions_failed"] for r in test_results)
    total_success = sum(r["sessions_created"] for r in test_results)
    total_failed = sum(r["sessions_failed"] for r in test_results)
    
    report.append(f"总测试次数: {total_sessions}")
    report.append(f"成功次数: {total_success}")
    report.append(f"失败次数: {total_failed}")
    report.append(f"成功率: {total_success/total_sessions*100:.1f}%" if total_sessions > 0 else "N/A")
    report.append("")
    
    # 各测试详情
    for result in test_results:
        report.append(f"  {result['test_name']}:")
        report.append(f"    市场: {'A 股' if result['market'] == 'cn' else '美股'}")
        report.append(f"    成功: {result['sessions_created']}")
        report.append(f"    失败: {result['sessions_failed']}")
        report.append("")
    
    # 失败日志摘要
    report.append("二、失败日志摘要")
    report.append("-"*80)
    
    stock_data = failed_logs["stock_data"]
    fundamental_data = failed_logs["fundamental_data"]
    
    report.append(f"行情数据失败: {stock_data['total']} 条")
    report.append(f"基本面数据失败: {fundamental_data['total']} 条")
    report.append("")
    
    # 行情数据失败详情
    if stock_data["total"] > 0:
        report.append("  行情数据失败详情:")
        for source, logs in stock_data["by_source"].items():
            report.append(f"    数据源: {source}")
            report.append(f"    失败次数: {len(logs)}")
            
            # 按错误类型分组
            by_error = {}
            for log in logs:
                error = log.get("error", "未知错误")
                if error not in by_error:
                    by_error[error] = []
                by_error[error].append(log)
            
            for error, error_logs in by_error.items():
                report.append(f"      错误类型: {error}")
                report.append(f"      出现次数: {len(error_logs)}")
                
                # 显示最近的几条
                recent = error_logs[-3:]
                for i, log in enumerate(recent):
                    symbol = log.get("symbol", "N/A")
                    duration = log.get("duration_ms", 0)
                    details = log.get("details", {})
                    report.append(f"        [{i+1}] {symbol} - {duration:.2f}ms - {json.dumps(details, ensure_ascii=False)}")
            report.append("")
    
    # 基本面数据失败详情
    if fundamental_data["total"] > 0:
        report.append("  基本面数据失败详情:")
        for source, logs in fundamental_data["by_source"].items():
            report.append(f"    数据源: {source}")
            report.append(f"    失败次数: {len(logs)}")
            
            # 按错误类型分组
            by_error = {}
            for log in logs:
                error = log.get("error", "未知错误")
                if error not in by_error:
                    by_error[error] = []
                by_error[error].append(log)
            
            for error, error_logs in by_error.items():
                report.append(f"      错误类型: {error}")
                report.append(f"      出现次数: {len(error_logs)}")
                
                # 显示最近的几条
                recent = error_logs[-3:]
                for i, log in enumerate(recent):
                    symbol = log.get("symbol", "N/A")
                    data_type = log.get("data_type", "N/A")
                    duration = log.get("duration_ms", 0)
                    details = log.get("details", {})
                    report.append(f"        [{i+1}] {symbol} - {data_type} - {duration:.2f}ms - {json.dumps(details, ensure_ascii=False)}")
            report.append("")
    
    # 统计摘要
    report.append("三、统计摘要")
    report.append("-"*80)
    
    stock_summary = DataFetchLogger.get_summary()
    fundamental_summary = FundamentalDataLogger.get_summary()
    
    report.append("行情数据统计:")
    report.append(f"  总请求数: {stock_summary.get('total', 0)}")
    report.append(f"  成功: {stock_summary.get('success', 0)}")
    report.append(f"  失败: {stock_summary.get('failed', 0)}")
    report.append(f"  平均耗时: {stock_summary.get('avg_duration_ms', 0):.2f}ms")
    report.append("")
    
    report.append("基本面数据统计:")
    report.append(f"  总请求数: {fundamental_summary.get('total', 0)}")
    report.append(f"  成功: {fundamental_summary.get('success', 0)}")
    report.append(f"  失败: {fundamental_summary.get('failed', 0)}")
    report.append(f"  平均耗时: {fundamental_summary.get('avg_duration_ms', 0):.2f}ms")
    report.append("")
    
    report.append("="*80)
    report.append("报告结束")
    report.append("="*80)
    
    return "\n".join(report)


def save_report(report: str, failed_logs: Dict[str, Any], output_dir: str = "."):
    """保存报告到文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 保存文本报告
    report_file = os.path.join(output_dir, f"test_report_{timestamp}.txt")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n📄 文本报告已保存: {report_file}")
    
    # 保存 JSON 数据
    json_file = os.path.join(output_dir, f"test_data_{timestamp}.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(failed_logs, f, ensure_ascii=False, indent=2)
    print(f"📄 JSON 数据已保存: {json_file}")


def main():
    """主函数"""
    print("🚀 开始自动测试数据获取...")
    print(f"后端地址: {BACKEND_URL}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查后端是否可用
    try:
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=5)
        if response.status_code != 200:
            print("❌ 后端服务不可用，请先启动后端服务")
            return
        print("✅ 后端服务正常")
    except Exception as e:
        print(f"❌ 无法连接到后端服务: {e}")
        print("请先启动后端服务: cd trading_agent_finance && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000")
        return
    
    # 运行测试
    test_results = []
    
    # 测试 A 股
    if TEST_STOCKS_CN:
        result = run_test(TEST_STOCKS_CN, "cn", "A 股测试")
        test_results.append(result)
    
    # 测试美股
    if TEST_STOCKS_US:
        result = run_test(TEST_STOCKS_US, "us", "美股测试")
        test_results.append(result)
    
    # 收集失败日志
    failed_logs = collect_failed_logs()
    
    # 生成报告
    report = generate_report(test_results, failed_logs)
    
    # 打印报告
    print("\n" + report)
    
    # 保存报告
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_results")
    os.makedirs(output_dir, exist_ok=True)
    save_report(report, failed_logs, output_dir)
    
    print("\n🎉 测试完成！")


if __name__ == "__main__":
    main()
