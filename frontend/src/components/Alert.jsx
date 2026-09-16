const STYLES = {
  error: 'bg-red-50 text-red-700 border-red-200',
  success: 'bg-accent-light text-accent border-accent/20',
  info: 'bg-amber-50 text-amber-800 border-amber-200',
}

export default function Alert({ type = 'info', children }) {
  if (!children) return null
  return <div className={`text-[15px] leading-6 border rounded-lg px-4 py-3 ${STYLES[type]}`}>{children}</div>
}
