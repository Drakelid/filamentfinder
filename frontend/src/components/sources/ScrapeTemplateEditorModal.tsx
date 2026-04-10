import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { api, type CrawlRules, type CustomScrapeTemplate, type SelectorOverrides } from '../../api'
import { cx } from '../admin/AdminUI'

function splitLines(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function joinLines(value?: string[]) {
  return (value ?? []).join('\n')
}

function buildInitialState(template?: CustomScrapeTemplate | null) {
  return {
    name: template?.name ?? '',
    parser: template?.parser ?? 'Custom selector preset',
    description: template?.description ?? '',
    detectionSignals: joinLines(template?.detection_signals),
    strengths: joinLines(template?.strengths),
    coverage: joinLines(template?.coverage),
    maxPages: template?.crawl_rules?.max_pages ?? 100,
    maxDepth: template?.crawl_rules?.max_depth ?? 3,
    sameDomainOnly: template?.crawl_rules?.same_domain_only ?? true,
    respectRobotsTxt: template?.crawl_rules?.respect_robots_txt ?? true,
    urlPatterns: joinLines(template?.crawl_rules?.url_patterns),
    excludePatterns: joinLines(template?.crawl_rules?.exclude_patterns),
    productName: template?.selector_overrides?.product_name ?? '',
    price: template?.selector_overrides?.price ?? '',
    currency: template?.selector_overrides?.currency ?? '',
    image: template?.selector_overrides?.image ?? '',
    brand: template?.selector_overrides?.brand ?? '',
    sku: template?.selector_overrides?.sku ?? '',
    inStock: template?.selector_overrides?.in_stock ?? '',
    productLinks: template?.selector_overrides?.product_links ?? '',
  }
}

export default function ScrapeTemplateEditorModal({
  template = null,
  onClose,
  onSuccess,
}: {
  template?: CustomScrapeTemplate | null
  onClose: () => void
  onSuccess: () => void
}) {
  const [state, setState] = useState(() => buildInitialState(template))
  const [error, setError] = useState('')

  useEffect(() => {
    setState(buildInitialState(template))
    setError('')
  }, [template])

  const mutation = useMutation({
    mutationFn: async () => {
      const crawlRules: CrawlRules = {
        max_pages: state.maxPages,
        max_depth: state.maxDepth,
        same_domain_only: state.sameDomainOnly,
        url_patterns: splitLines(state.urlPatterns),
        exclude_patterns: splitLines(state.excludePatterns),
        respect_robots_txt: state.respectRobotsTxt,
      }

      const selectorOverrides: SelectorOverrides = {}
      if (state.productName.trim()) selectorOverrides.product_name = state.productName.trim()
      if (state.price.trim()) selectorOverrides.price = state.price.trim()
      if (state.currency.trim()) selectorOverrides.currency = state.currency.trim()
      if (state.image.trim()) selectorOverrides.image = state.image.trim()
      if (state.brand.trim()) selectorOverrides.brand = state.brand.trim()
      if (state.sku.trim()) selectorOverrides.sku = state.sku.trim()
      if (state.inStock.trim()) selectorOverrides.in_stock = state.inStock.trim()
      if (state.productLinks.trim()) selectorOverrides.product_links = state.productLinks.trim()

      const payload = {
        name: state.name.trim(),
        parser: state.parser.trim(),
        description: state.description.trim(),
        detection_signals: splitLines(state.detectionSignals),
        strengths: splitLines(state.strengths),
        coverage: splitLines(state.coverage),
        crawl_rules: crawlRules,
        selector_overrides: Object.keys(selectorOverrides).length ? selectorOverrides : null,
      }

      if (template?.id) {
        return api.config.updateScrapeTemplate(template.id, payload)
      }
      return api.config.createScrapeTemplate(payload)
    },
    onSuccess: () => {
      onSuccess()
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 backdrop-blur-sm">
      <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-3xl border border-slate-800 bg-slate-900 shadow-2xl shadow-black/40">
        <div className="border-b border-slate-800 px-6 py-4">
          <p className="text-[11px] uppercase tracking-[0.3em] text-slate-500">Custom preset</p>
          <h2 className="mt-1 text-xl font-semibold text-slate-100">
            {template ? 'Edit Scraping Template' : 'Create Scraping Template'}
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            Custom templates are source presets. They do not add new parser code, but they can save crawl defaults and selector overrides for repeatable onboarding.
          </p>
        </div>

        <div className="space-y-6 px-6 py-5">
          {error && <div className="rounded-2xl border border-rose-500/30 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">{error}</div>}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Template name *</span>
              <input
                value={state.name}
                onChange={(e) => setState((current) => ({ ...current, name: e.target.value }))}
                type="text"
                placeholder="Nordic custom storefront"
                className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
              />
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Template label *</span>
              <input
                value={state.parser}
                onChange={(e) => setState((current) => ({ ...current, parser: e.target.value }))}
                type="text"
                placeholder="Custom selector preset"
                className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
              />
            </label>
          </div>

          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-300">Description</span>
            <textarea
              value={state.description}
              onChange={(e) => setState((current) => ({ ...current, description: e.target.value }))}
              rows={3}
              placeholder="Explain when this preset should be used."
              className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
            />
          </label>

          <div className="grid gap-4 md:grid-cols-3">
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Detection signals</span>
              <textarea value={state.detectionSignals} onChange={(e) => setState((current) => ({ ...current, detectionSignals: e.target.value }))} rows={4} placeholder="One per line" className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500" />
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Strengths</span>
              <textarea value={state.strengths} onChange={(e) => setState((current) => ({ ...current, strengths: e.target.value }))} rows={4} placeholder="One per line" className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500" />
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Coverage</span>
              <textarea value={state.coverage} onChange={(e) => setState((current) => ({ ...current, coverage: e.target.value }))} rows={4} placeholder="One per line" className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500" />
            </label>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-950/30 p-4">
            <p className="text-[11px] uppercase tracking-[0.3em] text-slate-500">Crawl defaults</p>
            <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <label className="space-y-2">
                <span className="text-sm text-slate-300">Max pages</span>
                <input type="number" min={1} max={10000} value={state.maxPages} onChange={(e) => setState((current) => ({ ...current, maxPages: parseInt(e.target.value, 10) || 100 }))} className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100" />
              </label>
              <label className="space-y-2">
                <span className="text-sm text-slate-300">Max depth</span>
                <input type="number" min={1} max={10} value={state.maxDepth} onChange={(e) => setState((current) => ({ ...current, maxDepth: parseInt(e.target.value, 10) || 3 }))} className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100" />
              </label>
              <button type="button" onClick={() => setState((current) => ({ ...current, sameDomainOnly: !current.sameDomainOnly }))} className={cx('mt-7 rounded-2xl border px-4 py-3 text-sm transition-colors', state.sameDomainOnly ? 'border-violet-500/40 bg-violet-500/15 text-violet-100' : 'border-slate-700 text-slate-300')}>
                Same domain only: {state.sameDomainOnly ? 'On' : 'Off'}
              </button>
              <button type="button" onClick={() => setState((current) => ({ ...current, respectRobotsTxt: !current.respectRobotsTxt }))} className={cx('mt-7 rounded-2xl border px-4 py-3 text-sm transition-colors', state.respectRobotsTxt ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-100' : 'border-slate-700 text-slate-300')}>
                Respect robots.txt: {state.respectRobotsTxt ? 'On' : 'Off'}
              </button>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="space-y-2">
                <span className="text-sm text-slate-300">URL patterns</span>
                <textarea value={state.urlPatterns} onChange={(e) => setState((current) => ({ ...current, urlPatterns: e.target.value }))} rows={4} placeholder="One glob per line" className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500" />
              </label>
              <label className="space-y-2">
                <span className="text-sm text-slate-300">Exclude patterns</span>
                <textarea value={state.excludePatterns} onChange={(e) => setState((current) => ({ ...current, excludePatterns: e.target.value }))} rows={4} placeholder="One glob per line" className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500" />
              </label>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-950/30 p-4">
            <p className="text-[11px] uppercase tracking-[0.3em] text-slate-500">Selector overrides</p>
            <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {[
                ['Product name', 'productName', state.productName],
                ['Price', 'price', state.price],
                ['Currency', 'currency', state.currency],
                ['Image', 'image', state.image],
                ['Brand', 'brand', state.brand],
                ['SKU', 'sku', state.sku],
                ['Stock', 'inStock', state.inStock],
                ['Product links', 'productLinks', state.productLinks],
              ].map(([label, key, value]) => (
                <label key={key} className="space-y-2">
                  <span className="text-sm text-slate-300">{label}</span>
                  <input
                    value={value}
                    onChange={(e) => setState((current) => ({ ...current, [key]: e.target.value }))}
                    type="text"
                    placeholder=".selector"
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500"
                  />
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-slate-800 px-6 py-4">
          <button onClick={onClose} className="rounded-xl px-4 py-2 text-slate-300 hover:bg-slate-800">Cancel</button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!state.name.trim() || !state.parser.trim() || mutation.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {template ? 'Save template' : 'Create template'}
          </button>
        </div>
      </div>
    </div>
  )
}
