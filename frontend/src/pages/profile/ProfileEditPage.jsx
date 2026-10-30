import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CircleCheck, X } from 'lucide-react'
import { createSkill, fetchSkills } from '../../api/auth'
import { completeProfile, updateFreelancerProfile } from '../../api/profile'
import { updateAccount } from '../../api/settings'
import { useAuth } from '../../context/AuthContext'
import useCounties from '../../hooks/useCounties'
import Alert from '../../components/Alert'
import ImageUpload from '../../components/ImageUpload'
import PortfolioManager from '../../components/PortfolioManager'
import ProfilePreviewCard from '../../components/profile/ProfilePreviewCard'
import { chipColour, PROFILE_COLOURS } from '../../utils/palette'
import {
  BIO_MAX,
  cleanPrice,
  draftFromUser,
  isDirty,
  profileStrength,
  withSkill,
} from './profileDraft'

export const SAVED_MESSAGE_MS = 3500

const fieldClass =
  'h-12 w-full border border-border rounded-input px-3.5 text-body text-ink bg-surface focus:outline focus:outline-2 focus:outline-primary focus:outline-offset-1 focus:border-primary'
const labelClass = 'flex flex-col gap-1.5 text-label text-ink'
const sectionClass = 'bg-surface rounded-card p-6 flex flex-col shadow-hairline'

function errorText(err, fallback) {
  const data = err?.response?.data
  if (!data || typeof data !== 'object') return fallback
  return Object.values(data).flat().join(' ') || fallback
}

export default function ProfileEditPage() {
  const { user, refreshUser } = useAuth()
  const counties = useCounties()
  const [saved, setSaved] = useState(() => draftFromUser(user))
  const [draft, setDraft] = useState(saved)
  const [photo, setPhoto] = useState(null)
  const [photoKey, setPhotoKey] = useState(0)
  const [portfolioItems, setPortfolioItems] = useState(user.profile?.portfolio_items || [])
  const [catalog, setCatalog] = useState([])
  const [newSkill, setNewSkill] = useState('')
  const [skillError, setSkillError] = useState('')
  const [addingSkill, setAddingSkill] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState(false)
  const toastTimer = useRef(null)

  useEffect(() => {
    fetchSkills().then(setCatalog).catch(() => setCatalog([]))
    return () => clearTimeout(toastTimer.current)
  }, [])

  const photoUrl = useMemo(() => (photo ? URL.createObjectURL(photo) : null), [photo])
  useEffect(() => () => photoUrl && URL.revokeObjectURL(photoUrl), [photoUrl])

  const dirty = isDirty(draft, saved) || photo !== null
  const strength = profileStrength(draft)

  // Any edit hides the "Profile saved" message, as in the mockup.
  const set = (key, value) => {
    setDraft((d) => ({ ...d, [key]: value }))
    setToast(false)
  }

  const addSkill = async () => {
    const name = newSkill.trim()
    setSkillError('')
    if (!name) return
    if (draft.skills.some((s) => s.name.toLowerCase() === name.toLowerCase())) {
      setNewSkill('')
      return
    }
    const known = catalog.find((s) => s.name.toLowerCase() === name.toLowerCase())
    if (known) {
      set('skills', withSkill(draft.skills, known))
      setNewSkill('')
      return
    }
    // Not in the list: the server adds it, or returns the existing skill it is another name for.
    setAddingSkill(true)
    try {
      const skill = await createSkill(name)
      setCatalog((c) => (c.some((s) => s.id === skill.id) ? c : [...c, skill]))
      setDraft((d) => ({ ...d, skills: withSkill(d.skills, skill) }))
      setToast(false)
      setNewSkill('')
    } catch (err) {
      setSkillError(
        err.response?.status === 429
          ? 'You are adding skills too quickly. Try again later.'
          : err.response?.data?.name?.[0] || 'Could not add this skill. Please try again.'
      )
    } finally {
      setAddingSkill(false)
    }
  }

  const removeSkill = (skill) => set('skills', draft.skills.filter((s) => s.id !== skill.id))

  const discard = () => {
    setDraft(saved)
    setPhoto(null)
    setPhotoKey((k) => k + 1)
    setToast(false)
    setError('')
  }

  const save = async (e) => {
    e.preventDefault()
    if (!dirty || saving) return
    setSaving(true)
    setError('')
    const next = { ...draft, name: draft.name.trim(), headline: draft.headline.trim() }
    try {
      if (next.name !== saved.name) await updateAccount({ full_name: next.name })
      await updateFreelancerProfile({
        headline: next.headline,
        county: next.county,
        bio: next.bio,
        starting_price: next.price ? Number(next.price) : null,
        is_available: next.available,
        profile_colour: next.colour,
        skills: next.skills.map((s) => s.id),
      })
      if (photo) await completeProfile({ profile_photo: photo })
      await refreshUser()
      setSaved(next)
      setDraft(next)
      setPhoto(null)
      setPhotoKey((k) => k + 1)
      setToast(true)
      clearTimeout(toastTimer.current)
      toastTimer.current = setTimeout(() => setToast(false), SAVED_MESSAGE_MS)
    } catch (err) {
      setError(errorText(err, 'Could not save your profile. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  const profile = user.profile || {}
  const preview = {
    ...draft,
    photoUrl: photoUrl || profile.profile_photo,
    verified: profile.verified,
    gigsCompleted: profile.gigs_completed,
    memberSince: profile.member_since,
    portfolioItems,
  }

  return (
    <div className="flex flex-col gap-5 pt-2">
      <div className="flex flex-wrap justify-between items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-hero">Edit your profile</h1>
          <p className="text-body text-ink-soft">Changes show in the preview as you type. Save when you&apos;re happy.</p>
        </div>
        {toast && (
          <div
            role="status"
            className="flex items-center gap-2.5 bg-accent-light text-accent px-4 py-3 rounded-button text-[15px] font-semibold"
          >
            <CircleCheck size={20} className="text-white fill-accent-dot" aria-hidden="true" />
            Profile saved. Clients now see this version.
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-7 items-start">
        <div className="flex-[999_1_520px] min-w-0 flex flex-col gap-[18px]">
          <form onSubmit={save} className="flex flex-col gap-[18px]" aria-label="Edit your profile">
            <section aria-labelledby="basics-heading" className={`${sectionClass} gap-[18px]`}>
              <h2 id="basics-heading" className="text-section-title">
                The basics
              </h2>
              <fieldset className="flex flex-col gap-2.5">
                <legend className="text-label mb-2.5">Profile colour</legend>
                <div className="flex flex-wrap gap-2.5">
                  {Object.entries(PROFILE_COLOURS).map(([key, c]) => (
                    <button
                      key={key}
                      type="button"
                      aria-label={`${c.label} profile colour`}
                      aria-pressed={draft.colour === key}
                      onClick={() => set('colour', key)}
                      className={`w-11 h-11 rounded-full border-[3px] border-white ${c.solid} ${
                        draft.colour === key ? 'shadow-ring-ink' : 'shadow-ring-border'
                      }`}
                    />
                  ))}
                </div>
              </fieldset>
              <div className="grid gap-3.5 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
                <label className={labelClass}>
                  Full name
                  <input type="text" value={draft.name} onChange={(e) => set('name', e.target.value)} className={fieldClass} />
                </label>
                <label className={labelClass}>
                  County
                  <select value={draft.county} onChange={(e) => set('county', e.target.value)} className={fieldClass}>
                    <option value="">Prefer not to say</option>
                    {counties.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className={labelClass}>
                Headline
                <input
                  type="text"
                  maxLength={120}
                  value={draft.headline}
                  onChange={(e) => set('headline', e.target.value)}
                  placeholder="e.g. Social media manager for small businesses"
                  className={fieldClass}
                />
                <span className="text-caption text-muted font-normal">One line clients see under your name.</span>
              </label>
              <ImageUpload key={photoKey} label="Profile photo" currentUrl={profile.profile_photo} onChange={setPhoto} round />
            </section>

            <section aria-labelledby="about-heading" className={`${sectionClass} gap-3`}>
              <h2 id="about-heading" className="text-section-title">
                About you
              </h2>
              <label className={labelClass}>
                Bio
                <textarea
                  rows={5}
                  maxLength={BIO_MAX}
                  value={draft.bio}
                  onChange={(e) => set('bio', e.target.value)}
                  className="border border-border rounded-input px-3.5 py-3 text-body leading-[1.5] text-ink bg-surface resize-y focus:outline focus:outline-2 focus:outline-primary focus:outline-offset-1 focus:border-primary"
                />
                <span className="flex justify-between gap-3 text-caption font-normal text-muted">
                  <span>What you do, who you have worked with, how you work.</span>
                  <span className="tabular-nums">
                    {draft.bio.length} / {BIO_MAX}
                  </span>
                </span>
              </label>
            </section>

            <section aria-labelledby="skills-heading" className={`${sectionClass} gap-3.5`}>
              <div className="flex justify-between items-baseline gap-2 flex-wrap">
                <h2 id="skills-heading" className="text-section-title">
                  Skills
                </h2>
                <span className="text-caption text-muted">These drive your gig recommendations</span>
              </div>
              {draft.skills.length > 0 ? (
                <ul className="flex flex-wrap gap-2" aria-label="Your skills">
                  {draft.skills.map((skill, i) => (
                    <li
                      key={skill.id}
                      className={`inline-flex items-center gap-0.5 text-[14px] font-semibold rounded-pill py-0.5 pr-1 pl-3.5 ${chipColour(i)}`}
                    >
                      {skill.name}
                      <button
                        type="button"
                        onClick={() => removeSkill(skill)}
                        aria-label={`Remove ${skill.name}`}
                        className="w-8 h-8 flex items-center justify-center"
                      >
                        <X size={14} strokeWidth={2.4} aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-caption text-muted">No skills yet. Add the things you are good at.</p>
              )}
              <div className="flex flex-wrap gap-2">
                <label className={`flex-[1_1_240px] ${labelClass}`}>
                  Add a skill
                  <input
                    type="text"
                    list="skill-options"
                    value={newSkill}
                    onChange={(e) => {
                      setNewSkill(e.target.value)
                      setSkillError('')
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addSkill()
                      }
                    }}
                    placeholder="e.g. Copywriting"
                    className={fieldClass}
                  />
                  <datalist id="skill-options">
                    {catalog.map((s) => (
                      <option key={s.id} value={s.name} />
                    ))}
                  </datalist>
                </label>
                <button
                  type="button"
                  onClick={addSkill}
                  disabled={addingSkill}
                  className="self-end min-h-[48px] px-5 rounded-input border-2 border-ink bg-surface text-ink text-[15px] font-bold hover:bg-sand disabled:opacity-50"
                >
                  {addingSkill ? 'Adding…' : 'Add'}
                </button>
              </div>
              {skillError && <p className="text-caption text-red-600">{skillError}</p>}
            </section>

            <section aria-labelledby="price-heading" className={`${sectionClass} gap-4`}>
              <h2 id="price-heading" className="text-section-title">
                Pricing and availability
              </h2>
              <label className={`${labelClass} max-w-[320px]`}>
                Starting price per gig (KES)
                <input
                  type="text"
                  inputMode="numeric"
                  value={draft.price}
                  onChange={(e) => set('price', cleanPrice(e.target.value))}
                  className={fieldClass}
                />
              </label>
              <div className="flex justify-between items-center gap-4">
                <span className="flex flex-col gap-0.5">
                  <span id="available-label" className="text-[15px] font-semibold">
                    Available for new gigs
                  </span>
                  <span className="text-caption text-muted">Turn off when you&apos;re fully booked.</span>
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={draft.available}
                  aria-labelledby="available-label"
                  onClick={() => set('available', !draft.available)}
                  className={`shrink-0 w-[52px] h-[30px] rounded-pill p-[3px] flex ${
                    draft.available ? 'justify-end bg-primary' : 'justify-start bg-toggle-off'
                  }`}
                >
                  <span className="w-6 h-6 rounded-full bg-white shadow-knob" />
                </button>
              </div>
            </section>

            {error && <Alert type="error">{error}</Alert>}

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={!dirty || saving}
                className={`min-h-[52px] px-7 rounded-button text-body font-bold ${
                  dirty ? 'bg-primary text-white hover:bg-primary-hover' : 'bg-disabled text-muted'
                }`}
              >
                {saving ? 'Saving…' : 'Save profile'}
              </button>
              <button
                type="button"
                onClick={discard}
                disabled={!dirty || saving}
                className="min-h-[52px] px-5 rounded-button text-[15px] font-semibold text-ink-soft underline disabled:opacity-50"
              >
                Discard changes
              </button>
              <span className={`text-[14px] font-semibold ${dirty ? 'text-warn' : 'text-accent'}`}>
                {dirty ? 'You have unsaved changes' : 'All changes saved'}
              </span>
            </div>
          </form>

          <section aria-labelledby="portfolio-heading" className={`${sectionClass} gap-4`}>
            <div className="flex justify-between items-baseline gap-2 flex-wrap">
              <h2 id="portfolio-heading" className="text-section-title">
                Portfolio
              </h2>
              <span className="text-caption text-muted">Items are added and removed straight away</span>
            </div>
            <PortfolioManager onItemsChange={setPortfolioItems} />
          </section>
        </div>

        <aside aria-label="Profile preview" className="flex-[1_1_380px] max-w-[460px] min-w-0 flex flex-col gap-3 lg:sticky lg:top-6">
          <div className="flex justify-between items-center gap-2.5">
            <span className="text-caption font-bold tracking-[0.06em] uppercase text-muted">How clients see you</span>
            <span
              className={`inline-flex items-center gap-1.5 text-badge px-[11px] py-[5px] rounded-pill ${
                dirty ? 'text-warn bg-sun-light' : 'text-accent bg-accent-light'
              }`}
            >
              <span className={`w-[7px] h-[7px] rounded-full ${dirty ? 'bg-warn' : 'bg-accent'}`} aria-hidden="true" />
              {dirty ? 'Preview · not saved yet' : 'Live on your profile'}
            </span>
          </div>
          <ProfilePreviewCard profile={preview} placeholders strength={strength} />
          <Link
            to={`/profile/${user.id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="self-center text-[14px] font-semibold text-primary hover:text-primary-hover"
          >
            Open public profile in a new tab
          </Link>
        </aside>
      </div>
    </div>
  )
}
