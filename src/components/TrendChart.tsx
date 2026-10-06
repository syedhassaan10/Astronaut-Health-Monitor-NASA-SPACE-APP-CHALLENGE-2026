import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Alert } from '../engine/healthTypes'

const COLOR: Record<Alert['level'], string> = { WATCH: '#fbbf24', ACT: '#f87171' }

export default function TrendChart({ alert }: { alert: Alert }) {
  const { series, baseline, unit, metric } = alert.what
  return (
    <div
      role="img"
      aria-label={`Trend of ${metric} over mission days. ${alert.what.summary}`}
      className="h-40 w-full"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 8, right: 12, bottom: 16, left: 0 }}>
          <CartesianGrid stroke="#26375a" strokeDasharray="3 3" />
          <XAxis dataKey="day" stroke="#7a8aa8" tick={{ fontSize: 11 }} label={{ value: 'mission day', position: 'insideBottom', offset: -10, fill: '#7a8aa8', fontSize: 10 }} />
          <YAxis stroke="#7a8aa8" tick={{ fontSize: 11 }} domain={['auto', 'auto']} width={44} unit={unit === '%' ? '%' : ''} />
          <Tooltip
            contentStyle={{ background: '#111b2e', border: '1px solid #26375a', fontSize: 12 }}
            formatter={(v) => [`${Number(v).toFixed(1)} ${unit}`, metric]}
            labelFormatter={(d) => `Day ${d}`}
          />
          {baseline !== null && <ReferenceLine y={baseline} stroke="#38bdf8" strokeDasharray="5 4" label={{ value: 'baseline', fill: '#38bdf8', fontSize: 10, position: 'insideTopLeft' }} />}
          <Line type="monotone" dataKey="value" stroke={COLOR[alert.level]} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
