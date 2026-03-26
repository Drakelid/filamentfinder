import { createContext, useContext, useState, type ReactNode } from 'react'
import { CheckCircle2, Info, XCircle, X } from 'lucide-react'

type ToastTone = 'info' | 'success' | 'error'

type ToastItem = {
  id: number
  title: string
  description?: string
  tone?: ToastTone
}

type ToastInput = Omit<ToastItem, 'id'>

type ToastContextValue = {
  toast: (toast: ToastInput) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const toast = (input: ToastInput) => {
    const id = Date.now() + Math.floor(Math.random() * 1000)
    setToasts((current) => [...current, { id, ...input }])
    window.setTimeout(() => {
      setToasts((current) => current.filter((item) => item.id !== id))
    }, 4000)
  }

  const dismiss = (id: number) => {
    setToasts((current) => current.filter((item) => item.id !== id))
  }

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex w-[min(92vw,24rem)] flex-col gap-3">
        {toasts.map((item) => {
          const toneClasses = {
            info: 'border-slate-700 bg-slate-900/95 text-slate-100',
            success: 'border-emerald-700/70 bg-emerald-950/90 text-emerald-50',
            error: 'border-rose-700/70 bg-rose-950/90 text-rose-50',
          }
          const tone = item.tone || 'info'
          const toneIcon = {
            info: <Info className="h-4 w-4 text-brand-cyan" />,
            success: <CheckCircle2 className="h-4 w-4 text-emerald-300" />,
            error: <XCircle className="h-4 w-4 text-rose-300" />,
          }

          return (
            <div
              key={item.id}
              className={`animate-panel-in rounded-2xl border px-4 py-3 shadow-panel ${toneClasses[tone]}`}
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5">{toneIcon[tone]}</div>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-sm text-balance">{item.title}</p>
                  {item.description && (
                    <p className="mt-1 text-sm text-slate-300/80">{item.description}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(item.id)}
                  className="rounded-full p-1 text-slate-400 hover:bg-white/5 hover:text-white"
                  aria-label="Dismiss toast"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return context
}
