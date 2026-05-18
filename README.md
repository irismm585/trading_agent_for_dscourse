# 📊 A-Share Trading Agents

多智能体 LLM 金融分析系统，支持 **A 股** 和 **美股** 股票分析。前端展示 K 线图、技术面/基本面/情绪分析，后端通过多智能体辩论与评委决策生成投资建议。

## 功能特性

- **📈 行情数据展示** — K 线图 + 技术指标（均线、EMA、布林带等）
- **🤖 多维度 AI 分析** — 技术面、基本面、市场情绪三大分析报告
- **⚔️ 多空辩论** — 多头分析师 vs 空头分析师回合制辩论
- **🏛️ 评委决策** — 综合辩论内容给出 Buy / Hold / Sell 评级
- **🔍 股票搜索** — 支持股票代码和名称模糊搜索（A 股 + 美股）
- **🇨🇳🇺🇸 双市场** — 同时支持 A 股和美股分析

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
│   │   └── types/
│   │       └── index.ts        # TypeScript 类型定义
│   └── package.json
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
