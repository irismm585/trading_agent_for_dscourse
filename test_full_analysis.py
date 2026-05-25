#!/usr/bin/env python3
"""
模拟完整的多智能体分析流程
测试贵州茅台（600519）的完整分析
"""

import json
import time
import requests
import websocket
import threading
from datetime import datetime
from typing import Dict, List

BACKEND_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


class AnalysisTester:
    def __init__(self, symbol: str, market: str = "cn"):
        self.symbol = symbol
        self.market = market
        self.session_id = None
        self.ws_messages = []
        self.ws_connected = False
        self.ws = None
        self.analysis_complete = False
        self.analysis_error = None
        self.debate_complete = False
        self.decision_complete = False

    def create_session(self) -> str:
        """创建分析会话"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.post(
            f"{BACKEND_URL}/api/session",
            json={
                "symbol": self.symbol,
                "trade_date": today,
                "market": self.market,
                "max_debate_rounds": 1,
                "llm_provider": "openai",
                "deep_think_llm": "Qwen/Qwen2.5-7B-Instruct",
                "quick_think_llm": "Qwen/Qwen2.5-7B-Instruct",
                "backend_url": "https://api.siliconflow.cn/v1",
            },
        )
        response.raise_for_status()
        data = response.json()
        self.session_id = data["session_id"]
        print(f"✅ 会话创建成功: {self.session_id}")
        return self.session_id

    def on_message(self, ws, message):
        """WebSocket 消息处理"""
        try:
            data = json.loads(message)
            self.ws_messages.append(data)
            msg_type = data.get("type", "unknown")
            
            if msg_type == "status":
                print(f"  📊 状态: {data.get('message', '')}")
            elif msg_type == "node_update":
                node = data.get("node", "")
                section = data.get("section", "")
                content = data.get("content", "")
                if content:
                    preview = content[:100] + "..." if len(content) > 100 else content
                    print(f"  📝 [{node}] {section}: {preview}")
                if node == "BullAgent" or node == "BearAgent":
                    print(f"  ⚔️ 辩论进行中: {node}")
                elif node == "JudgeAgent":
                    print(f"  👨‍⚖️ 评委决策中")
            elif msg_type == "section_complete":
                section = data.get("section", "")
                print(f"  ✅ 完成: {section}")
                if section == "debate":
                    self.debate_complete = True
                elif section == "decision":
                    self.decision_complete = True
            elif msg_type == "error":
                print(f"  ❌ 错误: {data.get('message', '')}")
                self.analysis_error = data.get("message", "")
            elif msg_type == "complete":
                print(f"  🎉 分析完成")
                self.analysis_complete = True
            elif msg_type == "stock_profile":
                profile = data.get("profile", {})
                print(f"  📈 股票信息: {profile.get('name', '未知')}")
            elif msg_type == "chart_data":
                chart_data = data.get("data", [])
                if chart_data:
                    print(f"  📊 图表数据: {len(chart_data)} 条数据")
        except Exception as e:
            print(f"  ⚠️ 消息解析错误: {e}")

    def on_error(self, ws, error):
        print(f"  ❌ WebSocket 错误: {error}")
        self.analysis_error = str(error)

    def on_close(self, ws, close_status_code, close_msg):
        print(f"  🔌 WebSocket 关闭: {close_status_code} - {close_msg}")
        self.ws_connected = False

    def on_open(self, ws):
        print("  🔌 WebSocket 连接成功")
        self.ws_connected = True

    def connect_websocket(self):
        """连接 WebSocket"""
        ws_url = f"{WS_URL}/ws/{self.session_id}"
        print(f"\n🔌 连接 WebSocket: {ws_url}")

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open,
        )

        ws_thread = threading.Thread(target=self.ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()

        # 等待连接
        timeout = 10
        start = time.time()
        while not self.ws_connected and time.time() - start < timeout:
            time.sleep(0.1)

        if not self.ws_connected:
            raise Exception("WebSocket 连接超时")

    def send_command(self, action: str, **kwargs):
        """通过 WebSocket 发送命令"""
        command = {"action": action, **kwargs}
        print(f"\n📤 发送命令: {action}")
        self.ws.send(json.dumps(command))

    def wait_for_section(self, section: str, timeout: int = 180):
        """等待某个部分完成"""
        print(f"  ⏳ 等待 {section} 完成（超时: {timeout}秒）...")
        start = time.time()
        while time.time() - start < timeout:
            # 检查会话状态
            status = self.get_session_status()
            if status.get("section_ready", {}).get(section, False):
                print(f"  ✅ {section} 已完成")
                return True
            time.sleep(2)
        print(f"  ⚠️ {section} 超时")
        return False

    def wait_for_debate(self, timeout: int = 300):
        """等待辩论完成"""
        print(f"  ⏳ 等待辩论完成（超时: {timeout}秒）...")
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_session_status()
            if status.get("section_ready", {}).get("debate", False):
                print(f"  ✅ 辩论已完成")
                return True
            if self.debate_complete:
                print(f"  ✅ 辩论已完成（通过消息检测）")
                return True
            time.sleep(3)
        print(f"  ⚠️ 辩论超时")
        return False

    def wait_for_decision(self, timeout: int = 300):
        """等待决策完成"""
        print(f"  ⏳ 等待决策完成（超时: {timeout}秒）...")
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_session_status()
            if status.get("section_ready", {}).get("decision", False):
                print(f"  ✅ 决策已完成")
                return True
            if self.decision_complete:
                print(f"  ✅ 决策已完成（通过消息检测）")
                return True
            time.sleep(3)
        print(f"  ⚠️ 决策超时")
        return False

    def get_session_status(self) -> Dict:
        """获取会话状态"""
        response = requests.get(f"{BACKEND_URL}/api/session/{self.session_id}")
        response.raise_for_status()
        return response.json()

    def run_full_analysis(self):
        """运行完整的分析流程"""
        print("=" * 80)
        print("  多智能体分析流程测试")
        print("=" * 80)
        print(f"\n📋 测试股票: {self.symbol}")
        print(f"📅 市场: {self.market}")
        print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        start_time = time.time()

        try:
            # 1. 创建会话
            self.create_session()

            # 2. 连接 WebSocket
            self.connect_websocket()

            # 3. 生成所有数据部分
            sections = ["valuation", "technical", "fundamental", "sentiment", "news", "summary"]
            
            for section in sections:
                self.send_command("generate_section", section=section)
                self.wait_for_section(section)
                time.sleep(2)

            # 4. 运行辩论
            print("\n⚔️ 运行多空辩论...")
            self.send_command("run_debate")
            self.wait_for_debate()

            # 5. 运行评委决策
            print("\n👨‍⚖️ 运行评委决策...")
            self.send_command("run_judge")
            self.wait_for_decision()

            # 6. 获取最终结果
            final_status = self.get_session_status()

            print("\n" + "=" * 80)
            print("  分析结果")
            print("=" * 80)

            print(f"\n📊 会话状态: {final_status['status']}")
            print(f"📊 各部分完成状态: {final_status.get('section_ready', {})}")

            if final_status.get("valuation_report"):
                print(f"\n📈 估值分析:")
                print(final_status["valuation_report"][:500] + "..." if len(final_status["valuation_report"]) > 500 else final_status["valuation_report"])

            if final_status.get("technical_report"):
                print(f"\n📉 技术分析:")
                print(final_status["technical_report"][:500] + "..." if len(final_status["technical_report"]) > 500 else final_status["technical_report"])

            if final_status.get("fundamental_report"):
                print(f"\n🏢 基本面分析:")
                print(final_status["fundamental_report"][:500] + "..." if len(final_status["fundamental_report"]) > 500 else final_status["fundamental_report"])

            if final_status.get("sentiment_report"):
                print(f"\n😊 市场情绪分析:")
                print(final_status["sentiment_report"][:500] + "..." if len(final_status["sentiment_report"]) > 500 else final_status["sentiment_report"])

            if final_status.get("news_report"):
                print(f"\n📰 新闻资讯:")
                print(final_status["news_report"][:500] + "..." if len(final_status["news_report"]) > 500 else final_status["news_report"])

            if final_status.get("research_summary"):
                print(f"\n📝 研究摘要:")
                print(final_status["research_summary"])

            if final_status.get("debate_history"):
                print(f"\n⚔️ 多空辩论:")
                print(final_status["debate_history"][:1500] + "..." if len(final_status["debate_history"]) > 1500 else final_status["debate_history"])

            if final_status.get("final_decision"):
                print(f"\n👨‍⚖️ 最终决策:")
                print(final_status["final_decision"])

            if final_status.get("error_message"):
                print(f"\n❌ 错误信息:")
                print(final_status["error_message"])

            print("\n" + "=" * 80)
            print(f"  分析完成！总耗时: {time.time() - start_time:.2f}秒")
            print("=" * 80)

            return final_status

        except Exception as e:
            print(f"\n❌ 分析失败: {e}")
            import traceback
            traceback.print_exc()
            return None

        finally:
            if self.ws:
                self.ws.close()


if __name__ == "__main__":
    tester = AnalysisTester(symbol="600519", market="cn")
    result = tester.run_full_analysis()

    if result:
        # 保存结果
        output_file = f"/Users/bytedance/Documents/trae_projects/trading_agent_finance/test_results/analysis_600519_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n📄 结果已保存到: {output_file}")
