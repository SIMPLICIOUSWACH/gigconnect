import { useEffect, useState } from 'react'
import { fetchCounties } from '../api/meta'

export default function useCounties() {
  const [counties, setCounties] = useState([])

  useEffect(() => {
    fetchCounties().then(setCounties).catch(() => setCounties([]))
  }, [])

  return counties
}
