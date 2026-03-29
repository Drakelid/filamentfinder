import type { LucideIcon } from 'lucide-react'
import { BarChart3, Bug, Database, History, Package, Settings, ShoppingCart, TrendingDown, Truck } from 'lucide-react'

export type NavItem = {
  label: string
  to: string
  icon: LucideIcon
  keywords: string[]
}

export type NavSection = {
  label: string
  items: NavItem[]
}

export const NAV_SECTIONS: NavSection[] = [
  {
    label: 'BROWSE',
    items: [
      { label: 'Products', to: '/products', icon: Package, keywords: ['products', 'pla', 'filament', 'resin'] },
      { label: 'Deals', to: '/deals', icon: TrendingDown, keywords: ['deals', 'price drops', 'discounts'] },
      { label: 'Price Changes', to: '/price-changes', icon: ShoppingCart, keywords: ['price changes', 'history', 'drops'] },
    ],
  },
  {
    label: 'MONITOR',
    items: [
      { label: 'Sources', to: '/sources', icon: Database, keywords: ['sources', 'stores', 'retailers'] },
      { label: 'Statistics', to: '/stats', icon: BarChart3, keywords: ['statistics', 'stats', 'overview'] },
      { label: 'Scan History', to: '/runs', icon: History, keywords: ['scan history', 'runs', 'jobs'] },
    ],
  },
  {
    label: 'SETTINGS',
    items: [
      { label: 'Shipping', to: '/shipping', icon: Truck, keywords: ['shipping', 'fees', 'logistics'] },
      { label: 'Configuration', to: '/config', icon: Settings, keywords: ['configuration', 'vpn', 'proxy', 'settings'] },
      { label: 'Debug', to: '/debug', icon: Bug, keywords: ['debug', 'errors', 'warnings', 'logs', 'issues'] },
    ],
  },
]

export const PAGE_TITLES: Record<string, { title: string; description: string; section: string }> = {
  '/': { title: 'Sources', description: 'Retailers, crawl rules, and source health', section: 'MONITOR' },
  '/sources': { title: 'Sources', description: 'Retailers, crawl rules, and source health', section: 'MONITOR' },
  '/stats': { title: 'Statistics', description: 'System health and aggregate tracking data', section: 'MONITOR' },
  '/products': { title: 'Products', description: 'Browse tracked filament and resin listings', section: 'BROWSE' },
  '/deals': { title: 'Deals', description: 'Live price drops from the last 48 hours', section: 'BROWSE' },
  '/price-changes': { title: 'Price Changes', description: 'Recent changes and historical shifts', section: 'BROWSE' },
  '/runs': { title: 'Scan History', description: 'Crawler runs and execution history', section: 'MONITOR' },
  '/shipping': { title: 'Shipping', description: 'Per-source shipping fee configuration', section: 'SETTINGS' },
  '/config': { title: 'Configuration', description: 'VPN, crawler, notifications, and data settings', section: 'SETTINGS' },
  '/debug': { title: 'Debug', description: 'Aggregated errors, warnings, and system health', section: 'SETTINGS' },
}

export function resolvePageMeta(pathname: string) {
  if (pathname.startsWith('/products/')) {
    return {
      title: 'Product Detail',
      description: 'Listing history and price intelligence',
      section: 'BROWSE',
    }
  }

  return PAGE_TITLES[pathname] ?? {
    title: 'Sources',
    description: 'Retailers, crawl rules, and source health',
    section: 'MONITOR',
  }
}
