import { Link } from 'react-router-dom'
import { Package, Info } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import type { ReactNode } from 'react'

export function formatPrice(amount: string | null, currency: string | null): string {
  if (!amount) return '-'
  const num = parseFloat(amount)
  const curr = currency || 'USD'
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: curr }).format(num)
  } catch {
    return `${curr} ${num.toFixed(2)}`
  }
}

export function formatNumberCurrency(amount: number | null, currency: string | null): string {
  if (amount === null) return '-'
  const curr = currency || 'USD'
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: curr, maximumFractionDigits: 2 }).format(amount)
  } catch {
    return `${curr} ${amount.toFixed(2)}`
  }
}

export function CategoryBadge({ category }: { category: string }) {
  const styles: Record<string, string> = {
    filament: 'bg-violet-500/15 text-violet-200 border-violet-500/30',
    resin: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
    unknown: 'bg-slate-700/80 text-slate-300 border-slate-600',
  }

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em] ${styles[category] || styles.unknown}`}>
      {category}
    </span>
  )
}

export function StockBadge({ inStock }: { inStock: boolean | null }) {
  if (inStock === null) return null

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em] ${
      inStock ? 'bg-emerald-500/15 text-emerald-200 border border-emerald-500/25' : 'bg-rose-500/15 text-rose-200 border border-rose-500/25'
    }`}>
      {inStock ? 'In Stock' : 'Out of Stock'}
    </span>
  )
}

export function MatchBadge({ confidence }: { confidence: number }) {
  const percentage = Math.round(confidence * 100)
  return (
    <span
      title="Relevance is a crawl confidence score based on name, brand, category, and product type alignment."
      className="inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-900/80 px-2.5 py-1 text-[11px] font-medium text-slate-300"
    >
      <Info className="h-3 w-3 text-slate-400" />
      Relevance {percentage}%
    </span>
  )
}

export function Breadcrumbs({ items }: { items: Array<{ label: string; href?: string }> }) {
  return (
    <nav className="flex flex-wrap items-center gap-2 text-sm text-slate-400">
      {items.map((item, index) => (
        <span key={`${item.label}-${index}`} className="flex items-center gap-2">
          {index > 0 && <span className="text-slate-600">/</span>}
          {item.href ? (
            <Link to={item.href} className="hover:text-slate-200 transition-colors">
              {item.label}
            </Link>
          ) : (
            <span className="text-slate-200">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}

export function ProductSkeletonList() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 animate-pulse">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_120px_120px_120px_110px_110px]">
            <div className="space-y-3">
              <div className="h-4 w-2/3 rounded bg-slate-700" />
              <div className="h-3 w-1/3 rounded bg-slate-800" />
              <div className="h-3 w-1/2 rounded bg-slate-800" />
            </div>
            <div className="h-10 rounded-xl bg-slate-800" />
            <div className="h-10 rounded-xl bg-slate-800" />
            <div className="h-10 rounded-xl bg-slate-800" />
            <div className="h-10 rounded-xl bg-slate-800" />
            <div className="h-10 rounded-xl bg-slate-800" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function ProductSkeletonGrid() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 animate-pulse">
          <div className="h-40 rounded-xl bg-slate-800" />
          <div className="mt-4 space-y-3">
            <div className="h-4 w-4/5 rounded bg-slate-700" />
            <div className="h-3 w-1/2 rounded bg-slate-800" />
            <div className="flex gap-3">
              <div className="h-9 flex-1 rounded-xl bg-slate-800" />
              <div className="h-9 w-24 rounded-xl bg-slate-800" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export function ProductEmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/80 p-10 text-center shadow-lg shadow-black/20">
      <div className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-violet-500/40 to-transparent" />
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-slate-700 bg-slate-950/80">
        <Package className="h-8 w-8 text-slate-500" />
      </div>
      <h3 className="text-xl font-semibold text-slate-100">{title}</h3>
      <p className="mx-auto mt-2 max-w-xl text-sm text-slate-400">{description}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}

export function ProductCardImage({ imageUrl, name }: { imageUrl: string | null; name: string }) {
  if (!imageUrl) return null

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/60">
      <img
        src={imageUrl}
        alt={name}
        className="h-full w-full object-contain"
        onError={(e) => {
          e.currentTarget.style.display = 'none'
        }}
      />
    </div>
  )
}

export function ProductUpdatedAt({ updatedAt }: { updatedAt: string }) {
  return <span>{formatDistanceToNow(new Date(updatedAt), { addSuffix: true })}</span>
}
