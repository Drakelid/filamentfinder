import { useMemo, useState } from 'react'
import { format, subDays } from 'date-fns'
import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
} from 'recharts'
import { PriceObservation } from '../api'

type RangeKey = '7D' | '30D' | 'All'

function getCurrencySymbol(currency: string) {
  try {
    const parts = new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      currencyDisplay: 'narrowSymbol',
    }).formatToParts(0)
    return parts.find((part) => part.type === 'currency')?.value || currency
  } catch {
    return currency
  }
}

function formatPrice(amount: number | null, currency: string) {
  if (amount === null) return '-'
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)
  } catch {
    return `${currency} ${amount.toFixed(2)}`
  }
}

export default function PriceHistoryChart({
  observations,
  currency,
}: {
  observations: PriceObservation[]
  currency: string
}) {
  const [range, setRange] = useState<RangeKey>('30D')
  const [showRawData, setShowRawData] = useState(false)

  const sortedObservations = useMemo(
    () => [...observations].sort((a, b) => new Date(a.observed_at).getTime() - new Date(b.observed_at).getTime()),
    [observations],
  )

  const filteredObservations = useMemo(() => {
    if (range === 'All' || sortedObservations.length === 0) {
      return sortedObservations
    }
    const latestObservedAt = new Date(sortedObservations[sortedObservations.length - 1].observed_at)
    const cutoff = subDays(latestObservedAt, range === '7D' ? 7 : 30)
    return sortedObservations.filter((observation) => new Date(observation.observed_at) >= cutoff)
  }, [range, sortedObservations])

  const chartData = useMemo(
    () =>
      filteredObservations.map((observation) => ({
        id: observation.id,
        observed_at: observation.observed_at,
        label: format(new Date(observation.observed_at), 'MMM d'),
        price: observation.price_amount !== null ? parseFloat(observation.price_amount) : null,
        in_stock: observation.in_stock,
      })),
    [filteredObservations],
  )

  const currencySymbol = getCurrencySymbol(currency || 'USD')

  if (observations.length === 0) {
    return <p className="text-gray-500 text-center py-4">No observations yet</p>
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        {(['7D', '30D', 'All'] as RangeKey[]).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setRange(option)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              range === option
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {option}
          </button>
        ))}
      </div>

      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <XAxis
              dataKey="observed_at"
              tickFormatter={(value: string) => format(new Date(value), 'MMM d')}
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              axisLine={{ stroke: '#374151' }}
              tickLine={{ stroke: '#374151' }}
            />
            <YAxis
              tickFormatter={(value: number) => `${currencySymbol}${value.toFixed(2)}`}
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              axisLine={{ stroke: '#374151' }}
              tickLine={{ stroke: '#374151' }}
              width={80}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload || payload.length === 0 || label === undefined) return null
                const point = payload[0]?.payload as { price: number | null; in_stock: boolean | null } | undefined
                return (
                  <div className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 shadow-xl">
                    <div className="text-sm text-gray-200">{format(new Date(label), 'MMM d, yyyy HH:mm')}</div>
                    <div className="text-sm font-medium text-gray-100 mt-1">
                      {formatPrice(point?.price ?? null, currency || 'USD')}
                    </div>
                    {point?.in_stock === false && (
                      <div className="text-xs text-red-400 mt-1">Out of stock</div>
                    )}
                  </div>
                )
              }}
            />
            {chartData
              .filter((point) => point.in_stock === false)
              .map((point) => (
                <ReferenceLine
                  key={`out-of-stock-${point.id}`}
                  x={point.observed_at}
                  stroke="#ef4444"
                  strokeDasharray="4 4"
                />
              ))}
            <Line
              type="monotone"
              dataKey="price"
              stroke="#6366f1"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 border-t border-gray-700 pt-4">
        <button
          type="button"
          onClick={() => setShowRawData((current) => !current)}
          className="text-sm text-gray-300 hover:text-gray-100"
        >
          {showRawData ? 'Hide raw data ▴' : 'Show raw data ▾'}
        </button>

        {showRawData && (
          <div className="mt-3 max-h-64 overflow-y-auto rounded-lg border border-gray-700">
            <table className="w-full text-sm">
              <thead className="bg-gray-900 border-b border-gray-700">
                <tr>
                  <th className="px-4 py-2 text-left text-gray-400 font-medium">Observed</th>
                  <th className="px-4 py-2 text-left text-gray-400 font-medium">Price</th>
                  <th className="px-4 py-2 text-left text-gray-400 font-medium">Stock</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {observations.map((observation) => (
                  <tr key={observation.id} className="bg-gray-800">
                    <td className="px-4 py-2 text-gray-300">
                      {format(new Date(observation.observed_at), 'MMM d, yyyy HH:mm')}
                    </td>
                    <td className="px-4 py-2 text-gray-100">
                      {formatPrice(
                        observation.price_amount !== null ? parseFloat(observation.price_amount) : null,
                        observation.currency || currency || 'USD',
                      )}
                    </td>
                    <td className="px-4 py-2 text-gray-300">
                      {observation.in_stock === true ? 'In stock' : observation.in_stock === false ? 'Out of stock' : 'Unknown'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
