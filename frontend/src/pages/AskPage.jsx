import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, BookOpen, Clock, User, HelpCircle } from 'lucide-react'
import { useStore } from '../contexts/StoreContext'

const SUGGESTIONS = [
  { icon: HelpCircle, text: 'What is the late work policy?' },
  { icon: BookOpen, text: 'How much is the final worth?' },
  { icon: User, text: 'Who is the instructor?' },
  { icon: Clock, text: 'When is the midterm?' },
]

export default function AskPage() {
  const { ask, llmMode, active } = useStore()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => { inputRef.current?.focus() }, [])

  const send = async (text) => {
    const q = (text || input).trim()
    if (!q || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: q }])
    setLoading(true)
    try {
      const data = await ask(q)
      setMessages(prev => [...prev, {
        role: 'assistant', text: data.answer,
        confidence: data.confidence, source: data.source,
      }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', text: 'Could not reach the server.' }])
    }
    setLoading(false)
    inputRef.current?.focus()
  }

  const courseName = active?.course_info?.course_code || 'your syllabus'
  const isEmpty = messages.length === 0

  return (
    <div className="ask-page">
      <div className="ask-content">
        {isEmpty ? (
          /* ── Empty state with suggestions ── */
          <motion.div className="ask-empty"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <div className="ask-hero-icon">
              <HelpCircle size={32} strokeWidth={1.5} />
            </div>
            <h2 className="ask-hero-title">Ask about {courseName}</h2>
            <p className="ask-hero-desc">
              Get instant answers grounded in your course syllabus.
            </p>
            <div className="ask-suggestions">
              {SUGGESTIONS.map((s, i) => (
                <motion.button key={i} className="ask-chip"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 + i * 0.06 }}
                  onClick={() => send(s.text)}>
                  <s.icon size={14} />
                  {s.text}
                </motion.button>
              ))}
            </div>
          </motion.div>
        ) : (
          /* ── Chat messages ── */
          <div className="ask-messages">
            <AnimatePresence>
              {messages.map((m, i) => (
                <motion.div key={i}
                  className={`ask-msg ${m.role}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.15 }}>
                  {m.role === 'assistant' && <div className="ask-msg-avatar">S</div>}
                  <div className="ask-msg-body">
                    <p>{m.text}</p>
                    {m.confidence != null && (
                      <div className="ask-meta">
                        <span className={`ask-conf ${m.confidence > 0.5 ? 'high' : m.confidence > 0.15 ? 'mid' : 'low'}`}>
                          {Math.round(m.confidence * 100)}% confidence
                        </span>
                        {m.source && <SourceToggle text={m.source} />}
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {loading && (
              <motion.div className="ask-msg assistant"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div className="ask-msg-avatar">S</div>
                <div className="ask-msg-body">
                  <div className="ask-typing"><span /><span /><span /></div>
                </div>
              </motion.div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* ── Input bar ── */}
      <div className="ask-input-wrap">
        <div className="ask-input-bar">
          <input
            ref={inputRef}
            className="ask-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder={`Ask about ${courseName}...`}
          />
          <button className="ask-send" onClick={() => send()} disabled={loading || !input.trim()}>
            <Send size={16} />
          </button>
        </div>
        <p className="ask-footer">
          Powered by {llmMode === 'openai' ? 'GPT' : llmMode === 'flan-t5' ? 'Flan-T5' : 'TF-IDF'} + syllabus context
        </p>
      </div>
    </div>
  )
}

function SourceToggle({ text }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button className="ask-source-btn" onClick={() => setOpen(!open)}>
        {open ? 'Hide source' : 'View source'}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div className="ask-source"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}>
            {text}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
