import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ChevronDown, Loader2, LucideIcon } from 'lucide-react'

export function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ')
}

export function SectionCard({
  eyebrow,
  title,
  description,
  action,
  children,
}: {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="rounded-3xl border border-slate-800/80 bg-slate-900/70 shadow-lg shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800/80 px-5 py-4">
        <div>
          {eyebrow && <p className="text-[11px] uppercase tracking-[0.32em] text-slate-500">{eyebrow}</p>}
          <h2 className="mt-1 text-lg font-semibold text-slate-100">{title}</h2>
          {description && <p className="mt-1 text-sm text-slate-400">{description}</p>}
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="rounded-3xl border border-slate-800/80 bg-slate-900/60 p-8 text-center shadow-lg shadow-black/20">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-slate-800 text-slate-300">
        <Icon className="h-7 w-7" />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-slate-100">{title}</h3>
      <p className="mx-auto mt-2 max-w-xl text-sm text-slate-400">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function LoadingState({ label = 'Loading...' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center rounded-3xl border border-slate-800/80 bg-slate-900/60 py-16 shadow-lg shadow-black/20">
      <div className="flex items-center gap-3 text-slate-300">
        <Loader2 className="h-5 w-5 animate-spin text-violet-400" />
        <span className="text-sm">{label}</span>
      </div>
    </div>
  )
}

export function TabStrip({
  tabs,
  active,
  onChange,
}: {
  tabs: string[]
  active: string
  onChange: (tab: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-2 rounded-2xl border border-slate-800 bg-slate-950/40 p-2">
      {tabs.map((tab) => (
        <button
          key={tab}
          type="button"
          onClick={() => onChange(tab)}
          className={cx(
            'rounded-xl px-3 py-2 text-sm font-medium transition-colors',
            active === tab
              ? 'bg-violet-500/15 text-violet-200 ring-1 ring-violet-400/30'
              : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100',
          )}
        >
          {tab}
        </button>
      ))}
    </div>
  )
}

export function MetricCard({
  label,
  value,
  sublabel,
  tone = 'violet',
}: {
  label: string
  value: string | number
  sublabel?: string
  tone?: 'violet' | 'amber' | 'emerald' | 'rose' | 'sky'
}) {
  const tones = {
    violet: 'from-violet-500/15 to-slate-900/80 text-violet-200 ring-violet-500/20',
    amber: 'from-amber-500/15 to-slate-900/80 text-amber-200 ring-amber-500/20',
    emerald: 'from-emerald-500/15 to-slate-900/80 text-emerald-200 ring-emerald-500/20',
    rose: 'from-rose-500/15 to-slate-900/80 text-rose-200 ring-rose-500/20',
    sky: 'from-sky-500/15 to-slate-900/80 text-sky-200 ring-sky-500/20',
  }

  return (
    <div className={cx('rounded-2xl border bg-gradient-to-br p-4 shadow-lg shadow-black/20 ring-1', tones[tone])}>
      <p className="text-[11px] uppercase tracking-[0.28em] text-slate-400">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-slate-50">{value}</p>
      {sublabel && <p className="mt-1 text-sm text-slate-400">{sublabel}</p>}
    </div>
  )
}

export function StatusDot({ tone }: { tone: 'emerald' | 'amber' | 'rose' | 'slate' }) {
  const colors = {
    emerald: 'bg-emerald-400 shadow-emerald-400/40',
    amber: 'bg-amber-400 shadow-amber-400/40',
    rose: 'bg-rose-400 shadow-rose-400/40',
    slate: 'bg-slate-500 shadow-slate-500/40',
  }

  return <span className={cx('inline-block h-2.5 w-2.5 rounded-full shadow-lg', colors[tone])} />
}

export function MiniSparkline({ values }: { values: number[] }) {
  const width = 96
  const height = 28
  const points = values.length ? values : [0]
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1
  const path = points
    .map((value, index) => {
      const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width
      const y = height - ((value - min) / range) * height
      return `${x},${y}`
    })
    .join(' ')

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-7 w-24 overflow-visible">
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={path}
      />
    </svg>
  )
}

export function ActionMenu({
  label = 'Actions',
  children,
}: {
  label?: ReactNode
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [])

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 transition-colors hover:bg-slate-800"
      >
        {label}
        <ChevronDown className={cx('h-4 w-4 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 min-w-44 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/95 shadow-xl shadow-black/30">
          <div onClick={() => setOpen(false)}>{children}</div>
        </div>
      )}
    </div>
  )
}
