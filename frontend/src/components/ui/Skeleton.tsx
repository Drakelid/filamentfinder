type SkeletonProps = {
  className?: string
}

export default function Skeleton({ className = '' }: SkeletonProps) {
  return <div className={`animate-pulse-soft rounded-lg bg-shell-700/60 ${className}`} aria-hidden="true" />
}

