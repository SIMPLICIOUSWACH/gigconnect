import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary: 'bg-primary text-white hover:bg-primary-hover disabled:bg-disabled disabled:text-muted',
  secondary: 'bg-surface text-ink border-2 border-ink hover:bg-sand disabled:opacity-50',
  danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300',
}

export default function Button({ variant = 'primary', className = '', loading = false, disabled, children, ...props }) {
  return (
    <button
      disabled={disabled || loading}
      className={`min-h-[48px] px-5 rounded-button text-[15px] font-bold leading-none transition-colors duration-150 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2 ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {loading && <Loader2 size={16} className="animate-spin" />}
      {children}
    </button>
  )
}
