import type { StockProfile, IndexData } from '../types'

interface Props {
  profile: StockProfile
  indexData: IndexData | null
  symbol: string
}

export default function StockProfileBar({ profile, indexData, symbol }: Props) {
  const price = profile.price
  const chg = profile.change_pct
  const isUp = chg !== undefined && chg >= 0

  return (
    <div className="profile-bar">
      <div className="profile-main">
        <span className="profile-symbol">{symbol}</span>
        <span className="profile-name">{profile.name}</span>
        {profile.industry && <span className="profile-industry">{profile.industry}</span>}
        {price !== undefined && (
          <span className={`profile-price ${isUp ? 'up' : 'down'}`}>
            ¥{price.toFixed(2)}
          </span>
        )}
        {chg !== undefined && (
          <span className={`profile-change ${isUp ? 'up' : 'down'}`}>
            {isUp ? '+' : ''}{chg.toFixed(2)}%
          </span>
        )}
      </div>
      <div className="profile-detail">
        {profile.open !== undefined && <span>开: {profile.open.toFixed(2)}</span>}
        {profile.high !== undefined && <span>高: {profile.high.toFixed(2)}</span>}
        {profile.low !== undefined && <span>低: {profile.low.toFixed(2)}</span>}
        {profile.last_close !== undefined && <span>昨收: {profile.last_close.toFixed(2)}</span>}
        {profile.volume !== undefined && <span>成交量: {(profile.volume / 10000).toFixed(0)}万</span>}
      </div>
      {indexData && Object.keys(indexData).length > 0 && (
        <div className="profile-index">
          {Object.entries(indexData).map(([name, idx]) => (
            <span key={name} className={idx.change_pct >= 0 ? 'up' : 'down'}>
              {name}: {idx.price.toFixed(1)} ({idx.change_pct >= 0 ? '+' : ''}{idx.change_pct}%)
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
