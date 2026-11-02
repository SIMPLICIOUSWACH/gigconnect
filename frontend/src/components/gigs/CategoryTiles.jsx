import { Briefcase, Camera, ChartColumn, ClipboardList, CodeXml, Megaphone, Palette, PenLine, Wrench } from 'lucide-react'
import { categoryColour } from '../../utils/palette'

const ICONS = {
  'design-creative': Palette,
  'marketing-sales': Megaphone,
  'web-software-development': CodeXml,
  'writing-content': PenLine,
  'admin-virtual-assistance': ClipboardList,
  'data-analytics': ChartColumn,
  'video-photography': Camera,
  'local-services': Wrench,
}

function countLabel(count) {
  return `${count} open gig${count === 1 ? '' : 's'}`
}

// "Browse by category": one tile per category with its open gig count. Choosing the selected tile
// again clears the category filter.
export default function CategoryTiles({ categories, selected, onSelect }) {
  if (categories.length === 0) return null

  return (
    <section aria-labelledby="categories-heading" className="max-w-page mx-auto px-4 sm:px-8 pb-9 flex flex-col gap-4">
      <h2 id="categories-heading" className="text-section-heading">
        Browse by category
      </h2>
      <div className="grid gap-3 grid-cols-[repeat(auto-fit,minmax(170px,1fr))]">
        {categories.map((category) => {
          const Icon = ICONS[category.slug] || Briefcase
          const active = selected === category.slug
          return (
            <button
              key={category.slug}
              type="button"
              aria-pressed={active}
              onClick={() => onSelect(active ? '' : category.slug)}
              className={`flex flex-col gap-[18px] p-[18px] rounded-tile text-left ${categoryColour(category.slug)} ${
                active ? 'outline outline-2 outline-ink outline-offset-2' : ''
              }`}
            >
              <span className="w-[42px] h-[42px] rounded-input bg-white flex items-center justify-center">
                <Icon size={22} strokeWidth={1.9} aria-hidden="true" />
              </span>
              <span className="flex flex-col gap-0.5">
                <span className="text-body font-bold">{category.name}</span>
                {category.open_gig_count !== undefined && (
                  <span className="text-caption font-medium">{countLabel(category.open_gig_count)}</span>
                )}
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
