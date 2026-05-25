/**
 * 数据类型转换工具库
 *
 * 包含：
 * 1. MarketDataNormalizer - 金融数据标准化转换器
 * 2. WsMessageConverter - WebSocket 消息类型转换器
 * 3. ChartDataConverter - 图表数据快速转换器
 */

// =============================================================================
// 1. 金融数据标准化转换器
// =============================================================================
interface MarketData {
  symbol: string;
  market: string;
  ohlcv: Array<Record<string, any>>;
  financial?: Record<string, any>;
  updated_at?: string;
}

interface NormalizedOHLCV {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  [key: string]: any;
}

export class MarketDataNormalizer {
  /**
   * 统一 A 股和美股数据格式的标准化转换器
   */

  private static fieldMapping: Record<string, Record<string, string>> = {
    cn: {
      date: 'date',
      open: 'open',
      high: 'high',
      low: 'low',
      close: 'close',
      volume: 'volume',
      amount: 'amount',
      市值: 'market_cap',
      市盈率: 'pe_ratio',
      市净率: 'pb_ratio',
      净利润: 'net_profit',
      营业收入: 'revenue',
    },
    us: {
      Date: 'date',
      Open: 'open',
      High: 'high',
      Low: 'low',
      Close: 'close',
      Volume: 'volume',
      marketCap: 'market_cap',
      trailingPE: 'pe_ratio',
      priceToBook: 'pb_ratio',
      netIncome: 'net_profit',
      totalRevenue: 'revenue',
    },
  };

  /**
   * 标准化 OHLCV 数据
   * @param data 原始数据（数组或单个对象）
   * @param market 市场类型 'cn' 或 'us'
   */
  static normalizeOHLCV(
    data: Array<Record<string, any>> | Record<string, any>,
    market: string
  ): Array<NormalizedOHLCV> {
    const dataArray = Array.isArray(data) ? data : [data];

    const mapping = this.fieldMapping[market] || this.fieldMapping.cn;

    return dataArray.map((row) => {
      const result: Record<string, any> = {};

      // 字段映射
      for (const [srcKey, destKey] of Object.entries(mapping)) {
        if (row[srcKey] !== undefined) {
          result[destKey] = row[srcKey];
        }
      }

      // 日期标准化
      if (result.date) {
        result.date = this.normalizeDate(result.date);
      }

      // 数值类型标准化
      const numericFields = ['open', 'high', 'low', 'close', 'volume', 'amount'];
      numericFields.forEach((field) => {
        if (result[field] !== undefined) {
          result[field] = this.safeParseFloat(result[field]);
        }
      });

      return result as NormalizedOHLCV;
    });
  }

  /**
   * 标准化财务数据
   */
  static normalizeFinancial(data: Record<string, any>, market: string): Record<string, any> {
    const mapping = this.fieldMapping[market] || this.fieldMapping.cn;
    const result: Record<string, any> = {};

    for (const [srcKey, destKey] of Object.entries(mapping)) {
      if (data[srcKey] !== undefined) {
        result[destKey] = data[srcKey];
      }
    }

    // 货币单位标准化
    if (result.market_cap) {
      result.market_cap = this.normalizeCurrency(result.market_cap, '亿');
    }

    return result;
  }

  /**
   * 转换为统一格式
   */
  static toUnifiedFormat(
    symbol: string,
    ohlcv: Array<any>,
    financial?: Record<string, any>,
    market: string = 'cn'
  ): MarketData {
    return {
      symbol,
      market,
      ohlcv: this.normalizeOHLCV(ohlcv, market),
      financial: financial ? this.normalizeFinancial(financial, market) : undefined,
      updated_at: new Date().toISOString(),
    };
  }

  private static normalizeDate(date: any): string {
    try {
      if (typeof date === 'string') {
        const d = new Date(date);
        return d.toISOString().split('T')[0];
      }
      if (date instanceof Date) {
        return date.toISOString().split('T')[0];
      }
      return String(date);
    } catch {
      return String(date);
    }
  }

  private static safeParseFloat(value: any): number {
    const parsed = parseFloat(value);
    return isNaN(parsed) ? 0 : parsed;
  }

  private static normalizeCurrency(value: any, unit: string): number | null {
    if (value == null) return null;
    const num = this.safeParseFloat(value);
    if (unit === '亿') {
      return Math.round(num / 100000000 * 100) / 100;
    }
    return num;
  }
}

// =============================================================================
// 2. WebSocket 消息类型转换器
// =============================================================================
interface WsMessage {
  type: string;
  [key: string]: any;
}

export class WsMessageConverter {
  /**
   * WebSocket 消息序列化/反序列化转换器
   */

  static validTypes = new Set([
    'connected', 'disconnected',
    'node_update', 'status', 'section_complete',
    'complete', 'error',
    'stock_profile', 'chart_data', 'financial_data',
  ]);

  /**
   * 对象转 WebSocket JSON 字符串
   */
  static toJSON(data: WsMessage): string {
    const message = { ...data };

    // 确保有 type 字段
    if (!message.type) {
      message.type = 'status';
    }

    // 验证消息类型
    if (!this.validTypes.has(message.type)) {
      message.type = 'status';
    }

    // 添加时间戳
    if (!message.timestamp) {
      message.timestamp = new Date().toISOString();
    }

    return JSON.stringify(message);
  }

  /**
   * WebSocket JSON 字符串转对象
   */
  static fromJSON(jsonStr: string): WsMessage {
    try {
      const data = JSON.parse(jsonStr);
      return this.processAfterDeserialization(data);
    } catch {
      return {
        type: 'error',
        message: 'Invalid JSON format',
        timestamp: new Date().toISOString(),
      };
    }
  }

  private static processAfterDeserialization(data: WsMessage): WsMessage {
    const result = { ...data };

    // 解析时间戳
    if (result.timestamp && typeof result.timestamp === 'string') {
      try {
        result.timestamp = new Date(result.timestamp);
      } catch {
        // 保持原样
      }
    }

    return result;
  }

  // 便捷方法
  static createStatus(message: string, extra?: Record<string, any>): WsMessage {
    return { type: 'status', message, ...extra };
  }

  static createNodeUpdate(node: string, section: string, content: string): WsMessage {
    return { type: 'node_update', node, section, content };
  }

  static createComplete(message: string = '分析完成'): WsMessage {
    return { type: 'complete', message };
  }

  static createError(message: string): WsMessage {
    return { type: 'error', message };
  }
}

// =============================================================================
// 3. 图表数据快速转换器
// =============================================================================
interface OHLCData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export class ChartDataConverter {
  /**
   * 图表数据快速转换器
   */

  /**
   * 数据数组转 OHLC 图表格式
   */
  static toOHLC(
    data: Array<Record<string, any>>,
    chartType: 'lightweight' | 'echarts' | 'plotly' = 'lightweight'
  ): Array<any> {
    if (!data || data.length === 0) {
      return [];
    }

    switch (chartType) {
      case 'lightweight':
        return this.toLightweightCharts(data);
      case 'echarts':
        return this.toECharts(data);
      case 'plotly':
        return this.toPlotly(data);
      default:
        return this.toLightweightCharts(data);
    }
  }

  /**
   * 转换为 Lightweight Charts 格式
   */
  static toLightweightCharts(data: Array<Record<string, any>>): Array<OHLCData> {
    return data
      .map((row) => {
        const timestamp = this.parseTimestamp(row.date || row.Date);
        if (!timestamp) return null;

        return {
          time: timestamp,
          open: this.safeParseFloat(row.open || row.Open),
          high: this.safeParseFloat(row.high || row.High),
          low: this.safeParseFloat(row.low || row.Low),
          close: this.safeParseFloat(row.close || row.Close),
          volume: row.volume !== undefined ? this.safeParseFloat(row.volume) : undefined,
        };
      })
      .filter(Boolean) as Array<OHLCData>;
  }

  /**
   * 转换为 ECharts 格式
   */
  static toECharts(data: Array<Record<string, any>>): Array<Array<any>> {
    return data.map((row) => [
      String(row.date || row.Date || ''),
      this.safeParseFloat(row.open || row.Open),
      this.safeParseFloat(row.close || row.Close),
      this.safeParseFloat(row.low || row.Low),
      this.safeParseFloat(row.high || row.High),
      row.volume !== undefined ? this.safeParseFloat(row.volume) : undefined,
    ]);
  }

  /**
   * 转换为 Plotly 格式
   */
  static toPlotly(data: Array<Record<string, any>>): Record<string, Array<any>> {
    return {
      x: data.map((row) => String(row.date || row.Date || '')),
      open: data.map((row) => this.safeParseFloat(row.open || row.Open)),
      high: data.map((row) => this.safeParseFloat(row.high || row.High)),
      low: data.map((row) => this.safeParseFloat(row.low || row.Low)),
      close: data.map((row) => this.safeParseFloat(row.close || row.Close)),
      volume: data.map((row) =>
        row.volume !== undefined ? this.safeParseFloat(row.volume) : null
      ),
    };
  }

  private static parseTimestamp(date: any): number | null {
    try {
      if (!date) return null;

      let timestamp: number;
      if (typeof date === 'string') {
        timestamp = new Date(date).getTime() / 1000;
      } else if (date instanceof Date) {
        timestamp = date.getTime() / 1000;
      } else if (typeof date === 'number') {
        timestamp = date > 1e11 ? date / 1000 : date;
      } else {
        timestamp = new Date(String(date)).getTime() / 1000;
      }

      return Math.floor(timestamp);
    } catch {
      return null;
    }
  }

  private static safeParseFloat(value: any): number {
    const parsed = parseFloat(value);
    return isNaN(parsed) ? 0 : parsed;
  }
}
