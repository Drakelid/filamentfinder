import { useQuery } from '@tanstack/react-query'
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { format } from 'date-fns'
import { Loader2 } from 'lucide-react'
import { api, PriceObservation } from '../../api'

function formatPrice(amount: string | null, currency: string | null): string {
  if (!amount) return '-'
  const num = Number.parseFloat(amount)
  const curr = currency || 'USD'
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: curr }).format(num)
  } catch {
    return `${curr} ${num.toFixed(2)}`
  }
}

type TrendPoint = {
  observed_at: string
  price: number | null
}

export default function PriceChangeSparkline({
  productId,
  currency,
}: {
  productId: number
  currency: string | null
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['price-change-trend', productId],
    queryFn: () => api.products.history(productId),
    staleTime: 5 * 60 * 1000,
    enabled: Boolean(productId),
  })

  const observations = (data?.observations ?? []) as PriceObservation[]
  const points: TrendPoint[] = observations
    .slice(-12)
    .map((observation) => ({
      observed_at: observation.observed_at,
      price: observation.price_amount ? Number.parseFloat(observation.price_amount) : null,
    }))
    .filter((point) => point.price !== null) as TrendPoint[]

  if (isLoading) {
    return (
      <div className="flex h-10 items-center justify-center text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" />
      </div>
    )
  }

  if (points.length < 2) {
    return (
      <div className="flex h-10 items-center justify-center rounded-lg border border-slate-800 bg-slate-950/40 text-xs text-slate-500">
        No trend data
      </div>
    )
  }

  return (
    <div className="h-12 w-28">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points}>
          <Tooltip
            cursor={{ stroke: '#475569', strokeDasharray: '3 3' }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const point = payload[0]?.payload as TrendPoint
              return (
                <div className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs shadow-xl shadow-black/40">
                  <div className="text-slate-400">{format(new Date(point.observed_at), 'MMM d, yyyy')}</div>
                  <div className="mt-1 font-medium text-slate-100">
                    {formatPrice(point.price !== null ? String(point.price) : null, currency)}
                  </div>
                </div>
              )
            }}
          />
          <Line
            type="monotone"
            dataKey="price"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
