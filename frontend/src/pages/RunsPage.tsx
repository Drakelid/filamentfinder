import { useQuery } from '@tanstack/react-query'
import { Loader2, CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react'
import { api, CrawlRun } from '../api'
import { format } from 'date-fns'

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    running: 'bg-blue-900 text-blue-300',
    completed: 'bg-green-900 text-green-300',
    failed: 'bg-red-900 text-red-300',
  }
  
  const icons: Record<string, React.ReactNode> = {
    running: <Loader2 className="w-3 h-3 animate-spin" />,
    completed: <CheckCircle className="w-3 h-3" />,
    failed: <XCircle className="w-3 h-3" />,
  }
  
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-700 text-gray-300'}`}>
      {icons[status] || <Clock className="w-3 h-3" />}
      {status}
    </span>
  )
}

function formatDuration(start: string, end: string | null): string {
  if (!end) return 'In progress...'
  
  const startDate = new Date(start)
  const endDate = new Date(end)
  const seconds = Math.round((endDate.getTime() - startDate.getTime()) / 1000)
  
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}

export default function RunsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['runs'],
    queryFn: () => api.runs.list(),
    refetchInterval: 5000,
  })
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Failed to load runs: {(error as Error).message}
      </div>
    )
  }
  
  const runs = data?.items || []
  
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-100">Scan History</h1>
        <p className="text-gray-400 mt-1">View past and ongoing crawl runs</p>
      </div>
      
      {runs.length === 0 ? (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
          <Clock className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">No scan runs yet</p>
          <p className="text-sm text-gray-500 mt-1">
            Add a source and run a scan to see results here
          </p>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-900 border-b border-gray-700">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Run ID</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Status</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Started</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Duration</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-300">Pages</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-300">Products</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-300">Changes</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-300">Errors</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {runs.map((run: CrawlRun) => (
                <tr key={run.id} className="hover:bg-gray-700/50">
                  <td className="px-4 py-3 font-medium text-gray-100">
                    #{run.id}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    <div>{format(new Date(run.started_at), 'MMM d, yyyy')}</div>
                    <div className="text-sm text-gray-500">
                      {format(new Date(run.started_at), 'HH:mm:ss')}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {formatDuration(run.started_at, run.finished_at)}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-300">
                    {run.pages_visited}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="text-gray-300">{run.products_found} new</div>
                    <div className="text-sm text-gray-500">{run.products_updated} updated</div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {run.price_changes_detected > 0 ? (
                      <span className="inline-flex items-center gap-1 text-amber-400 font-medium">
                        <AlertTriangle className="w-4 h-4" />
                        {run.price_changes_detected}
                      </span>
                    ) : (
                      <span className="text-gray-500">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {run.errors_count > 0 ? (
                      <span className="text-red-400 font-medium">{run.errors_count}</span>
                    ) : (
                      <span className="text-gray-500">0</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
