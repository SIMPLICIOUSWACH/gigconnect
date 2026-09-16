import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { fetchSkills, register } from '../api/auth'
import { INDUSTRIES as INDUSTRY_OPTIONS } from '../constants'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card from '../components/Card'
import Input from '../components/Input'
import Label from '../components/Label'
import Select from '../components/Select'

const INDUSTRIES = [{ value: '', label: 'Select industry (optional)' }, ...INDUSTRY_OPTIONS]

export default function Register() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialRole = searchParams.get('role') === 'client' ? 'client' : 'freelancer'
  const [skills, setSkills] = useState([])
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    confirm_password: '',
    phone: '',
    role: initialRole,
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
    <div className="min-h-screen bg-bg flex items-center justify-center px-4 py-10">
      <Card variant="elevated" className="w-full max-w-lg">
        <h1 className="text-page-title text-primary">Join GigConnect</h1>
        <p className="text-body text-muted mt-1 mb-8">Kenya's gig marketplace for clients and freelancers.</p>

        <div className="flex gap-2 mb-8">
          {['freelancer', 'client'].map((role) => (
            <button
              key={role}
              type="button"
              onClick={() => setForm((f) => ({ ...f, role }))}
              className={`flex-1 py-3 rounded-lg text-nav border transition-colors duration-150 ${
                form.role === role
                  ? 'bg-primary text-white border-primary'
                  : 'bg-surface text-ink border-border hover:bg-bg'
              }`}
            >
              {role === 'freelancer' ? "I'm a Freelancer" : "I'm a Client"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
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
              <Label required>Skills (select at least one)</Label>
              <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto border border-border rounded-lg p-4">
                {skills.map((skill) => (
                  <button
                    type="button"
                    key={skill.id}
                    onClick={() => toggleSkill(skill.id)}
                    className={`text-caption font-medium px-3 py-1.5 rounded-full border transition-colors ${
                      form.skills.includes(skill.id)
                        ? 'bg-primary text-white border-primary'
                        : 'bg-surface text-ink border-border hover:bg-bg'
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

        <p className="text-body text-muted mt-6 text-center">
          Already have an account?{' '}
          <Link to="/login" className="text-primary font-medium">
            Log in
          </Link>
        </p>
      </Card>
    </div>
  )
}
