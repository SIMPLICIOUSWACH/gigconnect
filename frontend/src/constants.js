export const INDUSTRIES = [
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

export const industryLabel = (value) => INDUSTRIES.find((i) => i.value === value)?.label || value
