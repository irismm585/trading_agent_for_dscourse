import { useEffect, useRef } from 'react'
import { createChart, ColorType, CandlestickSeries, HistogramSeries } from 'lightweight-charts'
import type { OhlcvPoint } from '../types'

interface ChartViewProps {
  data: OhlcvPoint[]
  height?: number
}

export default function ChartView({ data, height = 420 }: ChartViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current || !data.length) return

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: '#1a1a2e' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#2a2a3e' },
        horzLines: { color: '#2a2a3e' },
      },
      timeScale: {
        timeVisible: false,
        borderColor: '#2a2a3e',
      },
      rightPriceScale: {
        borderColor: '#2a2a3e',
      },
    })

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#22c55e',
      borderUpColor: '#ef4444',
      borderDownColor: '#22c55e',
      wickUpColor: '#ef4444',
      wickDownColor: '#22c55e',
    })

    // Volume series
    const volSeries = chart.addSeries(HistogramSeries, {
      color: '#3b82f6',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    })

    // Format data
    const candleData = data.map(d => ({
      time: d.date as any,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }))

    const volumeData = data.map(d => ({
      time: d.date as any,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(239, 68, 68, 0.4)' : 'rgba(34, 197, 94, 0.4)',
    }))

    candleSeries.setData(candleData)
    volSeries.setData(volumeData)
    chart.timeScale().fitContent()

    // Handle resize
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [data, height])

  if (!data.length) {
    return (
      <div className="chart-empty">
        <p>暂无行情数据</p>
      </div>
    )
  }

  return (
    <div className="chart-wrapper">
      <div ref={containerRef} className="chart-container" />
      <div className="chart-info">
        共 {data.length} 个交易日 · 最新收盘: ¥{data[data.length - 1]?.close?.toFixed(2) ?? '--'}
      </div>
    </div>
  )
}
