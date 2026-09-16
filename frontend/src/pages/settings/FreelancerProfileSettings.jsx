import { useEffect, useState } from 'react'
import { fetchSkills } from '../../api/auth'
import { completeProfile } from '../../api/profile'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Label from '../../components/Label'
import PortfolioManager from '../../components/PortfolioManager'

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
      <h1 className="text-page-title text-primary mb-6">Profile & Portfolio</h1>
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
            <label className="block">
              <Label>Profile photo</Label>
              <input type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files[0])} />
            </label>
            <div>
              <Label>Skills</Label>
              <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto border border-border rounded-lg p-4">
                {allSkills.map((skill) => (
                  <button
                    type="button"
                    key={skill.id}
                    onClick={() => toggleSkill(skill.id)}
                    className={`text-caption font-medium px-3 py-1.5 rounded-full border transition-colors ${
                      selectedSkills.includes(skill.id)
                        ? 'bg-primary text-white border-primary'
                        : 'bg-surface text-ink border-border hover:bg-bg'
                    }`}
                  >
                    {skill.name}
                  </button>
                ))}
              </div>
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
