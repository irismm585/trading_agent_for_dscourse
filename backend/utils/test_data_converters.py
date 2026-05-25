"""
数据转换器单元测试

测试内容：
1. MarketDataNormalizer - 金融数据标准化转换器
2. WsMessageConverter - WebSocket 消息类型转换器
3. ChartDataConverter - 图表数据快速转换器
4. LLMResponseParser - LLM响应解析器
"""

import json
from datetime import datetime
import pandas as pd
import numpy as np
import pytest

from backend.utils.data_converters import (
    MarketDataNormalizer,
    WsMessageConverter,
    ChartDataConverter,
    LLMResponseParser,
)


class TestMarketDataNormalizer:
    """测试 MarketDataNormalizer 类"""

    def test_normalize_ohlcv_cn_dict(self):
        """测试 A 股字典数据标准化"""
        data = {
            '日期': '2024-01-01',
            '开盘': 100.0,
            '最高': 105.0,
            '最低': 99.0,
            '收盘': 103.0,
            '成交量': 1000000,
        }

        result = MarketDataNormalizer.normalize_ohlcv(data, 'cn')

        assert isinstance(result, pd.DataFrame)
        assert result['date'][0] == '2024-01-01'
        assert result['open'][0] == 100.0
        assert result['high'][0] == 105.0
        assert result['low'][0] == 99.0
        assert result['close'][0] == 103.0
        assert result['volume'][0] == 1000000

    def test_normalize_ohlcv_us_dict(self):
        """测试美股字典数据标准化"""
        data = {
            'Date': '2024-01-01',
            'Open': 150.0,
            'High': 155.0,
            'Low': 149.0,
            'Close': 153.0,
            'Volume': 5000000,
        }

        result = MarketDataNormalizer.normalize_ohlcv(data, 'us')

        assert result['date'][0] == '2024-01-01'
        assert result['open'][0] == 150.0
        assert result['high'][0] == 155.0
        assert result['low'][0] == 149.0
        assert result['close'][0] == 153.0

    def test_normalize_ohlcv_list_dict(self):
        """测试列表字典数据标准化"""
        data = [
            {'日期': '2024-01-01', '开盘': 100, '收盘': 103},
            {'日期': '2024-01-02', '开盘': 103, '收盘': 106},
        ]

        result = MarketDataNormalizer.normalize_ohlcv(data, 'cn')

        assert len(result) == 2
        assert result['date'][0] == '2024-01-01'
        assert result['date'][1] == '2024-01-02'

    def test_normalize_ohlcv_dataframe(self):
        """测试 DataFrame 数据标准化"""
        df = pd.DataFrame([
            {'日期': '2024-01-01', '开盘': 100, '收盘': 103},
        ])

        result = MarketDataNormalizer.normalize_ohlcv(df, 'cn')

        assert isinstance(result, pd.DataFrame)
        assert result['date'][0] == '2024-01-01'

    def test_normalize_financial_cn(self):
        """测试 A 股财务数据标准化"""
        data = {
            '市值': 100000000000,
            '市盈率': 25.5,
            '市净率': 3.2,
        }

        result = MarketDataNormalizer.normalize_financial(data, 'cn')

        assert 'market_cap' in result
        assert result['market_cap'] == 1000.0

    def test_to_unified_format(self):
        """测试统一格式转换"""
        ohlcv = [
            {'日期': '2024-01-01', '开盘': 100, '收盘': 103},
        ]

        result = MarketDataNormalizer.to_unified_format(
            '600519', ohlcv, None, 'cn'
        )

        assert result['symbol'] == '600519'
        assert result['market'] == 'cn'
        assert 'ohlcv' in result
        assert 'updated_at' in result


class TestWsMessageConverter:
    """测试 WsMessageConverter 类"""

    def test_create_status(self):
        """测试创建状态消息"""
        msg = WsMessageConverter.create_status('测试消息')

        assert msg['type'] == 'status'
        assert msg['message'] == '测试消息'

    def test_create_node_update(self):
        """测试创建节点更新消息"""
        msg = WsMessageConverter.create_node_update(
            'DataCollector', 'valuation', '正在获取数据'
        )

        assert msg['type'] == 'node_update'
        assert msg['node'] == 'DataCollector'
        assert msg['section'] == 'valuation'

    def test_to_json(self):
        """测试 JSON 序列化"""
        data = {'type': 'status', 'message': '测试'}

        json_str = WsMessageConverter.to_json(data)

        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed['type'] == 'status'

    def test_from_json(self):
        """测试 JSON 反序列化"""
        json_str = '{"type": "status", "message": "测试"}'

        result = WsMessageConverter.from_json(json_str)

        assert result['type'] == 'status'
        assert result['message'] == '测试'

    def test_from_json_invalid(self):
        """测试无效 JSON 处理"""
        result = WsMessageConverter.from_json('invalid json')

        assert result['type'] == 'error'


class TestChartDataConverter:
    """测试 ChartDataConverter 类"""

    @pytest.fixture
    def sample_df(self):
        """示例 DataFrame"""
        return pd.DataFrame([
            {
                'date': '2024-01-01',
                'open': 100.0,
                'high': 105.0,
                'low': 99.0,
                'close': 103.0,
                'volume': 1000000,
            },
            {
                'date': '2024-01-02',
                'open': 103.0,
                'high': 108.0,
                'low': 102.0,
                'close': 106.0,
                'volume': 1200000,
            },
        ])

    def test_dataframe_to_ohlc_lightweight(self, sample_df):
        """测试转换为 Lightweight Charts 格式"""
        result = ChartDataConverter.dataframe_to_ohlc(
            sample_df, 'lightweight'
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert 'time' in result[0]
        assert 'open' in result[0]
        assert 'high' in result[0]
        assert 'low' in result[0]
        assert 'close' in result[0]

    def test_dataframe_to_ohlc_echarts(self, sample_df):
        """测试转换为 ECharts 格式"""
        result = ChartDataConverter.dataframe_to_ohlc(sample_df, 'echarts')

        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], list)

    def test_dataframe_to_ohlc_plotly(self, sample_df):
        """测试转换为 Plotly 格式"""
        result = ChartDataConverter.dataframe_to_ohlc(sample_df, 'plotly')

        assert isinstance(result, dict)
        assert 'x' in result
        assert 'open' in result

    def test_dataframe_to_ohlc_empty(self):
        """测试空 DataFrame 处理"""
        df = pd.DataFrame()

        result = ChartDataConverter.dataframe_to_ohlc(df)

        assert result == []

    def test_fast_convert_ndarray(self):
        """测试 numpy 数组快速转换"""
        # 使用时间戳而非字符串日期，避免 numpy 类型问题
        ts1 = pd.Timestamp('2024-01-01').timestamp()
        ts2 = pd.Timestamp('2024-01-02').timestamp()
        
        data = np.array([
            [ts1, 100.0, 105.0, 99.0, 103.0],
            [ts2, 103.0, 108.0, 102.0, 106.0],
        ])

        result = ChartDataConverter.fast_convert_ndarray(data)

        assert isinstance(result, list)
        assert len(result) == 2


class TestLLMResponseParser:
    """测试 LLMResponseParser 类"""

    def test_extract_json_from_markdown(self):
        """测试从 Markdown 代码块提取 JSON"""
        text = '''```json
        {"rating": "Buy", "reason": "测试"}
        ```'''

        result = LLMResponseParser.extract_json_from_markdown(text)

        assert result is not None
        assert result['rating'] == 'Buy'

    def test_extract_json_from_markdown_no_json_tag(self):
        """测试无 json 标签的代码块"""
        text = '''```
        {"rating": "Hold"}
        ```'''

        result = LLMResponseParser.extract_json_from_markdown(text)

        assert result is not None
        assert result['rating'] == 'Hold'

    def test_extract_final_decision_json(self):
        """测试从 JSON 格式提取决策"""
        text = '''```json
        {
            "rating": "持有/观望",
            "reasoning": "多空双方在技术面和基本面均提出了有力的论据",
            "key_risks": ["估值风险", "技术面背离"]
        }
        ```'''

        result = LLMResponseParser.extract_final_decision(text)

        assert result['rating'] == 'Hold'
        assert result['reasoning'] is not None
        assert len(result['key_risks']) == 2

    def test_extract_final_decision_plain_text(self):
        """测试从纯文本提取决策"""
        text = '''最终评级: 买入
评判理由: 公司基本面强劲
风险提示: 市场波动风险；政策风险'''

        result = LLMResponseParser.extract_final_decision(text)

        assert result['rating'] == 'Buy'
        assert result['reasoning'] is not None

    def test_normalize_rating_chinese(self):
        """测试中文评级标准化"""
        assert LLMResponseParser._normalize_rating('买入') == 'Buy'
        assert LLMResponseParser._normalize_rating('持有') == 'Hold'
        assert LLMResponseParser._normalize_rating('观望') == 'Hold'
        assert LLMResponseParser._normalize_rating('卖出') == 'Sell'

    def test_normalize_rating_english(self):
        """测试英文评级标准化"""
        assert LLMResponseParser._normalize_rating('Buy') == 'Buy'
        assert LLMResponseParser._normalize_rating('Hold') == 'Hold'
        assert LLMResponseParser._normalize_rating('Sell') == 'Sell'

    def test_normalize_rating_fuzzy(self):
        """测试模糊评级匹配"""
        assert LLMResponseParser._normalize_rating('建议买入') == 'Buy'
        assert LLMResponseParser._normalize_rating('强烈卖出') == 'Sell'

    def test_extract_financial_metrics(self):
        """测试财务指标提取"""
        text = '''估值分析：
市盈率: 18.5
市净率: 2.3
总市值: 500000000000'''

        result = LLMResponseParser.extract_financial_metrics(text)

        assert result['pe_ratio'] == 18.5
        assert result['pb_ratio'] == 2.3
        assert result['market_cap'] == 500000000000.0

    def test_extract_technical_indicators(self):
        """测试技术指标提取"""
        text = '''技术分析：
趋势: 上升趋势
MACD: 金叉信号，看涨'''

        result = LLMResponseParser.extract_technical_indicators(text)

        assert result['trend'] is not None
        assert result['macd_signal'] is not None

    def test_clean_dirty_text(self):
        """测试脏文本清理"""
        text = 'D这D是D测D试D文D本D'
        cleaned = LLMResponseParser._clean_dirty_text(text)
        assert 'D' not in cleaned

    def test_normalize_risks_list(self):
        """测试风险列表标准化"""
        risks = ['风险1', '风险2']

        result = LLMResponseParser._normalize_risks(risks)

        assert len(result) == 2

    def test_normalize_risks_dict_list(self):
        """测试字典风险列表标准化"""
        risks = [
            {'risk': '估值风险', 'description': '估值过高'},
            {'details': '技术面背离'},
        ]

        result = LLMResponseParser._normalize_risks(risks)

        assert len(result) >= 1

    def test_real_world_example(self):
        """测试真实世界数据解析"""
        text = '''```json
        {
            "rating": "持有/观望",
            "reason": "多空双方在技术面和基本面均提出了有力的论据",
            "key_risks": [
                {"risk": "估值风险"},
                {"risk": "技术面背离风险"}
            ]
        }
        ```'''

        result = LLMResponseParser.extract_final_decision(text)

        assert result['rating'] == 'Hold'
        assert len(result['key_risks']) >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
