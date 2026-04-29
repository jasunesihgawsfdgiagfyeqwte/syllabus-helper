import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const API = '/api'
const StoreContext = createContext(null)

function authFetch(url, opts = {}) {
  const token = localStorage.getItem('token')
  if (token) {
    opts.headers = { ...opts.headers, Authorization: `Bearer ${token}` }
  }
  return fetch(url, opts)
}

export function StoreProvider({ children }) {
  const [syllabi, setSyllabi] = useState({})
  const [activeId, setActiveId] = useState(null)
  const [llmMode, setLlmMode] = useState('regex')
  const [importedClasses, setImportedClasses] = useState([])
  const [scheduleData, setScheduleData] = useState(null)

  const active = activeId ? syllabi[activeId] : null

  const loadAll = useCallback(async () => {
    try {
      const [hRes, sRes] = await Promise.all([authFetch(`${API}/health`), authFetch(`${API}/syllabi`)])
      if (hRes.ok) {
        const h = await hRes.json()
        setLlmMode(h.llm_mode || 'regex')
      }
      if (sRes.ok) {
        const data = await sRes.json()
        setSyllabi(data)
        const ids = Object.keys(data)
        if (ids.length && !activeId) setActiveId(ids[0])
      }
    } catch { /* server offline */ }
  }, [activeId])

  useEffect(() => { loadAll() }, []) // eslint-disable-line

  const upload = async (file) => {
    const form = new FormData()
    form.append('file', file)
    const res = await authFetch(`${API}/upload`, { method: 'POST', body: form })
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Upload failed') }
    const data = await res.json()
    setSyllabi(prev => ({ ...prev, [data.syllabus_id]: data }))
    setActiveId(data.syllabus_id)
    pollRefine(data.syllabus_id)
    return data
  }

  const pollRefine = (sid, attempt = 0) => {
    if (attempt > 8) return
    setTimeout(async () => {
      try {
        const res = await authFetch(`${API}/syllabus/${sid}`)
        if (!res.ok) return
        const updated = await res.json()
        setSyllabi(prev => {
          const old = prev[sid]
          if (old?.course_info?.course_code !== updated.course_info?.course_code) {
            return { ...prev, [sid]: updated }
          }
          return prev
        })
      } catch { /* */ }
      pollRefine(sid, attempt + 1)
    }, 3000)
  }

  const ask = async (question) => {
    if (!activeId) throw new Error('No syllabus selected')
    const res = await authFetch(`${API}/ask/${activeId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    })
    return res.json()
  }

  const exportIcs = async (id) => {
    const res = await authFetch(`${API}/calendar/export/${id || activeId}`)
    const blob = await res.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${id || 'course'}_deadlines.ics`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const exportAll = async () => {
    const res = await authFetch(`${API}/calendar/export-all`)
    if (!res.ok) throw new Error('No courses')
    const blob = await res.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'all_courses_deadlines.ics'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const importIcs = async (file) => {
    const form = new FormData()
    form.append('file', file)
    const res = await authFetch(`${API}/calendar/import`, { method: 'POST', body: form })
    if (!res.ok) throw new Error('Import failed')
    const data = await res.json()
    setScheduleData(data)
    setImportedClasses(buildClassEvents(data.courses || []))
    return data
  }

  // Load saved schedule on init
  useEffect(() => {
    authFetch(`${API}/calendar/schedule`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.courses?.length) {
          setScheduleData(data)
          setImportedClasses(buildClassEvents(data.courses))
        }
      })
      .catch(() => {})
  }, [])

  return (
    <StoreContext.Provider value={{
      syllabi, activeId, setActiveId, active, llmMode,
      upload, ask, exportIcs, exportAll, importIcs, loadAll,
      importedClasses, scheduleData,
    }}>
      {children}
    </StoreContext.Provider>
  )
}

export const useStore = () => useContext(StoreContext)

function buildClassEvents(courses) {
  const DAY_MAP = { Sunday: 0, Monday: 1, Tuesday: 2, Wednesday: 3, Thursday: 4, Friday: 5, Saturday: 6 }
  const events = []
  for (const course of courses) {
    for (const session of course.sessions) {
      const dayNum = DAY_MAP[session.day]
      if (dayNum === undefined) continue
      let start = session.date ? new Date(session.date.split('T')[0] + 'T00:00:00') : new Date('2026-01-12T00:00:00')
      while (start.getDay() !== dayNum) start.setDate(start.getDate() + 1)
      for (let w = 0; w < 16; w++) {
        const d = new Date(start)
        d.setDate(d.getDate() + w * 7)
        events.push({
          title: `${course.course_code} ${session.start_time !== 'All day' ? session.start_time : ''} ${session.location || ''}`.trim(),
          start: d.toISOString().split('T')[0],
          allDay: true,
          color: '#14b8a6',
          extendedProps: { kind: 'class' },
        })
      }
    }
  }
  return events
}
