const STYLES = {
  error: 'bg-red-50 text-red-700 border-red-200',
  success: 'bg-green-50 text-green-700 border-green-200',
  info: 'bg-amber-50 text-amber-800 border-amber-200',
}

export default function Alert({ type = 'info', children }) {
  if (!children) return null
  return <div className={`text-sm border rounded-lg px-3 py-2 ${STYLES[type]}`}>{children}</div>
}
