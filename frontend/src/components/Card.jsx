const VARIANTS = {
  default: 'shadow-hairline',
  elevated: 'shadow-raised',
}

export default function Card({ className = '', variant = 'default', children }) {
  return <div className={`bg-surface rounded-card p-6 ${VARIANTS[variant]} ${className}`}>{children}</div>
}
