import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Calculator, TrendingUp } from 'lucide-react'
import { useStore } from '../contexts/StoreContext'

const GCOL = ['#2eaadc','#9b51e0','#f2994a','#eb5757','#27ae60','#2f80ed','#f2c94c','#56ccf2']

export default function GradesPage() {
  const { active } = useStore()
  const [scores, setScores] = useState({})
  const [result, setResult] = useState(null)

  if (!active) return (
    <div>
      <h1 className="page-title">Grade Estimator</h1>
      <p className="text-muted">Upload a syllabus first.</p>
    </div>
  )

  const gr = active.grading || []
  const scale = active.grade_scale || []
  const isPoints = gr.some(g => g.points)

  const calc = () => {
    let weighted = 0, totalW = 0
    gr.forEach((g, i) => {
      const v = parseFloat(scores[i])
      if (!isNaN(v)) {
        weighted += isPoints && g.points ? (v / g.points) * g.weight : v * (g.weight / 100)
        totalW += g.weight
      }
    })
    setResult({ score: weighted, letter: getLetter(weighted, scale), totalW })
  }

  const allFilled = gr.every((_, i) => scores[i] !== undefined && scores[i] !== '')

  return (
    <div className="grades-page">
      <h1 className="page-title">Grade Estimator</h1>
      <p className="page-desc">Enter your scores to see where you stand.</p>

      <div className="grades-layout">
        {/* Input section */}
        <div className="grades-input-section">
          {gr.map((g, i) => (
            <motion.div key={i} className="grade-card"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}>
              <div className="grade-card-left">
                <div className="grade-dot" style={{ background: GCOL[i % GCOL.length] }} />
                <div>
                  <div className="grade-comp-name">{g.component}</div>
                  <div className="grade-comp-weight">
                    {isPoints ? `${g.points} pts (${g.weight}%)` : `${g.weight}% of total`}
                  </div>
                </div>
              </div>
              <div className="grade-card-right">
                <input
                  type="number" min="0" max={isPoints ? g.points : 100}
                  value={scores[i] || ''}
                  onChange={e => {
                    const max = isPoints ? g.points : 100
                    const val = e.target.value
                    if (val === '' || (Number(val) >= 0 && Number(val) <= max)) {
                      setScores(prev => ({ ...prev, [i]: val }))
                    }
                  }}
                  placeholder="--"
                  className="grade-score-input"
                />
                <span className="grade-max">/ {isPoints ? g.points : 100}</span>
              </div>
            </motion.div>
          ))}

          <button className="grades-calc-btn" onClick={calc}>
            <Calculator size={15} />
            Calculate Grade
          </button>
        </div>

        {/* Result section */}
        <AnimatePresence>
          {result && (
            <motion.div className="grades-result-section"
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 300, damping: 25 }}>
              <div className="result-circle">
                <svg viewBox="0 0 120 120" className="result-ring">
                  <circle cx="60" cy="60" r="52" fill="none" stroke="var(--border)" strokeWidth="8" />
                  <motion.circle cx="60" cy="60" r="52" fill="none" stroke="var(--accent)" strokeWidth="8"
                    strokeLinecap="round" strokeDasharray={2 * Math.PI * 52}
                    initial={{ strokeDashoffset: 2 * Math.PI * 52 }}
                    animate={{ strokeDashoffset: 2 * Math.PI * 52 * (1 - result.score / 100) }}
                    transition={{ duration: 0.8, ease: 'easeOut' }}
                    transform="rotate(-90 60 60)" />
                </svg>
                <div className="result-center">
                  <div className="result-score">{result.score.toFixed(1)}</div>
                  <div className="result-letter">{result.letter}</div>
                </div>
              </div>

              <div className="result-detail">
                Based on {result.totalW}% of total weight
              </div>

              {scale.length > 0 && (
                <div className="result-scale">
                  {scale.map((s, i) => (
                    <span key={i} className={`scale-chip ${s.min <= result.score && result.score <= s.max ? 'active' : ''}`}>
                      {s.grade} ({s.min}-{s.max})
                    </span>
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

function getLetter(s, scale) {
  if (scale?.length) {
    for (const x of [...scale].sort((a, b) => b.min - a.min)) { if (s >= x.min) return x.grade }
    return 'F'
  }
  if(s>=93)return'A';if(s>=90)return'A-';if(s>=87)return'B+';if(s>=83)return'B';if(s>=80)return'B-';
  if(s>=77)return'C+';if(s>=73)return'C';if(s>=70)return'C-';if(s>=67)return'D+';if(s>=60)return'D';return'F'
}
