import React, { useState, useRef, useEffect } from 'react'
import type { AnalysisRequest } from '../types'

const API_BASE = '/api'

interface SearchResult {
  symbol: string
  name: string
  market: string
  exchange: string
}

interface Props {
  onStart: (request: AnalysisRequest) => void
  onMarketChange?: (market: 'cn' | 'us') => void
  disabled: boolean
  hasSession: boolean
}

const PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'xai', label: 'xAI (Grok)' },
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'google', label: 'Google (Gemini)' },
  { value: 'ollama', label: 'Ollama (本地)' },
]

export default function StockInput({ onStart, onMarketChange, disabled, hasSession }: Props) {
  const [market, setMarket] = useState<'cn' | 'us'>('cn')
  const [symbol, setSymbol] = useState('600519')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [searching, setSearching] = useState(false)
  const [selectedLabel, setSelectedLabel] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const [tradeDate, setTradeDate] = useState(
    new Date().toISOString().split('T')[0]
  )
  const [llmProvider, setLlmProvider] = useState('deepseek')
  const [deepThinkLlm, setDeepThinkLlm] = useState('deepseek-v4-pro')
  const [quickThinkLlm, setQuickThinkLlm] = useState('deepseek-v4-flash')
  const [maxRounds, setMaxRounds] = useState(1)
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
          inputRef.current && !inputRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const doSearch = async (query: string) => {
    if (!query || query.length < 1) {
      setSearchResults([])
      setShowDropdown(false)
      return
    }
    setSearching(true)
    try {
      const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&market=${market}&limit=8`)
      if (!res.ok) return
      const data = await res.json()
      const results = data.results || []
      setSearchResults(results)
      setShowDropdown(results.length > 0)
    } catch {
      // Ignore search errors
    } finally {
      setSearching(false)
    }
  }

  const handleInputChange = (value: string) => {
    const upper = value.toUpperCase()
    setSymbol(upper)
    setSelectedLabel('')

    // Debounce search
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(upper), 250)
  }

  const handleSelectResult = (result: SearchResult) => {
    setSymbol(result.symbol)
    setSelectedLabel(`${result.name} (${result.symbol})`)
    setShowDropdown(false)
    setSearchResults([])
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const trimmedSymbol = symbol.trim()
    if (!trimmedSymbol) {
      alert('请输入股票代码或名称')
      return
    }

    onStart({
      symbol: trimmedSymbol,
      trade_date: tradeDate,
      market: market,
      max_debate_rounds: maxRounds,
      llm_provider: llmProvider,
      deep_think_llm: deepThinkLlm,
      quick_think_llm: quickThinkLlm,
    })
  }

  const handleMarketChange = (newMarket: 'cn' | 'us') => {
    setMarket(newMarket)
    onMarketChange?.(newMarket)
    setSymbol(newMarket === 'cn' ? '600519' : 'AAPL')
    setSelectedLabel('')
    setSearchResults([])
    setShowDropdown(false)
  }

  const displayValue = selectedLabel || symbol

  return (
    <form className="stock-input" onSubmit={handleSubmit}>
      <div className="input-row">
        {/* Market selector */}
        <div className="field">
          <label>市场</label>
          <div className="market-toggle">
            <button
              type="button"
              className={`market-btn ${market === 'cn' ? 'active' : ''}`}
              onClick={() => handleMarketChange('cn')}
              disabled={disabled || hasSession}
            >
              🇨🇳 A股
            </button>
            <button
              type="button"
              className={`market-btn ${market === 'us' ? 'active' : ''}`}
              onClick={() => handleMarketChange('us')}
              disabled={disabled || hasSession}
            >
              🇺🇸 美股
            </button>
          </div>
        </div>

        <div className="field search-field">
          <label>股票代码/名称</label>
          <div className="search-input-wrap">
            <input
              ref={inputRef}
              type="text"
              value={displayValue}
              onChange={(e) => handleInputChange(e.target.value)}
              onFocus={() => { if (searchResults.length > 0) setShowDropdown(true) }}
              placeholder={market === 'cn' ? '输入代码或名称 (如 600519, 贵州茅台)' : '输入代码或名称 (如 AAPL, Apple)'}
              disabled={disabled || hasSession}
              autoComplete="off"
            />
            {searching && <span className="search-spinner" />}
          </div>
          {showDropdown && searchResults.length > 0 && (
            <div className="search-dropdown" ref={dropdownRef}>
              {searchResults.map((r) => (
                <button
                  key={`${r.exchange}:${r.symbol}`}
                  type="button"
                  className="search-item"
                  onClick={() => handleSelectResult(r)}
                >
                  <span className="search-item-symbol">{r.symbol}</span>
                  <span className="search-item-name">{r.name}</span>
                  <span className="search-item-exchange">{r.exchange}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="field">
          <label>分析日期</label>
          <input
            type="date"
            value={tradeDate}
            onChange={(e) => setTradeDate(e.target.value)}
            disabled={disabled || hasSession}
          />
        </div>

        <button
          type="submit"
          className="btn-primary"
          disabled={disabled || hasSession}
        >
          {hasSession ? '会话已创建' : '创建会话'}
        </button>
      </div>

      <button
        type="button"
        className="btn-link"
        onClick={() => setShowAdvanced(!showAdvanced)}
      >
        {showAdvanced ? '收起高级设置 ▲' : '展开高级设置 ▼'}
      </button>

      {showAdvanced && (
        <div className="advanced-settings">
          <div className="input-row">
            <div className="field">
              <label>LLM 提供商</label>
              <select
                value={llmProvider}
                onChange={(e) => setLlmProvider(e.target.value)}
                disabled={disabled || hasSession}
              >
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label>深思模型 (评委用)</label>
              <input
                type="text"
                value={deepThinkLlm}
                onChange={(e) => setDeepThinkLlm(e.target.value)}
                disabled={disabled || hasSession}
              />
            </div>

            <div className="field">
              <label>快速模型 (分析/辩论用)</label>
              <input
                type="text"
                value={quickThinkLlm}
                onChange={(e) => setQuickThinkLlm(e.target.value)}
                disabled={disabled || hasSession}
              />
            </div>

            <div className="field">
              <label>辩论轮数</label>
              <select
                value={maxRounds}
                onChange={(e) => setMaxRounds(Number(e.target.value))}
                disabled={disabled || hasSession}
              >
                {[1, 2, 3].map((n) => (
                  <option key={n} value={n}>
                    {n} 轮
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}
    </form>
  )
}
