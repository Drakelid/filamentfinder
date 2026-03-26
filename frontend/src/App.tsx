import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { Printer, Package, History, Home, TrendingDown, Settings, BarChart3, Truck } from 'lucide-react'
import SourcesPage from './pages/SourcesPage'
import ProductsPage from './pages/ProductsPage'
import DealsPage from './pages/DealsPage'
import ProductDetailPage from './pages/ProductDetailPage'
import RunsPage from './pages/RunsPage'
import PriceChangesPage from './pages/PriceChangesPage'
import ConfigPage from './pages/ConfigPage'
import StatsPage from './pages/StatsPage'
import ShippingPage from './pages/ShippingPage'

const routerBase = import.meta.env.BASE_URL.endsWith('/')
  ? import.meta.env.BASE_URL.slice(0, -1)
  : import.meta.env.BASE_URL

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const location = useLocation()
  const isActive = location.pathname === to || location.pathname.startsWith(to + '/')
  
  return (
    <Link
      to={to}
      className={`flex items-center gap-3 px-4 py-2 rounded-xl text-sm font-medium tracking-wide transition-all ${
        isActive
          ? 'bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 text-white shadow-lg shadow-blue-900/50'
          : 'text-slate-400 hover:text-white hover:bg-slate-800/80'
      }`}
    >
      {children}
    </Link>
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex bg-slate-950 text-slate-100">
      <aside className="w-64 bg-slate-900/80 border-r border-slate-800/80 p-5 backdrop-blur-xl">
        <div className="flex items-center gap-3 mb-10">
          <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-900/40">
            <Printer className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Dashboard</p>
            <h1 className="text-2xl font-semibold text-white">FilamentFinder</h1>
          </div>
        </div>
        
        <nav className="space-y-3">
          <NavLink to="/sources">
            <Home className="w-5 h-5" />
            Sources
          </NavLink>
          <NavLink to="/stats">
            <BarChart3 className="w-5 h-5" />
            Statistics
          </NavLink>
          <NavLink to="/products">
            <Package className="w-5 h-5" />
            Products
          </NavLink>
          <NavLink to="/deals">
            <TrendingDown className="w-5 h-5" />
            Deals
          </NavLink>
          <NavLink to="/price-changes">
            <TrendingDown className="w-5 h-5" />
            Price Changes
          </NavLink>
          <NavLink to="/runs">
            <History className="w-5 h-5" />
            Scan History
          </NavLink>
          <NavLink to="/shipping">
            <Truck className="w-5 h-5" />
            Shipping
          </NavLink>
          <NavLink to="/config">
            <Settings className="w-5 h-5" />
            Configuration
          </NavLink>
        </nav>
      </aside>
      
      <main className="flex-1 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_#1e1b4b,_transparent_50%),radial-gradient(circle_at_20%_20%,_#0f172a,_transparent_35%)] opacity-90 pointer-events-none" />
        <div className="relative z-10 p-8 flex flex-col gap-6">
          {children}
        </div>
      </main>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter basename={routerBase}>
      <Layout>
        <Routes>
          <Route path="/" element={<SourcesPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/deals" element={<DealsPage />} />
          <Route path="/products/:id" element={<ProductDetailPage />} />
          <Route path="/price-changes" element={<PriceChangesPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/shipping" element={<ShippingPage />} />
          <Route path="/config" element={<ConfigPage />} />
          <Route path="/stats" element={<StatsPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
