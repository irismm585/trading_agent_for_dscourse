# 数据流水线 - 严格模式技术文档

## 概述

本文档详细介绍 DataPipeline 的验证逻辑、错误处理机制，以及严格模式（Strict Mode）的工作原理。

---

## 目录
1. [架构概览](#架构概览)
2. [验证流程详解](#验证流程详解)
3. [严格模式 vs 宽松模式](#严格模式-vs-宽松模式)
4. [错误类型与处理](#错误类型与处理)
5. [实际使用示例](#实际使用示例)
6. [调试技巧](#调试技巧)

---

## 架构概览

### 核心组件

```
DataPipeline (主控制器)
├── TypeSafeDecorators (类型安全)
├── BatchDataValidator (数据验证)
│   ├── OHLCV 验证
│   ├── 财务指标验证
│   └── 数据质量报告
└── 验证日志系统
```

### 模块位置

- **流水线主逻辑**: [`backend/data_layer/data_pipeline.py`](../backend/data_layer/data_pipeline.py)
- **验证器**: [`backend/utils/data_converters.py`](../backend/utils/data_converters.py)
- **数据获取**: [`backend/data_layer/unified_data.py`](../backend/data_layer/unified_data.py)

---

## 验证流程详解

### 完整数据验证流程 (`fetch_validated_data`)

```
1. 获取数据
   ↓
2. OHLCV 验证 (先执行)
   ├─ 检查数据框是否为空
   ├─ 使用 BatchDataValidator.validate_ohlcv_data()
   ├─ 检查最小行数 (默认 >= 5)
   └─ 检查无效行比例 (<= 10%)
   ↓
3. 财务指标验证
   ├─ 使用 BatchDataValidator.validate_financial_metrics()
   └─ 检查关键指标有效性
   ↓
4. 数据质量报告生成
   ├─ 缺失值统计
   ├─ 重复行检查
   ├─ 数据类型报告
   └─ 数值列统计
   ↓
5. 返回结果 (含验证摘要)
```

### 验证流程图

```
开始
  │
  ▼
┌───────────────────────┐
│  1. 获取原始数据      │
│  (fetch_all_data)    │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  2. OHLCV 验证        │
│  - 空数据检查         │
│  - 最小行数检查       │
│  - 无效行比例检查     │
└───────────┬───────────┘
            │ 结果
            ▼
     ┌──────┴──────┐
     │ 验证通过?   │
     └──┬──────────┘
        │
   Yes  │  No
        ▼          ▼
   ┌─────────┐ ┌─────────────────┐
   │继续下一步│ │ 严格模式?       │
   └────┬────┘ └─┬─────────────┬─┘
        │        │ Yes         │ No
        │        ▼             ▼
        │  ┌──────────────┐ ┌─────────────┐
        │  │抛出异常      │ │记录警告继续 │
        │  └──────┬───────┘ └──────┬──────┘
        │         │                │
        │         └────────┬───────┘
        │                  │
        ▼                  ▼
┌───────────────────────┐  继续执行
│  3. 财务指标验证      │
│  - 指标完整性检查     │
│  - 指标有效性检查     │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  4. 数据质量报告生成  │
│  - 缺失值统计         │
│  - 重复行检查         │
│  - 数值列分析         │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  5. 返回验证结果      │
└───────────────────────┘
```

---

## 验证规则详解

### OHLCV 数据验证规则

| 检查项 | 验证规则 | 严格模式阈值 |
|--------|----------|-------------|
| **数据存在性** | 数据框不能为 None 或空 | 必须满足 |
| **最小行数** | 必须至少有 N 行有效数据 | 默认 5 行 |
| **无效行比例** | 无效行数 / 总行数 必须 < 10% | 必须满足 |
| **OHLC 逻辑** | High ≥ Open, High ≥ Close, High ≥ Low | 逐行检查 |
| **必填列** | 必须包含 date, open, high, low, close, volume | 必须满足 |

### 财务指标验证规则

- 必须包含基本指标 (PE, PB, Market Cap 等)
- 数值型指标必须在合理范围内
- 不能有明显的异常值

### 数据质量报告指标

```python
{
    "row_count": 总数据行数,
    "column_count": 列数,
    "duplicate_rows": 重复行数,
    "missing_values": {
        "列名": {
            "count": 缺失值数量,
            "percentage": 缺失值百分比
        }
    },
    "numeric_stats": {
        "列名": {
            "mean": 均值,
            "min": 最小值,
            "max": 最大值,
            "median": 中位数
        }
    }
}
```

---

## 严格模式 vs 宽松模式

### 模式对比

| 特性 | 严格模式 (Strict Mode) | 宽松模式 (Non-Strict Mode) |
|------|----------------------|--------------------------|
| **验证失败处理** | 抛出 `DataPipelineValidationError` | 记录警告，继续执行 |
| **适用场景** | 生产环境、关键任务 | 开发、调试、探索性分析 |
| **数据要求** | 只接受高质量数据 | 接受有警告的数据 |
| **异常抛出** | 是 | 否 |

### 代码示例 - 模式对比

```python
from backend.data_layer import (
    DataPipeline,
    DataPipelineValidationError
)

# ========== 严格模式 ==========
pipeline_strict = DataPipeline(strict_validation=True)
try:
    result = pipeline_strict.fetch_validated_data(
        "600519", "2026-05-25", "cn"
    )
    # 只有完全通过才会到这里
    print("✅ 完美数据")
except DataPipelineValidationError as e:
    # 任何验证失败都会在这里
    print(f"❌ 验证失败: {e}")
    print(f"详细报告: {e.validation_report}")


# ========== 宽松模式 ==========
pipeline_lax = DataPipeline(strict_validation=False)
result = pipeline_lax.fetch_validated_data(
    "600519", "2026-05-25", "cn"
)
# 即使有问题也会返回数据
if not result["validation_summary"]["overall_valid"]:
    print("⚠️ 数据有警告，但仍然可用")
    # 可以查看具体问题
    ohlcv_report = result["validation_summary"]["ohlcv"]
    if not ohlcv_report["valid"]:
        print(f"OHLCV 问题: {ohlcv_report['summary']}")
```

### 推荐使用场景

- **生产环境/正式交易**: 严格模式 (`strict=True`)
- **回测系统**: 严格模式，确保数据质量
- **快速原型开发**: 宽松模式，灵活迭代
- **数据调试**: 宽松模式，查看所有问题

---

## 错误类型与处理

### 主要错误类型

#### 1. DataPipelineValidationError

**说明**: 严格模式下验证失败时抛出的主异常

**结构**:
```python
class DataPipelineValidationError(Exception):
    def __init__(self, message: str, validation_report: Dict[str, Any]):
        self.message = message
        self.validation_report = validation_report
        # validation_report 包含详细的验证失败信息
```

**使用示例**:
```python
try:
    result = validated_data_fetch("600519", "2026-05-25", "cn", strict=True)
except DataPipelineValidationError as e:
    print(f"错误消息: {e.message}")
    
    # 检查哪里出了问题
    report = e.validation_report
    
    if "ohlcv" in report and not report["ohlcv"]["valid"]:
        print(f"OHLCV 验证失败: {report['ohlcv']['summary']}")
        
        if "ohlcv_details" in report["ohlcv"]:
            details = report["ohlcv"]["ohlcv_details"]
            print(f"无效行数: {len(details['invalid_rows'])}")
            for invalid_row in details["invalid_rows"]:
                print(f"  行 {invalid_row['index']}: {invalid_row['errors']}")
```

#### 2. 类型错误 (TypeError)

由 `TypeSafeDecorators` 提供，确保输入参数类型正确

```python
@TypeSafeDecorators.validate_types(symbol=str, market=str)
def fetch_data(symbol, market):
    # ...

fetch_data(600519, 123)  # 会抛出 TypeError!
```

### 常见验证失败场景与处理

| 场景 | 原因 | 解决方式 |
|------|------|---------|
| OHLCV 行数太少 | 交易日不足，或数据范围问题 | 放宽时间范围，或改用宽松模式 |
| 无效行比例过高 | 数据源有问题 | 检查数据源，清洗数据 |
| OHLC 逻辑错误 | High < Low, etc. | 检查数据质量，使用数据清洗步骤 |
| 财务指标缺失 | 数据源没有该股票的财务数据 | 可以忽略财务验证，只做 OHLCV 验证 |

### 恢复策略

```python
from backend.data_layer import DataPipeline

def robust_fetch_strategy(symbol, date, market):
    """健壮的数据获取策略"""
    
    # 策略 1: 先尝试严格模式
    try:
        pipeline = DataPipeline(strict_validation=True)
        return pipeline.fetch_validated_data(symbol, date, market)
    except Exception as e:
        print(f"严格模式失败: {e}")
    
    # 策略 2: 尝试宽松模式
    try:
        pipeline = DataPipeline(strict_validation=False)
        result = pipeline.fetch_validated_data(symbol, date, market)
        
        # 可以检查问题的严重程度
        summary = result["validation_summary"]
        if summary.get("ohlcv", {}).get("valid", False):
            # OHLCV 是好的，可能只是财务有问题
            # 可以选择性地使用数据
            return result
    except Exception as e:
        print(f"宽松模式也失败: {e}")
    
    # 策略 3: 只取 OHLCV，不做完整验证
    return pipeline.fetch_only_ohlcv(...)
```

---

## 实际使用示例

### 示例 1: 生产环境 - 严格模式

```python
"""生产环境示例 - 只接受高质量数据"""

from backend.data_layer import (
    validated_data_fetch,
    DataPipelineValidationError
)

def production_strategy_analysis(symbol, date):
    """用于交易策略的分析 - 必须保证数据质量"""
    
    try:
        result = validated_data_fetch(
            symbol=symbol,
            trade_date=date,
            market="cn",
            lookback_days=60,
            strict=True
        )
        
        # 只有完美数据才会执行到这里
        df = result["data"]["ohlcv_df"]
        indicators = result["data"]["indicators"]
        
        # 执行策略分析...
        return {
            "success": True,
            "data": result["data"],
            "analysis": run_strategy(df, indicators)
        }
        
    except DataPipelineValidationError as e:
        # 数据质量不满足要求，记录日志，发出警告
        print(f"[警告] 数据验证失败: {symbol}")
        return {
            "success": False,
            "error": str(e),
            "validation_report": e.validation_report
        }
```

### 示例 2: 开发环境 - 宽松模式 + 调试

```python
"""开发环境示例 - 调试数据问题"""

from backend.data_layer import get_pipeline

def debug_data_quality(symbol, date):
    """调试函数 - 详细查看数据质量"""
    
    pipeline = get_pipeline(strict=False)
    
    result = pipeline.fetch_validated_data(symbol, date, "cn")
    summary = result["validation_summary"]
    
    print(f"=== {symbol} 数据质量分析 ===")
    print(f"整体状态: {'✅ 正常' if summary['overall_valid'] else '⚠️ 有问题'}")
    
    # 检查 OHLCV
    if "ohlcv" in summary:
        ohlcv = summary["ohlcv"]
        print(f"\nOHLCV: {'✅' if ohlcv['valid'] else '❌'} {ohlcv['summary']}")
        
        if "ohlcv_details" in ohlcv:
            details = ohlcv["ohlcv_details"]
            print(f"  有效行数: {details.get('valid_rows')}")
            print(f"  无效行数: {len(details.get('invalid_rows', []))}")
            
            if details.get("invalid_rows"):
                print("\n  问题行:")
                for row in details["invalid_rows"][:5]:  # 只看前5个
                    print(f"    行 {row['index']} (日期 {row.get('date')}): {row['errors']}")
    
    # 检查质量报告
    if "data_quality" in summary:
        quality = summary["data_quality"]
        print(f"\n数据质量:")
        print(f"  总行数: {quality['row_count']}")
        print(f"  重复行: {quality['duplicate_rows']}")
        
        print(f"\n  缺失值:")
        for col, info in quality["missing_values"].items():
            status = "✅" if info["percentage"] == 0 else "⚠️"
            print(f"    {status} {col}: {info['count']} ({info['percentage']:.1f}%)")
    
    # 查看验证日志
    print(f"\n验证日志:")
    for log in pipeline.get_validation_logs():
        status = "✅" if log["success"] else "❌"
        print(f"  {status} {log['step']} - {log['timestamp']}")
    
    return result
```

### 示例 3: 批量处理多股票

```python
"""批量处理 - 带质量筛选"""

from backend.data_layer import get_pipeline

def process_portfolio(symbols, date):
    """处理一篮子股票，只保留高质量数据"""
    
    pipeline = get_pipeline(strict=False)
    results = []
    quality_stats = {
        "total": len(symbols),
        "success": 0,
        "failed": 0,
        "warnings": 0
    }
    
    for symbol in symbols:
        try:
            result = pipeline.fetch_validated_data(symbol, date, "cn")
            summary = result["validation_summary"]
            
            if summary["overall_valid"]:
                quality_stats["success"] += 1
                results.append({
                    "symbol": symbol,
                    "status": "success",
                    "data": result["data"]
                })
            else:
                quality_stats["warnings"] += 1
                results.append({
                    "symbol": symbol,
                    "status": "warning",
                    "issues": summary,
                    "data": result["data"]
                })
                
        except Exception as e:
            quality_stats["failed"] += 1
            results.append({
                "symbol": symbol,
                "status": "failed",
                "error": str(e)
            })
    
    # 统计总结
    print(f"批量处理完成:")
    print(f"  总计: {quality_stats['total']}")
    print(f"  成功: {quality_stats['success']}")
    print(f"  警告: {quality_stats['warnings']}")
    print(f"  失败: {quality_stats['failed']}")
    
    return results
```

---

## 调试技巧

### 1. 使用验证日志

```python
pipeline = DataPipeline(strict_validation=False)
# ... 执行一些操作 ...

# 获取所有日志
logs = pipeline.get_validation_logs()
for log in logs:
    print(f"{log['step']} - {log['symbol']}")
    print(f"  Success: {log['success']}")
    print(f"  Details: {log['details']}")

# 获取失败的日志
failed_logs = [log for log in logs if not log["success"]]
```

### 2. 直接使用 BatchDataValidator

```python
from backend.utils.data_converters import BatchDataValidator

# 已有数据框
df = get_some_ohlcv_data()

# 验证
report = BatchDataValidator.validate_ohlcv_data(df, strict=False)
print(f"有效行数: {report['valid_rows']}")
print(f"无效行数: {len(report['invalid_rows'])}")
```

### 3. 分步验证调试

```python
pipeline = DataPipeline(strict_validation=False)

# 只验证 OHLCV 部分
ohlcv_result = pipeline.fetch_only_ohlcv("600519", "2026-01-01", "2026-05-25", "cn")

# 查看 OHLCV 验证结果
if not ohlcv_result["validation_summary"]["valid"]:
    print("OHLCV 验证详情:")
    print(ohlcv_result["validation_summary"])

# 查看质量报告 (在完整数据获取中)
full_result = pipeline.fetch_validated_data("600519", "2026-05-25", "cn")
quality = full_result["validation_summary"]["data_quality"]
```

---

## 最佳实践

### 1. 生产环境检查清单

- [ ] 使用严格模式 (`strict_validation=True`)
- [ ] 捕获 `DataPipelineValidationError`
- [ ] 记录验证失败的详细日志
- [ ] 设置数据质量告警阈值
- [ ] 定期审查验证日志

### 2. 配置推荐

| 环境 | 严格模式 | 最小行数 | 最大无效比例 |
|------|---------|---------|------------|
| 生产 | True | 20 | 5% |
| 回测 | True | 60 | 2% |
| 开发 | False | 5 | 20% |

### 3. 常见问题排查

| 问题 | 可能原因 | 排查步骤 |
|------|---------|---------|
| 验证总是失败 | 数据获取有问题 | 检查数据源连接、日期格式 |
| 警告太多 | 数据质量差 | 查看数据质量报告，清洗数据 |
| 类型错误 | 参数类型不对 | 检查 TypeSafeDecorators 验证 |
| 验证速度慢 | 数据量大 | 考虑减少时间范围，或预缓存 |

---

## 相关文件

- [`data_pipeline.py`](../backend/data_layer/data_pipeline.py): 核心流水线实现
- [`data_converters.py`](../backend/utils/data_converters.py): 验证器与转换器
- [`PIPELINE_USAGE.md`](./PIPELINE_USAGE.md): 使用指南
- [`OPTIMIZATION_RECORDS.md`](./OPTIMIZATION_RECORDS.md): 优化历史

---

## 更新日志

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-05-25 | 1.0 | 初始版本，完整的验证逻辑与错误处理文档 |
