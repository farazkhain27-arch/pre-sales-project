import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import client, { Project, Requirement, BOQItem } from '../api/client'

const DOC_TYPES = ['RFP', 'BOQ', 'COST_SHEET', 'ESTIMATE_SHEET', 'DATASHEET', 'CUSTOMER_REQUIREMENTS']

export default function ProjectDetail() {
  const { id } = useParams()
  const [project, setProject] = useState<Project | null>(null)
  const [docType, setDocType] = useState('RFP')
  const [file, setFile] = useState<File | null>(null)
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [boq, setBoq] = useState<BOQItem[]>([])
  const [loading, setLoading] = useState(false)
  const [unmatched, setUnmatched] = useState<string[]>([])

  const loadProject = () => client.get(`/projects/${id}`).then((r) => setProject(r.data))
  const loadRequirements = () => client.get(`/projects/${id}/requirements`).then((r) => setRequirements(r.data))
  const loadBoq = () => client.get(`/projects/${id}/boq`).then((r) => setBoq(r.data))

  useEffect(() => { loadProject(); loadRequirements(); loadBoq() }, [id])

  const upload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return
    const form = new FormData()
    form.append('doc_type', docType)
    form.append('file', file)
    await client.post(`/projects/${id}/documents`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
    setFile(null)
    alert('Document uploaded')
  }

  const runExtraction = async () => {
    setLoading(true)
    try {
      await client.post(`/projects/${id}/extract`)
      await loadRequirements()
      await loadProject()
    } finally { setLoading(false) }
  }

  const toggleReview = async (r: Requirement) => {
    await client.patch(`/projects/${id}/requirements/${r.id}`, { reviewed: !r.reviewed })
    loadRequirements()
  }

  const generateBoq = async () => {
    setLoading(true)
    try {
      const { data } = await client.post(`/projects/${id}/boq/generate`)
      setUnmatched(data.unmatched_requirements)
      await loadBoq()
      await loadProject()
    } finally { setLoading(false) }
  }

  const download = async (path: string, filename: string) => {
    const res = await client.get(path, { responseType: 'blob' })
    const url = window.URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  }

  if (!project) return <p>Loading…</p>

  return (
    <div>
      <h2>{project.name}</h2>
      <div className="status-row">
        <span className="badge">{project.status}</span>
        <span className="badge">{project.currency}</span>
        <span className="badge">Margin {project.margin_percent}%</span>
      </div>

      <div className="card">
        <h3>1. Upload documents</h3>
        <form onSubmit={upload} style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
          <div>
            <label>Document type</label>
            <select value={docType} onChange={(e) => setDocType(e.target.value)}>
              {DOC_TYPES.map((t) => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
            </select>
          </div>
          <div>
            <label>File</label>
            <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>
          <button type="submit">Upload</button>
        </form>
      </div>

      <div className="card">
        <h3>2. Extract requirements (RFP / Customer Requirements)</h3>
        <p style={{ fontSize: 13, color: '#555' }}>
          The LLM agent only extracts candidate requirements — it never sets final quantities or prices.
          Review and check off each requirement before generating the BOQ.
        </p>
        <button onClick={runExtraction} disabled={loading}>{loading ? 'Working…' : 'Run extraction agent'}</button>

        <table style={{ marginTop: 16 }}>
          <thead>
            <tr><th>✓</th><th>Category</th><th>Description</th><th>Qty</th><th>Unit</th><th>Confidence</th></tr>
          </thead>
          <tbody>
            {requirements.map((r) => (
              <tr key={r.id}>
                <td><input type="checkbox" checked={r.reviewed} onChange={() => toggleReview(r)} /></td>
                <td>{r.category}</td>
                <td>{r.description}</td>
                <td>{r.quantity}</td>
                <td>{r.unit}</td>
                <td>{(r.confidence * 100).toFixed(0)}%</td>
              </tr>
            ))}
            {requirements.length === 0 && <tr><td colSpan={6}>No requirements extracted yet.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>3. Generate BOQ &amp; pricing (deterministic rules engine)</h3>
        <button onClick={generateBoq} disabled={loading}>{loading ? 'Working…' : 'Generate BOQ'}</button>
        {unmatched.length > 0 && (
          <p style={{ color: '#b45309', fontSize: 13 }}>
            {unmatched.length} requirement(s) had no confident product match — add them to your catalog or price manually.
          </p>
        )}
        <table style={{ marginTop: 16 }}>
          <thead>
            <tr><th>Code</th><th>Description</th><th>Qty</th><th>Unit Price</th><th>Line Price</th></tr>
          </thead>
          <tbody>
            {boq.map((i) => (
              <tr key={i.id}>
                <td>{i.item_code}</td>
                <td>{i.description}</td>
                <td>{i.quantity} {i.unit}</td>
                <td>{i.unit_price.toFixed(2)}</td>
                <td>{i.line_price.toFixed(2)}</td>
              </tr>
            ))}
            {boq.length === 0 && <tr><td colSpan={5}>No BOQ generated yet.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>4. Export</h3>
        <div style={{ display: 'flex', gap: 12 }}>
          <button className="secondary" onClick={() => download(`/projects/${id}/estimate-sheet.xlsx`, `estimate_sheet_${project.name}.xlsx`)}>
            Download Estimate Sheet (.xlsx)
          </button>
          <button className="secondary" onClick={() => download(`/projects/${id}/proposal.pdf`, `proposal_${project.name}.pdf`)}>
            Download Proposal (.pdf)
          </button>
        </div>
      </div>
    </div>
  )
}
