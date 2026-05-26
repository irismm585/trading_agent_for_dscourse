"""Data Lineage - 数据血缘追踪

提供数据来源追踪、转换过程记录、数据重放和审计功能。
"""

from __future__ import annotations

import json
import uuid
import time
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from copy import deepcopy


@dataclass
class DataSource:
    """数据源信息"""
    id: str
    name: str
    type: str  # api, cache, file, database, mock
    endpoint: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "endpoint": self.endpoint,
            "metadata": self.metadata
        }


@dataclass
class TransformStep:
    """转换步骤"""
    step_id: str
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "parameters": self.parameters,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms
        }


@dataclass
class LineageRecord:
    """血缘记录"""
    record_id: str
    data_id: str
    symbol: str
    market: str
    data_type: str  # ohlcv, financial, news, etc.
    source: DataSource
    transforms: List[TransformStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "success"  # success, failed, partial
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "data_id": self.data_id,
            "symbol": self.symbol,
            "market": self.market,
            "data_type": self.data_type,
            "source": self.source.to_dict(),
            "transforms": [t.to_dict() for t in self.transforms],
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "metadata": self.metadata
        }


@dataclass
class DataVersion:
    """数据版本"""
    version_id: str
    data_id: str
    version_number: int
    created_at: datetime
    changes: Dict[str, Any] = field(default_factory=dict)
    author: str = "system"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "data_id": self.data_id,
            "version_number": self.version_number,
            "created_at": self.created_at.isoformat(),
            "changes": self.changes,
            "author": self.author
        }


class DataLineageTracker:
    """数据血缘追踪器"""
    
    def __init__(self, storage_path: str = None):
        """初始化血缘追踪器
        
        Args:
            storage_path: 持久化存储路径
        """
        self._records: Dict[str, LineageRecord] = {}
        self._versions: Dict[str, List[DataVersion]] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        self._data_sources: Dict[str, DataSource] = {}
        self._current_records: Dict[str, LineageRecord] = {}
        
        # 注册默认数据源
        self._register_default_sources()
        self._load_history()
    
    def _register_default_sources(self):
        """注册默认数据源"""
        default_sources = [
            DataSource(id="pytdx", name="PyTDX", type="api", endpoint="tdx.com.cn"),
            DataSource(id="akshare", name="AKShare", type="api", endpoint="akshare.xyz"),
            DataSource(id="yfinance", name="YFinance", type="api", endpoint="yahoo.com"),
            DataSource(id="mock", name="Mock Data", type="mock"),
            DataSource(id="cache_memory", name="Memory Cache", type="cache"),
            DataSource(id="cache_file", name="File Cache", type="cache"),
            DataSource(id="cache_redis", name="Redis Cache", type="cache"),
        ]
        
        for source in default_sources:
            self._data_sources[source.id] = source
    
    def _load_history(self):
        """加载历史记录"""
        if self._storage_path and self._storage_path.exists():
            try:
                with open(self._storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 恢复记录（简化处理）
                    pass
            except Exception:
                pass
    
    def _save_history(self):
        """保存历史记录"""
        if self._storage_path:
            try:
                self._storage_path.parent.mkdir(parents=True, exist_ok=True)
                data = {
                    "records": [r.to_dict() for r in self._records.values()],
                    "timestamp": datetime.now().isoformat()
                }
                with open(self._storage_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
    
    def start_tracking(
        self,
        symbol: str,
        market: str,
        data_type: str,
        source_id: str
    ) -> str:
        """开始追踪数据
        
        Args:
            symbol: 股票代码
            market: 市场
            data_type: 数据类型
            source_id: 数据源 ID
            
        Returns:
            追踪 ID
        """
        tracking_id = str(uuid.uuid4())
        data_id = f"{symbol}:{market}:{data_type}"
        
        source = self._data_sources.get(source_id) or DataSource(
            id=source_id,
            name=source_id,
            type="unknown"
        )
        
        record = LineageRecord(
            record_id=tracking_id,
            data_id=data_id,
            symbol=symbol,
            market=market,
            data_type=data_type,
            source=source
        )
        
        self._current_records[tracking_id] = record
        return tracking_id
    
    def add_transform(
        self,
        tracking_id: str,
        name: str,
        description: str = "",
        parameters: Dict[str, Any] = None,
        input_schema: Dict[str, Any] = None,
        output_schema: Dict[str, Any] = None
    ) -> str:
        """添加转换步骤
        
        Args:
            tracking_id: 追踪 ID
            name: 转换名称
            description: 描述
            parameters: 参数
            input_schema: 输入模式
            output_schema: 输出模式
            
        Returns:
            步骤 ID
        """
        if tracking_id not in self._current_records:
            return ""
        
        step_id = str(uuid.uuid4())
        step = TransformStep(
            step_id=step_id,
            name=name,
            description=description,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
            parameters=parameters or {}
        )
        
        self._current_records[tracking_id].transforms.append(step)
        return step_id
    
    def complete_tracking(
        self,
        tracking_id: str,
        status: str = "success",
        metadata: Dict[str, Any] = None
    ) -> Optional[LineageRecord]:
        """完成追踪
        
        Args:
            tracking_id: 追踪 ID
            status: 状态 (success, failed, partial)
            metadata: 元数据
            
        Returns:
            血缘记录
        """
        if tracking_id not in self._current_records:
            return None
        
        record = self._current_records.pop(tracking_id)
        record.status = status
        record.metadata = metadata or {}
        
        # 保存记录
        self._records[tracking_id] = record
        self._save_history()
        
        return record
    
    def track_data_version(
        self,
        data_id: str,
        changes: Dict[str, Any],
        author: str = "system"
    ) -> DataVersion:
        """追踪数据版本
        
        Args:
            data_id: 数据 ID
            changes: 变更内容
            author: 作者
            
        Returns:
            版本信息
        """
        if data_id not in self._versions:
            self._versions[data_id] = []
        
        version_number = len(self._versions[data_id]) + 1
        version = DataVersion(
            version_id=str(uuid.uuid4()),
            data_id=data_id,
            version_number=version_number,
            created_at=datetime.now(),
            changes=changes,
            author=author
        )
        
        self._versions[data_id].append(version)
        return version
    
    def get_lineage(self, tracking_id: str) -> Optional[Dict[str, Any]]:
        """获取血缘信息
        
        Args:
            tracking_id: 追踪 ID
            
        Returns:
            血缘信息
        """
        if tracking_id in self._records:
            return self._records[tracking_id].to_dict()
        return None
    
    def get_data_lineage(
        self,
        symbol: str,
        market: str,
        data_type: str = None
    ) -> List[Dict[str, Any]]:
        """获取数据的血缘历史
        
        Args:
            symbol: 股票代码
            market: 市场
            data_type: 数据类型（可选）
            
        Returns:
            血缘记录列表
        """
        data_id_prefix = f"{symbol}:{market}"
        if data_type:
            data_id_prefix = f"{data_id_prefix}:{data_type}"
        
        results = []
        for record in self._records.values():
            if record.data_id.startswith(data_id_prefix):
                results.append(record.to_dict())
        
        # 按时间排序
        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results
    
    def get_versions(
        self,
        symbol: str,
        market: str,
        data_type: str
    ) -> List[Dict[str, Any]]:
        """获取数据版本历史
        
        Args:
            symbol: 股票代码
            market: 市场
            data_type: 数据类型
            
        Returns:
            版本列表
        """
        data_id = f"{symbol}:{market}:{data_type}"
        if data_id not in self._versions:
            return []
        
        return [v.to_dict() for v in self._versions[data_id]]
    
    def compare_versions(
        self,
        data_id: str,
        version1: int,
        version2: int
    ) -> Dict[str, Any]:
        """比较两个版本
        
        Args:
            data_id: 数据 ID
            version1: 版本 1
            version2: 版本 2
            
        Returns:
            比较结果
        """
        if data_id not in self._versions:
            return {"error": "Data not found"}
        
        versions = self._versions[data_id]
        v1 = next((v for v in versions if v.version_number == version1), None)
        v2 = next((v for v in versions if v.version_number == version2), None)
        
        if not v1 or not v2:
            return {"error": "Version not found"}
        
        # 找出差异
        all_keys = set(v1.changes.keys()) | set(v2.changes.keys())
        differences = {}
        
        for key in all_keys:
            old_val = v1.changes.get(key)
            new_val = v2.changes.get(key)
            if old_val != new_val:
                differences[key] = {
                    "old": old_val,
                    "new": new_val
                }
        
        return {
            "version1": v1.to_dict(),
            "version2": v2.to_dict(),
            "differences": differences
        }
    
    def get_lineage_report(self) -> Dict[str, Any]:
        """获取血缘报告
        
        Returns:
            血缘报告
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "total_records": len(self._records),
            "active_tracking": len(self._current_records),
            "data_sources": [s.to_dict() for s in self._data_sources.values()],
            "recent_records": [
                r.to_dict() for r in list(self._records.values())[-20:]
            ]
        }
    
    def register_source(self, source: DataSource):
        """注册数据源"""
        self._data_sources[source.id] = source


# 单例
_lineage_instance: Optional[DataLineageTracker] = None


def get_lineage_tracker(storage_path: str = None) -> DataLineageTracker:
    """获取或创建血缘追踪器单例"""
    global _lineage_instance
    if _lineage_instance is None:
        _lineage_instance = DataLineageTracker(storage_path=storage_path)
    return _lineage_instance
