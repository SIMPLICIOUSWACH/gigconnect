export default function Select({ label, error, options, className = '', ...props }) {
  return (
    <label className="block">
      {label && <span className="block text-sm font-medium text-navy-700 mb-1">{label}</span>}
      <select
        className={`w-full px-3 py-2 border rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy-500 ${
          error ? 'border-red-400' : 'border-navy-200'
        } ${className}`}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && <span className="block text-xs text-red-600 mt-1">{error}</span>}
    </label>
  )
}
