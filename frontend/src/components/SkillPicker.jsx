export default function SkillPicker({ skills, selected, onToggle }) {
  return (
    <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto border border-border rounded-lg p-4">
      {skills.map((skill) => (
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
    </div>
  )
}
