import { useEffect, useState } from 'react'
import Label from './Label'

export default function ImageUpload({ label, currentUrl, onChange, round = false }) {
  const [preview, setPreview] = useState(null)

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview)
    }
  }, [preview])

  const handleChange = (e) => {
    const file = e.target.files[0] || null
    if (preview) URL.revokeObjectURL(preview)
    setPreview(file ? URL.createObjectURL(file) : null)
    onChange(file)
  }

  const displayUrl = preview || currentUrl
  const shapeClass = round ? 'rounded-full' : 'rounded-lg'

  return (
    <div>
      <Label>{label}</Label>
      <div className="flex items-center gap-4">
        {displayUrl ? (
          <img src={displayUrl} alt="" className={`w-16 h-16 object-cover border border-border ${shapeClass}`} />
        ) : (
          <div
            className={`w-16 h-16 bg-bg border border-border flex items-center justify-center text-caption text-muted ${shapeClass}`}
          >
            None
          </div>
        )}
        <input type="file" accept="image/*" onChange={handleChange} />
      </div>
    </div>
  )
}
