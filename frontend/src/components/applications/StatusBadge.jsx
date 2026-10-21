import { STATUS_INFO } from '../../utils/applicationStatus'

export default function StatusBadge({ status }) {
  const info = STATUS_INFO[status]
  return (
    <span
      className={`text-caption font-medium px-2.5 py-1 rounded-full shrink-0 ${info?.className ?? 'bg-bg text-muted'}`}
    >
      {info?.label ?? status}
    </span>
  )
}
