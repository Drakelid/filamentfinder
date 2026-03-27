import { useEffect, useMemo, useState, type ComponentType, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ChevronsLeft, ChevronsRight, Clock3, Command, Menu, MoreHorizontal, RefreshCw, X } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { api, fetchDeals } from '../../api'
import { NAV_SECTIONS, resolvePageMeta, type NavItem } from './navigation'
import CommandPalette, { type CommandAction } from './CommandPalette'
import { useToast } from '../ui/Toast'
import Skeleton from '../ui/Skeleton'

function isProductsBadgeLoading(totalProducts: number | undefined) {
  return typeof totalProducts !== 'number'
}

function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'violet' | 'amber' }) {
  const tones = {
    neutral: 'border-slate-700 bg-slate-900/70 text-slate-300',
    violet: 'border-violet-500/20 bg-violet-500/10 text-violet-200',
    amber: 'border-amber-500/20 bg-amber-500/10 text-amber-200',
  }

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  )
}

function SidebarLink({
  to,
  label,
  icon: Icon,
  collapsed,
  active,
  count,
  onNavigate,
}: {
  to: string
  label: string
  icon: ComponentType<{ className?: string }>
  collapsed: boolean
  active: boolean
  count?: ReactNode
  onNavigate?: () => void
}) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      title={collapsed ? label : undefined}
      className={`group flex items-center gap-3 rounded-2xl border-l-[3px] px-3 py-2.5 text-sm transition-all ${
          active
          ? 'border-violet-500 bg-violet-500/10 text-white shadow-[inset_0_0_0_1px_rgba(139,92,246,0.15)]'
          : 'border-transparent text-slate-400 hover:border-slate-600 hover:bg-slate-800/70 hover:text-slate-100'
      } ${collapsed ? 'justify-center px-2.5' : ''}`}
    >
      <Icon className={`h-4 w-4 shrink-0 ${active ? 'text-violet-300' : 'text-slate-500 group-hover:text-slate-200'}`} />
      {!collapsed && (
        <>
          <span className="flex-1 truncate font-medium">{label}</span>
          {count !== undefined && count !== null && (
            <span className="rounded-full border border-slate-700 bg-slate-950/60 px-2 py-0.5 text-[11px] text-slate-300">
              {count}
            </span>
          )}
        </>
      )}
    </Link>
  )
}

function MobileTabButton({
  item,
  active,
  badge,
  onNavigate,
}: {
  item: NavItem
  active: boolean
  badge?: ReactNode
  onNavigate?: () => void
}) {
  const Icon = item.icon
  return (
    <Link
      to={item.to}
      onClick={onNavigate}
      className={`relative flex min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-2xl px-2 py-2 text-[11px] font-medium transition-colors ${
        active ? 'bg-violet-500/12 text-white' : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-200'
      }`}
    >
      <Icon className={`h-4 w-4 ${active ? 'text-violet-300' : 'text-slate-500'}`} />
      <span className="truncate">{item.label}</span>
      {badge !== undefined && badge !== null && (
        <span className="absolute right-3 top-1.5 rounded-full border border-slate-700 bg-slate-950 px-1.5 py-0.5 text-[10px] text-slate-200">
          {badge}
        </span>
      )}
    </Link>
  )
}

export default function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [collapsed, setCollapsed] = useState(() => typeof window !== 'undefined' ? window.innerWidth < 1280 : false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [updatedAt, setUpdatedAt] = useState(Date.now())
  const pageMeta = resolvePageMeta(location.pathname)

  const statsQuery = useQuery({
    queryKey: ['shell', 'stats'],
    queryFn: api.stats.get,
    staleTime: 60_000,
  })

  const dealsQuery = useQuery({
    queryKey: ['shell', 'deals-count'],
    queryFn: () => fetchDeals({ limit: 100 }),
    staleTime: 5 * 60_000,
  })

  useEffect(() => {
    const nextUpdatedAt = Math.max(statsQuery.dataUpdatedAt ?? 0, dealsQuery.dataUpdatedAt ?? 0)
    if (nextUpdatedAt > 0) {
      setUpdatedAt(nextUpdatedAt)
    }
  }, [statsQuery.dataUpdatedAt, dealsQuery.dataUpdatedAt])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const isShortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k'
      if (isShortcut) {
        event.preventDefault()
        setPaletteOpen(true)
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  useEffect(() => {
    setMobileNavOpen(false)
  }, [location.pathname])

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth >= 1024) {
        setMobileNavOpen(false)
      }
    }

    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    if (!mobileNavOpen) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [mobileNavOpen])

  const refreshShell = async () => {
    await queryClient.invalidateQueries()
    setUpdatedAt(Date.now())
    toast({
      title: 'Data refreshed',
      description: 'Active queries were invalidated and will refetch in the background.',
      tone: 'success',
    })
  }

  const navActions: CommandAction[] = NAV_SECTIONS.flatMap((section) =>
    section.items.map((item) => ({
      id: item.to,
      label: item.label,
      description: `Go to ${item.label.toLowerCase()}`,
      keywords: item.keywords,
      icon: item.icon,
      onSelect: () => navigate(item.to),
    })),
  )

  navActions.push({
    id: 'refresh',
    label: 'Refresh data',
    description: 'Refetch visible dashboard queries',
    keywords: ['refresh', 'reload', 'sync'],
    icon: RefreshCw,
    shortcut: 'R',
    onSelect: refreshShell,
  })

  const totalProducts = statsQuery.data?.overview.total_products
  const activeDeals = dealsQuery.data?.length ?? null
  const lastUpdatedLabel = updatedAt ? formatDistanceToNow(new Date(updatedAt), { addSuffix: true }) : 'just now'
  const logoSrc = `${import.meta.env.BASE_URL}fila-logo.png`
  const mobilePrimaryItems = useMemo(() => {
    const browse = NAV_SECTIONS.find((section) => section.label === 'BROWSE')?.items ?? []
    const monitor = NAV_SECTIONS.find((section) => section.label === 'MONITOR')?.items ?? []
    return [
      browse.find((item) => item.to === '/products'),
      browse.find((item) => item.to === '/deals'),
      monitor.find((item) => item.to === '/sources'),
      monitor.find((item) => item.to === '/stats'),
    ].filter((item): item is NavItem => Boolean(item))
  }, [])

  return (
    <div className="min-h-screen bg-shell-900 text-slate-100">
      {mobileNavOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setMobileNavOpen(false)}
          className="fixed inset-0 z-30 bg-slate-950/70 backdrop-blur-sm lg:hidden"
        />
      )}

      <div className="flex min-h-screen pb-24 lg:pb-0">
        <aside
          className={`fixed inset-y-0 left-0 z-40 h-screen shrink-0 border-r border-slate-800/80 bg-shell-950/95 backdrop-blur-xl transition-transform duration-200 ${
            mobileNavOpen ? 'translate-x-0' : '-translate-x-full'
          } w-72 lg:sticky lg:top-0 lg:z-auto lg:translate-x-0 lg:transition-all ${
            collapsed ? 'lg:w-20' : 'lg:w-72'
          }`}
        >
          <div className="flex h-full flex-col gap-6 p-4 pb-6">
            <div className={`flex items-center gap-3 ${collapsed ? 'lg:justify-center' : ''}`}>
              <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-2xl border border-slate-800 bg-white/95 shadow-glow">
                <img src={logoSrc} alt="FilamentFinder logo" className="h-full w-full object-contain p-1" />
              </div>
              {(!collapsed || mobileNavOpen) && (
                <div className="min-w-0">
                  <p className="text-[11px] uppercase tracking-[0.35em] text-slate-500">FilamentFinder</p>
                  <h1 className="truncate text-lg font-semibold text-white">Control Center</h1>
                </div>
              )}
              <button
                type="button"
                onClick={() => setMobileNavOpen(false)}
                className="ml-auto inline-flex items-center justify-center rounded-2xl border border-slate-700 bg-slate-900/60 p-2.5 text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white lg:hidden"
                aria-label="Close navigation"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4 lg:hidden">
              <p className="text-[11px] uppercase tracking-[0.35em] text-slate-500">Quick glance</p>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-3">
                  <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Products</div>
                  <div className="mt-1 text-lg font-semibold text-white">
                    {isProductsBadgeLoading(totalProducts) ? '...' : new Intl.NumberFormat('en-US').format(totalProducts ?? 0)}
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-3">
                  <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Deals</div>
                  <div className="mt-1 text-lg font-semibold text-white">{activeDeals ?? '...'}</div>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setCollapsed((value) => !value)}
              className={`hidden items-center justify-center rounded-2xl border border-slate-700 bg-slate-900/60 p-2.5 text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white lg:inline-flex ${
                collapsed ? 'mx-auto' : 'self-start'
              }`}
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
            </button>

            <nav className="flex-1 space-y-6 overflow-y-auto scrollbar-hidden">
              {NAV_SECTIONS.map((section) => (
                <div key={section.label} className="space-y-2">
                  {(!collapsed || mobileNavOpen) && (
                    <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.35em] text-slate-500">
                      {section.label}
                    </p>
                  )}
                  <div className="space-y-1">
                    {section.items.map((item) => {
                      const active = location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)
                      const badge = item.label === 'Products'
                        ? (isProductsBadgeLoading(totalProducts) ? <Skeleton className="h-5 w-12 rounded-full" /> : new Intl.NumberFormat('en-US').format(totalProducts ?? 0))
                        : item.label === 'Deals'
                          ? (activeDeals === null ? <Skeleton className="h-5 w-10 rounded-full" /> : activeDeals)
                          : null

                      return (
                        <SidebarLink
                          key={item.to}
                          to={item.to}
                          label={item.label}
                          icon={item.icon}
                          collapsed={collapsed}
                          active={active}
                          count={badge}
                          onNavigate={() => setPaletteOpen(false)}
                        />
                      )
                    })}
                  </div>
                </div>
              ))}
            </nav>

            <div className="space-y-2">
              {(!collapsed || mobileNavOpen) && (
                <button
                  type="button"
                  onClick={refreshShell}
                  className="flex w-full items-center gap-3 rounded-2xl border border-slate-700 bg-slate-900/60 px-3 py-2.5 text-sm text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white"
                >
                  <RefreshCw className="h-4 w-4 shrink-0 text-amber-300" />
                  <span className="flex-1 text-left font-medium">Refresh dashboard</span>
                </button>
              )}
            </div>
          </div>
        </aside>

        <main className="relative min-w-0 flex-1 overflow-hidden">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgb(var(--ff-brand-violet)_/_0.16),_transparent_28%),radial-gradient(circle_at_75%_12%,_rgb(var(--ff-brand-amber)_/_0.12),_transparent_24%),linear-gradient(180deg,_rgb(var(--ff-shell-900)),_rgb(var(--ff-shell-950)))]" />
          <div className="relative z-10 flex min-h-screen flex-col gap-4 px-4 py-4 sm:px-5 sm:py-5 lg:gap-6 lg:px-8 lg:py-6">
            <header className="sticky top-3 z-20 flex flex-col gap-4 rounded-3xl border border-slate-800/80 bg-shell-800/90 px-4 py-4 shadow-soft backdrop-blur-xl sm:px-5 lg:top-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-start gap-3 min-w-0">
                <button
                  type="button"
                  onClick={() => setMobileNavOpen(true)}
                  className="inline-flex items-center justify-center rounded-2xl border border-slate-700 bg-slate-900/60 p-2.5 text-slate-200 transition hover:border-slate-600 hover:bg-slate-800 lg:hidden"
                  aria-label="Open navigation"
                >
                  <Menu className="h-4 w-4" />
                </button>
                <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.35em] text-slate-500">{pageMeta.section}</p>
                <h2 className="truncate text-xl font-semibold text-white">{pageMeta.title}</h2>
                <p className="mt-1 text-sm text-slate-400">{pageMeta.description}</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone="violet">
                  <Clock3 className="mr-2 h-3.5 w-3.5" />
                  Updated {lastUpdatedLabel}
                </Badge>
                <button
                  type="button"
                  onClick={refreshShell}
                  className="inline-flex items-center gap-2 rounded-xl border border-violet-500/20 bg-violet-500/10 px-3 py-2 text-sm font-medium text-violet-100 transition hover:bg-violet-500/20 sm:px-4"
                >
                  <RefreshCw className="h-4 w-4" />
                  <span className="hidden sm:inline">Refresh</span>
                </button>
                <button
                  type="button"
                  onClick={() => setPaletteOpen(true)}
                  className="hidden items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:bg-slate-800 sm:inline-flex sm:px-4"
                >
                  <Command className="h-4 w-4 text-violet-300" />
                  <span className="hidden sm:inline">Command</span>
                </button>
              </div>
            </header>

            <div className="animate-fade-up">{children}</div>
          </div>
        </main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-800/90 bg-shell-950/95 px-3 pb-[calc(env(safe-area-inset-bottom,0px)+0.75rem)] pt-3 backdrop-blur-xl lg:hidden">
        <div className="flex items-center gap-2 rounded-3xl border border-slate-800 bg-slate-900/80 p-2 shadow-xl shadow-black/30">
          {mobilePrimaryItems.map((item) => {
            const active = location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)
            const badge = item.to === '/products'
              ? (isProductsBadgeLoading(totalProducts) ? '...' : new Intl.NumberFormat('en-US').format(totalProducts ?? 0))
              : item.to === '/deals'
                ? (activeDeals ?? undefined)
                : undefined

            return (
              <MobileTabButton
                key={item.to}
                item={item}
                active={active}
                badge={badge}
                onNavigate={() => setMobileNavOpen(false)}
              />
            )
          })}
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            className={`relative flex min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-2xl px-2 py-2 text-[11px] font-medium transition-colors ${
              mobileNavOpen ? 'bg-violet-500/12 text-white' : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-200'
            }`}
          >
            <MoreHorizontal className={`h-4 w-4 ${mobileNavOpen ? 'text-violet-300' : 'text-slate-500'}`} />
            <span className="truncate">More</span>
          </button>
        </div>
      </nav>

      <CommandPalette
        open={paletteOpen}
        actions={navActions}
        onClose={() => setPaletteOpen(false)}
      />
    </div>
  )
}
