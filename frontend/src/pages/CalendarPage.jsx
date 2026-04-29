import { useState } from 'react'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import listPlugin from '@fullcalendar/list'
import { Share, FolderDown } from 'lucide-react'
import { useStore } from '../contexts/StoreContext'

const ECOL = { midterm: '#eb5757', final_exam: '#eb5757', quiz: '#9b51e0', homework: '#2f80ed', deadline: '#2f80ed', project: '#f2994a', presentation: '#f2994a', other: '#9b9a97' }

export default function CalendarPage() {
  const { syllabi, exportAll, exportIcs, activeId, importIcs, importedClasses, scheduleData } = useStore()
  const [mode, setMode] = useState('all')

  // Build deadline events
  const deadlineEvents = []
  for (const [sid, d] of Object.entries(syllabi)) {
    const code = d.course_info?.course_code || sid
    for (const dl of d.deadlines || []) {
      if (!dl.date) continue
      deadlineEvents.push({
        title: `${code}: ${dl.description}`,
        start: dl.date,
        allDay: true,
        color: ECOL[dl.type] || ECOL.other,
        extendedProps: { kind: 'deadline' },
      })
    }
  }

  // Choose visible events based on mode
  let events = []
  if (mode === 'all') events = [...deadlineEvents, ...importedClasses]
  else if (mode === 'deadlines') events = deadlineEvents
  else if (mode === 'classes') events = importedClasses

  const handleImport = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      await importIcs(file)
    } catch (err) { alert(err.message) }
  }

  return (
    <div>
      <div className="cal-top">
        <div>
          <h1 className="page-title">Calendar</h1>
          <p className="page-desc">All deadlines across your courses.</p>
        </div>
        <div className="cal-actions">
          <button className="btn-accent" onClick={exportAll}><Share size={14} /> Export All</button>
          <button className="btn-outline" onClick={() => exportIcs(activeId)}><Share size={14} /> Current</button>
          <label className="btn-outline"><FolderDown size={14} /> Import
            <input type="file" accept=".ics" hidden onChange={handleImport} />
          </label>
        </div>
      </div>

      <div className="cal-modes">
        {['all', 'deadlines', 'classes'].map(m => (
          <button key={m} className={`cal-mode ${mode === m ? 'active' : ''}`}
            onClick={() => setMode(m)}>{m[0].toUpperCase() + m.slice(1)}</button>
        ))}
      </div>

      <div className="cal-wrap">
        <FullCalendar
          plugins={[dayGridPlugin, listPlugin]}
          initialView="dayGridMonth"
          headerToolbar={{ left: 'prev,next today', center: 'title', right: 'dayGridMonth,listMonth' }}
          height="auto"
          events={events}
          eventClick={info => alert(`${info.event.title}\n${info.event.startStr}`)}
        />
      </div>

      <div className="cal-legend">
        <span className="legend-item"><i className="dot dot-exam" /> Exams</span>
        <span className="legend-item"><i className="dot dot-hw" /> Homework</span>
        <span className="legend-item"><i className="dot dot-proj" /> Projects</span>
        <span className="legend-item"><i className="dot dot-quiz" /> Quizzes</span>
        {importedClasses.length > 0 && <span className="legend-item"><i className="dot dot-class" /> Classes</span>}
      </div>

      {scheduleData?.courses?.length > 0 && (
        <div>
          <h2 className="section-title sched-title">
            Imported Schedule
            <span className="pill sched-pill">{scheduleData.courses.length} courses</span>
          </h2>
          <div className="sched-grid">
            {scheduleData.courses.map((c, i) => (
              <div key={i} className="sched-card">
                <div className="sched-code">{c.course_code}</div>
                <div className="sched-name">{c.course_name}</div>
                {c.sessions.map((s, j) => (
                  <div key={j} className="sched-session">
                    {s.day} {s.start_time}{s.end_time ? ` - ${s.end_time}` : ''} {s.location || ''}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
