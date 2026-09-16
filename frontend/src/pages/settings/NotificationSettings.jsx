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

  return (
    <div>
      <h1 className="text-page-title text-primary mb-6">Notification Preferences</h1>
      <Card variant="elevated" className="max-w-xl">
        <Alert type="error">{error}</Alert>
        {!prefs ? (
          <p className="text-body text-muted">Loading…</p>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-left text-label text-muted">
                <th className="py-2 font-medium">Event</th>
                <th className="py-2 font-medium text-center">Email</th>
                <th className="py-2 font-medium text-center">In-app</th>
              </tr>
            </thead>
            <tbody>
              {EVENTS.map(({ key, label }) => (
                <tr key={key} className="border-t border-border">
                  <td className="py-4 text-body text-ink">{label}</td>
                  <td className="py-4 text-center">
                    <input
                      type="checkbox"
                      className="w-4 h-4 accent-primary"
                      checked={prefs[`${key}_email`]}
                      onChange={() => toggle(`${key}_email`)}
                    />
                  </td>
                  <td className="py-4 text-center">
                    <input
                      type="checkbox"
                      className="w-4 h-4 accent-primary"
                      checked={prefs[`${key}_inapp`]}
                      onChange={() => toggle(`${key}_inapp`)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
