import Label from '../Label'
import SkillPicker from '../SkillPicker'

const POSTED_WITHIN_OPTIONS = [
  { value: '', label: 'Any time' },
  { value: '1', label: 'Last 24 hours' },
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
]

const fieldClass =
  'w-full px-3 py-2.5 border border-border rounded-lg text-body text-ink bg-surface placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors'

export default function FilterSidebar({ categories, skills, filters, onChange, onClear }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-section-title text-ink">Filters</h2>
        <button
          type="button"
          onClick={onClear}
          className="text-caption font-medium text-primary hover:text-primary-hover"
        >
          Clear all
        </button>
      </div>

      <div>
        <Label>Category</Label>
        <div className="space-y-1.5">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="category"
              checked={!filters.category}
              onChange={() => onChange({ category: '' })}
              className="text-primary focus:ring-primary/30"
            />
            <span className="text-body text-ink">All categories</span>
          </label>
          {categories.map((cat) => (
            <label key={cat.id} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="category"
                checked={filters.category === cat.slug}
                onChange={() => onChange({ category: cat.slug })}
                className="text-primary focus:ring-primary/30"
              />
              <span className="text-body text-ink">{cat.name}</span>
            </label>
          ))}
        </div>
      </div>

      <div>
        <Label>Skills</Label>
        <SkillPicker
          skills={skills}
          selected={filters.skillIds}
          onToggle={(skillId) => {
            const next = filters.skillIds.includes(skillId)
              ? filters.skillIds.filter((id) => id !== skillId)
              : [...filters.skillIds, skillId]
            onChange({ skillIds: next })
          }}
        />
      </div>

      <div>
        <Label>Budget (KES)</Label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min="0"
            placeholder="Min"
            value={filters.budget_min}
            onChange={(e) => onChange({ budget_min: e.target.value })}
            className={fieldClass}
          />
          <span className="text-muted">–</span>
          <input
            type="number"
            min="0"
            placeholder="Max"
            value={filters.budget_max}
            onChange={(e) => onChange({ budget_max: e.target.value })}
            className={fieldClass}
          />
        </div>
      </div>

      <div>
        <Label>Posted within</Label>
        <div className="space-y-1.5">
          {POSTED_WITHIN_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="posted_within"
                checked={filters.posted_within === opt.value}
                onChange={() => onChange({ posted_within: opt.value })}
                className="text-primary focus:ring-primary/30"
              />
              <span className="text-body text-ink">{opt.label}</span>
            </label>
          ))}
        </div>
      </div>

      <div>
        <Label>Deadline before</Label>
        <input
          type="date"
          value={filters.deadline_before}
          onChange={(e) => onChange({ deadline_before: e.target.value })}
          className={fieldClass}
        />
      </div>

      <label className="flex items-center gap-2.5 cursor-pointer">
        <input
          type="checkbox"
          checked={filters.negotiable}
          onChange={(e) => onChange({ negotiable: e.target.checked })}
          className="w-4 h-4 rounded border-border text-primary focus:ring-2 focus:ring-primary/30"
        />
        <span className="text-body text-ink">Negotiable budget only</span>
      </label>
    </div>
  )
}
