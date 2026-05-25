"""In-memory session manager for analysis runs.

Stores session state, per-section content, data bundles, and results.
"""

import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class SessionData:
    """State for a single analysis session."""
    session_id: str
    symbol: str
    trade_date: str
    market: str  # "cn" or "us"
    status: str  # "pending" | "running" | "completed" | "error"
    max_debate_rounds: int = 1
    created_at: str = ""
    completed_at: Optional[str] = None

    # Per-section LLM-generated content
    valuation_report: str = ""
    technical_report: str = ""
    fundamental_report: str = ""
    sentiment_report: str = ""
    news_report: str = ""
    research_summary: str = ""

    # Raw data texts (pre-fetched)
    raw_ohlcv_text: str = ""
    raw_indicators_text: str = ""
    raw_financial_text: str = ""
    raw_news_text: str = ""
    raw_sentiment_text: str = ""

    # Debate and decision
    debate_history: str = ""
    final_decision: str = ""

    # Legacy combined report (for backward compat)
    research_report: str = ""

    error_message: str = ""
    config: dict[str, Any] = field(default_factory=dict)

    # Internal: cached data bundle for section generation
    _data_bundle: Optional[dict] = None

    def has_section(self, section: str) -> bool:
        """Check if a section has been generated."""
        section_map = {
            "valuation": "valuation_report",
            "technical": "technical_report",
            "fundamental": "fundamental_report",
            "sentiment": "sentiment_report",
            "news": "news_report",
            "summary": "research_summary",
        }
        field_name = section_map.get(section)
        if field_name:
            return bool(getattr(self, field_name, ""))
        return False

    def set_section(self, section: str, content: str):
        """Set a section's content."""
        section_map = {
            "valuation": "valuation_report",
            "technical": "technical_report",
            "fundamental": "fundamental_report",
            "sentiment": "sentiment_report",
            "news": "news_report",
            "summary": "research_summary",
        }
        field_name = section_map.get(section)
        if field_name:
            setattr(self, field_name, content)

    def get_section(self, section: str) -> str:
        """Get a section's content."""
        section_map = {
            "valuation": "valuation_report",
            "technical": "technical_report",
            "fundamental": "fundamental_report",
            "sentiment": "sentiment_report",
            "news": "news_report",
            "summary": "research_summary",
        }
        field_name = section_map.get(section)
        if field_name:
            return getattr(self, field_name, "")
        return ""

    @property
    def section_ready(self) -> dict[str, bool]:
        """Return a map of which sections are ready."""
        return {
            "valuation": bool(self.valuation_report),
            "technical": bool(self.technical_report),
            "fundamental": bool(self.fundamental_report),
            "sentiment": bool(self.sentiment_report),
            "news": bool(self.news_report),
            "summary": bool(self.research_summary),
            "debate": bool(self.debate_history),
            "decision": bool(self.final_decision),
        }

    @property
    def all_data_sections_ready(self) -> bool:
        """Check if all 3 available data sections are ready (technical, fundamental, sentiment)."""
        return all([
            self.technical_report,
            self.fundamental_report,
            self.sentiment_report,
        ])

    def _truncate(self, text: str, max_len: int = 2000) -> str:
        """Truncate text with an indicator if it exceeds max_len."""
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        return text[:max_len] + "\n\n[...内容已截断]"

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "market": self.market,
            "status": self.status,
            "max_debate_rounds": self.max_debate_rounds,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "section_ready": self.section_ready,
            "valuation_report": self._truncate(self.valuation_report),
            "technical_report": self._truncate(self.technical_report),
            "fundamental_report": self._truncate(self.fundamental_report),
            "sentiment_report": self._truncate(self.sentiment_report),
            "news_report": self._truncate(self.news_report),
            "research_summary": self._truncate(self.research_summary),
            "debate_history": self._truncate(self.debate_history),
            "final_decision": self.final_decision,
            "error_message": self.error_message,
        }


class SessionManager:
    """Manages analysis sessions in memory with optional JSON file persistence."""

    def __init__(self, storage_dir: str = "./data"):
        self._sessions: dict[str, SessionData] = {}
        self._lock = threading.Lock()
        self._storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self._history_file = os.path.join(storage_dir, "history.json")

    def create(self, symbol: str, trade_date: str, market: str = "cn",
               max_debate_rounds: int = 1,
               config: Optional[dict[str, Any]] = None) -> SessionData:
        """Create a new analysis session."""
        session_id = str(uuid.uuid4())
        session = SessionData(
            session_id=session_id,
            symbol=symbol,
            trade_date=trade_date,
            market=market,
            status="pending",
            max_debate_rounds=max_debate_rounds,
            created_at=datetime.now().isoformat(),
            config=config or {},
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[SessionData]:
        """Get a session by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def update(self, session_id: str, **kwargs):
        """Update session fields."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                for key, value in kwargs.items():
                    if hasattr(session, key):
                        setattr(session, key, value)

    def complete(self, session_id: str):
        """Mark a session as completed and persist to history."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.status = "completed"
                session.completed_at = datetime.now().isoformat()
                self._save_to_history(session)

    def fail(self, session_id: str, error_message: str):
        """Mark a session as failed."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.status = "error"
                session.error_message = error_message

    def list_history(self, limit: int = 20) -> list[dict]:
        """List recent completed analyses."""
        history = self._load_history_raw()
        history.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return history[:limit]

    def get_history(self, session_id: str) -> Optional[dict]:
        """Get full details of a past analysis."""
        history = self._load_history_raw()
        for item in history:
            if item.get("session_id") == session_id:
                return item
        return None

    def _save_to_history(self, session: SessionData):
        """Append a completed session to the history file."""
        history = self._load_history_raw()
        history.append(session.to_dict())
        history = history[-100:]
        with open(self._history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def _load_history_raw(self) -> list[dict]:
        """Load history from file."""
        if not os.path.exists(self._history_file):
            return []
        try:
            with open(self._history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

# Global singleton
session_manager = SessionManager()
