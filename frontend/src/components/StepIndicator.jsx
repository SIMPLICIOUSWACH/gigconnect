export default function StepIndicator({ steps, current }) {
  return (
    <div className="flex items-center mb-8">
      {steps.map((label, i) => {
        const step = i + 1
        const isActive = step === current
        const isDone = step < current
        return (
          <div key={label} className={`flex items-center ${step < steps.length ? 'flex-1' : ''}`}>
            <div className="flex items-center gap-2 shrink-0">
              <span
                className={`w-8 h-8 rounded-full flex items-center justify-center text-label font-semibold ${
                  isActive || isDone ? 'bg-primary text-white' : 'bg-bg text-muted border border-border'
                }`}
              >
                {step}
              </span>
              <span className={`text-nav ${isActive ? 'text-ink' : 'text-muted'}`}>{label}</span>
            </div>
            {step < steps.length && <div className={`flex-1 h-px mx-4 ${isDone ? 'bg-primary' : 'bg-border'}`} />}
          </div>
        )
      })}
    </div>
  )
}
