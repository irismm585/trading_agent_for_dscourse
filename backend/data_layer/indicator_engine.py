"""Indicator Engine - 指标计算引擎

提供可插拔的指标计算引擎，支持自定义指标、指标依赖管理、计算结果缓存。
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
class IndicatorDefinition:
    """指标定义"""
    name: str
    function: Callable
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    category: str = "technical"  # technical, fundamental, custom
    cache_ttl: int = 3600
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "dependencies": self.dependencies,
            "parameters": self.parameters,
            "category": self.category,
            "cache_ttl": self.cache_ttl
        }


@dataclass
class IndicatorResult:
    """指标计算结果"""
    name: str
    values: Any
    calculated_at: datetime
    duration_ms: float
    success: bool
    error: str = ""
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "calculated_at": self.calculated_at.isoformat(),
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "dependencies": self.dependencies
        }


class IndicatorEngine:
    """指标计算引擎"""
    
    def __init__(self):
        """初始化指标引擎"""
        self._indicators: Dict[str, IndicatorDefinition] = {}
        self._cache: Dict[str, IndicatorResult] = {}
        self._register_default_indicators()
    
    def _register_default_indicators(self):
        """注册默认指标"""
        # 移动平均线
        self.register_indicator(
            name="sma",
            function=self._calc_sma,
            description="简单移动平均线",
            category="technical",
            parameters={"period": 20}
        )
        
        self.register_indicator(
            name="ema",
            function=self._calc_ema,
            description="指数移动平均线",
            category="technical",
            parameters={"period": 20}
        )
        
        # 动量指标
        self.register_indicator(
            name="rsi",
            function=self._calc_rsi,
            description="相对强弱指标",
            category="technical",
            parameters={"period": 14}
        )
        
        self.register_indicator(
            name="macd",
            function=self._calc_macd,
            description="MACD 指标",
            category="technical",
            parameters={"fast_period": 12, "slow_period": 26, "signal_period": 9}
        )
        
        # 波动率指标
        self.register_indicator(
            name="bollinger_bands",
            function=self._calc_bollinger_bands,
            description="布林带",
            category="technical",
            parameters={"period": 20, "std_dev": 2}
        )
        
        self.register_indicator(
            name="atr",
            function=self._calc_atr,
            description="平均真实波幅",
            category="technical",
            parameters={"period": 14}
        )
        
        # 趋势指标
        self.register_indicator(
            name="adx",
            function=self._calc_adx,
            description="平均趋向指标",
            category="technical",
            parameters={"period": 14}
        )
        
        # 成交量指标
        self.register_indicator(
            name="obv",
            function=self._calc_obv,
            description="能量潮",
            category="technical",
            parameters={}
        )
        
        # 衍生指标
        self.register_indicator(
            name="price_change",
            function=self._calc_price_change,
            description="价格变化",
            category="technical",
            parameters={"period": 1}
        )
        
        self.register_indicator(
            name="price_change_pct",
            function=self._calc_price_change_pct,
            description="价格变化百分比",
            category="technical",
            parameters={"period": 1}
        )
        
        self.register_indicator(
            name="volatility",
            function=self._calc_volatility,
            description="波动率",
            category="technical",
            parameters={"period": 20}
        )
    
    def register_indicator(
        self,
        name: str,
        function: Callable,
        description: str = "",
        dependencies: List[str] = None,
        parameters: Dict[str, Any] = None,
        category: str = "custom",
        cache_ttl: int = 3600
    ):
        """注册自定义指标
        
        Args:
            name: 指标名称
            function: 计算函数
            description: 描述
            dependencies: 依赖的指标
            parameters: 默认参数
            category: 类别
            cache_ttl: 缓存 TTL
        """
        indicator = IndicatorDefinition(
            name=name,
            function=function,
            description=description,
            dependencies=dependencies or [],
            parameters=parameters or {},
            category=category,
            cache_ttl=cache_ttl
        )
        self._indicators[name] = indicator
    
    def _calc_sma(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """计算简单移动平均线"""
        period = params.get("period", 20)
        close = df["close"] if "close" in df.columns else df.iloc[:, 0]
        return close.rolling(window=period).mean()
    
    def _calc_ema(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """计算指数移动平均线"""
        period = params.get("period", 20)
        close = df["close"] if "close" in df.columns else df.iloc[:, 0]
        return close.ewm(span=period, adjust=False).mean()
    
    def _calc_rsi(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """计算 RSI"""
        period = params.get("period", 14)
        close = df["close"] if "close" in df.columns else df.iloc[:, 0]
        
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calc_macd(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, pd.Series]:
        """计算 MACD"""
        fast_period = params.get("fast_period", 12)
        slow_period = params.get("slow_period", 26)
        signal_period = params.get("signal_period", 9)
        
        close = df["close"] if "close" in df.columns else df.iloc[:, 0]
        
        ema_fast = close.ewm(span=fast_period, adjust=False).mean()
        ema_slow = close.ewm(span=slow_period, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            "macd_line": macd_line,
            "signal_line": signal_line,
            "histogram": histogram
        }
    
    def _calc_bollinger_bands(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, pd.Series]:
        """计算布林带"""
        period = params.get("period", 20)
        std_dev = params.get("std_dev", 2)
        
        close = df["close"] if "close" in df.columns else df.iloc[:, 0]
        
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        return {
            "middle": sma,
            "upper": upper,
            "lower": lower,
            "bandwidth": (upper - lower) / sma * 100
        }
    
    def _calc_atr(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """计算 ATR"""
        period = params.get("period", 14)
        
        high = df["high"] if "high" in df.columns else df.iloc[:, 1]
        low = df["low"] if "low" in df.columns else df.iloc[:, 2]
        close = df["close"] if "close" in df.columns else df.iloc[:, 3]
        
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def _calc_adx(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, pd.Series]:
        """计算 ADX"""
        period = params.get("period", 14)
        
        high = df["high"] if "high" in df.columns else df.iloc[:, 1]
        low = df["low"] if "low" in df.columns else df.iloc[:, 2]
        close = df["close"] if "close" in df.columns else df.iloc[:, 3]
        
        prev_high = high.shift(1)
        prev_low = low.shift(1)
        
        plus_dm = high - prev_high
        minus_dm = prev_low - low
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        tr = self._calc_atr(df, {"period": 1})
        
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / tr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / tr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return {
            "adx": adx,
            "plus_di": plus_di,
            "minus_di": minus_di
        }
    
    def _calc_obv(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """计算 OBV"""
        close = df["close"] if "close" in df.columns else df.iloc[:, 3]
        volume = df["volume"] if "volume" in df.columns else df.iloc[:, 4]
        
        direction = np.where(close > close.shift(1), 1, -1)
        direction = np.where(close == close.shift(1), 0, direction)
        
        obv = (volume * direction).cumsum()
        
        return obv
    
    def _calc_price_change(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """计算价格变化"""
        period = params.get("period", 1)
        close = df["close"] if "close" in df.columns else df.iloc[:, 0]
        return close.diff(period)
    
    def _calc_price_change_pct(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """计算价格变化百分比"""
        period = params.get("period", 1)
        close = df["close"] if "close" in df.columns else df.iloc[:, 0]
        return close.pct_change(period) * 100
    
    def _calc_volatility(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """计算波动率"""
        period = params.get("period", 20)
        close = df["close"] if "close" in df.columns else df.iloc[:, 0]
        returns = close.pct_change()
        return returns.rolling(window=period).std() * np.sqrt(252)
    
    def calculate(
        self,
        df: pd.DataFrame,
        indicators: List[str],
        parameters: Dict[str, Dict[str, Any]] = None
    ) -> Dict[str, IndicatorResult]:
        """计算多个指标
        
        Args:
            df: 数据框
            indicators: 指标名称列表
            parameters: 每个指标的参数覆盖
            
        Returns:
            指标结果字典
        """
        results = {}
        params = parameters or {}
        
        for indicator_name in indicators:
            if indicator_name not in self._indicators:
                results[indicator_name] = IndicatorResult(
                    name=indicator_name,
                    values=None,
                    calculated_at=datetime.now(),
                    duration_ms=0,
                    success=False,
                    error=f"Indicator not found: {indicator_name}"
                )
                continue
            
            indicator = self._indicators[indicator_name]
            
            # 合并参数
            indicator_params = {**indicator.parameters, **params.get(indicator_name, {})}
            
            try:
                start_time = time.time()
                
                # 计算依赖项
                dependencies = {}
                for dep_name in indicator.dependencies:
                    if dep_name in results and results[dep_name].success:
                        dependencies[dep_name] = results[dep_name].values
                
                # 计算指标
                values = indicator.function(df, indicator_params)
                
                duration_ms = (time.time() - start_time) * 1000
                
                results[indicator_name] = IndicatorResult(
                    name=indicator_name,
                    values=values,
                    calculated_at=datetime.now(),
                    duration_ms=duration_ms,
                    success=True,
                    dependencies=indicator.dependencies
                )
                
            except Exception as e:
                results[indicator_name] = IndicatorResult(
                    name=indicator_name,
                    values=None,
                    calculated_at=datetime.now(),
                    duration_ms=0,
                    success=False,
                    error=str(e),
                    dependencies=indicator.dependencies
                )
        
        return results
    
    def calculate_all(
        self,
        df: pd.DataFrame,
        category: str = None
    ) -> Dict[str, IndicatorResult]:
        """计算所有指标
        
        Args:
            df: 数据框
            category: 按类别过滤
            
        Returns:
            所有指标结果
        """
        if category:
            indicators = [
                name for name, ind in self._indicators.items()
                if ind.category == category
            ]
        else:
            indicators = list(self._indicators.keys())
        
        return self.calculate(df, indicators)
    
    def get_available_indicators(self) -> Dict[str, Dict[str, Any]]:
        """获取可用指标列表"""
        return {
            name: ind.to_dict()
            for name, ind in self._indicators.items()
        }
    
    def get_indicator_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指标信息"""
        if name in self._indicators:
            return self._indicators[name].to_dict()
        return None


# 单例
_engine_instance: Optional[IndicatorEngine] = None


def get_indicator_engine() -> IndicatorEngine:
    """获取或创建指标引擎单例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = IndicatorEngine()
    return _engine_instance
