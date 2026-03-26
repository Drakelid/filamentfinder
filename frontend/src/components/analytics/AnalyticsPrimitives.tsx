import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { Area, AreaChart, ResponsiveContainer, XAxis } from 'recharts'
import { ArrowUpRight, Sparkles } from 'lucide-react'

export function formatCompactNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(value >= 10_000_000 ? 0 : 1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(value >= 10_000 ? 0 : 1)}k`
  return value.toLocaleString()
}

export function AnimatedCounter({
  value,
  duration = 700,
  decimals = 0,
  formatter,
}: {
  value: number
  duration?: number
  decimals?: number
  formatter?: (value: number) => string
}) {
  const [displayValue, setDisplayValue] = useState(0)

  useEffect(() => {
    let frame = 0
    let startTime: number | null = null

    const tick = (timestamp: number) => {
      if (startTime === null) startTime = timestamp
      const progress = Math.min((timestamp - startTime) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplayValue(value * eased)
      if (progress < 1) {
        frame = window.requestAnimationFrame(tick)
      } else {
        setDisplayValue(value)
      }
    }

    frame = window.requestAnimationFrame(tick)
    return () => window.cancelAnimationFrame(frame)
  }, [duration, value])

  if (formatter) return <>{formatter(displayValue)}</>
  return <>{displayValue.toFixed(decimals)}</>
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        {eyebrow && (
          <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500">{eyebrow}</p>
        )}
        <h2 className="mt-1 text-xl font-semibold text-slate-100">{title}</h2>
        {description && <p className="mt-1 text-sm text-slate-400">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function Surface({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={`rounded-2xl border border-slate-800/90 bg-slate-900/80 shadow-lg shadow-black/20 ${className}`}>
      {children}
    </div>
  )
}

export function EmptyState({
  title,
  description,
  primaryAction,
  secondaryAction,
}: {
  title: string
  description: string
  primaryAction?: ReactNode
  secondaryAction?: ReactNode
}) {
  return (
    <Surface className="overflow-hidden">
      <div className="relative p-8 text-center">
        <div className="mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-full border border-amber-400/20 bg-amber-400/10">
          <div className="relative">
            <Sparkles className="h-8 w-8 text-amber-300" />
            <ArrowUpRight className="absolute -right-3 -top-3 h-4 w-4 text-violet-300" />
          </div>
        </div>
        <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
        <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-400">{description}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {primaryAction}
          {secondaryAction}
        </div>
      </div>
    </Surface>
  )
}

export function MiniSparkline({
  values,
  stroke = '#f59e0b',
  fill = 'rgba(245, 158, 11, 0.18)',
}: {
  values: number[]
  stroke?: string
  fill?: string
}) {
  const data = values.map((value, index) => ({ index, value }))

  if (!data.length) return null

  return (
    <ResponsiveContainer width="100%" height={36}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="miniSparklineFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={fill} stopOpacity={0.7} />
            <stop offset="95%" stopColor={fill} stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <XAxis dataKey="index" hide />
        <Area
          type="monotone"
          dataKey="value"
          stroke={stroke}
          strokeWidth={2}
          fill="url(#miniSparklineFill)"
          fillOpacity={1}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
