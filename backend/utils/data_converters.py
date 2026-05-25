"""
数据类型转换工具库

包含：
1. MarketDataNormalizer - 金融数据标准化转换器
2. WsMessageConverter - WebSocket 消息类型转换器
3. ChartDataConverter - 图表数据快速转换器
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import pandas as pd
import numpy as np


# =============================================================================
# 1. 金融数据标准化转换器
# =============================================================================
class MarketDataNormalizer:
    """统一 A 股和美股数据格式的标准化转换器
    
    功能：
    - 统一 A 股/美股数据字段命名
    - 货币单位标准化
    - 日期格式标准化
    """
    
    # 字段映射：原始字段 -> 标准字段
    _FIELD_MAPPING = {
        'cn': {
            'date': 'date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'amount',
            # 中文字段映射
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount',
            '市值': 'market_cap',
            '市盈率': 'pe_ratio',
            '市净率': 'pb_ratio',
            '净利润': 'net_profit',
            '营业收入': 'revenue',
        },
        'us': {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
            'marketCap': 'market_cap',
            'trailingPE': 'pe_ratio',
            'priceToBook': 'pb_ratio',
            'netIncome': 'net_profit',
            'totalRevenue': 'revenue',
        }
    }
    
    @classmethod
    def normalize_ohlcv(
        cls, 
        data: Union[pd.DataFrame, List[Dict], Dict], 
        market: str
    ) -> pd.DataFrame:
        """标准化 OHLCV 数据
        
        Args:
            data: 原始数据（DataFrame、字典列表或单字典）
            market: 市场类型 'cn' 或 'us'
            
        Returns:
            标准化后的 DataFrame
        """
        if isinstance(data, dict):
            data = [data]
            
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = data.copy()
        
        # 字段重命名
        mapping = cls._FIELD_MAPPING.get(market, {})
        df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
        
        # 确保必要字段存在
        required_fields = ['date', 'open', 'high', 'low', 'close', 'volume']
        for field in required_fields:
            if field not in df.columns:
                df[field] = None
        
        # 日期标准化
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        # 数值类型标准化
        numeric_fields = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for field in numeric_fields:
            if field in df.columns:
                df[field] = pd.to_numeric(df[field], errors='coerce')
        
        return df
    
    @classmethod
    def normalize_financial(
        cls, 
        data: Dict, 
        market: str
    ) -> Dict[str, Any]:
        """标准化财务数据
        
        Args:
            data: 原始财务数据
            market: 市场类型 'cn' 或 'us'
            
        Returns:
            标准化后的财务数据
        """
        mapping = cls._FIELD_MAPPING.get(market, {})
        result = {}
        
        for src_key, dest_key in mapping.items():
            if src_key in data:
                result[dest_key] = data[src_key]
        
        # 货币单位标准化（统一为亿元）
        if market == 'cn' and 'market_cap' in result:
            result['market_cap'] = cls._normalize_currency(result['market_cap'], '亿')
        elif market == 'us' and 'market_cap' in result:
            result['market_cap'] = cls._normalize_currency(result['market_cap'], '亿')
        
        return result
    
    @staticmethod
    def _normalize_currency(value: Any, unit: str) -> Optional[float]:
        """货币单位标准化"""
        if value is None:
            return None
            
        try:
            num = float(value)
            if unit == '亿':
                return round(num / 100000000, 2)
            return num
        except (ValueError, TypeError):
            return None
    
    @classmethod
    def to_unified_format(
        cls, 
        symbol: str, 
        ohlcv: Union[pd.DataFrame, List], 
        financial: Optional[Dict] = None,
        market: str = 'cn'
    ) -> Dict[str, Any]:
        """转换为统一的内部数据格式
        
        Args:
            symbol: 股票代码
            ohlcv: OHLCV 数据
            financial: 财务数据（可选）
            market: 市场类型
            
        Returns:
            统一格式的数据字典
        """
        normalized_ohlcv = cls.normalize_ohlcv(ohlcv, market)
        
        result = {
            'symbol': symbol,
            'market': market,
            'ohlcv': normalized_ohlcv.to_dict('records'),
            'updated_at': datetime.now().isoformat()
        }
        
        if financial:
            result['financial'] = cls.normalize_financial(financial, market)
        
        return result


# =============================================================================
# 2. WebSocket 消息类型转换器
# =============================================================================
class WsMessageConverter:
    """WebSocket 消息序列化/反序列化转换器
    
    功能：
    - Python 对象转 WebSocket JSON 消息
    - WebSocket JSON 消息转 Python 对象
    - 消息类型验证
    """
    
    # 支持的消息类型
    VALID_TYPES = {
        'connected', 'disconnected',
        'node_update', 'status', 'section_complete',
        'complete', 'error',
        'stock_profile', 'chart_data', 'financial_data',
    }
    
    @classmethod
    def to_json(cls, data: Dict[str, Any]) -> str:
        """Python 对象转 WebSocket JSON 字符串
        
        Args:
            data: 要发送的数据字典
            
        Returns:
            JSON 字符串
        """
        # 确保有 type 字段
        if 'type' not in data:
            data['type'] = 'status'
        
        # 验证消息类型
        if data['type'] not in cls.VALID_TYPES:
            data['type'] = 'status'
        
        # 添加时间戳
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        
        # 处理特殊类型
        data = cls._prepare_for_serialization(data)
        
        return json.dumps(data, ensure_ascii=False, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> Dict[str, Any]:
        """WebSocket JSON 字符串转 Python 对象
        
        Args:
            json_str: JSON 字符串
            
        Returns:
            解析后的字典
        """
        try:
            data = json.loads(json_str)
            return cls._prepare_after_deserialization(data)
        except json.JSONDecodeError:
            return {
                'type': 'error',
                'message': 'Invalid JSON format',
                'timestamp': datetime.now().isoformat()
            }
    
    @classmethod
    def _prepare_for_serialization(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """序列化前的数据预处理"""
        result = data.copy()
        
        # 处理 DataFrame
        if isinstance(result.get('chart_data'), pd.DataFrame):
            result['chart_data'] = result['chart_data'].to_dict('records')
        
        # 处理 numpy 类型
        for key, value in result.items():
            if isinstance(value, (np.integer, np.floating)):
                result[key] = float(value)
        
        return result
    
    @classmethod
    def _prepare_after_deserialization(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """反序列化后的数据处理"""
        result = data.copy()
        
        # 解析时间戳
        if 'timestamp' in result:
            try:
                result['timestamp'] = datetime.fromisoformat(result['timestamp'])
            except (ValueError, TypeError):
                pass
        
        return result
    
    # 便捷方法：创建各种类型的消息
    @classmethod
    def create_status(cls, message: str, **kwargs) -> Dict[str, Any]:
        """创建状态消息"""
        return {
            'type': 'status',
            'message': message,
            **kwargs
        }
    
    @classmethod
    def create_node_update(
        cls, 
        node: str, 
        section: str, 
        content: str
    ) -> Dict[str, Any]:
        """创建节点更新消息"""
        return {
            'type': 'node_update',
            'node': node,
            'section': section,
            'content': content
        }
    
    @classmethod
    def create_complete(cls, message: str = "分析完成") -> Dict[str, Any]:
        """创建完成消息"""
        return {
            'type': 'complete',
            'message': message
        }
    
    @classmethod
    def create_error(cls, message: str) -> Dict[str, Any]:
        """创建错误消息"""
        return {
            'type': 'error',
            'message': message
        }


# =============================================================================
# 3. 图表数据快速转换器
# =============================================================================
class ChartDataConverter:
    """图表数据快速转换器
    
    功能：
    - DataFrame 转 OHLC 图表格式
    - 零拷贝优化（适用于大数据量）
    - 支持多种图表库格式
    """
    
    @staticmethod
    def dataframe_to_ohlc(
        df: pd.DataFrame,
        chart_type: str = 'lightweight'
    ) -> List[Dict[str, Any]]:
        """DataFrame 转 OHLC 图表格式
        
        Args:
            df: OHLCV DataFrame
            chart_type: 图表类型 ('lightweight', 'echarts', 'plotly')
            
        Returns:
            图表数据数组
        """
        if df.empty:
            return []
        
        # 确保必要字段存在
        required = ['date', 'open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required):
            return []
        
        # 根据图表类型转换
        if chart_type == 'lightweight':
            return ChartDataConverter._to_lightweight(df)
        elif chart_type == 'echarts':
            return ChartDataConverter._to_echarts(df)
        elif chart_type == 'plotly':
            return ChartDataConverter._to_plotly(df)
        else:
            return ChartDataConverter._to_lightweight(df)
    
    @staticmethod
    def _to_lightweight(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """转换为 Lightweight Charts 格式"""
        result = []
        for _, row in df.iterrows():
            # 处理日期
            try:
                if isinstance(row['date'], str):
                    ts = int(pd.Timestamp(row['date']).timestamp())
                else:
                    ts = int(pd.Timestamp(row['date']).timestamp())
            except (ValueError, TypeError):
                continue
            
            result.append({
                'time': ts,
                'open': float(row['open']) if pd.notna(row['open']) else 0,
                'high': float(row['high']) if pd.notna(row['high']) else 0,
                'low': float(row['low']) if pd.notna(row['low']) else 0,
                'close': float(row['close']) if pd.notna(row['close']) else 0,
            })
            if 'volume' in df.columns and pd.notna(row['volume']):
                result[-1]['volume'] = float(row['volume'])
        
        return result
    
    @staticmethod
    def _to_echarts(df: pd.DataFrame) -> List[List]:
        """转换为 ECharts 格式"""
        result = []
        for _, row in df.iterrows():
            try:
                date_str = str(row['date'])
            except (ValueError, TypeError):
                continue
            
            result.append([
                date_str,
                float(row['open']) if pd.notna(row['open']) else None,
                float(row['close']) if pd.notna(row['close']) else None,
                float(row['low']) if pd.notna(row['low']) else None,
                float(row['high']) if pd.notna(row['high']) else None,
                float(row['volume']) if 'volume' in df.columns and pd.notna(row['volume']) else None,
            ])
        
        return result
    
    @staticmethod
    def _to_plotly(df: pd.DataFrame) -> Dict[str, List]:
        """转换为 Plotly 格式"""
        return {
            'x': df['date'].tolist(),
            'open': df['open'].tolist(),
            'high': df['high'].tolist(),
            'low': df['low'].tolist(),
            'close': df['close'].tolist(),
            'volume': df['volume'].tolist() if 'volume' in df.columns else [],
        }
    
    @staticmethod
    def fast_convert_ndarray(
        data: np.ndarray,
        date_index: int = 0,
        open_index: int = 1,
        high_index: int = 2,
        low_index: int = 3,
        close_index: int = 4
    ) -> List[Dict[str, Any]]:
        """零拷贝的 numpy 数组快速转换（性能优化）
        
        Args:
            data: numpy 数组 [date, open, high, low, close, ...]
            date_index: 日期列索引
            open_index: 开盘价列索引
            high_index: 最高价列索引
            low_index: 最低价列索引
            close_index: 收盘价列索引
            
        Returns:
            图表数据数组
        """
        result = []
        n = len(data)
        
        for i in range(n):
            row = data[i]
            
            # 处理日期
            try:
                date_val = row[date_index]
                if isinstance(date_val, str):
                    ts = int(pd.Timestamp(date_val).timestamp())
                elif isinstance(date_val, (int, float)):
                    ts = int(date_val)
                else:
                    ts = int(pd.Timestamp(str(date_val)).timestamp())
            except (ValueError, TypeError):
                continue
            
            result.append({
                'time': ts,
                'open': float(row[open_index]),
                'high': float(row[high_index]),
                'low': float(row[low_index]),
                'close': float(row[close_index]),
            })
        
        return result
