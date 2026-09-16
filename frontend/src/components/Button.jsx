const VARIANTS = {
  primary: 'bg-primary text-white hover:bg-primary-hover disabled:bg-primary/40',
  secondary: 'bg-surface text-primary border border-border hover:bg-primary-light disabled:opacity-50',
  danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300',
}

export default function Button({ variant = 'primary', className = '', children, ...props }) {
  return (
    <button
      className={`px-5 py-3 rounded-lg text-[15px] font-medium leading-none transition-colors duration-150 disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
