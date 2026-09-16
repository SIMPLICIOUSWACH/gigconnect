import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { deleteAccount, exportData } from '../../api/settings'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Input from '../../components/Input'

export default function PrivacySettings() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState('')

  const handleExport = async () => {
    const data = await exportData()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'gigconnect-data.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDelete = async () => {
    setError('')
    try {
      await deleteAccount(password)
      logout()
      navigate('/login')
    } catch (err) {
      setError(err.response?.data?.password || 'Could not delete account.')
    }
  }

  return (
    <div className="space-y-6 max-w-md">
      <Card>
        <h2 className="text-lg font-semibold text-navy-900 mb-2">Download My Data</h2>
        <p className="text-sm text-navy-500 mb-4">Get a JSON export of your profile and notification settings.</p>
        <Button variant="secondary" onClick={handleExport}>
          Download JSON
        </Button>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-navy-900 mb-2">Delete Account</h2>
        <p className="text-sm text-navy-500 mb-4">
          Your account will be deactivated and your personal details anonymized. This cannot be undone.
        </p>
        {!confirming ? (
          <Button variant="danger" onClick={() => setConfirming(true)}>
            Delete my account
          </Button>
        ) : (
          <div className="space-y-3">
            <Input
              label="Confirm your password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Alert type="error">{error}</Alert>
            <div className="flex gap-2">
              <Button variant="danger" onClick={handleDelete}>
                Confirm delete
              </Button>
              <Button variant="secondary" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
