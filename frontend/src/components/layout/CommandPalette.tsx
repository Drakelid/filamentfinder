import { useEffect, useRef, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Command, Search, X } from 'lucide-react'

export type CommandAction = {
  id: string
  label: string
  description?: string
  keywords?: string[]
  icon?: LucideIcon
  shortcut?: string
  onSelect: () => void
}

type CommandPaletteProps = {
  open: boolean
  actions: CommandAction[]
  onClose: () => void
}

function matchAction(action: CommandAction, query: string) {
  if (!query) return true
  const haystack = [action.label, action.description, ...(action.keywords || [])]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return haystack.includes(query.toLowerCase())
}

export default function CommandPalette({ open, actions, onClose }: CommandPaletteProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (!open) return
    setQuery('')
    window.setTimeout(() => inputRef.current?.focus(), 0)
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  const filteredActions = actions.filter((action) => matchAction(action, query))

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/65 px-4 pt-[12vh] backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div className="w-full max-w-2xl overflow-hidden rounded-3xl border border-slate-700 bg-shell-900 shadow-panel">
        <div className="flex items-center gap-3 border-b border-slate-800 px-4 py-3">
          <Command className="h-4 w-4 text-brand-violet" />
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search pages, actions, or shortcuts"
              className="w-full rounded-xl border border-slate-700 bg-slate-950/60 py-2.5 pl-9 pr-3 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-violet-500/60"
            />
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl p-2 text-slate-400 hover:bg-white/5 hover:text-white"
            aria-label="Close command palette"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-[50vh] overflow-y-auto p-2">
          {filteredActions.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-slate-500">
              No actions match this query.
            </div>
          ) : (
            filteredActions.map((action) => {
              const Icon = action.icon
              return (
                <button
                  key={action.id}
                  type="button"
                  onClick={() => {
                    action.onSelect()
                    onClose()
                  }}
                  className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm text-slate-200 transition hover:bg-slate-800/80"
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-950/50 text-slate-300">
                    {Icon ? <Icon className="h-4 w-4" /> : <Command className="h-4 w-4" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium text-slate-100">{action.label}</span>
                    {action.description && (
                      <span className="block truncate text-xs text-slate-500">{action.description}</span>
                    )}
                  </span>
                  {action.shortcut && (
                    <span className="rounded-lg border border-slate-700 px-2 py-1 text-xs text-slate-400">
                      {action.shortcut}
                    </span>
                  )}
                </button>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
