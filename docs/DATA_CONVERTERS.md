# 数据转换器使用文档

## 📋 概述

本项目提供了三个核心数据转换器，用于优化不同数据类型之间的转换：

1. **MarketDataNormalizer** - 金融数据标准化转换器
2. **WsMessageConverter** - WebSocket 消息类型转换器
3. **ChartDataConverter** - 图表数据快速转换器

## 📁 文件位置

### 后端
- `backend/utils/data_converters.py` - Python 版本转换器

### 前端
- `frontend/src/utils/dataConverters.ts` - TypeScript 版本转换器

---

## 🚀 1. MarketDataNormalizer - 金融数据标准化转换器

### 功能
- 统一 A 股/美股数据字段命名
- 货币单位标准化
- 日期格式标准化
- 支持 A 股（通达信/akshare）和美股（yfinance）数据格式

### 后端使用示例

```python
from backend.utils.data_converters import MarketDataNormalizer
import pandas as pd

# 示例1：标准化 OHLCV 数据
raw_data = [
    {'日期': '2024-01-01', '开盘': 100.0, '最高': 105.0, '最低': 99.0, '收盘': 103.0, '成交量': 1000000},
    {'日期': '2024-01-02', '开盘': 103.0, '最高': 108.0, '最低': 102.0, '收盘': 106.0, '成交量': 1500000},
]

normalized_df = MarketDataNormalizer.normalize_ohlcv(raw_data, market='cn')
print(normalized_df)

# 示例2：标准化财务数据
financial_data = {
    '市值': 10000000000,
    '市盈率': 25.5,
    '市净率': 3.2,
    '净利润': 500000000,
}

normalized_financial = MarketDataNormalizer.normalize_financial(financial_data, market='cn')
print(normalized_financial)

# 示例3：转换为统一格式
unified_data = MarketDataNormalizer.to_unified_format(
    symbol='600519',
    ohlcv=normalized_df,
    financial=normalized_financial,
    market='cn'
)
print(unified_data)
```

### 前端使用示例

```typescript
import { MarketDataNormalizer } from './utils/dataConverters';

// 标准化 OHLCV 数据
const rawData = [
  { Date: '2024-01-01', Open: 100.0, High: 105.0, Low: 99.0, Close: 103.0, Volume: 1000000 },
  { Date: '2024-01-02', Open: 103.0, High: 108.0, Low: 102.0, Close: 106.0, Volume: 1500000 },
];

const normalizedData = MarketDataNormalizer.normalizeOHLCV(rawData, 'us');
console.log(normalizedData);

// 转换为统一格式
const unified = MarketDataNormalizer.toUnifiedFormat('AAPL', normalizedData, {}, 'us');
console.log(unified);
```

---

## 🔌 2. WsMessageConverter - WebSocket 消息类型转换器

### 功能
- Python 对象转 WebSocket JSON 消息
- WebSocket JSON 消息转 Python 对象
- 消息类型验证
- 便捷方法创建常用消息类型

### 后端使用示例

```python
from backend.utils.data_converters import WsMessageConverter
from fastapi import WebSocket

async def handle_websocket(websocket: WebSocket):
    # 创建状态消息
    status_msg = WsMessageConverter.create_status("正在分析中...")
    json_str = WsMessageConverter.to_json(status_msg)
    await websocket.send_text(json_str)
    
    # 创建节点更新消息
    update_msg = WsMessageConverter.create_node_update(
        node="DataCollector",
        section="valuation",
        content="正在获取估值数据..."
    )
    await websocket.send_text(WsMessageConverter.to_json(update_msg))
    
    # 创建完成消息
    complete_msg = WsMessageConverter.create_complete("分析完成！")
    await websocket.send_text(WsMessageConverter.to_json(complete_msg))
    
    # 接收并解析消息
    data = await websocket.receive_text()
    parsed = WsMessageConverter.from_json(data)
    print(f"收到消息: {parsed}")
```

### 前端使用示例

```typescript
import { WsMessageConverter } from './utils/dataConverters';

// 发送消息
const statusMsg = WsMessageConverter.createStatus('正在连接...');
ws.send(WsMessageConverter.toJSON(statusMsg));

// 接收消息
ws.onmessage = (event) => {
  const message = WsMessageConverter.fromJSON(event.data);
  
  switch (message.type) {
    case 'node_update':
      console.log(`节点更新: ${message.node}`);
      break;
    case 'status':
      console.log(`状态: ${message.message}`);
      break;
    case 'complete':
      console.log('分析完成！');
      break;
  }
};
```

---

## 📊 3. ChartDataConverter - 图表数据快速转换器

### 功能
- DataFrame 转 OHLC 图表格式
- 支持多种图表库格式（Lightweight Charts、ECharts、Plotly）
- 零拷贝优化（适用于大数据量）

### 后端使用示例

```python
from backend.utils.data_converters import ChartDataConverter
import pandas as pd

# 示例1：转换为 Lightweight Charts 格式
df = pd.DataFrame({
    'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
    'open': [100, 103, 106],
    'high': [105, 108, 110],
    'low': [99, 102, 104],
    'close': [103, 106, 108],
    'volume': [1000000, 1500000, 2000000]
})

lightweight_data = ChartDataConverter.dataframe_to_ohlc(df, chart_type='lightweight')
print(lightweight_data)

# 示例2：转换为 ECharts 格式
echarts_data = ChartDataConverter.dataframe_to_ohlc(df, chart_type='echarts')
print(echarts_data)

# 示例3：零拷贝的 numpy 数组转换
import numpy as np
numpy_data = np.array([
    ['2024-01-01', 100, 105, 99, 103, 1000000],
    ['2024-01-02', 103, 108, 102, 106, 1500000],
])

fast_data = ChartDataConverter.fast_convert_ndarray(
    numpy_data,
    date_index=0,
    open_index=1,
    high_index=2,
    low_index=3,
    close_index=4
)
print(fast_data)
```

### 前端使用示例

```typescript
import { ChartDataConverter } from './utils/dataConverters';

const rawData = [
  { date: '2024-01-01', open: 100, high: 105, low: 99, close: 103, volume: 1000000 },
  { date: '2024-01-02', open: 103, high: 108, low: 102, close: 106, volume: 1500000 },
];

// 转换为 Lightweight Charts 格式
const lwData = ChartDataConverter.toOHLC(rawData, 'lightweight');
console.log(lwData);

// 转换为 ECharts 格式
const echartsData = ChartDataConverter.toOHLC(rawData, 'echarts');
console.log(echartsData);

// 转换为 Plotly 格式
const plotlyData = ChartDataConverter.toOHLC(rawData, 'plotly');
console.log(plotlyData);
```

---

## 🎯 实际应用场景

### 场景1：数据获取后标准化

```python
# 后端数据获取后立即标准化
from backend.data_layer.stock_data import fetch_ohlcv
from backend.utils.data_converters import MarketDataNormalizer

symbol = '600519'
raw_data = fetch_ohlcv(symbol, '2024-01-01', '2024-12-31', 'cn')
normalized_data = MarketDataNormalizer.normalize_ohlcv(raw_data, 'cn')
```

### 场景2：WebSocket 通信优化

```python
# 使用转换器替代手动 JSON 序列化
async def send_progress(websocket, message):
    msg = WsMessageConverter.create_status(message)
    await websocket.send_text(WsMessageConverter.to_json(msg))
```

### 场景3：图表渲染加速

```typescript
// 前端图表组件中使用
import { ChartDataConverter } from './utils/dataConverters';

const ChartComponent = ({ data }) => {
  const chartData = useMemo(() => {
    return ChartDataConverter.toOHLC(data, 'lightweight');
  }, [data]);
  
  return <LightweightChart data={chartData} />;
};
```

---

## 📈 性能优化建议

1. **批量转换优先**：一次处理多条数据，而非逐条转换
2. **使用零拷贝方法**：大数据量时使用 `fast_convert_ndarray`
3. **缓存转换结果**：对重复使用的数据进行缓存
4. **按需转换**：只转换需要的字段，避免不必要的计算

---

## 🔄 API 参考

### MarketDataNormalizer

| 方法 | 说明 |
|------|------|
| `normalize_ohlcv(data, market)` | 标准化 OHLCV 数据 |
| `normalize_financial(data, market)` | 标准化财务数据 |
| `to_unified_format(symbol, ohlcv, financial, market)` | 转换为统一格式 |

### WsMessageConverter

| 方法 | 说明 |
|------|------|
| `to_json(data)` | 对象转 JSON 字符串 |
| `from_json(json_str)` | JSON 字符串转对象 |
| `create_status(message, **kwargs)` | 创建状态消息 |
| `create_node_update(node, section, content)` | 创建节点更新消息 |
| `create_complete(message)` | 创建完成消息 |
| `create_error(message)` | 创建错误消息 |

### ChartDataConverter

| 方法 | 说明 |
|------|------|
| `dataframe_to_ohlc(df, chart_type)` | DataFrame 转图表格式 |
| `fast_convert_ndarray(data, ...)` | 零拷贝的 numpy 数组转换 |

---

## 📝 迁移指南

### 从旧代码迁移

**旧代码：**
```python
# 手动字段映射
df.rename(columns={'日期': 'date', '开盘': 'open'}, inplace=True)
```

**新代码：**
```python
# 使用转换器
from backend.utils.data_converters import MarketDataNormalizer
df = MarketDataNormalizer.normalize_ohlcv(raw_data, 'cn')
```

---

## 🤝 贡献指南

欢迎贡献更多数据转换场景！请参考：
- 添加新的数据源支持
- 支持更多图表库格式
- 性能优化改进

---

## 📄 许可证

本项目转换器遵循与主项目相同的许可证。
