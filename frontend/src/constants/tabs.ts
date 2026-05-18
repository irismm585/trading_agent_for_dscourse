import type { TabConfig, ReportSection } from '../types'

export const DATA_TABS: TabConfig[] = [
  { id: 'valuation_report',   label: '估值分析',   icon: '💰', group: 'data' },
  { id: 'technical_report',   label: '技术面',     icon: '📈', group: 'data' },
  { id: 'fundamental_report', label: '基本面',     icon: '📊', group: 'data' },
  { id: 'sentiment_report',   label: '情绪分析',   icon: '🔥', group: 'data' },
  { id: 'news_report',        label: '新闻资讯',   icon: '📰', group: 'data' },
  { id: 'research_summary',   label: '总体摘要',   icon: '📋', group: 'data' },
]

export const RAW_TABS: TabConfig[] = [
  { id: 'raw_ohlcv_text',       label: '行情数据',   icon: '📉', group: 'raw' },
  { id: 'raw_indicators_text',  label: '技术指标',   icon: '📐', group: 'raw' },
  { id: 'raw_financial_text',   label: '财务数据',   icon: '💵', group: 'raw' },
  { id: 'raw_news_text',        label: '新闻原文',   icon: '🗞️', group: 'raw' },
  { id: 'raw_sentiment_text',   label: '情绪原文',   icon: '💬', group: 'raw' },
]

export const DEBATE_TAB: TabConfig = { id: 'debate', label: '多空辩论', icon: '⚔️', group: 'debate' }
export const DECISION_TAB: TabConfig = { id: 'decision', label: '评委决策', icon: '🏛️', group: 'decision' }

export const ALL_TABS = [...DATA_TABS, ...RAW_TABS, DEBATE_TAB, DECISION_TAB]

// Section key mapping: tab id → section key for WS commands
export const SECTION_KEY_MAP: Record<string, string> = {
  'valuation_report': 'valuation',
  'technical_report': 'technical',
  'fundamental_report': 'fundamental',
  'sentiment_report': 'sentiment',
  'news_report': 'news',
  'research_summary': 'summary',
}

// Section label map: tab id → icon + label
export const SECTION_LABELS: Record<string, string> = {}
ALL_TABS.forEach(t => { SECTION_LABELS[t.id] = `${t.icon} ${t.label}` })
