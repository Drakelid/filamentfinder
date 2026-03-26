import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Settings, Shield, Eye, EyeOff, Save, TestTube, Loader2, CheckCircle, XCircle, Upload } from 'lucide-react'
import { api, uploadWireguardConfig, VPNConfig, VPNStatus, WireGuardConfigUploadResult } from '../api'

export default function ConfigPage() {
  const [vpnConfig, setVpnConfig] = useState<VPNConfig | null>(null)
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
  const wireguardInputRef = useRef<HTMLInputElement | null>(null)

  const vpnConfigQuery = useQuery<VPNConfig>({
    queryKey: ['vpn-config'],
    queryFn: api.config.getVpn,
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

  const saveMutation = useMutation<VPNConfig, Error, void>({
    mutationFn: () => {
      const payload: {
        account_number?: string
        socks_proxy?: string
        enabled: boolean
        auto_rotate: boolean
        rotate_interval_minutes: number
      } = {
        enabled,
        auto_rotate: autoRotate,
        rotate_interval_minutes: rotateInterval,
      }

      if (!vpnConfig?.gluetun_mode && accountNumber.trim()) {
        payload.account_number = accountNumber.trim()
      }
      if (socksProxy.trim()) {
        payload.socks_proxy = socksProxy.trim()
      }

      return api.config.updateVpn(payload)
    },
    onMutate: () => {
      setSaving(true)
      setError(null)
      setSaveSuccess(false)
      setUploadSuccess(null)
    },
    onSuccess: (data: VPNConfig) => {
      setVpnConfig(data)
      setEnabled(data.enabled)
      setAutoRotate(data.auto_rotate)
      setRotateInterval(data.rotate_interval_minutes)
      setAccountNumber('')
      setSocksProxy('')
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    },
    onError: (err: Error) => {
      setError(err.message)
    },
    onSettled: () => {
      setSaving(false)
    },
  })

  const testMutation = useMutation<VPNStatus, Error, void>({
    mutationFn: api.config.testVpn,
    onMutate: () => {
      setTesting(true)
      setTestResult(null)
      setError(null)
    },
    onSuccess: (data: VPNStatus) => {
      setTestResult(data)
    },
    onError: (err: Error) => {
      setError(err.message)
    },
    onSettled: () => {
      setTesting(false)
    },
  })

  const wireguardUploadMutation = useMutation<WireGuardConfigUploadResult, Error, File>({
    mutationFn: uploadWireguardConfig,
    onMutate: () => {
      setError(null)
      setUploadSuccess(null)
    },
    onSuccess: async (data: WireGuardConfigUploadResult) => {
      setUploadSuccess(`Uploaded ${data.file_name}. Restart Gluetun to apply it.`)
      await vpnConfigQuery.refetch()
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const loadError = vpnConfigQuery.isError
    ? vpnConfigQuery.error instanceof Error
      ? vpnConfigQuery.error.message
      : 'Failed to load VPN configuration'
    : null

  const configReady = !vpnConfigQuery.isLoading
  const displayedConfig: VPNConfig = vpnConfig ?? {
    gluetun_mode: false,
    account_number_set: false,
    proxy_configured: false,
    wireguard_file_configured: false,
    wireguard_file_name: null,
    wireguard_uploaded_at: null,
    enabled,
    auto_rotate: autoRotate,
    rotate_interval_minutes: rotateInterval,
    connected: false,
    current_server: null,
    current_ip: null,
  }
  const vpnConfigured = displayedConfig.enabled && (displayedConfig.proxy_configured || displayedConfig.gluetun_mode)
  const vpnVerified = testResult?.connected === true

  if (vpnConfigQuery.isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Settings className="w-8 h-8 text-blue-500" />
        <h1 className="text-2xl font-bold text-gray-100">Configuration</h1>
      </div>

      {loadError && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg flex items-center justify-between gap-4">
          <span>{loadError}</span>
          <button
            type="button"
            onClick={() => vpnConfigQuery.refetch()}
            className="px-3 py-1 rounded-md bg-red-800/60 text-red-100 hover:bg-red-800"
          >
            Retry
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {saveSuccess && (
        <div className="bg-green-900/50 border border-green-700 text-green-200 px-4 py-3 rounded-lg flex items-center gap-2">
          <CheckCircle className="w-5 h-5" />
          Configuration saved successfully
        </div>
      )}

      {uploadSuccess && (
        <div className="bg-green-900/50 border border-green-700 text-green-200 px-4 py-3 rounded-lg flex items-center gap-2">
          <CheckCircle className="w-5 h-5" />
          {uploadSuccess}
        </div>
      )}

      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div className="flex items-center gap-3 mb-6">
          <Shield className="w-6 h-6 text-purple-500" />
          <h2 className="text-xl font-semibold text-gray-100">Mullvad VPN</h2>
          {vpnVerified ? (
            <span className="px-2 py-1 text-xs font-medium bg-green-900/50 text-green-400 rounded-full">
              Verified
            </span>
          ) : vpnConfigured ? (
            <span className="px-2 py-1 text-xs font-medium bg-blue-900/50 text-blue-300 rounded-full">
              Configured
            </span>
          ) : null}
        </div>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              WireGuard Config File
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <input
                ref={wireguardInputRef}
                type="file"
                accept=".conf"
                className="hidden"
                onChange={(e) => {
                  const selectedFile = e.target.files?.[0]
                  if (!selectedFile) return
                  wireguardUploadMutation.mutate(selectedFile)
                  e.currentTarget.value = ''
                }}
              />
              <button
                type="button"
                onClick={() => wireguardInputRef.current?.click()}
                disabled={!configReady || wireguardUploadMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {wireguardUploadMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4" />
                )}
                Upload .conf
              </button>
              {displayedConfig.wireguard_file_configured && displayedConfig.wireguard_file_name && (
                <span className="text-sm text-green-400">
                  {displayedConfig.wireguard_file_name}
                  {displayedConfig.wireguard_uploaded_at ? ` uploaded ${new Date(displayedConfig.wireguard_uploaded_at).toLocaleString()}` : ''}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Upload a Mullvad WireGuard config file to write <code className="bg-gray-800 px-1 rounded">wg0.conf</code> into the shared Gluetun volume. Restart Gluetun after upload so it picks up the new file.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Account Number
            </label>
            <div className="relative">
              <input
                type={showAccountNumber ? 'text' : 'password'}
                value={accountNumber}
                onChange={(e) => setAccountNumber(e.target.value)}
                placeholder={
                  displayedConfig.gluetun_mode
                    ? 'Not used with Gluetun WireGuard mode'
                    : displayedConfig.account_number_set
                    ? '***************'
                    : 'Enter your Mullvad account number'
                }
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-10"
                disabled={!configReady || displayedConfig.gluetun_mode}
              />
              <button
                type="button"
                onClick={() => setShowAccountNumber(!showAccountNumber)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-300 disabled:opacity-50"
                disabled={!configReady || displayedConfig.gluetun_mode}
              >
                {showAccountNumber ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              {displayedConfig.gluetun_mode ? (
                'This deployment uses Gluetun + Mullvad WireGuard. The account number is not used here.'
              ) : (
                'Optional legacy field. For this deployment, uploading a Mullvad WireGuard config file is the preferred setup.'
              )}
            </p>
            {displayedConfig.account_number_set && !displayedConfig.gluetun_mode && (
              <p className="mt-1 text-sm text-green-500">
                Account number is configured
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              SOCKS5 Proxy URL
            </label>
            <input
              type="text"
              value={socksProxy}
              onChange={(e) => setSocksProxy(e.target.value)}
              placeholder={displayedConfig.proxy_configured ? 'Configured in backend' : 'socks5://user:pass@host:1080'}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={!configReady}
            />
            <p className="mt-1 text-sm text-gray-500">
              Required for crawler traffic. When VPN is enabled, the worker will only crawl through this SOCKS5 proxy.
            </p>
            {displayedConfig.proxy_configured && (
              <p className="mt-1 text-sm text-green-500">
                Proxy URL is configured
              </p>
            )}
          </div>

          <div className="flex items-center justify-between">
            <div>
              <label className="block text-sm font-medium text-gray-300">
                Enable VPN for Crawling
              </label>
              <p className="text-sm text-gray-500">
                Route crawler traffic through Mullvad VPN
              </p>
            </div>
            <button
              type="button"
              onClick={() => setEnabled(!enabled)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                enabled ? 'bg-blue-600' : 'bg-gray-600'
              }`}
              disabled={!configReady}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <label className="block text-sm font-medium text-gray-300">
                Auto-Rotate Servers
              </label>
              <p className="text-sm text-gray-500">
                Automatically switch VPN servers periodically
              </p>
            </div>
            <button
              type="button"
              onClick={() => setAutoRotate(!autoRotate)}
              disabled={!enabled || !configReady}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                autoRotate && enabled ? 'bg-blue-600' : 'bg-gray-600'
              } ${!enabled || !configReady ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  autoRotate ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Rotation Interval (minutes)
            </label>
            <input
              type="number"
              value={rotateInterval}
              onChange={(e) => setRotateInterval(parseInt(e.target.value, 10) || 30)}
              min={5}
              max={1440}
              disabled={!enabled || !autoRotate || !configReady}
              className={`w-32 bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                !enabled || !autoRotate || !configReady ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            />
            <p className="mt-1 text-sm text-gray-500">
              How often to switch to a new VPN server (5-1440 minutes)
            </p>
          </div>

          <div className="bg-gray-700/50 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-300 mb-2">Current Status</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Connection:</span>{' '}
                <span className={vpnVerified ? 'text-green-400' : vpnConfigured ? 'text-blue-300' : 'text-yellow-400'}>
                  {vpnVerified ? 'Verified by test' : vpnConfigured ? 'Configured, not verified' : (enabled ? 'Proxy Not Configured' : 'Disabled')}
                </span>
              </div>
              {displayedConfig.current_server && (
                <div>
                  <span className="text-gray-500">Server:</span>{' '}
                  <span className="text-gray-300">{displayedConfig.current_server}</span>
                </div>
              )}
              {displayedConfig.current_ip && (
                <div>
                  <span className="text-gray-500">IP:</span>{' '}
                  <span className="text-gray-300">{displayedConfig.current_ip}</span>
                </div>
              )}
            </div>
            {!vpnConfigured && (
              <div className="mt-3 p-3 bg-yellow-900/30 border border-yellow-700 rounded text-sm text-yellow-300">
                <p className="font-medium">VPN routing requires a SOCKS5 proxy URL:</p>
                <ol className="list-decimal list-inside mt-1 text-yellow-400 space-y-1">
                  <li>Set a SOCKS5 URL in this page or in <code className="bg-gray-800 px-1 rounded">.env</code></li>
                  <li>Use <code className="bg-gray-800 px-1 rounded">MULLVAD_SOCKS_PROXY=socks5://user:pass@host:1080</code></li>
                  <li>Restart containers after changing environment-based proxy settings</li>
                </ol>
              </div>
            )}
            {vpnConfigured && !vpnVerified && (
              <div className="mt-3 p-3 bg-blue-900/20 border border-blue-700 rounded text-sm text-blue-200">
                Configuration is present, but the live VPN path is only confirmed after <span className="font-medium">Test Connection</span> succeeds.
              </div>
            )}
          </div>

          {testResult && (
            <div className={`rounded-lg p-4 ${testResult.connected ? 'bg-green-900/30 border border-green-700' : 'bg-red-900/30 border border-red-700'}`}>
              <div className="flex items-center gap-2 mb-2">
                {testResult.connected ? (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-400" />
                )}
                <h3 className="text-sm font-medium text-gray-300">Test Result</h3>
              </div>
              <div className="text-sm">
                <p className={testResult.connected ? 'text-green-400' : 'text-red-400'}>
                  {testResult.connected ? 'Connection test succeeded' : 'Connection test failed'}
                </p>
                {testResult.ip && (
                  <p className="text-gray-400 mt-1">
                    IP {testResult.ip}{testResult.country ? ` (${testResult.country})` : ''}
                  </p>
                )}
                {testResult.mullvad_exit_ip && (
                  <p className="text-emerald-400 mt-1">Mullvad exit IP detected</p>
                )}
                {testResult.error && (
                  <p className="text-red-300 mt-1">{testResult.error}</p>
                )}
              </div>
            </div>
          )}

          <div className="flex gap-3 pt-4 border-t border-gray-700">
            <button
              onClick={() => saveMutation.mutate()}
              disabled={saving || !configReady}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Save Configuration
            </button>
            <button
              onClick={() => testMutation.mutate()}
              disabled={testing || !configReady}
              className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {testing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <TestTube className="w-4 h-4" />
              )}
              Test Connection
            </button>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-xl font-semibold text-gray-100 mb-4">Crawler Settings</h2>
        <p className="text-gray-500 text-sm">
          Additional crawler settings can be configured via environment variables.
          See the documentation for more details.
        </p>
      </div>
    </div>
  )
}
