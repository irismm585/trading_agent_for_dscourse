import { useState, useEffect, useRef, useCallback } from 'react'
import type { WebSocketMessage, WsCommand, OhlcvPoint, StockProfile, IndexData } from '../types'

export interface UseWebSocketReturn {
  messages: WebSocketMessage[]
  currentNode: string | null
  isConnected: boolean
  isComplete: boolean
  error: string | null
  generatingSections: Set<string>    // sections currently being generated
  chartData: OhlcvPoint[]            // OHLCV data for chart rendering
  stockProfile: StockProfile | null  // stock profile info
  indexData: IndexData | null        // market index data
  financialData: any | null          // structured financial metrics
  connect: (sessionId: string) => void
  disconnect: () => void
  sendCommand: (command: WsCommand) => void
}

export function useWebSocket(): UseWebSocketReturn {
  const [messages, setMessages] = useState<WebSocketMessage[]>([])
  const [currentNode, setCurrentNode] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [generatingSections, setGeneratingSections] = useState<Set<string>>(new Set())
  const [chartData, setChartData] = useState<OhlcvPoint[]>([])
  const [stockProfile, setStockProfile] = useState<StockProfile | null>(null)
  const [indexData, setIndexData] = useState<IndexData | null>(null)
  const [financialData, setFinancialData] = useState<any | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const commandQueueRef = useRef<WsCommand[]>([])

  const drainQueue = useCallback(() => {
    const queue = commandQueueRef.current
    commandQueueRef.current = []
    for (const cmd of queue) {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(cmd))
      }
    }
  }, [])

  const connect = useCallback((sessionId: string) => {
    // Reset state
    setMessages([])
    setCurrentNode(null)
    setIsConnected(false)
    setIsComplete(false)
    setError(null)
    setGeneratingSections(new Set())
    setChartData([])
    setStockProfile(null)
    setIndexData(null)
    setFinancialData(null)
    commandQueueRef.current = []

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      drainQueue()
    }

    ws.onmessage = (event) => {
      try {
        const msg: WebSocketMessage = JSON.parse(event.data)
        setMessages((prev) => [...prev, msg])

        if (msg.type === 'node_update' && msg.node) {
          setCurrentNode(msg.node)
        }

        if (msg.type === 'connected') {
          setIsConnected(true)
        }

        if (msg.type === 'status' && msg.section) {
          // Mark section as generating
          setGeneratingSections((prev) => new Set(prev).add(msg.section!))
        }

        if (msg.type === 'section_complete') {
          // Mark section as done generating
          setGeneratingSections((prev) => {
            const next = new Set(prev)
            next.delete(msg.section!)
            return next
          })
        }

        if (msg.type === 'chart_data' && msg.data) {
          setChartData(msg.data)
        }

        if (msg.type === 'stock_profile' && msg.profile) {
          setStockProfile(msg.profile)
          if (msg.index_data) setIndexData(msg.index_data)
        }

        if (msg.type === 'financial_data' && msg.data) {
          setFinancialData(msg.data)
        }

        if (msg.type === 'complete') {
          setIsComplete(true)
          setGeneratingSections(new Set())
        }

        if (msg.type === 'error') {
          setError(msg.message || 'Unknown error')
          // Clear generating sections on error
          if (msg.section) {
            setGeneratingSections((prev) => {
              const next = new Set(prev)
              next.delete(msg.section!)
              return next
            })
          }
        }
      } catch {
        // Ignore parse errors
      }
    }

    ws.onerror = () => {
      setError('WebSocket connection error')
    }

    ws.onclose = () => {
      setIsConnected(false)
    }
  }, [])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
    setGeneratingSections(new Set())
  }, [])

  const sendCommand = useCallback((command: WsCommand) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(command))
    } else if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) {
      // Queue for when connection opens
      commandQueueRef.current.push(command)
    }
    // Track generating sections regardless of connection state
    if (command.action === 'generate_section' && command.section) {
      setGeneratingSections((prev) => new Set(prev).add(command.section!))
    }
    if (command.action === 'run_debate') {
      setGeneratingSections((prev) => new Set(prev).add('debate'))
    }
    if (command.action === 'run_judge') {
      setGeneratingSections((prev) => new Set(prev).add('decision'))
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  return {
    messages,
    currentNode,
    isConnected,
    isComplete,
    error,
    generatingSections,
    chartData,
    stockProfile,
    indexData,
    financialData,
    connect,
    disconnect,
    sendCommand,
  }
}
