import { useEffect, useRef } from 'react'
import { createChart, ColorType, HistogramSeries } from 'lightweight-charts'

interface MetricCard {
  label: string
  value: number | string
  unit: string
}

interface TrendPoint {
  period: string
  value: number
}

interface FinancialMetricsData {
  metrics: Record<string, { label: string; value: number | string; unit: string }>
  revenueTrend: TrendPoint[]
  netProfitTrend: TrendPoint[]
}

interface Props {
  data: FinancialMetricsData
}

function MetricCardView({ card }: { card: MetricCard }) {
  return (
    <div className="metric-card">
      <span className="metric-label">{card.label}</span>
      <span className="metric-value">
        {typeof card.value === 'number' ? card.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : card.value}
        {card.unit && <span className="metric-unit">{card.unit}</span>}
      </span>
    </div>
  )
}

// Lightweight-charts histogram for trend data
function TrendChart({ data, color, label }: { data: TrendPoint[]; color: string; label: string }) {
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartRef.current || data.length === 0) return
    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 200,
      layout: { background: { type: ColorType.Solid, color: '#f8f9fc' }, textColor: '#666' },
      grid: { vertLines: { color: '#eee' }, horzLines: { color: '#eee' } },
      rightPriceScale: { borderColor: '#ddd' },
      timeScale: { borderColor: '#ddd', visible: true },
      crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
    })
    const series = chart.addSeries(HistogramSeries, {
      color,
      priceFormat: { type: 'volume' },
    })
    series.setData(data.map((d, i) => ({
      time: i as any,
      value: d.value,
    })))
    chart.timeScale().applyOptions({
      tickMarkFormatter: (time: number) => data[time]?.period?.slice(0, 7) || '',
    })
    chart.timeScale().fitContent()
    const handleResize = () => {
      chart.applyOptions({ width: chartRef.current?.clientWidth || 400 })
    }
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [data, color])

  if (data.length === 0) return null

  return (
    <div className="trend-chart-block">
      <h4 className="trend-chart-label">{label}</h4>
      <div ref={chartRef} className="trend-chart-container" />
    </div>
  )
}

const PRIORITY_KEYS = ['marketCap', 'pe', 'pb', 'roe', 'profitMargin', 'debtToEquity', 'eps', 'dividendYield', 'revenue', 'netProfit', 'beta', 'roa', 'grossMargin']

export default function FinancialMetrics({ data }: Props) {
  const { metrics } = data
  if (!metrics || Object.keys(metrics).length === 0) return null

  // Sort metrics by priority
  const sorted = PRIORITY_KEYS
    .filter(k => metrics[k])
    .map(k => ({ label: metrics[k].label, value: metrics[k].value, unit: metrics[k].unit } as MetricCard))
  const remaining = Object.entries(metrics)
    .filter(([k]) => !PRIORITY_KEYS.includes(k))
    .map(([_, v]) => ({ label: v.label, value: v.value, unit: v.unit } as MetricCard))
  const allCards = [...sorted, ...remaining]

  return (
    <div className="financial-metrics">
      <div className="metrics-grid">
        {allCards.map(m => <MetricCardView key={m.label} card={m} />)}
      </div>

      {/* Trend charts */}
      {data.revenueTrend && data.revenueTrend.length > 0 && (
        <TrendChart data={data.revenueTrend} color="#4a90d9" label="营收趋势 (亿)" />
      )}
      {data.netProfitTrend && data.netProfitTrend.length > 0 && (
        <TrendChart data={data.netProfitTrend} color="#27ae60" label="净利润趋势 (亿)" />
      )}
    </div>
  )
}
