import { useState } from 'react'
import { completeProfile } from '../../api/profile'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Input from '../../components/Input'
import Label from '../../components/Label'
import Select from '../../components/Select'

const INDUSTRIES = [
  { value: '', label: 'Select industry' },
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

export default function CompanyProfileSettings() {
  const { user, refreshUser } = useAuth()
  const profile = user.profile || {}
  const [companyName, setCompanyName] = useState(profile.company_name || '')
  const [industry, setIndustry] = useState(profile.industry || '')
  const [logo, setLogo] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setSubmitting(true)
    try {
      await completeProfile({ company_name: companyName, industry, company_logo: logo })
      await refreshUser()
      setMessage('Company profile updated.')
    } catch {
      setError('Could not update company profile.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <h1 className="text-page-title text-primary mb-6">Company Profile</h1>
      <Card variant="elevated" className="max-w-xl">
        <form onSubmit={handleSubmit} className="space-y-6">
          <Input label="Company name" value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
          <Select label="Industry" options={INDUSTRIES} value={industry} onChange={(e) => setIndustry(e.target.value)} />
          <label className="block">
            <Label>Company logo</Label>
            <input type="file" accept="image/*" onChange={(e) => setLogo(e.target.files[0])} />
          </label>
          <Alert type="success">{message}</Alert>
          <Alert type="error">{error}</Alert>
          <Button type="submit" disabled={submitting}>
            {submitting ? 'Saving…' : 'Save changes'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
