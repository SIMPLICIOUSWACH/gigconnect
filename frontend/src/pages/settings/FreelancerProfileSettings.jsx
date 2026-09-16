import { useEffect, useState } from 'react'
import { fetchSkills } from '../../api/auth'
import { completeProfile } from '../../api/profile'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
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
    <div className="space-y-6 max-w-md">
      <Card>
        <h2 className="text-lg font-semibold text-navy-900 mb-4">Profile & Portfolio</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="block text-sm font-medium text-navy-700 mb-1">Bio (max 300 characters)</span>
            <textarea
              maxLength={300}
              rows={4}
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-navy-500"
            />
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-navy-700 mb-1">Profile photo</span>
            <input type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files[0])} />
          </label>
          <div>
            <span className="block text-sm font-medium text-navy-700 mb-2">Skills</span>
            <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto border border-navy-100 rounded-lg p-3">
              {allSkills.map((skill) => (
                <button
                  type="button"
                  key={skill.id}
                  onClick={() => toggleSkill(skill.id)}
                  className={`text-xs px-3 py-1.5 rounded-full border ${
                    selectedSkills.includes(skill.id)
                      ? 'bg-navy-600 text-white border-navy-600'
                      : 'bg-white text-navy-600 border-navy-200'
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
        <h2 className="text-lg font-semibold text-navy-900 mb-4">Portfolio</h2>
        <PortfolioManager />
      </Card>
    </div>
  )
}
