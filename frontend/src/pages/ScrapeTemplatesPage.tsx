import { useState } from 'react'
import { Layers3, Sparkles, Wand2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { EmptyState, MetricCard, SectionCard } from '../components/admin/AdminUI'
import AddSourceModal from '../components/sources/AddSourceModal'
import { GENERIC_HEURISTIC_COVERAGE, SCRAPE_TEMPLATES, type ScrapeTemplate } from '../data/scrapeTemplates'

function TemplatePill({ children }: { children: string }) {
  return (
    <span className="rounded-full border border-slate-700 bg-slate-950/60 px-2.5 py-1 text-xs text-slate-300">
      {children}
    </span>
  )
}

export default function ScrapeTemplatesPage() {
  const navigate = useNavigate()
  const [selectedTemplate, setSelectedTemplate] = useState<ScrapeTemplate | null>(null)
  const [showBlankModal, setShowBlankModal] = useState(false)

  const maxPriority = Math.max(...SCRAPE_TEMPLATES.map((template) => template.priority))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.32em] text-slate-500">Monitor</p>
          <h1 className="mt-1 text-3xl font-semibold text-slate-100">Scraping Templates</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Start new sources from the scraper strategies already built into the worker. These presets mirror the current parser stack and seed source creation with sane crawl defaults instead of a blank form.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => setShowBlankModal(true)}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-slate-200 hover:bg-slate-800"
          >
            <Layers3 className="h-4 w-4" />
            Blank source
          </button>
          <button
            type="button"
            onClick={() => navigate('/sources')}
            className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-500"
          >
            <Wand2 className="h-4 w-4" />
            View sources
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Built-in templates" value={SCRAPE_TEMPLATES.length} sublabel="One card per parser strategy" tone="violet" />
        <MetricCard label="Fallback heuristics" value={GENERIC_HEURISTIC_COVERAGE.length} sublabel="Generic parser site packs and recovery paths" tone="sky" />
        <MetricCard label="Highest priority" value={maxPriority} sublabel="JSON-LD remains first in parser order" tone="emerald" />
      </div>

      <SectionCard
        eyebrow="Parser stack"
        title="Built-in scraper presets"
        description="These are the strategies already compiled into the worker. Picking one here does not force a parser lock; it gives operators a clear starting point and recommended crawl defaults."
      >
        <div className="grid gap-4 xl:grid-cols-2">
          {SCRAPE_TEMPLATES.map((template) => (
            <article key={template.id} className="rounded-3xl border border-slate-800 bg-slate-950/40 p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-lg font-semibold text-slate-100">{template.name}</h3>
                    <TemplatePill>{template.parser}</TemplatePill>
                  </div>
                  <p className="mt-2 text-sm text-slate-400">{template.description}</p>
                </div>
                <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-xs font-medium text-violet-200">
                  Priority {template.priority}
                </span>
              </div>

              <div className="mt-4 space-y-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Signals</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {template.detectionSignals.map((signal) => (
                      <TemplatePill key={signal}>{signal}</TemplatePill>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Strengths</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {template.strengths.map((strength) => (
                      <TemplatePill key={strength}>{strength}</TemplatePill>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Coverage</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {template.coverage.map((item) => (
                      <TemplatePill key={item}>{item}</TemplatePill>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 pt-4">
                <div className="text-xs text-slate-500">
                  Default crawl: {template.crawlRules?.max_pages ?? 100} pages, depth {template.crawlRules?.max_depth ?? 3}
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedTemplate(template)}
                  className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
                >
                  <Sparkles className="h-4 w-4" />
                  Use template
                </button>
              </div>
            </article>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        eyebrow="Generic coverage"
        title="Site-specific heuristics already in the worker"
        description="The generic parser is more than a last resort. It also carries specialized extraction branches for several storefronts and custom HTML shapes."
      >
        <div className="flex flex-wrap gap-2">
          {GENERIC_HEURISTIC_COVERAGE.map((item) => (
            <TemplatePill key={item}>{item}</TemplatePill>
          ))}
        </div>
      </SectionCard>

      <EmptyState
        icon={Layers3}
        title="Need a custom source anyway?"
        description="Use a built-in template when the site resembles one of the known parser strategies. If it still needs per-source selectors, the crawler now applies those overrides consistently during full crawls and scheduled price checks."
        action={
          <button
            type="button"
            onClick={() => setShowBlankModal(true)}
            className="rounded-xl bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-500"
          >
            Add blank source
          </button>
        }
      />

      {selectedTemplate && (
        <AddSourceModal
          templatePreset={selectedTemplate}
          onClose={() => setSelectedTemplate(null)}
          onSuccess={() => navigate('/sources')}
        />
      )}

      {showBlankModal && (
        <AddSourceModal
          onClose={() => setShowBlankModal(false)}
          onSuccess={() => navigate('/sources')}
        />
      )}
    </div>
  )
}
