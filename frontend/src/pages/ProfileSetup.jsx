import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { completeProfile, createPortfolioItem } from '../api/profile'
import { useAuth } from '../context/AuthContext'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card from '../components/Card'
import Input from '../components/Input'
import Label from '../components/Label'

function FreelancerWizard({ onDone }) {
  const [step, setStep] = useState(1)
  const [bio, setBio] = useState('')
  const [photo, setPhoto] = useState(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [portfolio, setPortfolio] = useState({ title: '', description: '', link: '' })
  const [items, setItems] = useState([])

  const saveBio = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await completeProfile({ bio, profile_photo: photo })
      setStep(2)
    } catch (err) {
      setError(err.response?.data?.bio?.[0] || 'Could not save profile.')
    } finally {
      setSubmitting(false)
    }
  }

  const addPortfolioItem = async () => {
    if (!portfolio.title) return
    try {
      const created = await createPortfolioItem(portfolio)
      setItems((prev) => [...prev, created])
      setPortfolio({ title: '', description: '', link: '' })
    } catch {
      setError('Could not add portfolio item.')
    }
  }

  if (step === 1) {
    return (
      <form onSubmit={saveBio} className="space-y-6">
        <label className="block">
          <Label required>Bio (max 300 characters)</Label>
          <textarea
            required
            maxLength={300}
            rows={4}
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            className="w-full px-4 py-3 border border-border rounded-lg text-body text-ink focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </label>
        <label className="block">
          <Label>Profile photo (optional)</Label>
          <input type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files[0])} />
        </label>
        <Alert type="error">{error}</Alert>
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? 'Saving…' : 'Continue'}
        </Button>
      </form>
    )
  }

  return (
    <div className="space-y-6">
      <p className="text-body text-muted">Add a few portfolio pieces (optional). Up to 6 will show on your public profile.</p>
      <div className="space-y-4">
        <Input
          label="Title"
          value={portfolio.title}
          onChange={(e) => setPortfolio((p) => ({ ...p, title: e.target.value }))}
        />
        <Input
          label="Link (optional)"
          value={portfolio.link}
          onChange={(e) => setPortfolio((p) => ({ ...p, link: e.target.value }))}
        />
        <Button type="button" variant="secondary" onClick={addPortfolioItem}>
          Add item
        </Button>
      </div>

      {items.length > 0 && (
        <ul className="text-body text-ink list-disc list-inside">
          {items.map((item) => (
            <li key={item.id}>{item.title}</li>
          ))}
        </ul>
      )}

      <Alert type="error">{error}</Alert>
      <Button className="w-full" onClick={onDone}>
        Finish
      </Button>
    </div>
  )
}

function ClientForm({ onDone }) {
  const [logo, setLogo] = useState(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await completeProfile({ company_logo: logo })
      onDone()
    } catch {
      setError('Could not save profile.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <label className="block">
        <Label>Company logo (optional)</Label>
        <input type="file" accept="image/*" onChange={(e) => setLogo(e.target.files[0])} />
      </label>
      <Alert type="error">{error}</Alert>
      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? 'Saving…' : 'Finish'}
      </Button>
    </form>
  )
}

export default function ProfileSetup() {
  const { user, refreshUser } = useAuth()
  const navigate = useNavigate()

  const handleDone = async () => {
    await refreshUser()
    navigate('/dashboard')
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4 py-10">
      <Card variant="elevated" className="w-full max-w-md">
        <h1 className="text-page-title text-primary mb-1">Set up your profile</h1>
        <p className="text-body text-muted mb-8">
          {user?.role === 'freelancer'
            ? 'Tell clients a bit about yourself.'
            : 'Add your company details.'}
        </p>
        {user?.role === 'freelancer' ? <FreelancerWizard onDone={handleDone} /> : <ClientForm onDone={handleDone} />}
      </Card>
    </div>
  )
}
