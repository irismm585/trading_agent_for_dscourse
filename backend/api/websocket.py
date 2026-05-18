"""WebSocket endpoint — on-demand, step-by-step analysis streaming.

The client connects to a session's WebSocket, then sends JSON commands
to generate individual sections, debate, or judge decision.

Commands from client:
  {"action": "generate_section", "section": "valuation"}
  {"action": "generate_raw_data"}
  {"action": "run_debate"}
  {"action": "run_judge"}

Server streams progress and final content back.
"""

import asyncio
import json
import queue
import threading
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.graph.trading_graph import build_debate_judge_graph
from backend.graph.agent_state import create_initial_state, DebateState
from backend.agents.section_generator import generate_section, get_raw_data_texts
from backend.data_layer.unified_data import fetch_all_data
from backend.llm_clients import create_llm_client
from backend.session.manager import session_manager

router = APIRouter()

# ── Section metadata for streaming ─────────────────────────────────
SECTION_LABELS: dict[str, str] = {
    "valuation": "估值分析",
    "technical": "技术面分析",
    "fundamental": "基本面分析",
    "sentiment": "市场情绪分析",
    "news": "新闻资讯",
    "summary": "总体摘要",
}

RAW_SECTION_LABELS: dict[str, str] = {
    "raw_ohlcv_text": "行情数据",
    "raw_indicators_text": "技术指标",
    "raw_financial_text": "财务数据",
    "raw_news_text": "新闻原文",
    "raw_sentiment_text": "情绪原文",
}


async def _send_stock_profile(websocket: WebSocket, data_bundle: dict):
    """Send stock profile data to frontend."""
    profile = data_bundle.get("profile", {})
    index_data = data_bundle.get("index_data", {})
    if profile:
        await websocket.send_json({
            "type": "stock_profile",
            "profile": profile,
            "index_data": index_data,
            "timestamp": datetime.now().isoformat(),
        })


async def _handle_generate_section(websocket: WebSocket, session, section: str):
    """Generate a single section and stream the result."""
    config = session.config
    market = session.market

    # Use cached data bundle or fetch fresh
    data_bundle = session._data_bundle
    if data_bundle is None:
        await websocket.send_json({
            "type": "status",
            "message": f"正在获取{session.symbol}的{('A股' if market == 'cn' else '美股')}数据…",
            "timestamp": datetime.now().isoformat(),
        })
        data_bundle = fetch_all_data(session.symbol, session.trade_date, market)
        session._data_bundle = data_bundle

        # Send stock profile
        await _send_stock_profile(websocket, data_bundle)

        # Send raw data to frontend
        bundle_map = {
            "raw_ohlcv_text": "ohlcv_text",
            "raw_indicators_text": "indicators_text",
            "raw_financial_text": "financial_text",
            "raw_news_text": "news_text",
            "raw_sentiment_text": "sentiment_text",
        }
        for raw_key, bundle_key in bundle_map.items():
            text = data_bundle.get(bundle_key, "")
            if text:
                await websocket.send_json({
                    "type": "node_update",
                    "node": "DataCollector",
                    "section": raw_key,
                    "content": text,
                    "timestamp": datetime.now().isoformat(),
                })

        # Send OHLCV JSON for chart rendering
        ohlcv_json = data_bundle.get("ohlcv_json", [])
        if ohlcv_json:
            await websocket.send_json({
                "type": "chart_data",
                "data": ohlcv_json,
                "timestamp": datetime.now().isoformat(),
            })

    # Create LLM client
    provider = config.get("llm_provider", "deepseek")
    try:
        quick_client = create_llm_client(
            provider=provider,
            model=config.get("quick_think_llm", "deepseek-v4-flash"),
            base_url=config.get("backend_url"),
        )
        llm = quick_client.get_llm()
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"LLM客户端创建失败: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        })
        session_manager.fail(session.session_id, str(e))
        return

    # Stream generating status
    label = SECTION_LABELS.get(section, section)
    await websocket.send_json({
        "type": "status",
        "message": f"正在生成{label}…",
        "section": section,
        "timestamp": datetime.now().isoformat(),
    })

    try:
        content = await generate_section(
            section=section,
            symbol=session.symbol,
            trade_date=session.trade_date,
            market=market,
            llm=llm,
            data_bundle=data_bundle,
        )

        # Save to session
        session.set_section(section, content)

        # Stream content to frontend
        await websocket.send_json({
            "type": "node_update",
            "node": "DataCollector",
            "section": f"{section}_report",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

        # Send completion
        await websocket.send_json({
            "type": "section_complete",
            "section": section,
            "message": f"{label}生成完成",
            "timestamp": datetime.now().isoformat(),
        })

    except Exception as e:
        error_msg = str(e)
        session_manager.fail(session.session_id, error_msg)
        await websocket.send_json({
            "type": "error",
            "message": f"生成{label}失败: {error_msg}",
            "section": section,
            "timestamp": datetime.now().isoformat(),
        })


async def _handle_generate_raw_data(websocket: WebSocket, session):
    """Generate and stream raw data texts only."""
    market = session.market

    try:
        data_bundle = fetch_all_data(session.symbol, session.trade_date, market)
        session._data_bundle = data_bundle

        bundle_map = {
            "raw_ohlcv_text": "ohlcv_text",
            "raw_indicators_text": "indicators_text",
            "raw_financial_text": "financial_text",
            "raw_news_text": "news_text",
            "raw_sentiment_text": "sentiment_text",
        }

        for raw_key, bundle_key in bundle_map.items():
            text = data_bundle.get(bundle_key, "")
            if text:
                await websocket.send_json({
                    "type": "node_update",
                    "node": "DataCollector",
                    "section": raw_key,
                    "content": text,
                    "timestamp": datetime.now().isoformat(),
                })
                # Save to session
                setattr(session, raw_key, text)

        # Send OHLCV JSON for chart rendering
        ohlcv_json = data_bundle.get("ohlcv_json", [])
        if ohlcv_json:
            await websocket.send_json({
                "type": "chart_data",
                "data": ohlcv_json,
                "timestamp": datetime.now().isoformat(),
            })

        await websocket.send_json({
            "type": "status",
            "message": "原始数据获取完成",
            "timestamp": datetime.now().isoformat(),
        })

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"数据获取失败: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        })


async def _handle_run_debate(websocket: WebSocket, session):
    """Run the full bull/bear debate and stream rounds."""
    try:
        config = session.config
        max_rounds = session.max_debate_rounds

        provider = config.get("llm_provider", "deepseek")
        deep_client = create_llm_client(
            provider=provider,
            model=config.get("deep_think_llm", "deepseek-v4-pro"),
            base_url=config.get("backend_url"),
        )
        quick_client = create_llm_client(
            provider=provider,
            model=config.get("quick_think_llm", "deepseek-v4-flash"),
            base_url=config.get("backend_url"),
        )
        deep_llm = deep_client.get_llm()
        quick_llm = quick_client.get_llm()

        # Build research report from available sections (skip empty ones, skip news)
        sections = [
            ("估值分析", session.valuation_report),
            ("技术面分析", session.technical_report),
            ("基本面分析", session.fundamental_report),
            ("市场情绪分析", session.sentiment_report),
            ("总体摘要", session.research_summary),
        ]
        parts = [f"=== {label} ===\n\n{content}" for label, content in sections if content]
        research_report = "\n\n".join(parts) if parts else ""

        # Build graph
        graph = build_debate_judge_graph(deep_llm, quick_llm, max_debate_rounds=max_rounds)
        initial_state = create_initial_state(session.symbol, session.trade_date)
        initial_state["research_report"] = research_report

        session_manager.update(session.session_id, status="running")

        # Run blocking graph in a thread, stream events via thread-safe queue
        event_queue: queue.Queue = queue.Queue()
        _sentinel = object()

        def _run_graph():
            try:
                for event in graph.stream(initial_state, stream_mode="updates"):
                    event_queue.put(event)
            finally:
                event_queue.put(_sentinel)

        loop = asyncio.get_event_loop()
        thread = threading.Thread(target=_run_graph, daemon=True)
        thread.start()

        while True:
            event = await loop.run_in_executor(None, event_queue.get)
            if event is _sentinel:
                break

            node_name = list(event.keys())[0]
            node_output = event[node_name]

            if node_name in ("BullAgent", "BearAgent"):
                debate_state = node_output.get("debate_state", {})
                argument = debate_state.get("current_response", "")
                role = "bull" if node_name == "BullAgent" else "bear"
                rnd = (debate_state.get("count", 0) + 1) // 2 if role == "bull" else debate_state.get("count", 0) // 2

                await websocket.send_json({
                    "type": "node_update",
                    "node": node_name,
                    "section": "debate",
                    "content": argument,
                    "role": role,
                    "round": max(rnd, 1),
                    "timestamp": datetime.now().isoformat(),
                })

            elif node_name == "JudgeAgent":
                decision = node_output.get("final_decision", "")
                debate_state_full = node_output.get("debate_state", {})
                full_history = debate_state_full.get("history", "")

                await websocket.send_json({
                    "type": "node_update",
                    "node": node_name,
                    "section": "decision",
                    "content": decision,
                    "timestamp": datetime.now().isoformat(),
                })

                session_manager.update(
                    session.session_id,
                    debate_history=full_history,
                    final_decision=decision,
                )

        thread.join(timeout=30)
        session_manager.complete(session.session_id)
        await websocket.send_json({
            "type": "complete",
            "session_id": session.session_id,
            "timestamp": datetime.now().isoformat(),
        })

    except Exception as e:
        error_msg = str(e)
        session_manager.fail(session.session_id, error_msg)
        try:
            await websocket.send_json({
                "type": "error",
                "message": error_msg,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass


async def _handle_run_judge(websocket: WebSocket, session):
    """Run only the judge (debate history already exists)."""
    try:
        # Signal generating state
        await websocket.send_json({
            "type": "status",
            "message": "评委正在综合评判…",
            "section": "decision",
            "timestamp": datetime.now().isoformat(),
        })

        config = session.config
        provider = config.get("llm_provider", "deepseek")
        deep_client = create_llm_client(
            provider=provider,
            model=config.get("deep_think_llm", "deepseek-v4-pro"),
            base_url=config.get("backend_url"),
        )
        deep_llm = deep_client.get_llm()

        from backend.agents.judge_agent import create_judge_agent
        judge = create_judge_agent(deep_llm)

        debate_state = DebateState(
            history=session.debate_history,
            current_response="",
            count=session.max_debate_rounds * 2,
        )

        sections = [
            ("估值分析", session.valuation_report),
            ("技术面分析", session.technical_report),
            ("基本面分析", session.fundamental_report),
            ("市场情绪分析", session.sentiment_report),
            ("总体摘要", session.research_summary),
        ]
        parts = [f"=== {label} ===\n\n{content}" for label, content in sections if content]
        research_report = "\n\n".join(parts) if parts else ""

        state = {
            "symbol": session.symbol,
            "trade_date": session.trade_date,
            "research_report": research_report,
            "debate_state": debate_state,
            "final_decision": "",
        }

        # Run blocking judge call in a thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, judge, state)
        decision = result.get("final_decision", "")
        await websocket.send_json({
            "type": "node_update",
            "node": "JudgeAgent",
            "section": "decision",
            "content": decision,
            "timestamp": datetime.now().isoformat(),
        })

        session_manager.update(session.session_id, final_decision=decision)

        await websocket.send_json({
            "type": "section_complete",
            "section": "decision",
            "message": "评委决策完成",
            "timestamp": datetime.now().isoformat(),
        })

        session_manager.complete(session.session_id)

        await websocket.send_json({
            "type": "complete",
            "session_id": session.session_id,
            "timestamp": datetime.now().isoformat(),
        })

    except Exception as e:
        error_msg = str(e)
        session_manager.fail(session.session_id, error_msg)
        try:
            await websocket.send_json({
                "type": "error",
                "message": error_msg,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    session = session_manager.get(session_id)
    if not session:
        await websocket.send_json({
            "type": "error",
            "message": f"Session not found: {session_id}",
        })
        await websocket.close()
        return

    # Send connection ack
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "symbol": session.symbol,
        "market": session.market,
        "timestamp": datetime.now().isoformat(),
    })

    # Eagerly fetch data bundle and push stock profile to frontend
    try:
        if session._data_bundle is None:
            if session.market == "us":
                print(f"[websocket] eager fetching US data for {session.symbol}...")
            data_bundle = fetch_all_data(
                session.symbol, session.trade_date, session.market
            )
            session._data_bundle = data_bundle
        else:
            data_bundle = session._data_bundle

        # Log US data quality check
        if session.market == "us":
            ohlcv_ok = "无行情数据" not in data_bundle.get("ohlcv_text", "")
            ohlcv_count = len(data_bundle.get("ohlcv_json", []))
            print(f"[websocket] US data for {session.symbol}: ohlcv_ok={ohlcv_ok}, chart_points={ohlcv_count}")

        await _send_stock_profile(websocket, data_bundle)

        # Also push raw data texts + chart data
        bundle_map = {
            "raw_ohlcv_text": "ohlcv_text",
            "raw_indicators_text": "indicators_text",
            "raw_financial_text": "financial_text",
            "raw_news_text": "news_text",
            "raw_sentiment_text": "sentiment_text",
        }
        for raw_key, bundle_key in bundle_map.items():
            text = data_bundle.get(bundle_key, "")
            if text:
                await websocket.send_json({
                    "type": "node_update",
                    "node": "DataCollector",
                    "section": raw_key,
                    "content": text,
                    "timestamp": datetime.now().isoformat(),
                })

        ohlcv_json = data_bundle.get("ohlcv_json", [])
        if ohlcv_json:
            await websocket.send_json({
                "type": "chart_data",
                "data": ohlcv_json,
                "timestamp": datetime.now().isoformat(),
            })

        await websocket.send_json({
            "type": "status",
            "message": f"已获取{session.symbol}的基础数据",
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        print(f"[websocket] eager data fetch error for {session.symbol} ({session.market}): {e}")
        # Non-blocking — user can still trigger section generation

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                    "timestamp": datetime.now().isoformat(),
                })
                continue

            action = msg.get("action", "")

            if action == "generate_section":
                section = msg.get("section", "")
                if section:
                    await _handle_generate_section(websocket, session, section)

            elif action == "generate_raw_data":
                await _handle_generate_raw_data(websocket, session)

            elif action == "run_debate":
                await _handle_run_debate(websocket, session)

            elif action == "run_judge":
                await _handle_run_judge(websocket, session)

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown action: {action}",
                    "timestamp": datetime.now().isoformat(),
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass
