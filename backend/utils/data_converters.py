"""
数据类型转换工具库

包含：
1. MarketDataNormalizer - 金融数据标准化转换器
2. WsMessageConverter - WebSocket 消息类型转换器
3. ChartDataConverter - 图表数据快速转换器
4. LLMResponseParser - LLM响应解析器
5. TypeSafeDecorators - 类型安全装饰器（方案4）
6. CacheDecorators - 性能优化缓存装饰器（方案5）
7. BatchDataValidator - 批量数据验证器（方案7）
"""

from __future__ import annotations

import json
import re
import hashlib
import functools
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import pandas as pd
import numpy as np


# =============================================================================
# 常量定义
# =============================================================================
# 图表类型
CHART_TYPE_LIGHTWEIGHT = 'lightweight'
CHART_TYPE_ECHARTS = 'echarts'
CHART_TYPE_PLOTLY = 'plotly'
VALID_CHART_TYPES = {CHART_TYPE_LIGHTWEIGHT, CHART_TYPE_ECHARTS, CHART_TYPE_PLOTLY}


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
        # 验证市场类型
        if market not in cls._FIELD_MAPPING:
            raise ValueError(
                f"Invalid market: {market}. Must be one of {list(cls._FIELD_MAPPING.keys())}"
            )
        
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
        chart_type: str = CHART_TYPE_LIGHTWEIGHT
    ) -> List[Dict[str, Any]]:
        """DataFrame 转 OHLC 图表格式
        
        Args:
            df: OHLCV DataFrame
            chart_type: 图表类型 (CHART_TYPE_LIGHTWEIGHT, CHART_TYPE_ECHARTS, CHART_TYPE_PLOTLY)
            
        Returns:图表数据数组
        """
        if df.empty:
            return []
        
        # 确保必要字段存在
        required = ['date', 'open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required):
            return []
        
        # 验证图表类型，默认使用 lightweight
        if chart_type not in VALID_CHART_TYPES:
            chart_type = CHART_TYPE_LIGHTWEIGHT
        
        # 根据图表类型转换
        if chart_type == CHART_TYPE_LIGHTWEIGHT:
            return ChartDataConverter._to_lightweight(df)
        elif chart_type == CHART_TYPE_ECHARTS:
            return ChartDataConverter._to_echarts(df)
        elif chart_type == CHART_TYPE_PLOTLY:
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
    
    # 预编译的正则表达式模式
    _JSON_BLOCK_PATTERN = re.compile(r'```(?:json)?\s*([\s\S]*?)\s*```')
    _SINGLE_D_PATTERN = re.compile(r'D')  # 简化：移除所有D字符
    _MULTIPLE_D_PATTERN = re.compile(r'D{2,}')
    
    # 评级映射（使用标准化的键，查找时统一转小写）
    RATING_MAPPING = {
        # 中文
        '买入': 'Buy',
        '持有': 'Hold',
        '观望': 'Hold',
        '持有/观望': 'Hold',
        '卖出': 'Sell',
        # 英文
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
        # 首先清理文本，去除乱码字符
        cleaned_text = cls._clean_dirty_text(text)
        
        # 匹配 ```json ... ``` 格式（可能有多个代码块）
        matches = cls._JSON_BLOCK_PATTERN.findall(cleaned_text)
        
        for json_candidate in matches:
            # 尝试修复JSON格式
            repaired_json = cls._repair_json(json_candidate.strip())
            if repaired_json:
                try:
                    return json.loads(repaired_json)
                except json.JSONDecodeError:
                    continue
        
        # 如果没有找到代码块，尝试直接解析整个文本
        try:
            repaired_text = cls._repair_json(cleaned_text.strip())
            if repaired_text:
                return json.loads(repaired_text)
        except json.JSONDecodeError:
            pass
        
        return None
    
    @classmethod
    def _clean_dirty_text(cls, text: str) -> str:
        """清理脏文本，去除乱码字符
        
        Args:
            text: 原始文本
            
        Returns:清理后的文本
        """
        # 移除所有D字符（乱码）
        cleaned = cls._SINGLE_D_PATTERN.sub('', text)
        # 移除问号字符
        cleaned = re.sub(r'[�?]', '', cleaned)
        # 移除多余的空格和换行
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    @classmethod
    def _repair_json(cls, json_str: str) -> Optional[str]:
        """尝试修复格式错误的JSON
        
        Args:
            json_str: 有问题的JSON字符串
            
        Returns:修复后的JSON字符串，或None如果无法修复
        """
        if not json_str:
            return None
        
        repaired = json_str
        
        # 修复常见的JSON格式错误
        # 1. 修复缺少逗号的问题（在}或]前添加逗号）
        repaired = re.sub(r'(\s*})(\s*"[^"]+"\s*:)', r'\1,\2', repaired)
        repaired = re.sub(r'(\s*\])(\s*"[^"]+"\s*:)', r'\1,\2', repaired)
        
        # 2. 修复多余的花括号
        # 查找第一个{和最后一个}，只保留中间部分
        start_idx = repaired.find('{')
        end_idx = repaired.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            repaired = repaired[start_idx:end_idx + 1]
        
        # 3. 修复不匹配的引号
        # 移除多余的引号
        repaired = repaired.replace('""', '"')
        repaired = repaired.replace("''", "'")
        
        # 4. 尝试简单修复（这是一个简化版，实际中可能需要更复杂的逻辑）
        # 尝试删除行首/行尾的非JSON字符
        repaired = repaired.strip()
        
        # 检查是否看起来像JSON
        if repaired.startswith('{') and repaired.endswith('}'):
            return repaired
        
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
        # 首先清理文本
        cleaned_text = cls._clean_dirty_text(text)
        
        # 1. 先尝试在JSON字符串中查找评级（即使JSON格式错误）
        # 查找 "rating": "..." 模式
        rating_json_match = re.search(
            r'"rating"\s*:\s*["\']([^"\']+)["\']',
            cleaned_text
        )
        if rating_json_match:
            result['rating'] = cls._normalize_rating(rating_json_match.group(1).strip())
        
        # 2. 如果JSON模式没找到，再尝试文本模式
        if not result['rating']:
            rating_match = re.search(
                r'(?:最终评级|评级|rating)[：:]\s*([^\n"\',}]+)',
                text
            )
            if rating_match:
                result['rating'] = cls._normalize_rating(rating_match.group(1).strip())
        
        # 3. 直接搜索常见的评级关键词
        if not result['rating']:
            for chinese_rating, english_rating in [
                ('买入', 'Buy'),
                ('持有/观望', 'Hold'),
                ('持有', 'Hold'),
                ('观望', 'Hold'),
                ('卖出', 'Sell'),
            ]:
                if chinese_rating in cleaned_text:
                    result['rating'] = english_rating
                    break
        
        # 4. 提取理由 - 同时支持JSON模式和文本模式
        reasoning_json_match = re.search(
            r'"(?:reasoning|reason)"\s*:\s*["\']([^"\']+)["\']',
            cleaned_text
        )
        if reasoning_json_match:
            result['reasoning'] = reasoning_json_match.group(1).strip()
        else:
            # 尝试文本模式
            reasoning_match = re.search(
                r'(?:评判理由|理由|reasoning|reason)[：:]\s*([^\n]+)',
                text
            )
            if reasoning_match:
                result['reasoning'] = reasoning_match.group(1).strip()
        
        # 5. 提取风险 - 同时支持JSON模式和文本模式
        # 先从JSON数组中提取
        risk_patterns = [
            r'"risk"\s*:\s*["\']([^"\']+)["\']',
            r'"description"\s*:\s*["\']([^"\']+)["\']',
            r'"details"\s*:\s*["\']([^"\']+)["\']',
        ]
        
        risks = []
        for pattern in risk_patterns:
            matches = re.findall(pattern, cleaned_text)
            risks.extend(m.strip() for m in matches if m.strip())
        
        # 如果JSON模式没找到，尝试文本模式
        if not risks:
            risks_match = re.search(
                r'(?:风险提示|主要风险|key_risks|key risks)[：:]\s*([^\n]+)',
                text
            )
            if risks_match:
                risk_text = risks_match.group(1).strip()
                # 分号分隔
                if '；' in risk_text:
                    risks = [r.strip() for r in risk_text.split('；') if r.strip()]
                elif ';' in risk_text:
                    risks = [r.strip() for r in risk_text.split(';') if r.strip()]
        
        # 去重
        result['key_risks'] = list(set(risks))
        
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
        rating_lower = rating_str.lower()
        
        # 先尝试精确匹配中文
        if rating_str in cls.RATING_MAPPING:
            return cls.RATING_MAPPING[rating_str]
        
        # 再尝试匹配小写英文
        if rating_lower in cls.RATING_MAPPING:
            return cls.RATING_MAPPING[rating_lower]
        
        # 最后尝试子字符串匹配（优先中文，再英文）
        for key, value in cls.RATING_MAPPING.items():
            if key in rating_str or key in rating_lower:
                return value
        
        # 如果没有匹配，尝试更宽松的匹配
        if '买' in rating_str or 'buy' in rating_lower:
            return 'Buy'
        elif '卖' in rating_str or 'sell' in rating_lower:
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


# =============================================================================
# 5. 类型安全装饰器（方案4）
# =============================================================================
class TypeSafeDecorators:
    """类型安全装饰器集合
    
    功能：
    - 参数类型检查
    - 返回值类型验证
    - 自动类型转换
    - 参数范围验证
    """
    
    @staticmethod
    def validate_types(**type_specs):
        """参数类型验证装饰器
        
        Args:
            **type_specs: 参数名 -> 类型 的映射
            
        Example:
            @TypeSafeDecorators.validate_types(data=pd.DataFrame, market=str)
            def process_data(data, market):
                pass
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                import inspect
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                for param_name, expected_type in type_specs.items():
                    if param_name in bound_args.arguments:
                        value = bound_args.arguments[param_name]
                        if not isinstance(value, expected_type):
                            raise TypeError(
                                f"Parameter '{param_name}' should be {expected_type.__name__}, "
                                f"got {type(value).__name__}"
                            )
                
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def validate_return(expected_type: type):
        """返回值类型验证装饰器
        
        Args:
            expected_type: 期望的返回值类型
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                if not isinstance(result, expected_type):
                    raise TypeError(
                        f"Function should return {expected_type.__name__}, "
                        f"got {type(result).__name__}"
                    )
                return result
            return wrapper
        return decorator
    
    @staticmethod
    def validate_in_set(param_name: str, valid_values: Set[Any]):
        """参数值范围验证装饰器
        
        Args:
            param_name: 要验证的参数名
            valid_values: 允许的取值集合
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                import inspect
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    if value not in valid_values:
                        raise ValueError(
                            f"Parameter '{param_name}' should be one of {valid_values}, "
                            f"got {value}"
                        )
                
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def auto_convert(**converters):
        """自动类型转换装饰器
        
        Args:
            **converters: 参数名 -> 转换函数 的映射
            
        Example:
            @TypeSafeDecorators.auto_convert(value=float)
            def process(value):
                pass
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                import inspect
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                for param_name, converter in converters.items():
                    if param_name in bound_args.arguments:
                        try:
                            bound_args.arguments[param_name] = converter(
                                bound_args.arguments[param_name]
                            )
                        except (ValueError, TypeError) as e:
                            raise TypeError(
                                f"Could not convert parameter '{param_name}': {e}"
                            )
                
                return func(*bound_args.args, **bound_args.kwargs)
            return wrapper
        return decorator


# =============================================================================
# 6. 性能优化缓存装饰器（方案5）
# =============================================================================
class CacheDecorators:
    """性能优化缓存装饰器集合
    
    功能：
    - LRU 缓存装饰器
    - TTL 缓存装饰器
    - 结果缓存装饰器
    - 基于参数哈希的缓存键生成
    """
    
    _cache_store: Dict[str, Tuple[Any, float]] = {}
    
    @staticmethod
    def cache_result(ttl_seconds: Optional[float] = None):
        """结果缓存装饰器
        
        Args:
            ttl_seconds: 缓存过期时间（秒），None表示永不过期
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # 生成缓存键
                key_parts = [func.__module__, func.__qualname__]
                
                # 处理位置参数
                for arg in args:
                    key_parts.append(CacheDecorators._hashable(arg))
                
                # 处理关键字参数（排序以确保一致性）
                sorted_kwargs = sorted(kwargs.items())
                for key, value in sorted_kwargs:
                    key_parts.append(f"{key}={CacheDecorators._hashable(value)}")
                
                cache_key = "|".join(key_parts)
                cache_key = hashlib.sha256(cache_key.encode()).hexdigest()
                
                # 检查缓存
                if cache_key in CacheDecorators._cache_store:
                    cached_value, expire_time = CacheDecorators._cache_store[cache_key]
                    if ttl_seconds is None or (expire_time is None or datetime.now().timestamp() < expire_time):
                        return cached_value
                
                # 执行函数
                result = func(*args, **kwargs)
                
                # 存储到缓存
                expire_time = None if ttl_seconds is None else datetime.now().timestamp() + ttl_seconds
                CacheDecorators._cache_store[cache_key] = (result, expire_time)
                
                return result
            return wrapper
        return decorator
    
    @staticmethod
    def _hashable(obj: Any) -> str:
        """转换对象为可哈希的字符串"""
        if isinstance(obj, pd.DataFrame):
            # DataFrame 使用其字符串表示的哈希
            return f"DF:{hashlib.md5(obj.to_csv(index=False).encode()).hexdigest()}"
        elif isinstance(obj, np.ndarray):
            # numpy 数组使用其数据哈希
            return f"NP:{hashlib.md5(obj.tobytes()).hexdigest()}"
        elif isinstance(obj, list):
            # 列表递归处理
            return f"LIST:[{','.join(CacheDecorators._hashable(x) for x in obj)}]"
        elif isinstance(obj, dict):
            # 字典排序后递归处理
            sorted_items = sorted((str(k), CacheDecorators._hashable(v)) for k, v in obj.items())
            return f"DICT:{{{','.join(f'{k}={v}' for k, v in sorted_items)}}}"
        else:
            return str(obj)
    
    @staticmethod
    def clear_cache():
        """清空所有缓存"""
        CacheDecorators._cache_store.clear()
    
    @staticmethod
    def cache_info():
        """获取缓存统计信息
        
        Returns:
            包含缓存大小等信息的字典
        """
        return {
            'size': len(CacheDecorators._cache_store),
            'keys': list(CacheDecorators._cache_store.keys())
        }


# =============================================================================
# 7. 批量数据验证器（方案7）
# =============================================================================
class BatchDataValidator:
    """批量数据验证器
    
    功能：
    - 批量验证数据完整性
    - 数据格式验证
    - 范围检查
    - 数据质量报告生成
    """
    
    @staticmethod
    def validate_ohlcv_data(df: pd.DataFrame, strict: bool = True) -> Dict[str, Any]:
        """批量验证 OHLCV 数据
        
        Args:
            df: 待验证的 DataFrame
            strict: 是否严格模式（发现错误直接抛异常）
            
        Returns:
            包含验证结果的字典
        """
        report = {
            'total_rows': len(df),
            'valid_rows': 0,
            'invalid_rows': [],
            'errors': [],
            'warnings': []
        }
        
        # 检查必要列
        required_columns = ['date', 'open', 'high', 'low', 'close']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            error_msg = f"Missing required columns: {missing_columns}"
            report['errors'].append(error_msg)
            if strict:
                raise ValueError(error_msg)
            return report
        
        # 验证每一行
        for idx, row in df.iterrows():
            row_errors = []
            
            # 检查日期
            try:
                pd.to_datetime(row['date'])
            except (ValueError, TypeError):
                row_errors.append(f"Invalid date: {row['date']}")
            
            # 检查 OHLC 数值
            for col in ['open', 'high', 'low', 'close']:
                try:
                    val = float(row[col])
                    if pd.isna(val):
                        row_errors.append(f"{col} is NaN")
                except (ValueError, TypeError):
                    row_errors.append(f"Invalid {col}: {row[col]}")
            
            # 检查 OHLC 逻辑
            if not row_errors:
                if float(row['high']) < float(row['low']):
                    row_errors.append("High < Low")
                if float(row['high']) < float(row['open']):
                    row_errors.append("High < Open")
                if float(row['high']) < float(row['close']):
                    row_errors.append("High < Close")
                if float(row['low']) > float(row['open']):
                    row_errors.append("Low > Open")
                if float(row['low']) > float(row['close']):
                    row_errors.append("Low > Close")
            
            if row_errors:
                report['invalid_rows'].append({
                    'index': idx,
                    'date': row['date'],
                    'errors': row_errors
                })
            else:
                report['valid_rows'] += 1
        
        # 检查 volume 列（如果有）
        if 'volume' in df.columns:
            invalid_volumes = df[df['volume'] < 0].index.tolist()
            if invalid_volumes:
                report['warnings'].append(f"Negative volume in rows: {invalid_volumes[:10]}")
        
        return report
    
    @staticmethod
    def validate_financial_data(data: Dict[str, Any], strict: bool = True) -> Dict[str, Any]:
        """批量验证财务数据
        
        Args:
            data: 待验证的财务数据字典
            strict: 是否严格模式
            
        Returns:
            包含验证结果的字典
        """
        report = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # 验证数值字段
        numeric_fields = ['pe_ratio', 'pb_ratio', 'market_cap', 'net_profit', 'revenue']
        
        for field in numeric_fields:
            if field in data and data[field] is not None:
                try:
                    val = float(data[field])
                    if val < 0 and field not in ['net_profit']:
                        report['warnings'].append(f"{field} has negative value: {val}")
                except (ValueError, TypeError):
                    error_msg = f"{field} is not a valid number: {data[field]}"
                    report['errors'].append(error_msg)
        
        report['valid'] = len(report['errors']) == 0
        
        if strict and not report['valid']:
            raise ValueError("Financial data validation failed: " + "; ".join(report['errors']))
        
        return report
    
    @staticmethod
    def validate_dataframe_schema(df: pd.DataFrame, expected_schema: Dict[str, type], strict: bool = True) -> Dict[str, Any]:
        """验证 DataFrame 模式
        
        Args:
            df: 待验证的 DataFrame
            expected_schema: 期望的列名 -> 类型 的映射
            strict: 是否严格模式
            
        Returns:
            包含验证结果的字典
        """
        report = {
            'valid': True,
            'missing_columns': [],
            'type_mismatches': [],
            'extra_columns': []
        }
        
        # 类型兼容性映射（numpy类型到Python类型的兼容关系）
        type_compatibility = {
            int: (int, np.integer),
            float: (float, np.floating),
            str: (str, np.str_, np.object_)
        }
        
        # 检查缺失的列
        for col, dtype in expected_schema.items():
            if col not in df.columns:
                report['missing_columns'].append(col)
        
        # 检查类型不匹配
        for col, dtype in expected_schema.items():
            if col in df.columns:
                # 简单类型检查
                sample = df[col].iloc[0] if len(df) > 0 else None
                if sample is not None:
                    # 检查类型兼容性
                    compatible = False
                    if isinstance(sample, dtype):
                        compatible = True
                    elif dtype in type_compatibility:
                        # 检查是否是兼容的numpy类型
                        for compatible_type in type_compatibility[dtype]:
                            if isinstance(sample, compatible_type):
                                compatible = True
                                break
                    # 如果不兼容，报告错误
                    if not compatible:
                        report['type_mismatches'].append({
                            'column': col,
                            'expected': dtype.__name__,
                            'got': type(sample).__name__
                        })
        
        # 检查额外的列
        extra_cols = set(df.columns) - set(expected_schema.keys())
        if extra_cols:
            report['extra_columns'] = list(extra_cols)
        
        report['valid'] = len(report['missing_columns']) == 0 and len(report['type_mismatches']) == 0
        
        if strict and not report['valid']:
            raise ValueError(f"Schema validation failed: {report}")
        
        return report
    
    @staticmethod
    def generate_quality_report(df: pd.DataFrame) -> Dict[str, Any]:
        """生成数据质量报告
        
        Args:
            df: 待分析的 DataFrame
            
        Returns:
            包含数据质量指标的字典
        """
        report = {
            'row_count': len(df),
            'column_count': len(df.columns),
            'columns': list(df.columns),
            'missing_values': {},
            'duplicate_rows': 0,
            'data_types': {},
            'numeric_stats': {}
        }
        
        # 检查缺失值
        for col in df.columns:
            missing = df[col].isna().sum()
            report['missing_values'][col] = {
                'count': int(missing),
                'percentage': float(missing / len(df) * 100)
            }
        
        # 检查重复行
        report['duplicate_rows'] = int(df.duplicated().sum())
        
        # 获取数据类型
        for col in df.columns:
            report['data_types'][col] = str(df[col].dtype)
        
        # 数值列统计
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            report['numeric_stats'][col] = {
                'mean': float(df[col].mean()),
                'min': float(df[col].min()),
                'max': float(df[col].max()),
                'median': float(df[col].median())
            }
        
        return report
