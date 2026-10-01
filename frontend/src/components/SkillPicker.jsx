import { useState } from 'react'

export default function SkillPicker({ skills, selected, onToggle, onCreate }) {
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  const trimmed = query.trim()
  const filtered = trimmed
    ? skills.filter((skill) => skill.name.toLowerCase().includes(trimmed.toLowerCase()))
    : skills
  const exactMatch = trimmed && skills.some((skill) => skill.name.toLowerCase() === trimmed.toLowerCase())
  const canOfferCreate = Boolean(onCreate) && trimmed.length > 0 && !exactMatch

  const handleCreate = async () => {
    setCreating(true)
    setCreateError('')
    try {
      await onCreate(trimmed)
      setQuery('')
    } catch {
      setCreateError('Could not add this skill. Please try again.')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      {onCreate && (
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search skills…"
          className="w-full px-4 py-2.5 mb-3 border border-border rounded-lg text-body text-ink placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
        />
      )}

      <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto border border-border rounded-lg p-4">
        {filtered.map((skill) => (
          <button
            type="button"
            key={skill.id}
            onClick={() => onToggle(skill.id)}
            className={`text-caption font-medium px-3 py-1.5 rounded-full border transition-colors ${
              selected.includes(skill.id)
                ? 'bg-primary text-white border-primary'
                : 'bg-surface text-ink border-border hover:bg-bg'
            }`}
          >
            {skill.name}
          </button>
        ))}
        {filtered.length === 0 && !canOfferCreate && (
          <p className="text-caption text-muted">No skills match "{trimmed}".</p>
        )}
      </div>

      {canOfferCreate && (
        <button
          type="button"
          onClick={handleCreate}
          disabled={creating}
          className="mt-2 text-caption font-medium text-primary hover:text-primary-hover disabled:opacity-50"
        >
          {creating ? 'Adding…' : `+ Add "${trimmed}" as a new skill`}
        </button>
      )}
      {createError && <p className="text-caption text-red-600 mt-1">{createError}</p>}
    </div>
  )
}
