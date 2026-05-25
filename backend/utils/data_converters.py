"""
数据类型转换工具库

包含：
1. MarketDataNormalizer - 金融数据标准化转换器
2. WsMessageConverter - WebSocket 消息类型转换器
3. ChartDataConverter - 图表数据快速转换器
4. LLMResponseParser - LLM响应解析器
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
            
        Returns:统一格式的数据字典
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
            
        Returns:JSON 字符串
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
            
        Returns:解析后的字典
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
            
        Returns:图表数据数组
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
            
        Returns:图表数据数组
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


# =============================================================================
# 4. LLM响应解析器
# =============================================================================
class LLMResponseParser:
    """LLM响应解析器
    
    功能：
    - 从LLM返回的非结构化文本中提取结构化数据
    - 支持JSON代码块解析
    - 支持多种数据格式的智能提取
    - 专门针对金融分析场景优化
    """
    
    # 评级映射
    RATING_MAPPING = {
        # 中文
        '买入': 'Buy',
        '持有': 'Hold',
        '观望': 'Hold',
        '持有/观望': 'Hold',
        '卖出': 'Sell',
        # 英文
        'Buy': 'Buy',
        'Hold': 'Hold',
        'Sell': 'Sell',
        'buy': 'Buy',
        'hold': 'Hold',
        'sell': 'Sell',
    }
    
    @classmethod
    def extract_json_from_markdown(cls, text: str) -> Optional[Dict[str, Any]]:
        """从Markdown代码块中提取JSON
        
        Args:
            text: 包含JSON代码块的文本
            
        Returns:解析后的JSON字典，失败返回None
        """
        # 匹配 ```json ... ``` 格式
        pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(pattern, text)
        
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # 如果没有找到代码块，尝试直接解析整个文本
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None
    
    @classmethod
    def extract_final_decision(cls, text: str) -> Dict[str, Any]:
        """从LLM响应中提取最终投资决策
        
        Args:
            text: LLM返回的文本
            
        Returns:包含rating、reasoning、key_risks等字段的字典
        """
        result = {
            'rating': None,
            'reasoning': None,
            'key_risks': [],
            'suggested_entry_price': None,
            'suggested_holding_period': None,
        }
        
        # 首先尝试从JSON代码块中提取
        json_data = cls.extract_json_from_markdown(text)
        if json_data:
            return cls._parse_final_decision_from_json(json_data, result)
        
        # 如果JSON解析失败，尝试使用正则表达式提取
        return cls._extract_final_decision_with_regex(text, result)
    
    @classmethod
    def _parse_final_decision_from_json(
        cls, 
        json_data: Dict[str, Any], 
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """从JSON数据中解析最终决策
        
        Args:
            json_data: 解析后的JSON字典
            result: 结果字典
            
        Returns:填充后的结果字典
        """
        # 提取评级
        if 'rating' in json_data:
            result['rating'] = cls._normalize_rating(json_data['rating'])
        
        # 提取理由
        if 'reasoning' in json_data:
            result['reasoning'] = json_data['reasoning']
        elif 'reason' in json_data:
            result['reasoning'] = json_data['reason']
        
        # 提取风险
        if 'key_risks' in json_data:
            risks = json_data['key_risks']
            result['key_risks'] = cls._normalize_risks(risks)
        
        # 提取建议入场价
        if 'suggested_entry_price' in json_data:
            result['suggested_entry_price'] = cls._safe_float(json_data['suggested_entry_price'])
        
        # 提取建议持有周期
        if 'suggested_holding_period' in json_data:
            result['suggested_holding_period'] = json_data['suggested_holding_period']
        
        return result
    
    @classmethod
    def _extract_final_decision_with_regex(
        cls, 
        text: str, 
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用正则表达式从文本中提取最终决策
        
        Args:
            text: 文本内容
            result: 结果字典
            
        Returns:填充后的结果字典
        """
        # 提取评级
        rating_match = re.search(
            r'(?:最终评级|评级|rating)[：:]\s*([^\n]+)',
            text
        )
        if rating_match:
            result['rating'] = cls._normalize_rating(rating_match.group(1).strip())
        
        # 提取理由
        reasoning_match = re.search(
            r'(?:评判理由|理由|reasoning|reason)[：:]\s*([\s\S]*?)(?=\n\*\*|$)',
            text
        )
        if reasoning_match:
            result['reasoning'] = reasoning_match.group(1).strip()
        
        # 提取风险
        risks_match = re.search(
            r'(?:风险提示|主要风险|key_risks|key risks)[：:]\s*([\s\S]*?)(?=\n\*\*|$)',
            text
        )
        if risks_match:
            result['key_risks'] = cls._extract_risks_from_text(risks_match.group(1).strip())
        
        # 提取建议入场价
        price_match = re.search(
            r'(?:建议入场价|入场价|suggested_entry_price)[：:]\s*[^¥]?[¥]?\s*([\d.]+)',
            text
        )
        if price_match:
            result['suggested_entry_price'] = cls._safe_float(price_match.group(1))
        
        # 提取建议持有周期
        period_match = re.search(
            r'(?:建议持有周期|持有周期|suggested_holding_period)[：:]\s*([^\n]+)',
            text
        )
        if period_match:
            result['suggested_holding_period'] = period_match.group(1).strip()
        
        return result
    
    @classmethod
    def _normalize_rating(cls, rating: Any) -> Optional[str]:
        """标准化评级
        
        Args:
            rating: 原始评级
            
        Returns:标准化后的评级 ('Buy', 'Hold', 'Sell') 或 None
        """
        if rating is None:
            return None
        
        rating_str = str(rating).strip()
        
        for key, value in cls.RATING_MAPPING.items():
            if key in rating_str:
                return value
        
        # 如果没有匹配，尝试更宽松的匹配
        if '买' in rating_str or 'Buy' in rating_str or 'buy' in rating_str:
            return 'Buy'
        elif '卖' in rating_str or 'Sell' in rating_str or 'sell' in rating_str:
            return 'Sell'
        else:
            return 'Hold'
    
    @classmethod
    def _normalize_risks(cls, risks: Any) -> List[str]:
        """标准化风险列表
        
        Args:
            risks: 原始风险数据（可以是列表、字符串或其他类型）
            
        Returns:标准化的风险字符串列表
        """
        if risks is None:
            return []
        
        if isinstance(risks, list):
            normalized = []
            for risk in risks:
                if isinstance(risk, dict):
                    # 如果是字典，尝试提取描述
                    risk_str = (
                        risk.get('description', '') or
                        risk.get('details', '') or
                        risk.get('risk', '')
                    )
                    if risk_str:
                        normalized.append(str(risk_str).strip())
                elif risk:
                    normalized.append(str(risk).strip())
            return [r for r in normalized if r]
        
        if isinstance(risks, str):
            return cls._extract_risks_from_text(risks)
        
        return []
    
    @classmethod
    def _extract_risks_from_text(cls, text: str) -> List[str]:
        """从文本中提取风险列表
        
        Args:
            text: 包含风险的文本
            
        Returns:风险字符串列表
        """
        risks = []
        
        # 尝试按分号或换行分割
        parts = re.split(r'[；;\n]', text)
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # 去除可能的编号前缀
            part = re.sub(r'^[0-9]+[.、]\s*', '', part)
            
            if part:
                risks.append(part)
        
        return risks
    
    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """安全地转换为浮点数
        
        Args:
            value: 要转换的值
            
        Returns:浮点数或None
        """
        if value is None:
            return None
        
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    @classmethod
    def extract_financial_metrics(cls, text: str) -> Dict[str, Optional[float]]:
        """从文本中提取财务指标
        
        Args:
            text: 包含财务指标的文本
            
        Returns:包含pe_ratio、pb_ratio、market_cap等字段的字典
        """
        result = {
            'pe_ratio': None,
            'pb_ratio': None,
            'market_cap': None,
            'net_profit': None,
            'revenue': None,
        }
        
        # 提取市盈率 - 简单直接的模式
        pe_match = re.search(r'市盈率.*?[:：]\s*([\d.]+)', text, re.DOTALL | re.IGNORECASE)
        if pe_match:
            result['pe_ratio'] = cls._safe_float(pe_match.group(1))
        
        # 提取市净率
        pb_match = re.search(r'市净率.*?[:：]\s*([\d.]+)', text, re.DOTALL | re.IGNORECASE)
        if pb_match:
            result['pb_ratio'] = cls._safe_float(pb_match.group(1))
        
        # 提取市值
        cap_match = re.search(r'(?:市值|总市值).*?[:：]\s*([\d,.]+)', text, re.DOTALL | re.IGNORECASE)
        if cap_match:
            cap_str = cap_match.group(1).replace(',', '')
            result['market_cap'] = cls._safe_float(cap_str)
        
        return result
    
    @classmethod
    def extract_technical_indicators(cls, text: str) -> Dict[str, Any]:
        """从文本中提取技术指标
        
        Args:
            text: 包含技术指标的文本
            
        Returns:包含技术指标的字典
        """
        result = {
            'ma5': None,
            'ma10': None,
            'ma20': None,
            'macd_signal': None,
            'trend': None,
        }
        
        # 提取趋势
        trend_match = re.search(
            r'(?:趋势|trend)[：:]\s*([^\n]+)',
            text, re.IGNORECASE
        )
        if trend_match:
            result['trend'] = trend_match.group(1).strip()
        
        # 提取MACD信号
        macd_match = re.search(
            r'(?:MACD|macd_signal)[：:]\s*([^\n]+)',
            text, re.IGNORECASE
        )
        if macd_match:
            result['macd_signal'] = macd_match.group(1).strip()
        
        return result
