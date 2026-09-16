import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { changePassword, listSessions, logoutAllSessions, revokeSession } from '../../api/settings'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Input from '../../components/Input'

function ChangePasswordForm() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await changePassword(currentPassword, newPassword)
      setMessage('Password changed. You have been logged out of all sessions — please log in again.')
      setTimeout(() => {
        logout()
        navigate('/login')
      }, 2000)
    } catch (err) {
      const data = err.response?.data
      setError(data ? Object.values(data).flat().join(' ') : 'Could not change password.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        label="Current password"
        type="password"
        required
        value={currentPassword}
        onChange={(e) => setCurrentPassword(e.target.value)}
      />
      <Input
        label="New password"
        type="password"
        required
        value={newPassword}
        onChange={(e) => setNewPassword(e.target.value)}
      />
      <Alert type="success">{message}</Alert>
      <Alert type="error">{error}</Alert>
      <Button type="submit" disabled={submitting}>
        {submitting ? 'Changing…' : 'Change password'}
      </Button>
    </form>
  )
}

function SessionList() {
  const [sessions, setSessions] = useState([])
  const [error, setError] = useState('')

  const load = () => listSessions().then(setSessions).catch(() => setError('Could not load sessions.'))

  useEffect(() => {
    load()
  }, [])

  const handleRevoke = async (id) => {
    await revokeSession(id)
    load()
  }

  const handleLogoutAll = async () => {
    await logoutAllSessions()
    load()
  }

  return (
    <div className="space-y-3">
      <Alert type="error">{error}</Alert>
      <ul className="space-y-2">
        {sessions.map((session) => (
          <li
            key={session.id}
            className="flex items-center justify-between text-sm border border-navy-100 rounded-lg px-3 py-2"
          >
            <span className="text-navy-600 truncate max-w-xs">{session.user_agent || 'Unknown device'}</span>
            <button onClick={() => handleRevoke(session.id)} className="text-red-600 text-xs font-medium">
              Revoke
            </button>
          </li>
        ))}
        {sessions.length === 0 && <p className="text-sm text-navy-400">No active sessions.</p>}
      </ul>
      <Button variant="danger" onClick={handleLogoutAll}>
        Log out of all devices
      </Button>
    </div>
  )
}

export default function SecuritySettings() {
  return (
    <div className="space-y-6 max-w-md">
      <Card>
        <h2 className="text-lg font-semibold text-navy-900 mb-4">Change Password</h2>
        <ChangePasswordForm />
      </Card>
      <Card>
        <h2 className="text-lg font-semibold text-navy-900 mb-4">Active Sessions</h2>
        <SessionList />
      </Card>
    </div>
  )
}
