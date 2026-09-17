import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchSkills } from '../../api/auth'
import { completeProfile } from '../../api/profile'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import ImageUpload from '../../components/ImageUpload'
import Label from '../../components/Label'
import PortfolioManager from '../../components/PortfolioManager'
import SkillPicker from '../../components/SkillPicker'

export default function FreelancerProfileSettings() {
  const { user, refreshUser } = useAuth()
  const profile = user.profile || {}
  const [allSkills, setAllSkills] = useState([])
  const [bio, setBio] = useState(profile.bio || '')
  const [photo, setPhoto] = useState(null)
  const [selectedSkills, setSelectedSkills] = useState((profile.skills || []).map((s) => s.id))
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    fetchSkills().then(setAllSkills).catch(() => setAllSkills([]))
  }, [])

  const toggleSkill = (id) =>
    setSelectedSkills((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setSubmitting(true)
    try {
      await completeProfile({ bio, profile_photo: photo, skills: selectedSkills })
      await refreshUser()
      setMessage('Profile updated.')
    } catch (err) {
      setError(err.response?.data?.bio?.[0] || 'Could not update profile.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-page-title text-primary">Profile & Portfolio</h1>
        <Link to={`/profile/${user.id}`} className="text-body text-primary font-medium">
          View public profile
        </Link>
      </div>
      <div className="space-y-6 max-w-xl">
        <Card variant="elevated">
          <h2 className="text-section-title text-ink mb-6">About You</h2>
          <form onSubmit={handleSubmit} className="space-y-6">
            <label className="block">
              <Label>Bio (max 300 characters)</Label>
              <textarea
                maxLength={300}
                rows={4}
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                className="w-full px-4 py-3 border border-border rounded-lg text-body text-ink focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </label>
            <ImageUpload label="Profile photo" currentUrl={profile.profile_photo} onChange={setPhoto} round />
            <div>
              <Label>Skills</Label>
              <SkillPicker skills={allSkills} selected={selectedSkills} onToggle={toggleSkill} />
            </div>
            <Alert type="success">{message}</Alert>
            <Alert type="error">{error}</Alert>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Saving…' : 'Save changes'}
            </Button>
          </form>
        </Card>

        <Card>
          <h2 className="text-section-title text-ink mb-6">Portfolio</h2>
          <PortfolioManager />
        </Card>
      </div>
    </div>
  )
}
