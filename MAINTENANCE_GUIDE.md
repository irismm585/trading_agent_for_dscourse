# 多智能体金融分析系统 - 维护指南

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-05-25 |
| 作者 | 系统维护团队 |
| 适用版本 | trading_agent_for_dscourse |

---

## 目录

1. [问题修复记录](#问题修复记录)
   - [LLM 客户端兼容问题](#11-llm-客户端兼容问题)
2. [测试验证流程](#测试验证流程)
   - [数据获取测试](#21-数据获取测试)
   - [完整分析流程测试](#22-完整分析流程测试)
3. [配置指南](#配置指南)
   - [LLM API 配置](#31-llm-api-配置)
   - [数据源配置](#32-数据源配置)
4. [故障排查](#故障排查)
   - [常见错误及解决方案](#41-常见错误及解决方案)
5. [代码参考](#代码参考)

---

## 1. 问题修复记录

### 1.1 LLM 客户端兼容问题

#### 问题描述

当使用第三方 OpenAI 兼容 API（如硅基流动）时，调用失败，返回 `Not Found` 错误。

#### 根本原因

在 `openai_client.py` 中，当 `provider` 设置为 `"openai"` 时，代码会强制设置 `use_responses_api=True`：

```python
# 修复前的代码
if self.provider == "openai":
    llm_kwargs["use_responses_api"] = True
```

该参数是 OpenAI 官方 API 的特性，第三方 API（如硅基流动）不支持此参数，导致请求失败。

#### 修复方案

修改判断逻辑，只有当使用官方 OpenAI API（未设置自定义 `base_url`）时才启用该参数：

```python
# 修复后的代码
if self.provider == "openai" and not self.base_url:
    llm_kwargs["use_responses_api"] = True
```

**文件位置**: [backend/llm_clients/openai_client.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/backend/llm_clients/openai_client.py#L152-L153)

#### 验证结果

| 测试项 | 结果 |
|--------|------|
| 硅基流动 API 调用 | ✅ 成功 |
| OpenAI 官方 API | ✅ 正常 |
| DeepSeek API | ✅ 正常 |
| 完整分析流程 | ✅ 通过 |

---

## 2. 测试验证流程

### 2.1 数据获取测试

#### 测试脚本

运行以下命令测试数据获取功能：

```bash
python3 /Users/bytedance/Documents/trae_projects/trading_agent_finance/test_data_fetch.py
```

**测试脚本位置**: [test_data_fetch.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/test_data_fetch.py)

#### 测试结果

| 测试类别 | 测试数量 | 成功 | 失败 |
|----------|----------|------|------|
| A股测试 | 5 | ✅ 5 | ❌ 0 |
| 美股测试 | 3 | ✅ 3 | ❌ 0 |
| **总计** | **8** | **✅ 8** | **❌ 0** |

#### 测试用例

| 股票代码 | 名称 | 市场 |
|----------|------|------|
| 600519 | 贵州茅台 | A股 |
| 000001 | 平安银行 | A股 |
| 601318 | 中国平安 | A股 |
| 000858 | 五粮液 | A股 |
| 600036 | 招商银行 | A股 |
| AAPL | 苹果 | 美股 |
| MSFT | 微软 | 美股 |
| GOOGL | 谷歌 | 美股 |

### 2.2 完整分析流程测试

#### 测试脚本

运行以下命令测试完整分析流程：

```bash
python3 /Users/bytedance/Documents/trae_projects/trading_agent_finance/test_full_analysis.py
```

**测试脚本位置**: [test_full_analysis.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/test_full_analysis.py)

#### 测试流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    完整分析流程测试步骤                          │
├─────────────────────────────────────────────────────────────────┤
│  1. 创建会话                                                    │
│     └─ POST /api/session                                       │
│                                                                 │
│  2. 连接 WebSocket                                              │
│     └─ ws://localhost:8000/ws/{session_id}                     │
│                                                                 │
│  3. 生成分析报告（6个维度）                                      │
│     ├─ valuation      (估值分析)                                │
│     ├─ technical      (技术面分析)                              │
│     ├─ fundamental    (基本面分析)                              │
│     ├─ sentiment      (市场情绪分析)                            │
│     ├─ news           (新闻资讯)                                │
│     └─ summary        (研究摘要)                                │
│                                                                 │
│  4. 多空辩论                                                    │
│     ├─ BullAgent      (多头分析师)                              │
│     └─ BearAgent      (空头分析师)                              │
│                                                                 │
│  5. 评委决策                                                    │
│     └─ JudgeAgent     (综合评判)                                │
│                                                                 │
│  6. 获取结果                                                    │
│     └─ GET /api/session/{session_id}                           │
└─────────────────────────────────────────────────────────────────┘
```

#### 测试结果（贵州茅台 600519）

| 分析阶段 | 状态 | 耗时 |
|----------|------|------|
| 估值分析 | ✅ 完成 | ~30秒 |
| 技术面分析 | ✅ 完成 | ~25秒 |
| 基本面分析 | ✅ 完成 | ~35秒 |
| 市场情绪分析 | ✅ 完成 | ~20秒 |
| 新闻资讯 | ✅ 完成 | ~15秒 |
| 研究摘要 | ✅ 完成 | ~20秒 |
| 多空辩论 | ✅ 完成 | ~30秒 |
| 评委决策 | ✅ 完成 | ~30秒 |
| **总计** | **✅ 全部通过** | **~208秒** |

#### 输出示例

最终决策 JSON 格式：

```json
{
  "rating": "持有/观望",
  "reason": "多空双方在技术面和基本面上均提出了有力的论据...",
  "key_risks": [
    {
      "risk": "估值分析中的长期估值风险",
      "details": "虽然市盈率动态PE当前位置合理..."
    },
    {
      "risk": "短期技术指标背离风险",
      "details": "MACD指标出现背离信号..."
    }
  ]
}
```

---

## 3. 配置指南

### 3.1 LLM API 配置

#### 环境变量配置

**文件位置**: [.env](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/.env)

```env
# 硅基流动 API 配置示例
OPENAI_API_KEY=sk-xxx
TRADINGAGENTS_LLM_BACKEND_URL=https://api.siliconflow.cn/v1
TRADINGAGENTS_LLM_PROVIDER=openai
TRADINGAGENTS_DEEP_THINK_LLM=Qwen/Qwen2.5-7B-Instruct
TRADINGAGENTS_QUICK_THINK_LLM=Qwen/Qwen2.5-7B-Instruct
```

#### 支持的 LLM 提供商

| Provider | Base URL | API Key 环境变量 |
|----------|----------|------------------|
| openai | https://api.openai.com/v1 | OPENAI_API_KEY |
| deepseek | https://api.deepseek.com | DEEPSEEK_API_KEY |
| qwen | https://dashscope-intl.aliyuncs.com/compatible-mode/v1 | DASHSCOPE_API_KEY |
| qwen-cn | https://dashscope.aliyuncs.com/compatible-mode/v1 | DASHSCOPE_API_KEY |
| glm | https://api.z.ai/api/paas/v4/ | GLM_API_KEY |
| minimax | https://api.minimax.io/v1 | MINIMAX_API_KEY |
| openrouter | https://openrouter.ai/api/v1 | OPENROUTER_API_KEY |
| ollama | http://localhost:11434/v1 | 无需 API Key |

### 3.2 数据源配置

#### 数据源优先级

系统支持多级数据源回退机制：

```
┌─────────────────────────────────────────────────────────────┐
│                    A股数据源优先级                          │
├─────────────────────────────────────────────────────────────┤
│  1. pytdx       (通达信协议)      ← 首选                   │
│  2. akshare     (备用)            ← 次之                   │
│  3. yfinance    (回退)            ← 最后                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    美股数据源                                │
├─────────────────────────────────────────────────────────────┤
│  1. yfinance    (Yahoo Finance)  ← 唯一数据源              │
└─────────────────────────────────────────────────────────────┘
```

#### 重试机制配置

**文件位置**: [backend/data_layer/stock_data.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/backend/data_layer/stock_data.py)

| 参数 | 当前值 | 说明 |
|------|--------|------|
| 最大重试次数 | 5 | 每次请求的最大重试次数 |
| 重试延迟 | 指数退避 | 1s, 2s, 4s, 8s, 16s |

---

## 4. 故障排查

### 4.1 常见错误及解决方案

| 错误信息 | 可能原因 | 解决方案 |
|----------|----------|----------|
| `Not Found` | LLM API 调用失败 | 检查 `base_url` 配置，确保未启用 `use_responses_api` |
| `RemoteDisconnected` | akshare 连接失败 | 等待重试，系统会自动切换到 pytdx 或 yfinance |
| `WebSocket connection failed` | 后端服务未启动 | 启动后端服务: `uvicorn backend.main:app --host 0.0.0.0 --port 8000` |
| `ModuleNotFoundError: websocket` | 缺少依赖 | 安装依赖: `pip3 install websocket-client` |
| 分析结果乱码 | 模型输出问题 | 尝试使用更强大的模型，或增加 `max_tokens` 参数 |

### 4.2 服务状态检查

运行以下命令检查服务状态：

```bash
python3 /Users/bytedance/Documents/trae_projects/trading_agent_finance/check_services.py
```

**脚本位置**: [check_services.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/check_services.py)

#### 检查内容

| 检查项 | 说明 |
|--------|------|
| 端口占用 | 检查 8000（后端）和 5173（前端）端口 |
| 进程状态 | 检查 Python 和 Node.js 进程 |
| HTTP 连通性 | 检查服务是否正常响应 |

---

## 5. 代码参考

### 核心文件清单

| 文件路径 | 功能描述 |
|----------|----------|
| [backend/main.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/backend/main.py) | FastAPI 应用入口 |
| [backend/api/routes.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/backend/api/routes.py) | REST API 路由定义 |
| [backend/api/websocket.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/backend/api/websocket.py) | WebSocket 实时通信 |
| [backend/llm_clients/openai_client.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/backend/llm_clients/openai_client.py) | LLM 客户端实现 |
| [backend/graph/trading_graph.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/backend/graph/trading_graph.py) | 多智能体工作流 |
| [backend/data_layer/stock_data.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/backend/data_layer/stock_data.py) | 行情数据获取 |
| [backend/data_layer/fundamental_data.py](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/backend/data_layer/fundamental_data.py) | 基本面数据获取 |

### VS Code 任务集成

**文件位置**: [.vscode/tasks.json](file:///Users/bytedance/Documents/trae_projects/trading_agent_finance/.vscode/tasks.json)

| 任务名称 | 快捷键 | 说明 |
|----------|--------|------|
| 检查服务状态 | Ctrl+Shift+C | 运行 check_services.py |
| 启动所有服务 | Ctrl+Shift+S | 启动后端和前端 |
| 测试数据获取 | Ctrl+Shift+T | 运行 test_data_fetch.py |

---

## 附录

### 测试结果存储位置

测试结果自动保存到以下目录：

```
/Users/bytedance/Documents/trae_projects/trading_agent_finance/test_results/
├── analysis_600519_YYYYMMDD_HHMMSS.json   # 完整分析结果
├── test_report_YYYYMMDD_HHMMSS.txt         # 测试报告
└── test_data_YYYYMMDD_HHMMSS.json          # 测试数据
```

### 日志记录

数据获取日志记录在以下文件：

- 行情数据失败记录: `data_fetch_errors.json`
- 基本面数据失败记录: `fundamental_errors.json`

---

**文档版本**: v1.0  
**最后更新**: 2026-05-25