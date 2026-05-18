export interface AnalysisRequest {
  symbol: string
  trade_date: string
  market: 'cn' | 'us'
  max_debate_rounds: number
  llm_provider: string
  deep_think_llm: string
  quick_think_llm: string
  backend_url?: string
}

export interface CreateSessionResponse {
  session_id: string
  status: string
  market: string
  symbol: string
  trade_date: string
  ws_url: string
}

export type ReportSection =
  | 'valuation_report'
  | 'technical_report'
  | 'fundamental_report'
  | 'sentiment_report'
  | 'news_report'
  | 'research_summary'
  | 'raw_ohlcv_text'
  | 'raw_indicators_text'
  | 'raw_financial_text'
  | 'raw_news_text'
  | 'raw_sentiment_text'
  | 'debate'
  | 'decision'

export interface OhlcvPoint {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface StockProfile {
  symbol: string
  name: string
  industry?: string
  price?: number
  change_pct?: number
  open?: number
  high?: number
  low?: number
  last_close?: number
  volume?: number
  amount?: number
}

export interface IndexData {
  [name: string]: { price: number; change_pct: number }
}

// WebSocket messages FROM server
export interface WebSocketMessage {
  type: 'connected' | 'node_update' | 'status' | 'section_complete' | 'complete' | 'error' | 'chart_data' | 'stock_profile'
  node?: 'DataCollector' | 'BullAgent' | 'BearAgent' | 'JudgeAgent'
  section?: ReportSection | string
  content?: string
  role?: 'bull' | 'bear'
  round?: number
  timestamp: string
  message?: string
  session_id?: string
  symbol?: string
  market?: string
  data?: OhlcvPoint[]
  profile?: StockProfile
  index_data?: IndexData
}

// WebSocket commands TO server
export interface WsCommand {
  action: 'generate_section' | 'generate_raw_data' | 'run_debate' | 'run_judge'
  section?: string
}

export interface TabConfig {
  id: ReportSection
  label: string
  icon: string
  group: 'data' | 'raw' | 'debate' | 'decision'
  comingSoon?: boolean
}
