"""Async Data Fetcher - 异步数据获取模块

提供异步版本的数据获取功能，支持并行获取多种数据类型。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

from backend.data_layer.stock_data import get_stock_ohlcv, compute_indicators
from backend.data_layer.fundamental_data import get_financial_data
from backend.data_layer.news_data import get_stock_news, get_market_news
from backend.data_layer.sentiment_data import get_social_sentiment
from backend.data_layer.anysearch import search_stock_info


class AsyncDataFetcher:
    """异步数据获取器
    
    支持并行获取 OHLCV、财务、新闻、情绪等数据。
    """
    
    def __init__(self, max_concurrent: int = 5, timeout: int = 30):
        """初始化异步数据获取器
        
        Args:
            max_concurrent: 最大并发数
            timeout: 单个请求超时时间（秒）
        """
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _run_in_thread(self, func, *args, **kwargs):
        """在线程池中运行同步函数"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    async def fetch_ohlcv_async(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        market: str = "cn"
    ) -> Dict[str, Any]:
        """异步获取 OHLCV 数据"""
        async with self._semaphore:
            try:
                start_time = time.time()
                df = await self._run_in_thread(
                    get_stock_ohlcv, symbol, start_date, end_date, market
                )
                
                indicators = {}
                if df is not None and not df.empty:
                    indicators = await self._run_in_thread(compute_indicators, df)
                
                return {
                    "success": True,
                    "ohlcv_df": df,
                    "indicators": indicators,
                    "fetch_time_ms": (time.time() - start_time) * 1000,
                    "error": None
                }
            except Exception as e:
                return {
                    "success": False,
                    "ohlcv_df": None,
                    "indicators": {},
                    "fetch_time_ms": 0,
                    "error": str(e)
                }
    
    async def fetch_financial_async(
        self,
        symbol: str,
        market: str = "cn"
    ) -> Dict[str, Any]:
        """异步获取财务数据"""
        async with self._semaphore:
            try:
                start_time = time.time()
                data = await self._run_in_thread(get_financial_data, symbol, market)
                return {
                    "success": True,
                    "data": data,
                    "fetch_time_ms": (time.time() - start_time) * 1000,
                    "error": None
                }
            except Exception as e:
                return {
                    "success": False,
                    "data": {},
                    "fetch_time_ms": 0,
                    "error": str(e)
                }
    
    async def fetch_news_async(
        self,
        symbol: str,
        market: str = "cn",
        limit: int = 20
    ) -> Dict[str, Any]:
        """异步获取新闻数据"""
        async with self._semaphore:
            try:
                start_time = time.time()
                stock_news = await self._run_in_thread(
                    get_stock_news, symbol, market, limit
                )
                market_news = await self._run_in_thread(
                    get_market_news, market, 10
                )
                return {
                    "success": True,
                    "stock_news": stock_news,
                    "market_news": market_news,
                    "fetch_time_ms": (time.time() - start_time) * 1000,
                    "error": None
                }
            except Exception as e:
                return {
                    "success": False,
                    "stock_news": [],
                    "market_news": [],
                    "fetch_time_ms": 0,
                    "error": str(e)
                }
    
    async def fetch_sentiment_async(
        self,
        symbol: str,
        market: str = "cn"
    ) -> Dict[str, Any]:
        """异步获取情绪数据"""
        async with self._semaphore:
            try:
                start_time = time.time()
                data = await self._run_in_thread(get_social_sentiment, symbol, market)
                return {
                    "success": True,
                    "data": data,
                    "fetch_time_ms": (time.time() - start_time) * 1000,
                    "error": None
                }
            except Exception as e:
                return {
                    "success": False,
                    "data": {},
                    "fetch_time_ms": 0,
                    "error": str(e)
                }
    
    async def fetch_search_async(
        self,
        symbol: str,
        name: str = "",
        max_results: int = 5
    ) -> Dict[str, Any]:
        """异步获取搜索数据"""
        async with self._semaphore:
            try:
                start_time = time.time()
                results = await self._run_in_thread(
                    search_stock_info, symbol, name, max_results
                )
                return {
                    "success": True,
                    "results": results,
                    "fetch_time_ms": (time.time() - start_time) * 1000,
                    "error": None
                }
            except Exception as e:
                return {
                    "success": False,
                    "results": [],
                    "fetch_time_ms": 0,
                    "error": str(e)
                }
    
    async def fetch_all_parallel(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        market: str = "cn",
        include_news: bool = True,
        include_sentiment: bool = True,
        include_search: bool = True
    ) -> Dict[str, Any]:
        """并行获取所有数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            market: 市场 (cn/us)
            include_news: 是否包含新闻
            include_sentiment: 是否包含情绪数据
            include_search: 是否包含搜索数据
            
        Returns:
            包含所有数据的字典
        """
        start_time = time.time()
        
        # 准备并行任务
        tasks = [
            self.fetch_ohlcv_async(symbol, start_date, end_date, market),
            self.fetch_financial_async(symbol, market),
        ]
        
        if include_news:
            tasks.append(self.fetch_news_async(symbol, market))
        
        if include_sentiment:
            tasks.append(self.fetch_sentiment_async(symbol, market))
        
        if include_search:
            tasks.append(self.fetch_search_async(symbol))
        
        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 整理结果
        result = {
            "symbol": symbol,
            "market": market,
            "start_date": start_date,
            "end_date": end_date,
            "total_time_ms": (time.time() - start_time) * 1000,
            "ohlcv": None,
            "financial": None,
            "news": None,
            "sentiment": None,
            "search": None,
            "errors": []
        }
        
        idx = 0
        result["ohlcv"] = results[idx] if not isinstance(results[idx], Exception) else None
        if isinstance(results[idx], Exception):
            result["errors"].append(f"OHLCV: {str(results[idx])}")
        
        idx += 1
        result["financial"] = results[idx] if not isinstance(results[idx], Exception) else None
        if isinstance(results[idx], Exception):
            result["errors"].append(f"Financial: {str(results[idx])}")
        
        if include_news:
            idx += 1
            result["news"] = results[idx] if not isinstance(results[idx], Exception) else None
            if isinstance(results[idx], Exception):
                result["errors"].append(f"News: {str(results[idx])}")
        
        if include_sentiment:
            idx += 1
            result["sentiment"] = results[idx] if not isinstance(results[idx], Exception) else None
            if isinstance(results[idx], Exception):
                result["errors"].append(f"Sentiment: {str(results[idx])}")
        
        if include_search:
            idx += 1
            result["search"] = results[idx] if not isinstance(results[idx], Exception) else None
            if isinstance(results[idx], Exception):
                result["errors"].append(f"Search: {str(results[idx])}")
        
        return result


# 便捷函数
_fetcher_instance: Optional[AsyncDataFetcher] = None


def get_async_fetcher(max_concurrent: int = 5) -> AsyncDataFetcher:
    """获取或创建异步数据获取器单例"""
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = AsyncDataFetcher(max_concurrent=max_concurrent)
    return _fetcher_instance


async def async_fetch_all(
    symbol: str,
    start_date: str,
    end_date: str,
    market: str = "cn"
) -> Dict[str, Any]:
    """便捷函数：异步获取所有数据"""
    fetcher = get_async_fetcher()
    return await fetcher.fetch_all_parallel(symbol, start_date, end_date, market)
