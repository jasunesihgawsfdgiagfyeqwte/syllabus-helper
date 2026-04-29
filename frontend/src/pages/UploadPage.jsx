import { useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import { UploadCloud, CheckCircle, AlertCircle } from 'lucide-react'
import { useStore } from '../contexts/StoreContext'

export default function UploadPage({ onDone }) {
  const { upload } = useStore()
  const [status, setStatus] = useState(null) // { type, msg }
  const [dragging, setDragging] = useState(false)

  const handleFile = useCallback(async (file) => {
    if (!file) return
    const ext = file.name.split('.').pop().toLowerCase()
    if (!['pdf', 'docx', 'txt', 'text'].includes(ext)) {
      setStatus({ type: 'error', msg: 'Unsupported file type' })
      return
    }
    setStatus({ type: 'loading', msg: 'Parsing syllabus...' })
    try {
      const data = await upload(file)
      setStatus({ type: 'success', msg: `Parsed! ${data.grading?.length || 0} components, ${data.deadlines?.length || 0} deadlines.` })
      setTimeout(() => onDone?.(), 600)
    } catch (err) {
      setStatus({ type: 'error', msg: err.message })
    }
  }, [upload, onDone])

  return (
    <div>
      <h1 className="page-title">Upload Syllabus</h1>
      <p className="page-desc">Drop a PDF, DOCX, or TXT file to get started.</p>

      <motion.div
        className={`upload-zone ${dragging ? 'dragging' : ''}`}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        onClick={() => document.getElementById('file-pick').click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
      >
        <input id="file-pick" type="file" accept=".pdf,.docx,.txt,.text" hidden
          onChange={e => handleFile(e.target.files[0])} />
        <UploadCloud size={36} strokeWidth={1.5} className="upload-icon" />
        <p className="upload-main">Drop file here or <span className="upload-link">browse</span></p>
        <p className="upload-sub">PDF, DOCX, TXT</p>
      </motion.div>

      {status && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className={`status-bar status-${status.type}`}
        >
          {status.type === 'success' && <CheckCircle size={14} />}
          {status.type === 'error' && <AlertCircle size={14} />}
          {status.msg}
        </motion.div>
      )}
    </div>
  )
}
