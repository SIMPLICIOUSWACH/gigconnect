import { Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { createPortfolioItem, deletePortfolioItem, listPortfolioItems } from '../api/profile'
import Button from './Button'
import Input from './Input'

export default function PortfolioManager({ limit }) {
  const [items, setItems] = useState([])
  const [form, setForm] = useState({ title: '', description: '', link: '' })
  const [loadError, setLoadError] = useState('')
  const [addError, setAddError] = useState('')
  const [adding, setAdding] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [deleteError, setDeleteError] = useState('')

  const load = () => listPortfolioItems().then(setItems).catch(() => setLoadError('Could not load portfolio.'))

  useEffect(() => {
    load()
  }, [])

  const handleAdd = async () => {
    setAddError('')
    if (!form.title) {
      setAddError('Title is required to add a portfolio item.')
      return
    }
    setAdding(true)
    try {
      await createPortfolioItem(form)
      setForm({ title: '', description: '', link: '' })
      await load()
    } catch {
      setAddError('Could not add portfolio item. Please try again.')
    } finally {
      setAdding(false)
    }
  }

  const handleDelete = async (id) => {
    setDeleteError('')
    setDeletingId(id)
    try {
      await deletePortfolioItem(id)
      await load()
    } catch {
      setDeleteError('Could not remove that item. Please try again.')
    } finally {
      setDeletingId(null)
    }
  }

  const visibleItems = limit ? items.slice(0, limit) : items

  return (
    <div className="space-y-5">
      {loadError && <p className="text-caption text-red-600">{loadError}</p>}
      <ul className="space-y-2">
        {visibleItems.map((item) => (
          <li
            key={item.id}
            className="flex items-center justify-between text-body border border-border rounded-lg px-4 py-3"
          >
            <span className="text-ink">{item.title}</span>
            <button
              onClick={() => handleDelete(item.id)}
              disabled={deletingId === item.id}
              className="flex items-center gap-1.5 text-red-600 text-caption font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {deletingId === item.id && <Loader2 size={14} className="animate-spin" />}
              {deletingId === item.id ? 'Removing…' : 'Remove'}
            </button>
          </li>
        ))}
        {items.length === 0 && <p className="text-caption text-muted">No portfolio items yet.</p>}
      </ul>
      {deleteError && <p className="text-caption text-red-600">{deleteError}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Title"
          required
          value={form.title}
          onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
        />
        <Input
          label="Link (optional)"
          value={form.link}
          onChange={(e) => setForm((f) => ({ ...f, link: e.target.value }))}
        />
      </div>
      {addError && <p className="text-caption text-red-600">{addError}</p>}
      <Button type="button" variant="secondary" onClick={handleAdd} loading={adding}>
        {adding ? 'Adding…' : 'Add item'}
      </Button>
    </div>
  )
}
