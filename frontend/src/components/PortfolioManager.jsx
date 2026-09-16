import { useEffect, useState } from 'react'
import { createPortfolioItem, deletePortfolioItem, listPortfolioItems } from '../api/profile'
import Button from './Button'
import Input from './Input'

export default function PortfolioManager({ limit }) {
  const [items, setItems] = useState([])
  const [form, setForm] = useState({ title: '', description: '', link: '' })
  const [error, setError] = useState('')

  const load = () => listPortfolioItems().then(setItems).catch(() => setError('Could not load portfolio.'))

  useEffect(() => {
    load()
  }, [])

  const handleAdd = async () => {
    if (!form.title) return
    try {
      await createPortfolioItem(form)
      setForm({ title: '', description: '', link: '' })
      load()
    } catch {
      setError('Could not add portfolio item.')
    }
  }

  const handleDelete = async (id) => {
    await deletePortfolioItem(id)
    load()
  }

  const visibleItems = limit ? items.slice(0, limit) : items

  return (
    <div className="space-y-3">
      <ul className="space-y-2">
        {visibleItems.map((item) => (
          <li
            key={item.id}
            className="flex items-center justify-between text-sm border border-navy-100 rounded-lg px-3 py-2"
          >
            <span className="text-navy-700">{item.title}</span>
            <button onClick={() => handleDelete(item.id)} className="text-red-600 text-xs font-medium">
              Remove
            </button>
          </li>
        ))}
        {items.length === 0 && <p className="text-sm text-navy-400">No portfolio items yet.</p>}
      </ul>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <Input
          label="Title"
          value={form.title}
          onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
        />
        <Input
          label="Link (optional)"
          value={form.link}
          onChange={(e) => setForm((f) => ({ ...f, link: e.target.value }))}
        />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <Button type="button" variant="secondary" onClick={handleAdd}>
        Add item
      </Button>
    </div>
  )
}
