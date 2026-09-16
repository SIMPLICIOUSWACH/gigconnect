import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fetchSkills, register } from '../api/auth'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card from '../components/Card'
import Input from '../components/Input'
import Select from '../components/Select'

const INDUSTRIES = [
  { value: '', label: 'Select industry (optional)' },
  { value: 'technology', label: 'Technology' },
  { value: 'retail', label: 'Retail' },
  { value: 'agriculture', label: 'Agriculture' },
  { value: 'construction', label: 'Construction' },
  { value: 'hospitality', label: 'Hospitality' },
  { value: 'finance', label: 'Finance' },
  { value: 'education', label: 'Education' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'other', label: 'Other' },
]

export default function Register() {
  const navigate = useNavigate()
  const [skills, setSkills] = useState([])
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    confirm_password: '',
    phone: '',
    role: 'freelancer',
    company_name: '',
    industry: '',
    skills: [],
  })

  useEffect(() => {
    fetchSkills().then(setSkills).catch(() => setSkills([]))
  }, [])

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const toggleSkill = (id) => {
    setForm((f) => ({
      ...f,
      skills: f.skills.includes(id) ? f.skills.filter((s) => s !== id) : [...f.skills, id],
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    const payload = {
      full_name: form.full_name,
      email: form.email,
      password: form.password,
      confirm_password: form.confirm_password,
      phone: form.phone,
      role: form.role,
    }
    if (form.role === 'client') {
      payload.company_name = form.company_name
      payload.industry = form.industry
    } else {
      payload.skills = form.skills
    }

    setSubmitting(true)
    try {
      await register(payload)
      navigate('/login', { state: { registered: true } })
    } catch (err) {
      const data = err.response?.data
      if (data && typeof data === 'object') {
        setError(Object.values(data).flat().join(' '))
      } else {
        setError('Registration failed. Please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-navy-50 flex items-center justify-center px-4 py-10">
      <Card className="w-full max-w-lg">
        <h1 className="text-2xl font-bold text-navy-900">Join GigConnect</h1>
        <p className="text-sm text-navy-500 mt-1 mb-6">Kenya's gig marketplace for clients and freelancers.</p>

        <div className="flex gap-2 mb-6">
          {['freelancer', 'client'].map((role) => (
            <button
              key={role}
              type="button"
              onClick={() => setForm((f) => ({ ...f, role }))}
              className={`flex-1 py-2 rounded-lg text-sm font-medium border ${
                form.role === role
                  ? 'bg-navy-600 text-white border-navy-600'
                  : 'bg-white text-navy-700 border-navy-200'
              }`}
            >
              {role === 'freelancer' ? "I'm a Freelancer" : "I'm a Client"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input label="Full name" required value={form.full_name} onChange={update('full_name')} />
          <Input label="Email" type="email" required value={form.email} onChange={update('email')} />
          <Input label="Phone" required placeholder="2547XXXXXXXX" value={form.phone} onChange={update('phone')} />
          <Input label="Password" type="password" required value={form.password} onChange={update('password')} />
          <Input
            label="Confirm password"
            type="password"
            required
            value={form.confirm_password}
            onChange={update('confirm_password')}
          />

          {form.role === 'client' ? (
            <>
              <Input
                label="Company name (optional)"
                value={form.company_name}
                onChange={update('company_name')}
              />
              <Select label="Industry (optional)" options={INDUSTRIES} value={form.industry} onChange={update('industry')} />
            </>
          ) : (
            <div>
              <span className="block text-sm font-medium text-navy-700 mb-2">
                Skills <span className="text-red-500">*</span> (select at least one)
              </span>
              <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto border border-navy-100 rounded-lg p-3">
                {skills.map((skill) => (
                  <button
                    type="button"
                    key={skill.id}
                    onClick={() => toggleSkill(skill.id)}
                    className={`text-xs px-3 py-1.5 rounded-full border ${
                      form.skills.includes(skill.id)
                        ? 'bg-navy-600 text-white border-navy-600'
                        : 'bg-white text-navy-600 border-navy-200'
                    }`}
                  >
                    {skill.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <Alert type="error">{error}</Alert>

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? 'Creating account…' : 'Create account'}
          </Button>
        </form>

        <p className="text-sm text-navy-500 mt-4 text-center">
          Already have an account?{' '}
          <Link to="/login" className="text-navy-700 font-medium">
            Log in
          </Link>
        </p>
      </Card>
    </div>
  )
}
