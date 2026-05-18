interface RatingBadgeProps {
  decisionText: string
}

const RATING_INFO: Record<string, { bg: string; color: string; text: string; emoji: string }> = {
  Buy:  { bg: '#d4edda', color: '#155724', text: '买入', emoji: '🟢' },
  Hold: { bg: '#fff3cd', color: '#856404', text: '持有/观望', emoji: '🟡' },
  Sell: { bg: '#f8d7da', color: '#721c24', text: '卖出', emoji: '🔴' },
}

function parseRating(text: string): string | null {
  const ratingMatch = text.match(/\*\*最终评级\*\*[：:]\s*(\S+)/)
  if (ratingMatch) {
    const label = ratingMatch[1].toLowerCase()
    if (label.startsWith('buy') || label.includes('买入')) return 'Buy'
    if (label.startsWith('hold') || label.includes('持有')) return 'Hold'
    if (label.startsWith('sell') || label.includes('卖出')) return 'Sell'
  }
  return null
}

export default function RatingBadge({ decisionText }: RatingBadgeProps) {
  const rating = parseRating(decisionText)
  if (!rating) return null

  const info = RATING_INFO[rating]
  return (
    <span className="decision-badge-sm" style={{
      background: info?.bg, color: info?.color,
    }}>
      {info?.emoji} {info?.text}
    </span>
  )
}
