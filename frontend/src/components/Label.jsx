export default function Label({ children, required, className = '' }) {
  if (!children) return null
  return (
    <span className={`block text-label text-ink mb-1.5 ${className}`}>
      {children}
      {required && <span className="text-red-500"> *</span>}
    </span>
  )
}
