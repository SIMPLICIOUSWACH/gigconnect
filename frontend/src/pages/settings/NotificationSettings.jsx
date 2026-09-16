import { useEffect, useState } from 'react'
import { fetchNotificationPreferences, updateNotificationPreferences } from '../../api/settings'
import Alert from '../../components/Alert'
import Card from '../../components/Card'

const EVENTS = [
  { key: 'new_application', label: 'New application received' },
  { key: 'status_change', label: 'Application status changes' },
  { key: 'new_match', label: 'New gig match' },
  { key: 'security_alert', label: 'Security alerts' },
]

export default function NotificationSettings() {
  const [prefs, setPrefs] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchNotificationPreferences().then(setPrefs).catch(() => setError('Could not load preferences.'))
  }, [])

  const toggle = async (field) => {
    const updated = { ...prefs, [field]: !prefs[field] }
    setPrefs(updated)
    try {
      await updateNotificationPreferences({ [field]: updated[field] })
    } catch {
      setError('Could not save preference.')
    }
  }

  if (!prefs) return <Alert type="error">{error}</Alert>

  return (
    <Card className="max-w-md">
      <h2 className="text-lg font-semibold text-navy-900 mb-4">Notification Preferences</h2>
      <Alert type="error">{error}</Alert>
      <table className="w-full text-sm mt-2">
        <thead>
          <tr className="text-left text-navy-400 text-xs uppercase">
            <th className="py-2">Event</th>
            <th className="py-2 text-center">Email</th>
            <th className="py-2 text-center">In-app</th>
          </tr>
        </thead>
        <tbody>
          {EVENTS.map(({ key, label }) => (
            <tr key={key} className="border-t border-navy-100">
              <td className="py-2 text-navy-700">{label}</td>
              <td className="py-2 text-center">
                <input
                  type="checkbox"
                  checked={prefs[`${key}_email`]}
                  onChange={() => toggle(`${key}_email`)}
                />
              </td>
              <td className="py-2 text-center">
                <input
                  type="checkbox"
                  checked={prefs[`${key}_inapp`]}
                  onChange={() => toggle(`${key}_inapp`)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
