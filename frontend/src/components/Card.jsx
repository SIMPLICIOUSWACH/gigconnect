const VARIANTS = {
  default: 'border border-border',
  elevated: 'border border-border shadow-[0_1px_3px_rgba(26,31,43,0.08),0_1px_2px_rgba(26,31,43,0.04)]',
}

export default function Card({ className = '', variant = 'default', children }) {
  return <div className={`bg-surface rounded-xl p-8 ${VARIANTS[variant]} ${className}`}>{children}</div>
}
