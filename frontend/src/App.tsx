import { BrowserRouter, Route, Routes } from 'react-router-dom'
import SourcesPage from './pages/SourcesPage'
import ProductsPage from './pages/ProductsPage'
import DealsPage from './pages/DealsPage'
import ProductDetailPage from './pages/ProductDetailPage'
import RunsPage from './pages/RunsPage'
import PriceChangesPage from './pages/PriceChangesPage'
import ConfigPage from './pages/ConfigPage'
import StatsPage from './pages/StatsPage'
import ShippingPage from './pages/ShippingPage'
import DebugPage from './pages/DebugPage'
import ScrapeTemplatesPage from './pages/ScrapeTemplatesPage'
import AppShell from './components/layout/AppShell'
import { ToastProvider } from './components/ui/Toast'

const routerBase = import.meta.env.BASE_URL.endsWith('/')
  ? import.meta.env.BASE_URL.slice(0, -1)
  : import.meta.env.BASE_URL

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<SourcesPage />} />
      <Route path="/sources" element={<SourcesPage />} />
      <Route path="/products" element={<ProductsPage />} />
      <Route path="/deals" element={<DealsPage />} />
      <Route path="/products/:id" element={<ProductDetailPage />} />
      <Route path="/price-changes" element={<PriceChangesPage />} />
      <Route path="/runs" element={<RunsPage />} />
      <Route path="/shipping" element={<ShippingPage />} />
      <Route path="/templates" element={<ScrapeTemplatesPage />} />
      <Route path="/config" element={<ConfigPage />} />
      <Route path="/stats" element={<StatsPage />} />
      <Route path="/debug" element={<DebugPage />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter basename={routerBase}>
      <ToastProvider>
        <AppShell>
          <AppRoutes />
        </AppShell>
      </ToastProvider>
    </BrowserRouter>
  )
}
