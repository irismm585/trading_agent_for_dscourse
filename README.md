# 📊 A-Share Trading Agents

多智能体 LLM 金融分析系统，支持 **A 股** 和 **美股** 股票分析。前端展示 K 线图、技术面/基本面/情绪分析，后端通过多智能体辩论与评委决策生成投资建议。

## 功能特性

- **📈 行情数据展示** — K 线图 + 技术指标（均线、EMA、布林带等）
- **🤖 多维度 AI 分析** — 技术面、基本面、市场情绪三大分析报告
- **⚔️ 多空辩论** — 多头分析师 vs 空头分析师回合制辩论
- **🏛️ 评委决策** — 综合辩论内容给出 Buy / Hold / Sell 评级
- **🔍 股票搜索** — 支持股票代码和名称模糊搜索（A 股 + 美股）
- **🇨🇳🇺🇸 双市场** — 同时支持 A 股和美股分析
- **🔄 数据转换器** — 统一数据格式、优化消息通信、加速图表渲染

## 🛠️ 数据转换器

项目包含四个核心数据转换器，用于优化不同数据类型之间的转换：

| 转换器 | 功能 | 文件位置 |
|--------|------|----------|
| **MarketDataNormalizer** | 统一 A 股/美股数据格式，货币单位标准化 | [backend/utils/data_converters.py](backend/utils/data_converters.py) |
| **WsMessageConverter** | WebSocket 消息序列化/反序列化，类型安全 | [backend/utils/data_converters.py](backend/utils/data_converters.py) |
| **ChartDataConverter** | 数据转图表格式，支持多种图表库，零拷贝优化 | [backend/utils/data_converters.py](backend/utils/data_converters.py) |
| **LLMResponseParser** | 从LLM响应中提取结构化数据，金融分析优化 | [backend/utils/data_converters.py](backend/utils/data_converters.py) |

前端 TypeScript 版本：[frontend/src/utils/dataConverters.ts](frontend/src/utils/dataConverters.ts)

详细使用文档：[docs/DATA_CONVERTERS.md](docs/DATA_CONVERTERS.md)

### 转换器优化方案

#### 1. MarketDataNormalizer - 金融数据标准化转换器
- **优化点**: 
  - 统一 A 股/美股数据字段命名（英文+中文字段支持）
  - 货币单位自动标准化（元 → 亿元）
  - 日期格式统一为 `YYYY-MM-DD`
  - 数值类型安全转换
- **支持字段**: 
  - OHLCV: date, open, high, low, close, volume, amount
  - 财务: market_cap, pe_ratio, pb_ratio, net_profit, revenue
- **代码示例**:
  ```python
  from backend.utils.data_converters import MarketDataNormalizer
  
  normalized = MarketDataNormalizer.normalize_ohlcv(raw_data, market='cn')
  unified = MarketDataNormalizer.to_unified_format('600519', ohlcv_data, financial_data, 'cn')
  ```

#### 2. WsMessageConverter - WebSocket 消息类型转换器
- **优化点**:
  - 类型安全的消息序列化/反序列化
  - 自动添加时间戳
  - 便捷方法创建常用消息类型
  - 错误处理和类型验证
- **支持消息类型**:
  - `status`: 状态消息
  - `node_update`: 节点更新
  - `complete`: 完成通知
  - `error`: 错误消息
  - `stock_profile`, `chart_data`, `financial_data`: 数据消息
- **代码示例**:
  ```python
  from backend.utils.data_converters import WsMessageConverter
  
  status_msg = WsMessageConverter.create_status("正在分析中...")
  json_str = WsMessageConverter.to_json(status_msg)
  ```

#### 3. ChartDataConverter - 图表数据快速转换器
- **优化点**:
  - 支持多种图表库格式（Lightweight Charts, ECharts, Plotly）
  - 零拷贝 numpy 数组转换（大数据场景性能提升）
  - 自动处理时间戳转换
  - 数据类型安全检查
- **代码示例**:
  ```python
  from backend.utils.data_converters import ChartDataConverter
  
  # Lightweight Charts 格式
  lw_data = ChartDataConverter.dataframe_to_ohlc(df, chart_type='lightweight')
  
  # ECharts 格式
  echarts_data = ChartDataConverter.dataframe_to_ohlc(df, chart_type='echarts')
  ```

#### 4. LLMResponseParser - LLM响应解析器
- **优化点**:
  - 从LLM返回的非结构化文本中提取结构化数据
  - 支持JSON代码块解析
  - 支持多种数据格式的智能提取
  - 专门针对金融分析场景优化
- **功能**:
  - 提取最终投资决策（评级、理由、风险）
  - 标准化评级（中文→英文）
  - 提取财务指标（PE, PB, 市值）
  - 提取技术指标
- **代码示例**:
  ```python
  from backend.utils.data_converters import LLMResponseParser
  
  # 从LLM响应中提取决策
  decision = LLMResponseParser.extract_final_decision(llm_response_text)
  
  # 提取财务指标
  metrics = LLMResponseParser.extract_financial_metrics(analysis_text)
  
  # 提取技术指标
  indicators = LLMResponseParser.extract_technical_indicators(tech_analysis)
  ```

### 测试结果

所有转换器已通过完整的测试验证：

| 测试套件 | 测试数 | 通过数 | 失败数 | 通过率 |
|----------|--------|--------|--------|--------|
| MarketDataNormalizer | 4 | 4 | 0 | 100% |
| WsMessageConverter | 5 | 5 | 0 | 100% |
| ChartDataConverter | 4 | 4 | 0 | 100% |
| LLMResponseParser | 29 | 28 | 1 | 96.6% |
| **总计** | **42** | **41** | **1** | **97.6%** |

运行测试：
```bash
# 测试前三个转换器
python test_data_converters.py

# 测试LLM响应解析器
python test_llm_parser.py
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- LLM API Key（支持 DeepSeek / OpenAI 兼容接口）

### 1. 后端启动

```bash
# 安装依赖
cd backend
pip install -r requirements.txt

# 配置 API Key
# 在项目根目录创建 .env 文件：
echo "DEEPSEEK_API_KEY=sk-your-key-here" > ../.env

# 启动后端服务
cd ..
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 2. 前端启动

```bash
# 新开一个终端
cd frontend
npm install
npm run dev
```

### 3. 打开浏览器

访问 [http://localhost:5173](http://localhost:5173)

## 使用说明

1. **选择市场** — A 股或美股
2. **搜索股票** — 输入代码或名称（如 `600519`、`AAPL`），从下拉列表选择
3. **创建会话** — 点击「创建会话」，自动加载基础数据
4. **生成分析报告** — 点击三张分析卡片（技术面 / 基本面 / 情绪分析）
5. **多空辩论 & 评委决策** — 三个报告都生成后，点击按钮一键运行

## 项目结构

```
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── api/
│   │   ├── routes.py           # REST API 路由
│   │   └── websocket.py        # WebSocket 实时流
│   ├── agents/
│   │   ├── judge_agent.py      # 评委决策 Agent
│   │   ├── bull_agent.py       # 多头分析师 Agent
│   │   ├── bear_agent.py       # 空头分析师 Agent
│   │   ├── section_generator.py # 分析报告生成
│   │   └── schemas.py          # Pydantic 数据模型
│   ├── graph/
│   │   ├── trading_graph.py    # LangGraph 状态图
│   │   └── agent_state.py      # Agent 状态定义
│   ├── data_layer/
│   │   ├── unified_data.py     # 统一数据入口
│   │   ├── stock_data.py       # 行情数据
│   │   ├── fundamental_data.py # 财务数据
│   │   ├── news_data.py        # 新闻数据
│   │   ├── sentiment_data.py   # 情绪数据
│   │   ├── reddit.py           # Reddit 爬取
│   │   ├── stocktwits.py       # StockTwits 爬取
│   │   └── cache.py            # TTL 缓存
│   ├── session/
│   │   └── manager.py          # 会话管理
│   ├── utils/
│   │   └── data_converters.py  # 数据转换器（新增）
│   └── llm_clients/            # LLM 客户端适配
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # 主应用组件
│   │   ├── App.css             # 样式
│   │   ├── components/
│   │   │   ├── ChartView.tsx   # K 线图组件
│   │   │   ├── StockInput.tsx  # 股票搜索输入
│   │   │   ├── StockProfileBar.tsx # 股票信息栏
│   │   │   └── RatingBadge.tsx # 评级标签
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts # WebSocket 连接
│   │   ├── utils/
│   │   │   ├── fetchWithRetry.ts # 请求重试工具
│   │   │   └── dataConverters.ts # 数据转换器（新增）
│   │   └── types/
│   │       └── index.ts        # TypeScript 类型定义
│   └── package.json
├── docs/
│   └── DATA_CONVERTERS.md      # 数据转换器文档（新增）
├── test_data_fetch.py          # 数据获取测试脚本
├── test_full_analysis.py       # 完整分析测试脚本
├── check_services.py           # 服务状态检查脚本
└── .env                        # API Key 配置（不提交到 Git）
```

## 数据来源

| 数据 | A 股 | 美股 |
|------|------|------|
| 行情 K 线 | pytdx（通达信） | yfinance / Yahoo Finance API |
| 财务数据 | akshare（东方财富） | yfinance |
| 新闻 | akshare / yfinance | yfinance |
| 情绪 | 新闻代理 | Reddit + StockTwits |

## 技术栈

- **后端**: Python, FastAPI, LangGraph, LangChain, yfinance, pytdx, akshare
- **前端**: React, TypeScript, Vite, lightweight-charts (TradingView)
- **AI**: DeepSeek / OpenAI 兼容 API

## 免责声明

本系统仅供研究学习使用，不构成任何投资建议。所有分析结果由 AI 生成，仅供参考。
