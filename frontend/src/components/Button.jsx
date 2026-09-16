const VARIANTS = {
  primary: 'bg-navy-600 text-white hover:bg-navy-700 disabled:bg-navy-300',
  secondary: 'bg-white text-navy-700 border border-navy-200 hover:bg-navy-50',
  danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300',
}

export default function Button({ variant = 'primary', className = '', children, ...props }) {
  return (
    <button
      className={`px-4 py-2 rounded-lg font-medium text-sm transition-colors disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
