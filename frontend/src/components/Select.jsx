import Label from './Label'

export default function Select({ label, required, error, options, className = '', ...props }) {
  return (
    <label className="block">
      <Label required={required}>{label}</Label>
      <select
        required={required}
        className={`w-full px-4 py-3 border rounded-lg text-body text-ink bg-surface focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors ${
          error ? 'border-red-400' : 'border-border'
        } ${className}`}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && <span className="block text-caption text-red-600 mt-1.5">{error}</span>}
    </label>
  )
}
