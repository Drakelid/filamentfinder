import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { CheckCircle, Eye, EyeOff, Loader2, Save, Settings, TestTube, Upload, XCircle } from 'lucide-react'
import { api, CrawlerConfig, uploadWireguardConfig, VPNConfig, VPNStatus, WireGuardConfigUploadResult } from '../api'
import { LoadingState, SectionCard, TabStrip, cx } from '../components/admin/AdminUI'

const TABS = ['VPN & Proxy', 'Crawler Settings', 'Notifications', 'Data Management']
const DEFAULT_CRAWLER_CONFIG: CrawlerConfig = {
  user_agent: 'FilamentFinder/1.0 (+https://github.com/filamentfinder; bot)',
  rate_limit: 1,
  min_delay: 2,
  max_delay: 5,
  max_pages: 100,
  max_depth: 3,
  timeout: 30,
  respect_robots_txt: true,
  concurrent_requests: 1,
  max_concurrent_sources: 6,
  scan_schedule_enabled: true,
  scan_schedule_cron: '0 6 * * *',
  price_check_enabled: true,
  price_check_interval_hours: 48,
  price_check_batch_size: 50,
}

export default function ConfigPage() {
  const [vpnConfig, setVpnConfig] = useState<VPNConfig | null>(null)
  const [crawlerConfig, setCrawlerConfig] = useState<CrawlerConfig>(DEFAULT_CRAWLER_CONFIG)
  const [accountNumber, setAccountNumber] = useState('')
  const [socksProxy, setSocksProxy] = useState('')
  const [showAccountNumber, setShowAccountNumber] = useState(false)
  const [enabled, setEnabled] = useState(false)
  const [autoRotate, setAutoRotate] = useState(true)
  const [rotateInterval, setRotateInterval] = useState(30)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<VPNStatus | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState(TABS[0])
  const wireguardInputRef = useRef<HTMLInputElement | null>(null)

  const vpnConfigQuery = useQuery<VPNConfig>({
    queryKey: ['vpn-config'],
    queryFn: api.config.getVpn,
    staleTime: Infinity,
    retry: 1,
  })

  const crawlerConfigQuery = useQuery<CrawlerConfig>({
    queryKey: ['crawler-config'],
    queryFn: api.config.getCrawler,
    staleTime: Infinity,
    retry: 1,
  })

  useEffect(() => {
    if (!vpnConfigQuery.data) return
    setVpnConfig(vpnConfigQuery.data)
    setEnabled(vpnConfigQuery.data.enabled)
    setAutoRotate(vpnConfigQuery.data.auto_rotate)
    setRotateInterval(vpnConfigQuery.data.rotate_interval_minutes)
  }, [vpnConfigQuery.data])

  useEffect(() => {
    if (!crawlerConfigQuery.data) return
    setCrawlerConfig(crawlerConfigQuery.data)
  }, [crawlerConfigQuery.data])

  const saveMutation = useMutation<VPNConfig, Error, void>({
    mutationFn: () => {
      const payload: {
        account_number?: string
        socks_proxy?: string
        enabled: boolean
        auto_rotate: boolean
        rotate_interval_minutes: number
      } = { enabled, auto_rotate: autoRotate, rotate_interval_minutes: rotateInterval }

      if (!vpnConfig?.gluetun_mode && accountNumber.trim()) payload.account_number = accountNumber.trim()
      if (socksProxy.trim()) payload.socks_proxy = socksProxy.trim()

      return api.config.updateVpn(payload)
    },
    onMutate: () => {
      setSaving(true)
      setError(null)
      setSaveSuccess(false)
      setUploadSuccess(null)
    },
    onSuccess: (data) => {
      setVpnConfig(data)
      setEnabled(data.enabled)
      setAutoRotate(data.auto_rotate)
      setRotateInterval(data.rotate_interval_minutes)
      setAccountNumber('')
      setSocksProxy('')
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    },
    onError: (err: Error) => setError(err.message),
    onSettled: () => setSaving(false),
  })

  const testMutation = useMutation<VPNStatus, Error, void>({
    mutationFn: api.config.testVpn,
    onMutate: () => {
      setTesting(true)
      setTestResult(null)
      setError(null)
    },
    onSuccess: (data) => setTestResult(data),
    onError: (err: Error) => setError(err.message),
    onSettled: () => setTesting(false),
  })

  const uploadMutation = useMutation<WireGuardConfigUploadResult, Error, File[]>({
    mutationFn: uploadWireguardConfig,
    onMutate: () => {
      setError(null)
      setUploadSuccess(null)
    },
    onSuccess: async (data) => {
      const restartMessage = data.restarted ? 'Gluetun restarted automatically.' : `Gluetun restart failed: ${data.restart_error || 'unknown error'}`
      setUploadSuccess(`Uploaded ${data.file_names.length} config file(s). Active profile: ${data.active_file_name}. ${restartMessage}`)
      await vpnConfigQuery.refetch()
    },
    onError: (err: Error) => setError(err.message),
  })

  const saveCrawlerMutation = useMutation<CrawlerConfig, Error, void>({
    mutationFn: () => api.config.updateCrawler(crawlerConfig),
    onMutate: () => {
      setSaving(true)
      setError(null)
      setSaveSuccess(false)
      setUploadSuccess(null)
    },
    onSuccess: (data) => {
      setCrawlerConfig(data)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    },
    onError: (err: Error) => setError(err.message),
    onSettled: () => setSaving(false),
  })

  const configReady = !vpnConfigQuery.isLoading && !crawlerConfigQuery.isLoading
  const displayedConfig: VPNConfig = vpnConfig ?? {
    gluetun_mode: false,
    account_number_set: false,
    proxy_configured: false,
    wireguard_file_configured: false,
    wireguard_file_name: null,
    wireguard_uploaded_at: null,
    wireguard_profile_count: 0,
    wireguard_active_file_name: null,
    enabled,
    auto_rotate: autoRotate,
    rotate_interval_minutes: rotateInterval,
    connected: false,
    current_server: null,
    current_ip: null,
  }

  const vpnConfigured = displayedConfig.enabled && (displayedConfig.proxy_configured || displayedConfig.gluetun_mode)
  const vpnVerified = testResult?.connected === true

  if (vpnConfigQuery.isLoading || crawlerConfigQuery.isLoading) return <LoadingState label="Loading configuration" />

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.32em] text-slate-500">Administration</p>
          <h1 className="mt-1 flex items-center gap-3 text-3xl font-semibold text-slate-100">
            <Settings className="h-7 w-7 text-violet-300" />
            Configuration
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">Split configuration by intent so VPN settings, crawler behavior, notifications, and data tasks stay easier to reason about.</p>
        </div>
      </div>

      <TabStrip tabs={TABS} active={activeTab} onChange={setActiveTab} />

      {error && <div className="rounded-3xl border border-rose-500/30 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">{error}</div>}
      {saveSuccess && <div className="rounded-3xl border border-emerald-500/20 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-200">Configuration saved successfully</div>}
      {uploadSuccess && <div className="rounded-3xl border border-emerald-500/20 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-200">{uploadSuccess}</div>}

      {activeTab === 'VPN & Proxy' && (
        <div className="grid gap-6 lg:grid-cols-[1.2fr,0.8fr]">
          <SectionCard eyebrow="VPN" title="Mullvad VPN" description="Upload WireGuard profiles, set a legacy account number if needed, and test the live route." action={<span className={cx('rounded-full px-3 py-1 text-xs font-medium', vpnVerified ? 'bg-emerald-500/15 text-emerald-200' : vpnConfigured ? 'bg-sky-500/15 text-sky-200' : 'bg-amber-500/15 text-amber-200')}>{vpnVerified ? 'Verified' : vpnConfigured ? 'Configured' : 'Not configured'}</span>}>
            <div className="space-y-6">
              <div className="rounded-3xl border border-slate-800 bg-slate-950/40 p-4">
                <label className="block text-sm font-medium text-slate-300">WireGuard config files</label>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <input
                    ref={wireguardInputRef}
                    type="file"
                    accept=".conf"
                    multiple
                    className="hidden"
                    onChange={(e) => {
                      const selectedFiles = Array.from(e.target.files ?? [])
                      if (!selectedFiles.length) return
                      uploadMutation.mutate(selectedFiles)
                      e.currentTarget.value = ''
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => wireguardInputRef.current?.click()}
                    disabled={!configReady || uploadMutation.isPending}
                    className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-500 disabled:opacity-50"
                  >
                    {uploadMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                    Upload .conf files
                  </button>
                  {displayedConfig.wireguard_file_configured && displayedConfig.wireguard_active_file_name && (
                    <span className="text-sm text-emerald-300">
                      Active: {displayedConfig.wireguard_active_file_name}
                      {displayedConfig.wireguard_uploaded_at ? ` uploaded ${new Date(displayedConfig.wireguard_uploaded_at).toLocaleString()}` : ''}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-sm text-slate-500">Uploaded profiles are stored and reused for automatic rotation. Gluetun restarts after upload.</p>
                {displayedConfig.wireguard_profile_count > 0 && <p className="mt-2 text-sm text-violet-200">{displayedConfig.wireguard_profile_count} profile(s) available for rotation.</p>}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Account number</span>
                  <div className="relative">
                    <input
                      type={showAccountNumber ? 'text' : 'password'}
                      value={accountNumber}
                      onChange={(e) => setAccountNumber(e.target.value)}
                      placeholder={displayedConfig.gluetun_mode ? 'Not used with Gluetun WireGuard mode' : displayedConfig.account_number_set ? '***************' : 'Enter your Mullvad account number'}
                      disabled={!configReady || displayedConfig.gluetun_mode}
                      className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 pr-11 text-slate-100 placeholder-slate-500 disabled:opacity-50"
                    />
                    <button
                      type="button"
                      onClick={() => setShowAccountNumber((prev) => !prev)}
                      disabled={!configReady || displayedConfig.gluetun_mode}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 disabled:opacity-50"
                    >
                      {showAccountNumber ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                    </button>
                  </div>
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">SOCKS5 proxy URL</span>
                  <input
                    type="text"
                    value={socksProxy}
                    onChange={(e) => setSocksProxy(e.target.value)}
                    placeholder={displayedConfig.proxy_configured ? 'Configured in backend' : 'socks5://user:pass@host:1080'}
                    disabled={!configReady}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500 disabled:opacity-50"
                  />
                </label>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="flex items-center justify-between rounded-3xl border border-slate-800 bg-slate-950/40 p-4">
                  <div>
                    <p className="text-sm font-medium text-slate-200">Enable VPN for Crawling</p>
                    <p className="text-sm text-slate-500">Route crawler traffic through the configured proxy.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setEnabled(!enabled)}
                    disabled={!configReady}
                    className={cx('relative inline-flex h-6 w-11 items-center rounded-full transition-colors', enabled ? 'bg-violet-600' : 'bg-slate-700', !configReady && 'opacity-50')}
                  >
                    <span className={cx('inline-block h-4 w-4 transform rounded-full bg-white transition-transform', enabled ? 'translate-x-6' : 'translate-x-1')} />
                  </button>
                </div>
                <div className="flex items-center justify-between rounded-3xl border border-slate-800 bg-slate-950/40 p-4">
                  <div>
                    <p className="text-sm font-medium text-slate-200">Auto-Rotate Servers</p>
                    <p className="text-sm text-slate-500">Automatically switch VPN servers periodically.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAutoRotate(!autoRotate)}
                    disabled={!enabled || !configReady}
                    className={cx('relative inline-flex h-6 w-11 items-center rounded-full transition-colors', autoRotate && enabled ? 'bg-violet-600' : 'bg-slate-700', (!enabled || !configReady) && 'opacity-50')}
                  >
                    <span className={cx('inline-block h-4 w-4 transform rounded-full bg-white transition-transform', autoRotate ? 'translate-x-6' : 'translate-x-1')} />
                  </button>
                </div>
              </div>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-300">Rotation interval (minutes)</span>
                <input
                  type="number"
                  value={rotateInterval}
                  onChange={(e) => setRotateInterval(parseInt(e.target.value, 10) || 30)}
                  min={5}
                  max={1440}
                  disabled={!enabled || !autoRotate || !configReady}
                  className="w-40 rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 disabled:opacity-50"
                />
              </label>

              <div className="flex flex-wrap gap-3 border-t border-slate-800 pt-4">
                <button onClick={() => saveMutation.mutate()} disabled={saving || !configReady} className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-500 disabled:opacity-50">
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save configuration
                </button>
                <button onClick={() => testMutation.mutate()} disabled={testing || !configReady} className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-slate-200 hover:bg-slate-800 disabled:opacity-50">
                  {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTube className="h-4 w-4" />}
                  Test connection
                </button>
              </div>

              {testResult && (
                <div className={cx('rounded-3xl border p-4', testResult.connected ? 'border-emerald-500/20 bg-emerald-950/30' : 'border-rose-500/20 bg-rose-950/30')}>
                  <div className="flex items-center gap-2">
                    {testResult.connected ? <CheckCircle className="h-5 w-5 text-emerald-300" /> : <XCircle className="h-5 w-5 text-rose-300" />}
                    <h3 className="text-sm font-medium text-slate-200">Test Result</h3>
                  </div>
                  <p className={cx('mt-2 text-sm', testResult.connected ? 'text-emerald-200' : 'text-rose-200')}>{testResult.connected ? 'Connection test succeeded' : 'Connection test failed'}</p>
                  {testResult.ip && <p className="mt-1 text-sm text-slate-400">IP {testResult.ip}{testResult.country ? ` (${testResult.country})` : ''}</p>}
                  {testResult.mullvad_exit_ip && <p className="mt-1 text-sm text-emerald-300">Mullvad exit IP detected</p>}
                  {testResult.error && <p className="mt-1 text-sm text-rose-300">{testResult.error}</p>}
                </div>
              )}
            </div>
          </SectionCard>

          <div className="space-y-4">
            <SectionCard eyebrow="Status" title="Current state" description="Configured status versus verified live tunnel.">
              <div className="space-y-3 text-sm">
                <div><span className="text-slate-500">Connection:</span> <span className={vpnVerified ? 'text-emerald-300' : vpnConfigured ? 'text-sky-200' : 'text-amber-200'}>{vpnVerified ? 'Verified by test' : vpnConfigured ? 'Configured, not verified' : enabled ? 'Proxy not configured' : 'Disabled'}</span></div>
                {displayedConfig.current_server && <div><span className="text-slate-500">Server:</span> <span className="text-slate-200">{displayedConfig.current_server}</span></div>}
                {displayedConfig.current_ip && <div><span className="text-slate-500">IP:</span> <span className="text-slate-200">{displayedConfig.current_ip}</span></div>}
              </div>
            </SectionCard>

            <SectionCard eyebrow="Notes" title="Deployment guidance" description="Keep the current VPN path explicit.">
              <div className="space-y-3 text-sm text-slate-400">
                <p>Use uploaded WireGuard profiles for Gluetun deployments. If a SOCKS5 proxy is configured, it should point to the VPN proxy path.</p>
                <p>Legacy account number fields are kept for compatibility, but the live routing path is what the connection test verifies.</p>
              </div>
            </SectionCard>
          </div>
        </div>
      )}

      {activeTab === 'Crawler Settings' && (
        <div className="space-y-6">
          <SectionCard eyebrow="Crawler" title="Crawler settings" description="Tune crawl cadence, depth, concurrency, and price-check behavior from the UI.">
            <div className="space-y-6">
              <div className="grid gap-4 lg:grid-cols-2">
                <label className="space-y-2 lg:col-span-2">
                  <span className="text-sm font-medium text-slate-300">User agent</span>
                  <input
                    type="text"
                    value={crawlerConfig.user_agent}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, user_agent: e.target.value }))}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Rate limit</span>
                  <input
                    type="number"
                    min={0}
                    step="0.1"
                    value={crawlerConfig.rate_limit}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, rate_limit: Number(e.target.value) }))}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100"
                  />
                  <p className="text-xs text-slate-500">Requests per second target before source-specific delays apply.</p>
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Timeout</span>
                  <input
                    type="number"
                    min={1}
                    value={crawlerConfig.timeout}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, timeout: Number(e.target.value) }))}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100"
                  />
                  <p className="text-xs text-slate-500">Per-request timeout in seconds.</p>
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Minimum delay</span>
                  <input
                    type="number"
                    min={0}
                    step="0.1"
                    value={crawlerConfig.min_delay}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, min_delay: Number(e.target.value) }))}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100"
                  />
                  <p className="text-xs text-slate-500">Base delay between product price checks.</p>
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Maximum delay</span>
                  <input
                    type="number"
                    min={0}
                    step="0.1"
                    value={crawlerConfig.max_delay}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, max_delay: Number(e.target.value) }))}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100"
                  />
                  <p className="text-xs text-slate-500">Upper bound for randomized delay jitter.</p>
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Max pages per source</span>
                  <input
                    type="number"
                    min={1}
                    value={crawlerConfig.max_pages}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, max_pages: Number(e.target.value) }))}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Max depth</span>
                  <input
                    type="number"
                    min={0}
                    value={crawlerConfig.max_depth}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, max_depth: Number(e.target.value) }))}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Concurrent requests</span>
                  <input
                    type="number"
                    min={1}
                    value={crawlerConfig.concurrent_requests}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, concurrent_requests: Number(e.target.value) }))}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Max concurrent sources</span>
                  <input
                    type="number"
                    min={1}
                    value={crawlerConfig.max_concurrent_sources}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, max_concurrent_sources: Number(e.target.value) }))}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100"
                  />
                </label>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="flex items-center justify-between rounded-3xl border border-slate-800 bg-slate-950/40 p-4">
                  <div>
                    <p className="text-sm font-medium text-slate-200">Respect robots.txt</p>
                    <p className="text-sm text-slate-500">Apply robots.txt rules during listing and product crawling.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setCrawlerConfig((current) => ({ ...current, respect_robots_txt: !current.respect_robots_txt }))}
                    className={cx('relative inline-flex h-6 w-11 items-center rounded-full transition-colors', crawlerConfig.respect_robots_txt ? 'bg-violet-600' : 'bg-slate-700')}
                  >
                    <span className={cx('inline-block h-4 w-4 transform rounded-full bg-white transition-transform', crawlerConfig.respect_robots_txt ? 'translate-x-6' : 'translate-x-1')} />
                  </button>
                </div>
                <div className="flex items-center justify-between rounded-3xl border border-slate-800 bg-slate-950/40 p-4">
                  <div>
                    <p className="text-sm font-medium text-slate-200">Scheduled scans</p>
                    <p className="text-sm text-slate-500">Enable the worker cron schedule for full-source scans.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setCrawlerConfig((current) => ({ ...current, scan_schedule_enabled: !current.scan_schedule_enabled }))}
                    className={cx('relative inline-flex h-6 w-11 items-center rounded-full transition-colors', crawlerConfig.scan_schedule_enabled ? 'bg-violet-600' : 'bg-slate-700')}
                  >
                    <span className={cx('inline-block h-4 w-4 transform rounded-full bg-white transition-transform', crawlerConfig.scan_schedule_enabled ? 'translate-x-6' : 'translate-x-1')} />
                  </button>
                </div>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Scan schedule cron</span>
                  <input
                    type="text"
                    value={crawlerConfig.scan_schedule_cron}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, scan_schedule_cron: e.target.value }))}
                    disabled={!crawlerConfig.scan_schedule_enabled}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 disabled:opacity-50"
                  />
                </label>
                <div className="flex items-center justify-between rounded-3xl border border-slate-800 bg-slate-950/40 p-4">
                  <div>
                    <p className="text-sm font-medium text-slate-200">Periodic price checks</p>
                    <p className="text-sm text-slate-500">Revisit stale product pages between full-source crawls.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setCrawlerConfig((current) => ({ ...current, price_check_enabled: !current.price_check_enabled }))}
                    className={cx('relative inline-flex h-6 w-11 items-center rounded-full transition-colors', crawlerConfig.price_check_enabled ? 'bg-violet-600' : 'bg-slate-700')}
                  >
                    <span className={cx('inline-block h-4 w-4 transform rounded-full bg-white transition-transform', crawlerConfig.price_check_enabled ? 'translate-x-6' : 'translate-x-1')} />
                  </button>
                </div>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Price check interval (hours)</span>
                  <input
                    type="number"
                    min={1}
                    value={crawlerConfig.price_check_interval_hours}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, price_check_interval_hours: Number(e.target.value) }))}
                    disabled={!crawlerConfig.price_check_enabled}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 disabled:opacity-50"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Price check batch size</span>
                  <input
                    type="number"
                    min={1}
                    value={crawlerConfig.price_check_batch_size}
                    onChange={(e) => setCrawlerConfig((current) => ({ ...current, price_check_batch_size: Number(e.target.value) }))}
                    disabled={!crawlerConfig.price_check_enabled}
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 disabled:opacity-50"
                  />
                </label>
              </div>

              <div className="flex flex-wrap gap-3 border-t border-slate-800 pt-4">
                <button
                  type="button"
                  onClick={() => saveCrawlerMutation.mutate()}
                  disabled={saving || !configReady}
                  className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-500 disabled:opacity-50"
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save crawler settings
                </button>
              </div>
            </div>
          </SectionCard>
        </div>
      )}

      {activeTab === 'Notifications' && (
        <SectionCard eyebrow="Notifications" title="Notifications" description="Wire up alerts from the backend when you are ready.">
          <p className="text-sm text-slate-400">Email and webhook settings are not exposed here yet. Add them when the backend supports editable notification settings.</p>
        </SectionCard>
      )}

      {activeTab === 'Data Management' && (
        <SectionCard eyebrow="Data" title="Data management" description="Housekeeping actions for imports and retention.">
          <p className="text-sm text-slate-400">Use the admin tools elsewhere in the app for exports and bulk data operations. This section stays reserved for future maintenance actions.</p>
        </SectionCard>
      )}
    </div>
  )
}
