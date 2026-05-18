"""REST API endpoints — on-demand section generation.

Flow:
  1. POST /api/session      → create session (no analysis yet)
  2. POST /api/section/{id}  → generate one section at a time
  3. POST /api/debate/{id}   → run debate
  4. POST /api/judge/{id}    → run judge decision
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.session.manager import session_manager
from backend.config import get_config

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "A-Share Trading Agents"}


# ── Request / Response models ──────────────────────────────────────


class CreateSessionRequest(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol (6-digit CN code or US ticker)")
    trade_date: str = Field(..., description="Analysis date, YYYY-MM-DD")
    market: str = Field(default="cn", description="Market: 'cn' (A-shares) or 'us' (US stocks)")
    max_debate_rounds: int = Field(default=1, ge=1, le=5, description="Debate rounds (1-5)")
    llm_provider: str = Field(default="deepseek", description="LLM provider name")
    deep_think_llm: str = Field(default="deepseek-v4-pro", description="Model for Judge")
    quick_think_llm: str = Field(default="deepseek-v4-flash", description="Model for other agents")
    backend_url: str | None = Field(default=None, description="Custom LLM backend URL")


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str
    market: str
    symbol: str
    trade_date: str
    ws_url: str


class SectionRequest(BaseModel):
    section: str = Field(..., description="Section key: valuation|technical|fundamental|sentiment|news|summary")
    market: str = Field(default="cn")


class SectionResponse(BaseModel):
    session_id: str
    section: str
    status: str  # "generating" | "completed"


class DebateRequest(BaseModel):
    pass  # Uses session config


class DebateResponse(BaseModel):
    session_id: str
    status: str


class SessionStatusResponse(BaseModel):
    session_id: str
    symbol: str
    trade_date: str
    market: str
    status: str
    section_ready: dict[str, bool]
    valuation_report: str = ""
    technical_report: str = ""
    fundamental_report: str = ""
    sentiment_report: str = ""
    news_report: str = ""
    research_summary: str = ""
    debate_history: str = ""
    final_decision: str = ""
    error_message: str = ""


class ConfigResponse(BaseModel):
    llm_provider: str
    deep_think_llm: str
    quick_think_llm: str
    output_language: str


# ── Endpoints ──────────────────────────────────────────────────────


@router.post("/session", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new analysis session (does NOT start analysis)."""
    symbol = request.symbol.strip().upper()
    market = request.market.strip().lower()

    # Validate
    if market not in ("cn", "us"):
        raise HTTPException(status_code=400, detail="market must be 'cn' or 'us'")

    if market == "cn":
        if not symbol.isdigit() or len(symbol) != 6:
            raise HTTPException(status_code=400, detail="A-share stock code must be 6 digits")

    config = {
        "llm_provider": request.llm_provider,
        "deep_think_llm": request.deep_think_llm,
        "quick_think_llm": request.quick_think_llm,
        "backend_url": request.backend_url,
        "market": market,
    }

    session = session_manager.create(
        symbol=symbol,
        trade_date=request.trade_date,
        market=market,
        max_debate_rounds=request.max_debate_rounds,
        config=config,
    )

    return CreateSessionResponse(
        session_id=session.session_id,
        status="pending",
        market=market,
        symbol=symbol,
        trade_date=request.trade_date,
        ws_url=f"/ws/{session.session_id}",
    )


@router.post("/section/{session_id}", response_model=SectionResponse)
async def generate_section(session_id: str, request: SectionRequest):
    """Trigger generation of a specific section (returns immediately, streams via WS)."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    section = request.section.strip().lower()
    valid_sections = {"valuation", "technical", "fundamental", "sentiment", "news", "summary"}
    if section not in valid_sections:
        raise HTTPException(status_code=400, detail=f"Invalid section. Choose from: {', '.join(valid_sections)}")

    # Mark section as pending
    session.status = "running"

    # This is handled by the WebSocket — the client should connect to WS
    # first, then call this endpoint to trigger generation.
    return SectionResponse(
        session_id=session_id,
        section=section,
        status="generating",
    )


@router.post("/debate/{session_id}", response_model=DebateResponse)
async def trigger_debate(session_id: str):
    """Trigger the bull/bear debate (returns immediately, streams via WS)."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.all_data_sections_ready:
        raise HTTPException(status_code=400, detail="All 6 data sections must be generated before debate")

    session.status = "running"
    return DebateResponse(session_id=session_id, status="generating")


@router.post("/judge/{session_id}", response_model=DebateResponse)
async def trigger_judge(session_id: str):
    """Trigger the judge decision (returns immediately, streams via WS)."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.debate_history:
        raise HTTPException(status_code=400, detail="Debate must be completed before judge can make a decision")

    session.status = "running"
    return DebateResponse(session_id=session_id, status="generating")


@router.get("/session/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str):
    """Get the full status and results of an analysis session."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionStatusResponse(
        session_id=session.session_id,
        symbol=session.symbol,
        trade_date=session.trade_date,
        market=session.market,
        status=session.status,
        section_ready=session.section_ready,
        valuation_report=session.valuation_report,
        technical_report=session.technical_report,
        fundamental_report=session.fundamental_report,
        sentiment_report=session.sentiment_report,
        news_report=session.news_report,
        research_summary=session.research_summary,
        debate_history=session.debate_history,
        final_decision=session.final_decision,
        error_message=session.error_message,
    )


@router.get("/history")
async def list_history(limit: int = 20):
    """List recent completed analyses."""
    return session_manager.list_history(limit=limit)


@router.get("/history/{session_id}")
async def get_history_detail(session_id: str):
    """Get full details of a completed analysis."""
    detail = session_manager.get_history(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="History entry not found")
    return detail


@router.get("/config", response_model=ConfigResponse)
async def get_current_config():
    """Get current LLM configuration."""
    config = get_config()
    return ConfigResponse(
        llm_provider=config["llm_provider"],
        deep_think_llm=config["deep_think_llm"],
        quick_think_llm=config["quick_think_llm"],
        output_language=config.get("output_language", "Chinese"),
    )


# ── Stock search ─────────────────────────────────────────────────────

def _search_cn_stocks(query: str, limit: int = 10) -> list[dict]:
    """Search A-share stocks by code or name via pytdx."""
    results = []
    q = query.strip().lower()
    try:
        from pytdx.hq import TdxHq_API
        servers = [
            ("180.153.18.170", 7709),
            ("119.147.212.81", 7709),
            ("119.147.212.113", 7709),
        ]
        for host, port in servers:
            api = TdxHq_API()
            try:
                api.connect(host, port, time_out=5)
                for market in (1, 0):
                    start = 0
                    while True:
                        batch = api.get_security_list(market, start)
                        if not batch:
                            break
                        for s in batch:
                            code = str(s.get("code", "")).strip()
                            name = s.get("name", "").strip()
                            if q in code.lower() or q in name.lower():
                                results.append({
                                    "symbol": code,
                                    "name": name,
                                    "market": "cn",
                                    "exchange": "SH" if market == 1 else "SZ",
                                })
                                if len(results) >= limit:
                                    break
                        if len(results) >= limit:
                            break
                        start += len(batch)
                    if len(results) >= limit:
                        break
                api.disconnect()
                if results:
                    return results[:limit]
            except Exception:
                try:
                    api.disconnect()
                except Exception:
                    pass
    except ImportError:
        pass
    return results[:limit]


def _search_us_stocks(query: str, limit: int = 10) -> list[dict]:
    """Search US stocks by symbol or name via yfinance."""
    results = []
    q = query.strip().lower()
    try:
        import yfinance as yf
        search = yf.Search(query=q, news_count=0, enable_fuzzy_query=True)
        if search and hasattr(search, "quotes") and search.quotes:
            for q in search.quotes[:limit]:
                symbol = q.get("symbol", "")
                name = q.get("shortname") or q.get("longname") or symbol
                exchange = q.get("exchange", "")
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "market": "us",
                    "exchange": exchange,
                })
    except Exception:
        pass
    return results


@router.get("/search")
async def search_stocks(
    q: str = Query(..., min_length=1, max_length=50, description="Search keyword"),
    market: str = Query("cn", description="Market: cn or us"),
    limit: int = Query(10, ge=1, le=20),
):
    """Search stocks by name or code."""
    if market == "cn":
        stocks = _search_cn_stocks(q, limit)
    else:
        stocks = _search_us_stocks(q, limit)
    return {"results": stocks, "total": len(stocks)}


@router.get("/test/us-data")
async def test_us_data(symbol: str = Query("AAPL"), trade_date: str = Query("2026-05-18")):
    """Test US stock data fetching — returns detailed diagnostics."""
    diagnostics = {"symbol": symbol, "trade_date": trade_date}

    # Test OHLCV
    from backend.data_layer.stock_data import _us_ohlcv, format_ohlcv_summary
    try:
        df = _us_ohlcv(symbol, (lambda d: f"{int(d[:4])-1}{d[4:]}")(trade_date), trade_date)
        if df is not None and not df.empty:
            diagnostics["ohlcv"] = {"status": "ok", "rows": len(df), "last_date": str(df.iloc[-1]["date"]), "last_close": float(df.iloc[-1]["close"])}
        else:
            diagnostics["ohlcv"] = {"status": "empty", "rows": 0}
    except Exception as e:
        diagnostics["ohlcv"] = {"status": "error", "message": str(e)}

    # Test quote
    from backend.data_layer.stock_data import _get_us_stock_quote
    try:
        q = _get_us_stock_quote(symbol)
        diagnostics["quote"] = {"status": "ok" if q else "empty", "price": q.get("price") if q else None}
    except Exception as e:
        diagnostics["quote"] = {"status": "error", "message": str(e)}

    # Test financial
    from backend.data_layer.fundamental_data import _us_financial
    try:
        fin = _us_financial(symbol)
        info = fin.get("info", {})
        diagnostics["financial"] = {"status": "ok" if info else "empty", "keys": list(info.keys())[:5] if info else []}
    except Exception as e:
        diagnostics["financial"] = {"status": "error", "message": str(e)}

    return diagnostics
