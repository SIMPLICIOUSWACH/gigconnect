import { useState } from 'react'
import { updateAccount } from '../../api/settings'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Input from '../../components/Input'

export default function AccountSettings() {
  const { user, refreshUser } = useAuth()
  const [form, setForm] = useState({ full_name: user.full_name, email: user.email, phone: user.phone })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setSubmitting(true)
    try {
      await updateAccount(form)
      await refreshUser()
      setMessage('Account updated.')
    } catch (err) {
      const data = err.response?.data
      setError(data ? Object.values(data).flat().join(' ') : 'Could not update account.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card className="max-w-md">
      <h2 className="text-lg font-semibold text-navy-900 mb-4">Account Settings</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Full name"
          value={form.full_name}
          onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
        />
        <Input
          label="Email"
          type="email"
          value={form.email}
          onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
        />
        <Input
          label="Phone"
          value={form.phone}
          onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
        />
        <p className="text-xs text-navy-400">
          Changing your email or phone will require re-verification.
        </p>
        <Alert type="success">{message}</Alert>
        <Alert type="error">{error}</Alert>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : 'Save changes'}
        </Button>
      </form>
    </Card>
  )
}
