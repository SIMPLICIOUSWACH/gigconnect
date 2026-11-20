import Label from './Label'

export default function Input({ label, required, error, hint, className = '', ...props }) {
  return (
    <label className="block">
      <Label required={required}>{label}</Label>
      <input
        required={required}
        className={`w-full h-12 px-3.5 border rounded-input text-body text-ink bg-surface placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors ${
          error ? 'border-red-400' : 'border-border'
        } ${className}`}
        {...props}
      />
      {hint && <span className="block text-caption text-muted mt-1.5">{hint}</span>}
      {error && <span className="block text-caption text-red-600 mt-1.5">{error}</span>}
    </label>
  )
}
