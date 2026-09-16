export default function Card({ className = '', children }) {
  return (
    <div className={`bg-white rounded-xl border border-navy-100 shadow-sm p-6 ${className}`}>
      {children}
    </div>
  )
}
