import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { CheckIn } from '../engine/healthTypes'

// Colour + dash pattern so the four lines are distinguishable without colour.
const LINES = [
  { key: 'sleep', name: 'Sleep', color: '#38bdf8', dash: undefined },
  { key: 'fatigue', name: 'Fatigue', color: '#fbbf24', dash: '6 3' },
  { key: 'pain', name: 'Pain', color: '#f87171', dash: undefined },
  { key: 'stress', name: 'Stress', color: '#a78bfa', dash: '2 3' },
] as const

export default function CheckinTrend({ checkins, label }: { checkins: CheckIn[]; label: string }) {
  const data = [...checkins].sort((a, b) => a.day - b.day)
  return (
    <div role="img" aria-label={`Daily check-in trend for ${label}: sleep, fatigue, pain and stress, 0 to 10, by mission day.`} className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#26375a" strokeDasharray="3 3" />
          <XAxis dataKey="day" stroke="#7a8aa8" tick={{ fontSize: 11 }} />
          <YAxis stroke="#7a8aa8" tick={{ fontSize: 11 }} domain={[0, 10]} width={28} />
          <Tooltip contentStyle={{ background: '#111b2e', border: '1px solid #26375a', fontSize: 12 }} labelFormatter={(d) => `Day ${d}`} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {LINES.map((l) => (
            <Line key={l.key} type="monotone" dataKey={l.key} name={l.name} stroke={l.color} strokeDasharray={l.dash}
              strokeWidth={2} dot={false} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
