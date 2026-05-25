#!/usr/bin/env python3
"""
服务状态检查脚本
自动检查端口占用、进程状态和服务连通性
"""

import sys
import os
import subprocess
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# 配置
SERVICES = [
    {
        "name": "后端服务",
        "port": 8000,
        "health_check": "http://localhost:8000/api/health",
        "start_command": "cd /Users/bytedance/Documents/trae_projects/trading_agent_finance && python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000",
    },
    {
        "name": "前端服务",
        "port": 5173,
        "health_check": "http://localhost:5173/",
        "start_command": "cd /Users/bytedance/Documents/trae_projects/trading_agent_finance/frontend && npm run dev",
    },
]


def run_command(cmd: str, timeout: int = 10) -> Tuple[int, str, str]:
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "命令超时"
    except Exception as e:
        return -1, "", str(e)


def check_port(port: int) -> Dict:
    """检查端口占用情况"""
    result = {
        "port": port,
        "is_used": False,
        "process": None,
        "pid": None,
        "user": None,
        "command": None,
    }

    # 使用 lsof 检查端口（macOS）
    code, stdout, stderr = run_command(f"lsof -i :{port} -P -n 2>/dev/null | grep LISTEN")
    
    if code == 0 and stdout:
        lines = stdout.strip().split('\n')
        if lines:
            parts = lines[0].split()
            if len(parts) >= 9:
                result["is_used"] = True
                result["process"] = parts[0]
                result["pid"] = parts[1]
                result["user"] = parts[2]
                result["command"] = ' '.join(parts[8:]) if len(parts) > 8 else None

    return result


def check_process(pid: str) -> Dict:
    """检查进程状态"""
    result = {
        "pid": pid,
        "exists": False,
        "name": None,
        "cpu": None,
        "memory": None,
        "start_time": None,
        "running_time": None,
    }

    if not pid:
        return result

    code, stdout, stderr = run_command(f"ps -p {pid} -o pid=,comm=,pcpu=,pmem=,lstart=,etime=")
    
    if code == 0 and stdout.strip():
        parts = stdout.strip().split()
        if len(parts) >= 2:
            result["exists"] = True
            result["name"] = parts[1]
            if len(parts) >= 4:
                result["cpu"] = parts[2]
                result["memory"] = parts[3]
            if len(parts) >= 6:
                result["start_time"] = ' '.join(parts[4:9]) if len(parts) >= 9 else None
                result["running_time"] = parts[-1] if len(parts) >= 10 else None

    return result


def check_http(url: str, timeout: int = 10) -> Dict:
    """检查 HTTP 服务连通性"""
    result = {
        "url": url,
        "status": "unknown",
        "status_code": None,
        "response_time": None,
        "error": None,
        "content": None,
    }

    try:
        import urllib.request
        import urllib.error
        
        start_time = time.time()
        
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'ServiceChecker/1.0'}
        )
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result["status_code"] = response.status
            result["response_time"] = round((time.time() - start_time) * 1000, 2)
            
            if response.status == 200:
                result["status"] = "ok"
                try:
                    content = response.read().decode('utf-8')
                    if content.strip().startswith('{') or content.strip().startswith('['):
                        result["content"] = json.loads(content)
                    else:
                        result["content"] = content[:200] + "..." if len(content) > 200 else content
                except:
                    result["content"] = "无法解析响应"
            else:
                result["status"] = "error"
                
    except urllib.error.HTTPError as e:
        result["status"] = "error"
        result["status_code"] = e.code
        result["error"] = f"HTTP Error: {e.code}"
    except urllib.error.URLError as e:
        result["status"] = "error"
        result["error"] = f"URL Error: {e.reason}"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def get_service_status(service: Dict) -> Dict:
    """获取服务完整状态"""
    result = {
        "name": service["name"],
        "port": service["port"],
        "port_status": None,
        "process_status": None,
        "http_status": None,
        "overall": "unknown",
        "recommendation": None,
    }

    # 检查端口
    port_info = check_port(service["port"])
    result["port_status"] = port_info

    # 检查进程
    if port_info["pid"]:
        process_info = check_process(port_info["pid"])
        result["process_status"] = process_info

    # 检查 HTTP
    if service.get("health_check"):
        http_info = check_http(service["health_check"])
        result["http_status"] = http_info

    # 判断整体状态
    if port_info["is_used"] and result.get("http_status") and result["http_status"]["status"] == "ok":
        result["overall"] = "running"
        result["recommendation"] = "服务正常运行"
    elif port_info["is_used"]:
        result["overall"] = "partial"
        result["recommendation"] = "端口被占用但服务可能异常，建议检查"
    else:
        result["overall"] = "stopped"
        result["recommendation"] = f"服务未运行，启动命令: {service['start_command']}"

    return result


def print_separator(title: str = ""):
    """打印分隔线"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")


def print_service_status(service: Dict, status: Dict):
    """打印服务状态"""
    print(f"\n📊 {service['name']} (端口: {service['port']})")
    print(f"  {'-'*50}")

    # 端口状态
    port_status = status["port_status"]
    if port_status["is_used"]:
        print(f"  🟢 端口状态: 已占用")
        print(f"     进程: {port_status['process']} (PID: {port_status['pid']})")
        print(f"     用户: {port_status['user']}")
        if port_status["command"]:
            print(f"     命令: {port_status['command'][:80]}...")
    else:
        print(f"  🔴 端口状态: 未占用")

    # 进程状态
    if status.get("process_status") and status["process_status"]["exists"]:
        proc = status["process_status"]
        print(f"  🟢 进程状态: 运行中")
        print(f"     CPU: {proc['cpu']}% | 内存: {proc['memory']}%")
        if proc["start_time"]:
            print(f"     启动时间: {proc['start_time']}")
        if proc["running_time"]:
            print(f"     运行时长: {proc['running_time']}")

    # HTTP 状态
    if status.get("http_status"):
        http = status["http_status"]
        if http["status"] == "ok":
            print(f"  🟢 HTTP 状态: 正常")
            print(f"     状态码: {http['status_code']}")
            print(f"     响应时间: {http['response_time']}ms")
            if http.get("content"):
                if isinstance(http["content"], dict):
                    print(f"     响应: {json.dumps(http['content'], ensure_ascii=False)}")
                else:
                    print(f"     响应: {http['content']}")
        else:
            print(f"  🔴 HTTP 状态: 异常")
            if http["status_code"]:
                print(f"     状态码: {http['status_code']}")
            if http["error"]:
                print(f"     错误: {http['error']}")

    # 整体状态
    print(f"  {'-'*50}")
    if status["overall"] == "running":
        print(f"  ✅ 整体状态: 正常运行")
    elif status["overall"] == "partial":
        print(f"  ⚠️  整体状态: 部分异常")
    else:
        print(f"  ❌ 整体状态: 未运行")
    
    print(f"  💡 建议: {status['recommendation']}")


def print_summary(all_statuses: List[Dict]):
    """打印汇总信息"""
    print_separator("汇总信息")

    running = sum(1 for s in all_statuses if s["overall"] == "running")
    partial = sum(1 for s in all_statuses if s["overall"] == "partial")
    stopped = sum(1 for s in all_statuses if s["overall"] == "stopped")

    print(f"\n  运行中: {running} | 部分异常: {partial} | 未运行: {stopped}")
    
    if stopped > 0:
        print(f"\n  🚀 启动命令:")
        for service in SERVICES:
            print(f"     {service['name']}:")
            print(f"       {service['start_command']}")

    print(f"\n  🕐 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    """主函数"""
    print_separator("服务状态检查")
    print(f"\n  📋 检查 {len(SERVICES)} 个服务...")

    all_statuses = []

    for service in SERVICES:
        status = get_service_status(service)
        all_statuses.append(status)
        print_service_status(service, status)

    print_summary(all_statuses)

    print_separator()

    # 返回退出码
    if any(s["overall"] == "stopped" for s in all_statuses):
        return 1
    elif any(s["overall"] == "partial" for s in all_statuses):
        return 2
    else:
        return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n  ⏹️  用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n  ❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
