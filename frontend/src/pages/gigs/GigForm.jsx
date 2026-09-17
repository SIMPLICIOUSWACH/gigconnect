import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { fetchSkills } from '../../api/auth'
import { createGig, fetchCategories, fetchGig, updateGig } from '../../api/gigs'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Input from '../../components/Input'
import Label from '../../components/Label'
import Select from '../../components/Select'
import SkillPicker from '../../components/SkillPicker'
import StepIndicator from '../../components/StepIndicator'

const STEPS = ['Basic Info', 'Skills', 'Budget & Deadline']

const EMPTY_FORM = {
  title: '',
  description: '',
  category: '',
  skills: [],
  budget_min: '',
  budget_max: '',
  deadline: '',
}

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

export default function GigForm() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const navigate = useNavigate()

  const [step, setStep] = useState(1)
  const [categories, setCategories] = useState([])
  const [skills, setSkills] = useState([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [loading, setLoading] = useState(isEdit)

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => setCategories([]))
    fetchSkills().then(setSkills).catch(() => setSkills([]))
  }, [])

  useEffect(() => {
    if (!isEdit) return
    fetchGig(id)
      .then((gig) => {
        setForm({
          title: gig.title,
          description: gig.description,
          category: gig.category.id,
          skills: gig.skills.map((s) => s.id),
          budget_min: gig.budget_min,
          budget_max: gig.budget_max,
          deadline: gig.deadline,
        })
      })
      .catch(() => setLoadError('Could not load this gig for editing.'))
      .finally(() => setLoading(false))
  }, [id, isEdit])

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const toggleSkill = (skillId) =>
    setForm((f) => ({
      ...f,
      skills: f.skills.includes(skillId) ? f.skills.filter((s) => s !== skillId) : [...f.skills, skillId],
    }))

  const validateStep = (targetStep) => {
    const stepErrors = {}
    if (targetStep === 1) {
      if (!form.title) stepErrors.title = 'Title is required.'
      if (!form.description) stepErrors.description = 'Description is required.'
      if (!form.category) stepErrors.category = 'Category is required.'
    }
    if (targetStep === 2) {
      if (form.skills.length === 0) stepErrors.skills = 'Select at least one required skill.'
    }
    if (targetStep === 3) {
      if (!form.budget_min) stepErrors.budget_min = 'Minimum budget is required.'
      if (!form.budget_max) stepErrors.budget_max = 'Maximum budget is required.'
      if (form.budget_min && form.budget_max && Number(form.budget_max) < Number(form.budget_min)) {
        stepErrors.budget_max = 'Max budget must be greater than or equal to min budget.'
      }
      if (!form.deadline) {
        stepErrors.deadline = 'Deadline is required.'
      } else if (form.deadline <= todayISO()) {
        stepErrors.deadline = 'Deadline must be in the future.'
      }
    }
    setErrors(stepErrors)
    return Object.keys(stepErrors).length === 0
  }

  const goNext = () => {
    if (validateStep(step)) setStep((s) => s + 1)
  }
  const goBack = () => setStep((s) => s - 1)

  const handleSubmit = async () => {
    if (!validateStep(3)) return
    setSubmitting(true)
    setErrors({})
    const payload = {
      title: form.title,
      description: form.description,
      category: form.category,
      skills: form.skills,
      budget_min: form.budget_min,
      budget_max: form.budget_max,
      deadline: form.deadline,
    }
    try {
      const gig = isEdit ? await updateGig(id, payload) : await createGig(payload)
      navigate(`/gigs/${gig.id}`)
    } catch (err) {
      const data = err.response?.data
      const message = data && typeof data === 'object' ? Object.values(data).flat().join(' ') : null
      setErrors({ submit: message || 'Could not save this gig. Please try again.' })
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <p className="text-body text-muted">Loading…</p>

  return (
    <div className="max-w-xl">
      <h1 className="text-page-title text-primary mb-8">{isEdit ? 'Edit Gig' : 'Post a Gig'}</h1>
      <StepIndicator steps={STEPS} current={step} />

      <Card variant="elevated">
        {loadError && (
          <div className="mb-6">
            <Alert type="error">{loadError}</Alert>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-6">
            <Input label="Title" required value={form.title} onChange={update('title')} error={errors.title} />
            <label className="block">
              <Label required>Description</Label>
              <textarea
                rows={5}
                value={form.description}
                onChange={update('description')}
                className="w-full px-4 py-3 border border-border rounded-lg text-body text-ink focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
              {errors.description && (
                <span className="block text-caption text-red-600 mt-1.5">{errors.description}</span>
              )}
            </label>
            <Select
              label="Category"
              required
              options={[
                { value: '', label: 'Select a category' },
                ...categories.map((c) => ({ value: c.id, label: c.name })),
              ]}
              value={form.category}
              onChange={update('category')}
              error={errors.category}
            />
          </div>
        )}

        {step === 2 && (
          <div>
            <Label required>Required skills (select at least one)</Label>
            <SkillPicker skills={skills} selected={form.skills} onToggle={toggleSkill} />
            {errors.skills && <p className="text-caption text-red-600 mt-2">{errors.skills}</p>}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Min budget (KES)"
                required
                type="number"
                min="0"
                value={form.budget_min}
                onChange={update('budget_min')}
                error={errors.budget_min}
              />
              <Input
                label="Max budget (KES)"
                required
                type="number"
                min="0"
                value={form.budget_max}
                onChange={update('budget_max')}
                error={errors.budget_max}
              />
            </div>
            <Input
              label="Deadline"
              required
              type="date"
              min={todayISO()}
              value={form.deadline}
              onChange={update('deadline')}
              error={errors.deadline}
            />
          </div>
        )}

        {errors.submit && (
          <div className="mt-6">
            <Alert type="error">{errors.submit}</Alert>
          </div>
        )}

        <div className="flex justify-between mt-8">
          {step > 1 ? (
            <Button type="button" variant="secondary" onClick={goBack}>
              Back
            </Button>
          ) : (
            <span />
          )}
          {step < 3 ? (
            <Button type="button" onClick={goNext}>
              Continue
            </Button>
          ) : (
            <Button type="button" onClick={handleSubmit} loading={submitting}>
              {submitting ? 'Saving…' : isEdit ? 'Save changes' : 'Post gig'}
            </Button>
          )}
        </div>
      </Card>
    </div>
  )
}
