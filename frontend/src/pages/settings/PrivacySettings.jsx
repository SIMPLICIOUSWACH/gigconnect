import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { deleteAccount, exportData } from '../../api/settings'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Input from '../../components/Input'
import ChatPrivacyNotice from '../../components/messages/ChatPrivacyNotice'
import IdPrivacyNotice from '../../components/verification/IdPrivacyNotice'

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
    <div>
      <h1 className="text-page-title text-primary mb-6">Privacy & Data</h1>
      <div className="space-y-6 max-w-xl">
        <Card>
          <h2 className="text-section-title text-ink mb-2">Download My Data</h2>
          <p className="text-body text-muted mb-6">Get a JSON export of your profile, notification settings, applications, notifications, the chat messages you sent, and the gigs you have viewed or opened from search results.</p>
          <Button variant="secondary" onClick={handleExport}>
            Download JSON
          </Button>
        </Card>

        <Card>
          <ChatPrivacyNotice />
        </Card>

        <Card>
          <IdPrivacyNotice />
        </Card>

        <Card>
          <h2 className="text-section-title text-ink mb-2">Delete Account</h2>
          <p className="text-body text-muted mb-6">
            Your account will be deactivated, your personal details anonymized, and your gig viewing history deleted.
            Your ID images, selfie and ID number are deleted too. Your chats stay with the other person, who sees you as
            &quot;Deleted user&quot;. This cannot be undone.
          </p>
          {!confirming ? (
            <Button variant="danger" onClick={() => setConfirming(true)}>
              Delete my account
            </Button>
          ) : (
            <div className="space-y-5">
              <Input
                label="Confirm your password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <Alert type="error">{error}</Alert>
              <div className="flex gap-3">
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
    </div>
  )
}
