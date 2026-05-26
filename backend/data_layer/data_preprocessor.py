"""Data Preprocessor - 数据预处理流水线

提供数据清洗、标准化、异常值检测和修复的 DAG 流水线。
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from copy import deepcopy

import pandas as pd
import numpy as np


@dataclass
class PipelineStep:
    """流水线步骤"""
    name: str
    function: Callable
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class PipelineResult:
    """流水线结果"""
    success: bool
    data: Any
    steps_executed: List[str]
    step_results: Dict[str, Any]
    errors: List[str]
    warnings: List[str]
    duration_ms: float
    quality_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "steps_executed": self.steps_executed,
            "errors": self.errors,
            "warnings": self.warnings,
            "duration_ms": self.duration_ms,
            "quality_score": self.quality_score
        }


class DataPreprocessor:
    """数据预处理器"""
    
    def __init__(self):
        """初始化预处理器"""
        self._steps: List[PipelineStep] = []
        self._step_registry: Dict[str, Callable] = {}
        self._register_default_steps()
    
    def _register_default_steps(self):
        """注册默认处理步骤"""
        self._step_registry = {
            "remove_duplicates": self._remove_duplicates,
            "fill_missing_values": self._fill_missing_values,
            "handle_outliers": self._handle_outliers,
            "normalize_columns": self._normalize_columns,
            "validate_ohlc_logic": self._validate_ohlc_logic,
            "ensure_data_types": self._ensure_data_types,
            "sort_by_date": self._sort_by_date,
            "add_derived_columns": self._add_derived_columns,
            "calculate_quality_score": self._calculate_quality_score,
        }
    
    def add_step(
        self,
        name: str,
        parameters: Dict[str, Any] = None,
        enabled: bool = True
    ):
        """添加处理步骤
        
        Args:
            name: 步骤名称
            parameters: 步骤参数
            enabled: 是否启用
        """
        if name not in self._step_registry:
            raise ValueError(f"Unknown step: {name}")
        
        step = PipelineStep(
            name=name,
            function=self._step_registry[name],
            enabled=enabled,
            parameters=parameters or {},
            description=self._get_step_description(name)
        )
        self._steps.append(step)
    
    def add_custom_step(
        self,
        name: str,
        function: Callable,
        parameters: Dict[str, Any] = None,
        description: str = ""
    ):
        """添加自定义步骤
        
        Args:
            name: 步骤名称
            function: 处理函数
            parameters: 步骤参数
            description: 描述
        """
        self._step_registry[name] = function
        step = PipelineStep(
            name=name,
            function=function,
            enabled=True,
            parameters=parameters or {},
            description=description
        )
        self._steps.append(step)
    
    def _get_step_description(self, name: str) -> str:
        """获取步骤描述"""
        descriptions = {
            "remove_duplicates": "移除重复行",
            "fill_missing_values": "填充缺失值",
            "handle_outliers": "处理异常值",
            "normalize_columns": "标准化列名",
            "validate_ohlc_logic": "验证 OHLC 逻辑",
            "ensure_data_types": "确保数据类型正确",
            "sort_by_date": "按日期排序",
            "add_derived_columns": "添加衍生列",
            "calculate_quality_score": "计算质量分数",
        }
        return descriptions.get(name, "")
    
    def _remove_duplicates(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """移除重复行"""
        subset = params.get("subset")
        keep = params.get("keep", "last")
        return df.drop_duplicates(subset=subset, keep=keep).reset_index(drop=True)
    
    def _fill_missing_values(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """填充缺失值"""
        method = params.get("method", "interpolate")
        limit = params.get("limit", 5)
        
        result = df.copy()
        
        # 先转换数值列的数据类型
        numeric_cols = result.select_dtypes(include=['number']).columns
        for col in numeric_cols:
            result[col] = pd.to_numeric(result[col], errors='coerce')
        
        if method == "interpolate":
            # 只对数值列进行插值
            for col in numeric_cols:
                if result[col].isnull().any():
                    result[col] = result[col].interpolate(method="time", limit=limit)
            return result
        elif method == "ffill":
            return result.ffill(limit=limit)
        elif method == "bfill":
            return result.bfill(limit=limit)
        else:
            return result.fillna(method=method, limit=limit)
    
    def _handle_outliers(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """处理异常值"""
        columns = params.get("columns", ["open", "high", "low", "close", "volume"])
        method = params.get("method", "clip")
        z_threshold = params.get("z_threshold", 3.0)
        
        result = df.copy()
        
        for col in columns:
            if col not in result.columns:
                continue
            
            if method == "clip":
                # 使用 IQR 方法
                Q1 = result[col].quantile(0.25)
                Q3 = result[col].quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR
                result[col] = result[col].clip(lower=lower, upper=upper)
            elif method == "zscore":
                # 使用 Z-score 方法
                mean = result[col].mean()
                std = result[col].std()
                if std > 0:
                    z_scores = (result[col] - mean) / std
                    mask = z_scores.abs() > z_threshold
                    result.loc[mask, col] = np.nan
        
        return result
    
    def _normalize_columns(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """标准化列名"""
        mapping = params.get("mapping", {})
        if mapping:
            return df.rename(columns=mapping)
        return df
    
    def _validate_ohlc_logic(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """验证 OHLC 逻辑"""
        result = df.copy()
        
        # 确保 high >= open, high >= close, high >= low
        if all(col in result.columns for col in ["open", "high", "low", "close"]):
            # 修复 high < low 的情况
            mask = result["high"] < result["low"]
            if mask.any():
                result.loc[mask, "high"] = result.loc[mask, ["open", "close", "low"]].max(axis=1)
                result.loc[mask, "low"] = result.loc[mask, ["open", "close", "high"]].min(axis=1)
        
        return result
    
    def _ensure_data_types(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """确保数据类型正确"""
        type_mapping = params.get("type_mapping", {
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "volume": int,
        })
        
        result = df.copy()
        for col, dtype in type_mapping.items():
            if col in result.columns:
                try:
                    result[col] = result[col].astype(dtype)
                except Exception:
                    pass
        
        return result
    
    def _sort_by_date(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """按日期排序"""
        date_col = params.get("date_column", "date")
        ascending = params.get("ascending", True)
        
        if date_col in df.columns:
            return df.sort_values(by=date_col, ascending=ascending).reset_index(drop=True)
        return df
    
    def _add_derived_columns(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """添加衍生列"""
        result = df.copy()
        
        # 添加价格变化
        if all(col in result.columns for col in ["open", "close"]):
            result["price_change"] = result["close"] - result["open"]
            result["price_change_pct"] = (result["close"] / result["open"] - 1) * 100
        
        # 添加日振幅
        if all(col in result.columns for col in ["high", "low"]):
            result["daily_range"] = result["high"] - result["low"]
            result["daily_range_pct"] = (result["high"] / result["low"] - 1) * 100
        
        return result
    
    def _calculate_quality_score(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> float:
        """计算质量分数"""
        score = 100.0
        
        # 缺失值惩罚
        missing_pct = df.isnull().sum().sum() / (df.shape[0] * df.shape[1]) if df.size > 0 else 0
        score -= missing_pct * 50
        
        # 重复值惩罚
        duplicate_pct = df.duplicated().sum() / len(df) if len(df) > 0 else 0
        score -= duplicate_pct * 30
        
        return max(0.0, min(100.0, score))
    
    def process(self, data: Any) -> PipelineResult:
        """执行预处理
        
        Args:
            data: 待处理数据
            
        Returns:
            流水线结果
        """
        start_time = time.time()
        errors = []
        warnings = []
        steps_executed = []
        step_results = {}
        quality_score = 0.0
        
        current_data = deepcopy(data)
        
        for step in self._steps:
            if not step.enabled:
                continue
            
            try:
                steps_executed.append(step.name)
                
                if step.name == "calculate_quality_score":
                    quality_score = step.function(current_data, step.parameters)
                    step_results[step.name] = quality_score
                else:
                    current_data = step.function(current_data, step.parameters)
                    step_results[step.name] = "success"
                
            except Exception as e:
                errors.append(f"{step.name}: {str(e)}")
        
        duration_ms = (time.time() - start_time) * 1000
        
        return PipelineResult(
            success=len(errors) == 0,
            data=current_data,
            steps_executed=steps_executed,
            step_results=step_results,
            errors=errors,
            warnings=warnings,
            duration_ms=duration_ms,
            quality_score=quality_score
        )
    
    def get_steps(self) -> List[Dict[str, Any]]:
        """获取所有步骤"""
        return [
            {
                "name": step.name,
                "enabled": step.enabled,
                "description": step.description,
                "parameters": step.parameters
            }
            for step in self._steps
        ]


def create_ohlcv_pipeline() -> DataPreprocessor:
    """创建 OHLCV 数据预处理流水线"""
    pipeline = DataPreprocessor()
    
    pipeline.add_step("remove_duplicates", {"subset": ["date"]})
    pipeline.add_step("ensure_data_types")
    pipeline.add_step("validate_ohlc_logic")
    pipeline.add_step("handle_outliers", {"method": "clip"})
    pipeline.add_step("fill_missing_values", {"method": "interpolate"})
    pipeline.add_step("sort_by_date")
    pipeline.add_step("add_derived_columns")
    pipeline.add_step("calculate_quality_score")
    
    return pipeline


def create_financial_pipeline() -> DataPreprocessor:
    """创建财务数据预处理流水线"""
    pipeline = DataPreprocessor()
    
    pipeline.add_step("remove_duplicates")
    pipeline.add_step("ensure_data_types", {
        "type_mapping": {
            "pe_ratio": float,
            "pb_ratio": float,
            "market_cap": float,
        }
    })
    pipeline.add_step("handle_outliers", {
        "columns": ["pe_ratio", "pb_ratio", "market_cap"],
        "method": "clip"
    })
    pipeline.add_step("calculate_quality_score")
    
    return pipeline
