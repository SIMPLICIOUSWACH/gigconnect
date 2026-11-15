import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { updateFreelancerProfile } from '../../api/profile'
import { deleteAccount, exportData } from '../../api/settings'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Input from '../../components/Input'
import ChatPrivacyNotice from '../../components/messages/ChatPrivacyNotice'
import IdPrivacyNotice from '../../components/verification/IdPrivacyNotice'

export default function PrivacySettings() {
  const { logout, user, refreshUser } = useAuth()
  // "Show my profile in Find freelancers", for freelancers. Saved as soon as it is switched.
  const [visible, setVisible] = useState(user?.profile?.search_visible ?? true)
  const [visibleError, setVisibleError] = useState('')

  const toggleVisible = async () => {
    const next = !visible
    setVisible(next)
    setVisibleError('')
    try {
      await updateFreelancerProfile({ search_visible: next })
      await refreshUser?.()
    } catch {
      setVisible(!next)
      setVisibleError('Could not save this. Try again.')
    }
  }
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState('')
  // In-progress work that stops the deletion, as the server listed it.
  const [activeWork, setActiveWork] = useState([])

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
    setActiveWork([])
    try {
      await deleteAccount(password)
      logout()
      navigate('/login')
    } catch (err) {
      const data = err.response?.data
      if (data?.code === 'active_work') {
        setActiveWork(data.active_work)
        setError(data.detail)
      } else {
        setError(data?.password || 'Could not delete account.')
      }
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

        {user?.role === 'freelancer' && (
          <Card>
            <h2 className="text-section-title text-ink mb-2">Find freelancers</h2>
            <div className="flex justify-between items-center gap-4">
              <span className="flex flex-col gap-0.5">
                <span id="search-visible-label" className="text-[15px] font-semibold text-ink">
                  Show my profile in Find freelancers
                </span>
                <span className="text-body text-muted">
                  Clients can find you by your name, skills and what you do, and invite you to apply. Your email,
                  phone and ID are never shown. Turn this off and your profile only opens from a link or from your
                  own applications.
                </span>
              </span>
              <button
                type="button"
                role="switch"
                aria-checked={visible}
                aria-labelledby="search-visible-label"
                onClick={toggleVisible}
                className={`shrink-0 w-[52px] h-[30px] rounded-pill p-[3px] flex ${
                  visible ? 'justify-end bg-primary' : 'justify-start bg-toggle-off'
                }`}
              >
                <span className="w-6 h-6 rounded-full bg-white shadow-knob" />
              </button>
            </div>
            {visibleError && (
              <p role="alert" className="text-caption text-coral-ink mt-2">
                {visibleError}
              </p>
            )}
          </Card>
        )}

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
            Your ID images, selfie and ID number are deleted too. Any open gigs you posted are closed, and freelancers
            waiting on them are told. Your chats stay with the other person, who sees you as &quot;Deleted user&quot;.
            This cannot be undone. You can&apos;t delete your account while a gig you run or were hired on is in
            progress. An administrator can also delete a suspended account in the same way; you would be emailed the
            reason.
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
              {activeWork.length > 0 && (
                <ul aria-label="Work in progress" className="space-y-1 text-body text-ink">
                  {activeWork.map((item) => (
                    <li key={item.gig_id}>
                      <Link to={`/gigs/${item.gig_id}`} className="text-primary font-semibold hover:underline">
                        {item.title}
                      </Link>
                      <span className="text-muted">
                        {' '}
                        · {item.as === 'client' ? 'your gig' : 'you were hired'}
                        {item.other_party && ` · with ${item.other_party}`}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
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
