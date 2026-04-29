import { motion } from 'framer-motion'
import { BookOpen, Clock, Award, FileText, Mail, User } from 'lucide-react'
import { useStore } from '../contexts/StoreContext'

const GCOL = ['#2eaadc','#9b51e0','#f2994a','#eb5757','#27ae60','#2f80ed','#f2c94c','#56ccf2']

export default function DashboardPage() {
  const { active } = useStore()
  if (!active) return <EmptyState />

  const ci = active.course_info || {}
  const gr = active.grading || []
  const dl = active.deadlines || []
  const pol = active.policies || []

  return (
    <div>
      <h1 className="page-title">
        {ci.course_code ? `${ci.course_code} \u2014 ${ci.course_name || ''}` : 'Dashboard'}
      </h1>
      <p className="page-desc">
        {[ci.instructor, ci.semester, ci.meeting_time, ci.location].filter(Boolean).join(' \u00b7 ')}
      </p>

      {/* Metrics */}
      <div className="metrics">
        {[
          { v: ci.units || '-', l: 'Credits', icon: BookOpen },
          { v: gr.length, l: 'Components', icon: Award },
          { v: dl.length, l: 'Deadlines', icon: Clock },
          { v: pol.length, l: 'Policies', icon: FileText },
        ].map((m, i) => (
          <motion.div key={i} className="metric" initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
            <m.icon size={14} className="metric-icon" />
            <div className="metric-val">{m.v}</div>
            <div className="metric-label">{m.l}</div>
          </motion.div>
        ))}
      </div>

      {/* Contact */}
      {(ci.instructor || ci.ta_name) && (
        <Section title="Contact">
          <div className="contact-grid">
            {ci.instructor && (
              <div className="contact-card">
                <User size={12} className="contact-icon" />
                <div className="contact-role">Instructor</div>
                <div className="contact-name">{ci.instructor}</div>
                {ci.email && <a className="contact-email" href={`mailto:${ci.email.split(',')[0].trim()}`}>{ci.email.split(',')[0].trim()}</a>}
                {ci.office_hours && <div className="contact-detail">OH: {ci.office_hours}</div>}
              </div>
            )}
            {ci.ta_name && (
              <div className="contact-card">
                <User size={12} className="contact-icon" />
                <div className="contact-role">Teaching Assistant</div>
                <div className="contact-name">{ci.ta_name}</div>
                {ci.ta_email && <a className="contact-email" href={`mailto:${ci.ta_email}`}>{ci.ta_email}</a>}
              </div>
            )}
          </div>
        </Section>
      )}

      {/* Two columns */}
      <div className="two-col">
        <Section title="Deadlines">
          {dl.length === 0 ? <p className="text-muted">No deadlines found.</p> :
            dl.sort((a, b) => (a.date || '').localeCompare(b.date || '')).map((d, i) => (
              <motion.div key={i} className="dl-item" initial={{ opacity: 0 }}
                animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }}>
                <span className="dl-date">{fmtDate(d.date)}</span>
                <span className="dl-desc">{d.description}</span>
                <span className={`dl-type dl-type-${d.type}`}>{d.type.replace('_', ' ')}</span>
              </motion.div>
            ))}
        </Section>

        <Section title="Grading">
          {gr.length === 0 ? <p className="text-muted">No grading found.</p> :
            gr.map((g, i) => (
              <div key={i} className="gr-row">
                <span className="gr-label">{g.component}</span>
                <div className="gr-track">
                  <motion.div className="gr-fill" style={{ background: GCOL[i % GCOL.length] }}
                    initial={{ width: 0 }} animate={{ width: `${g.weight}%` }}
                    transition={{ delay: i * 0.08, duration: 0.5 }}>
                    {g.weight >= 10 && `${g.weight}%`}
                  </motion.div>
                </div>
                <span className="gr-pct">{g.weight}%</span>
              </div>
            ))}
        </Section>
      </div>

      {/* Policies */}
      {pol.length > 0 && (
        <Section title="Policies">
          <div className="pol-grid">
            {pol.map((p, i) => (
              <motion.div key={i} className="pol-card" initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                <div className="pol-label">{p.label}</div>
                <div className="pol-text">{p.text}</div>
              </motion.div>
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="section-block">
      <h2 className="section-title">{title}</h2>
      {children}
    </div>
  )
}

function EmptyState() {
  return (
    <div>
      <h1 className="page-title">Dashboard</h1>
      <p className="text-muted">Upload a syllabus to get started.</p>
    </div>
  )
}

function fmtDate(d) {
  if (!d || d.length < 5) return d || 'TBD'
  try { return new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }
  catch { return d }
}
