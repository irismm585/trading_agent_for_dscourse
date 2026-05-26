"""Incremental Updater - 增量数据更新机制

提供增量数据获取、版本管理、断点续传和数据变更检测功能。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class DataVersion:
    """数据版本信息"""
    symbol: str
    market: str
    data_type: str  # ohlcv, financial, news, etc.
    version: int
    last_update: datetime
    data_hash: str
    row_count: int
    date_range: Tuple[str, str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "market": self.market,
            "data_type": self.data_type,
            "version": self.version,
            "last_update": self.last_update.isoformat(),
            "data_hash": self.data_hash,
            "row_count": self.row_count,
            "date_range": list(self.date_range),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataVersion":
        return cls(
            symbol=data["symbol"],
            market=data["market"],
            data_type=data["data_type"],
            version=data["version"],
            last_update=datetime.fromisoformat(data["last_update"]),
            data_hash=data["data_hash"],
            row_count=data["row_count"],
            date_range=tuple(data["date_range"]),
            metadata=data.get("metadata", {})
        )


class IncrementalUpdater:
    """增量数据更新器"""
    
    def __init__(self, storage_path: str = None):
        """初始化增量更新器
        
        Args:
            storage_path: 版本信息存储路径
        """
        self._versions: Dict[str, DataVersion] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        self._load_versions()
    
    def _load_versions(self):
        """加载版本信息"""
        if self._storage_path and self._storage_path.exists():
            try:
                with open(self._storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, version_data in data.items():
                        self._versions[key] = DataVersion.from_dict(version_data)
            except Exception:
                pass
    
    def _save_versions(self):
        """保存版本信息"""
        if self._storage_path:
            try:
                self._storage_path.parent.mkdir(parents=True, exist_ok=True)
                data = {
                    key: version.to_dict()
                    for key, version in self._versions.items()
                }
                with open(self._storage_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
    
    def _get_version_key(self, symbol: str, market: str, data_type: str) -> str:
        """获取版本键"""
        return f"{symbol}:{market}:{data_type}"
    
    def _compute_data_hash(self, df: pd.DataFrame) -> str:
        """计算数据哈希"""
        if df is None or df.empty:
            return hashlib.md5(b"empty").hexdigest()
        
        # 使用最后几行计算哈希（避免全量计算）
        sample = df.tail(min(100, len(df)))
        data_str = sample.to_string()
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def get_current_version(
        self,
        symbol: str,
        market: str,
        data_type: str = "ohlcv"
    ) -> Optional[DataVersion]:
        """获取当前版本"""
        key = self._get_version_key(symbol, market, data_type)
        return self._versions.get(key)
    
    def needs_update(
        self,
        symbol: str,
        market: str,
        data_type: str = "ohlcv",
        max_age_hours: int = 24
    ) -> bool:
        """检查是否需要更新
        
        Args:
            symbol: 股票代码
            market: 市场
            data_type: 数据类型
            max_age_hours: 最大允许的更新间隔（小时）
            
        Returns:
            是否需要更新
        """
        version = self.get_current_version(symbol, market, data_type)
        
        if not version:
            return True  # 没有版本记录，需要更新
        
        age = (datetime.now() - version.last_update).total_seconds() / 3600
        return age > max_age_hours
    
    def get_incremental_range(
        self,
        symbol: str,
        market: str,
        data_type: str = "ohlcv",
        full_refresh_days: int = 90
    ) -> Tuple[str, str, bool]:
        """获取增量更新范围
        
        Args:
            symbol: 股票代码
            market: 市场
            data_type: 数据类型
            full_refresh_days: 全量刷新间隔（天）
            
        Returns:
            (start_date, end_date, is_incremental)
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        version = self.get_current_version(symbol, market, data_type)
        
        if not version:
            # 没有版本记录，全量获取
            start_date = (datetime.now() - timedelta(days=full_refresh_days)).strftime("%Y-%m-%d")
            return start_date, end_date, False
        
        # 检查是否需要全量刷新
        days_since_full = (datetime.now() - version.last_update).days
        if days_since_full > full_refresh_days:
            start_date = (datetime.now() - timedelta(days=full_refresh_days)).strftime("%Y-%m-%d")
            return start_date, end_date, False
        
        # 增量获取：从上次更新日期开始
        start_date = version.date_range[1]
        return start_date, end_date, True
    
    def update_version(
        self,
        symbol: str,
        market: str,
        data_type: str,
        df: pd.DataFrame,
        date_range: Tuple[str, str],
        metadata: Dict[str, Any] = None
    ) -> DataVersion:
        """更新版本信息
        
        Args:
            symbol: 股票代码
            market: 市场
            data_type: 数据类型
            df: 数据框
            date_range: 日期范围
            metadata: 元数据
            
        Returns:
            更新后的版本信息
        """
        key = self._get_version_key(symbol, market, data_type)
        existing = self._versions.get(key)
        
        new_version = DataVersion(
            symbol=symbol,
            market=market,
            data_type=data_type,
            version=(existing.version + 1) if existing else 1,
            last_update=datetime.now(),
            data_hash=self._compute_data_hash(df),
            row_count=len(df) if df is not None else 0,
            date_range=date_range,
            metadata=metadata or {}
        )
        
        self._versions[key] = new_version
        self._save_versions()
        
        return new_version
    
    def detect_changes(
        self,
        symbol: str,
        market: str,
        data_type: str,
        new_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """检测数据变更
        
        Args:
            symbol: 股票代码
            market: 市场
            data_type: 数据类型
            new_df: 新数据
            
        Returns:
            变更检测结果
        """
        version = self.get_current_version(symbol, market, data_type)
        
        result = {
            "has_changes": False,
            "changed_rows": 0,
            "new_rows": 0,
            "hash_changed": False,
            "row_count_changed": False
        }
        
        if not version:
            result["has_changes"] = True
            result["new_rows"] = len(new_df) if new_df is not None else 0
            return result
        
        new_hash = self._compute_data_hash(new_df)
        result["hash_changed"] = new_hash != version.data_hash
        result["row_count_changed"] = (
            len(new_df) if new_df is not None else 0
        ) != version.row_count
        
        result["has_changes"] = result["hash_changed"] or result["row_count_changed"]
        
        if result["row_count_changed"]:
            result["new_rows"] = (
                (len(new_df) if new_df is not None else 0) - version.row_count
            )
        
        return result
    
    def merge_incremental(
        self,
        existing_df: pd.DataFrame,
        incremental_df: pd.DataFrame,
        key_column: str = "date"
    ) -> pd.DataFrame:
        """合并增量数据
        
        Args:
            existing_df: 现有数据
            incremental_df: 增量数据
            key_column: 主键列名
            
        Returns:
            合并后的数据
        """
        if existing_df is None or existing_df.empty:
            return incremental_df
        
        if incremental_df is None or incremental_df.empty:
            return existing_df
        
        # 合并并去重
        combined = pd.concat([existing_df, incremental_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=[key_column], keep="last")
        combined = combined.sort_values(by=[key_column]).reset_index(drop=True)
        
        return combined
    
    def get_update_report(self) -> Dict[str, Any]:
        """获取更新报告"""
        return {
            "timestamp": datetime.now().isoformat(),
            "total_versions": len(self._versions),
            "versions": [
                version.to_dict()
                for version in self._versions.values()
            ]
        }


# 单例
_updater_instance: Optional[IncrementalUpdater] = None


def get_incremental_updater(storage_path: str = None) -> IncrementalUpdater:
    """获取或创建增量更新器单例"""
    global _updater_instance
    if _updater_instance is None:
        _updater_instance = IncrementalUpdater(storage_path=storage_path)
    return _updater_instance
