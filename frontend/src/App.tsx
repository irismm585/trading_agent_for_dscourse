import { useState, useMemo, useCallback, useEffect } from 'react'
import type { AnalysisRequest } from './types'
import { useWebSocket } from './hooks/useWebSocket'
import StockInput from './components/StockInput'
import RatingBadge from './components/RatingBadge'
import ChartView from './components/ChartView'
import StockProfileBar from './components/StockProfileBar'
import { SECTION_KEY_MAP } from './constants/tabs'
import { simpleMarkdown } from './utils/markdown'
import './App.css'

const API_BASE = '/api'

type SectionType = 'technical' | 'fundamental' | 'sentiment' | null

const SECTION_META: Record<string, { label: string; icon: string; rawKeys: string[] }> = {
  technical:   { label: '技术面分析', icon: '📈', rawKeys: ['raw_ohlcv_text', 'raw_indicators_text'] },
  fundamental: { label: '基本面分析', icon: '📊', rawKeys: ['raw_financial_text'] },
  sentiment:   { label: '情绪分析',   icon: '🔥', rawKeys: ['raw_news_text', 'raw_sentiment_text'] },
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [market, setMarket] = useState<'cn' | 'us'>('cn')
  const [appMarket, setAppMarket] = useState<'cn' | 'us'>('cn')
  const [symbol, setSymbol] = useState('')
  const [activeSection, setActiveSection] = useState<SectionType>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [generatedSections, setGeneratedSections] = useState<Set<string>>(new Set())

  const {
    messages,
    currentNode,
    isConnected,
    isComplete,
    error,
    generatingSections,
    chartData,
    stockProfile,
    indexData,
    connect,
    disconnect,
    sendCommand,
  } = useWebSocket()

  // Build content map from WS messages
  const sectionContent = useMemo(() => {
    const map: Record<string, string> = {}
    const debateMsgs: { role: string; round: number; content: string }[] = []

    for (const msg of messages) {
      if (msg.type === 'node_update' && msg.section && msg.content) {
        if (msg.section === 'debate') {
          debateMsgs.push({ role: msg.role || '?', round: msg.round || 1, content: msg.content })
        } else if (msg.section === 'decision') {
          map[msg.section] = msg.content
        } else {
          map[msg.section] = (map[msg.section] || '') + msg.content
        }
      }
      // Also listen for section_complete to track generated sections
      if (msg.type === 'section_complete' && msg.section) {
        setGeneratedSections(prev => new Set(prev).add(msg.section!))
      }
    }

    if (debateMsgs.length > 0) {
      map['debate'] = debateMsgs.map(m => {
        const label = m.role === 'bull' ? '🟢 多头分析师' : '🔴 空头分析师'
        return `### ${label}（第${m.round}轮）\n\n${m.content}`
      }).join('\n\n---\n\n')
    }

    return map
  }, [messages])

  const hasContent = useCallback((id: string) => !!(sectionContent[id]), [sectionContent])

  const allDataReady = useMemo(() => {
    return ['technical_report','fundamental_report','sentiment_report']
      .every(k => hasContent(k))
  }, [hasContent])

  const debateStarted = hasContent('debate')
  const decisionReady = hasContent('decision')

  // ── Combined debate+judge phase tracking ──
  const [debatePhase, setDebatePhase] = useState<'idle' | 'debate' | 'judge' | 'done'>('idle')

  // Auto-trigger judge after debate completes
  useEffect(() => {
    if (debatePhase === 'debate' && debateStarted && !decisionReady) {
      setDebatePhase('judge')
      sendCommand({ action: 'run_judge' })
    }
    if (debatePhase === 'judge' && decisionReady) {
      setDebatePhase('done')
    }
  }, [debateStarted, decisionReady, debatePhase, sendCommand])

  // ── Handlers ──
  const handleCreateSession = async (request: AnalysisRequest) => {
    setIsCreating(true)
    setCreateError(null)

    // Quick health check to verify backend is reachable
    try {
      const hc = new AbortController()
      const ht = setTimeout(() => hc.abort(), 5000)
      const healthRes = await fetch(`${API_BASE}/health`, { signal: hc.signal })
      clearTimeout(ht)
      if (!healthRes.ok) throw new Error('Backend unhealthy')
    } catch (healthErr) {
      const aborted = (healthErr instanceof DOMException && healthErr.name === 'AbortError') ||
                      (healthErr instanceof Error && healthErr.name === 'AbortError')
      setCreateError(aborted
        ? '无法连接后端服务，请确认后端已启动 (http://localhost:8000)'
        : `后端检测失败: ${healthErr instanceof Error ? healthErr.message : '未知错误'}`)
      setIsCreating(false)
      return
    }

    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 120000)
      const res = await fetch(`${API_BASE}/session`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request), signal: controller.signal,
      })
      clearTimeout(timeoutId)
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed')
      const data = await res.json()
      setSessionId(data.session_id)
      setMarket(data.market as 'cn' | 'us')
      setAppMarket(data.market as 'cn' | 'us')
      setSymbol(data.symbol)
      connect(data.session_id)
      setIsCreating(false)
    } catch (e) {
      const isAbort = (e instanceof DOMException && e.name === 'AbortError') ||
                       (e instanceof Error && e.name === 'AbortError')
      if (isAbort) {
        setCreateError('创建会话失败: 请求超时，请检查后端服务是否已启动 (http://localhost:8000)')
      } else {
        setCreateError(`创建会话失败: ${e instanceof Error ? e.message : '未知错误'}`)
      }
      setIsCreating(false)
    }
  }

  const handleSectionClick = (section: SectionType) => {
    if (!section) return
    setActiveSection(section)
    const sectionKey = SECTION_KEY_MAP[`${section}_report`]
    if (sectionKey && !hasContent(`${section}_report`)) {
      sendCommand({ action: 'generate_section', section: sectionKey })
    }
  }

  const handleReset = () => {
    disconnect()
    setSessionId(null)
    setIsCreating(false)
    setCreateError(null)
    setActiveSection(null)
    setGeneratedSections(new Set())
    setDebatePhase('idle')
    setAppMarket(market)
  }

  // ── Render helpers ──
  const renderSectionContent = () => {
    if (!sessionId || !activeSection) return null
    const meta = SECTION_META[activeSection]
    const reportKey = `${activeSection}_report`
    const reportContent = sectionContent[reportKey]
    const isGen = generatingSections.has(SECTION_KEY_MAP[reportKey] || reportKey)

    return (
      <div className="section-content">
        <h2 className="section-title">{meta.icon} {meta.label}</h2>

        {/* Raw data section */}
        {meta.rawKeys.map(key => {
          const text = sectionContent[key]
          if (!text) return null
          if (key === 'raw_ohlcv_text' && chartData.length > 0) {
            return (
              <div key={key} className="raw-block">
                <ChartView data={chartData} />
              </div>
            )
          }
          return (
            <div key={key} className="raw-block">
              <div className="markdown-content" dangerouslySetInnerHTML={{ __html: simpleMarkdown(text) }} />
            </div>
          )
        })}

        {/* LLM analysis */}
        {reportContent && (
          <div className="analysis-block">
            <div className="markdown-content" dangerouslySetInnerHTML={{ __html: simpleMarkdown(reportContent) }} />
          </div>
        )}
        {isGen && (
          <div className="loading-card small">
            <div className="spinner" />
            <p>AI 分析生成中…</p>
            <span className="muted">{currentNode || ''}</span>
          </div>
        )}
      </div>
    )
  }

  // ── Render ──
  return (
    <div className="app">
      <header className="app-header">
        <h1>📊 A-Share Trading Agents</h1>
        <p className="subtitle">A 股智能分析 · {appMarket === 'cn' ? 'A股' : '美股'}</p>
      </header>

      <main className="app-main">
        {/* Input */}
        <StockInput
          onStart={handleCreateSession}
          onMarketChange={setAppMarket}
          disabled={isCreating}
          hasSession={!!sessionId}
        />

        {/* Errors */}
        {createError && <div className="error-banner">⚠️ {createError}<button onClick={() => setCreateError(null)} className="btn-reset">关闭</button></div>}
        {error && <div className="error-banner">⚠️ {error}<button onClick={handleReset} className="btn-reset">重新开始</button></div>}

        {/* Loading */}
        {!sessionId && isCreating && <div className="loading-card"><div className="spinner-lg" /><p>正在创建分析会话…</p></div>}
        {!sessionId && !isCreating && <div className="empty-card"><p>👆 输入股票代码并点击「创建会话」</p></div>}

        {/* Status bar */}
        {sessionId && (
          <div className="status-bar">
            <span className="market-badge">{market === 'cn' ? '🇨🇳 A股' : '🇺🇸 美股'}</span>
            <span>{symbol}</span>
            {!isConnected && !isComplete && <><span className="dot yellow" />连接中…</>}
            {isConnected && !isComplete && <><span className="dot green" />分析中</>}
            {isComplete && <><span className="dot green" />完成</>}
            <RatingBadge decisionText={sectionContent['decision'] || ''} />
            <button onClick={handleReset} className="btn-reset">重新开始</button>
          </div>
        )}

        {/* Stock Profile */}
        {sessionId && stockProfile && (
          <StockProfileBar profile={stockProfile} indexData={indexData} symbol={symbol} />
        )}

        {/* Three Section Cards */}
        {sessionId && (
          <div className="section-cards">
            {(['technical', 'fundamental', 'sentiment'] as SectionType[]).map(s => {
              if (!s) return null
              const meta = SECTION_META[s]
              const isActive = activeSection === s
              const isGen = generatingSections.has(SECTION_KEY_MAP[`${s}_report`] || `${s}_report`)
              const hasContentFlag = hasContent(`${s}_report`)
              return (
                <button
                  key={s}
                  className={`section-card ${isActive ? 'active' : ''}`}
                  onClick={() => handleSectionClick(s)}
                >
                  <span className="card-icon">{meta.icon}</span>
                  <span className="card-label">{meta.label}</span>
                  {isGen && <span className="card-spinner" />}
                  {hasContentFlag && !isGen && <span className="card-check">✓</span>}
                </button>
              )
            })}
          </div>
        )}

        {/* Single Debate + Judge button */}
        {sessionId && (
          <div className="action-bar">
            <button
              className="btn-action"
              onClick={() => {
                setDebatePhase('debate')
                sendCommand({ action: 'run_debate' })
              }}
              disabled={!allDataReady || !isConnected || debatePhase !== 'idle'}
            >
              {debatePhase === 'idle' && '⚔️ 多空辩论 & 评委决策'}
              {debatePhase === 'debate' && '⏳ 辩论进行中…'}
              {debatePhase === 'judge' && '⏳ 评委评判中…'}
              {debatePhase === 'done' && '✅ 分析完成'}
            </button>
          </div>
        )}

        {/* Combined Debate + Judge section */}
        {sessionId && (debateStarted || decisionReady || generatingSections.has('debate') || generatingSections.has('decision')) && (
          <div className="section-content">
            <h2 className="section-title">⚔️ 多空辩论 &amp; 评委决策</h2>

            {/* Debate loading (no content yet) */}
            {generatingSections.has('debate') && !debateStarted && (
              <div className="loading-card small">
                <div className="spinner" />
                <p>多空辩论进行中…</p>
                <span className="muted">{currentNode || ''}</span>
              </div>
            )}

            {/* Debate content */}
            {debateStarted && (
              <div className="analysis-block">
                <div className="markdown-content" dangerouslySetInnerHTML={{ __html: simpleMarkdown(sectionContent['debate']) }} />
              </div>
            )}

            {/* Divider between debate and judge */}
            {debateStarted && decisionReady && <hr className="section-divider" />}

            {/* Judge loading (no content yet) */}
            {generatingSections.has('decision') && !decisionReady && (
              <div className="loading-card small">
                <div className="spinner" />
                <p>评委决策进行中…</p>
              </div>
            )}

            {/* Judge decision content */}
            {decisionReady && (
              <div className="analysis-block">
                <div className="markdown-content" dangerouslySetInnerHTML={{ __html: simpleMarkdown(sectionContent['decision']) }} />
              </div>
            )}
          </div>
        )}

        {/* Active section content — hidden when debate/judge is active */}
        {!debateStarted && !generatingSections.has('debate') && renderSectionContent()}
      </main>

      <footer className="app-footer">
        <p>免责声明：本系统仅供研究学习使用，不构成任何投资建议。</p>
      </footer>
    </div>
  )
}
