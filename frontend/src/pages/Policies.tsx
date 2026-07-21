import { useEffect, useState } from 'react'
import client, { PolicyDocument, PolicyAskResponse } from '../api/client'

export default function Policies() {
  const [policies, setPolicies] = useState<PolicyDocument[]>([])
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)

  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [result, setResult] = useState<PolicyAskResponse | null>(null)

  const load = () => client.get('/policies').then((r) => setPolicies(r.data))
  useEffect(() => { load() }, [])

  const upload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file || !title) return
    setUploading(true)
    try {
      const form = new FormData()
      form.append('title', title)
      form.append('file', file)
      await client.post('/policies/upload', form)
      setTitle(''); setFile(null)
      await load()
    } finally {
      setUploading(false)
    }
  }

  const removePolicy = async (id: string) => {
    await client.delete(`/policies/${id}`)
    load()
  }

  const ask = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return
    setAsking(true)
    setResult(null)
    try {
      const { data } = await client.post('/policies/ask', { question })
      setResult(data)
    } catch (err: any) {
      setResult({
        answer: err?.response?.data?.detail || 'Something went wrong.',
        sources: [],
        grounded: false,
      })
    } finally {
      setAsking(false)
    }
  }

  return (
    <div>
      <h2>Company Policy Library</h2>
      <p style={{ fontSize: 13, color: '#555', marginTop: -8 }}>
        Upload internal policy documents (discount rules, approval thresholds, technical
        standards, compliance clauses). Each upload is chunked and embedded immediately so
        it's searchable right away — ask a question below to confirm the pipeline is
        actually grounded in what you just uploaded.
      </p>

      <div className="card">
        <h3>Upload a policy document</h3>
        <form onSubmit={upload} style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
          <div>
            <label>Title</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)}
                   placeholder="Discount Approval Policy 2026" required style={{ width: 260 }} />
          </div>
          <div>
            <label>File (.pdf or .txt)</label>
            <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>
          <button type="submit" disabled={uploading}>{uploading ? 'Ingesting…' : 'Upload & Ingest'}</button>
        </form>

        <table style={{ marginTop: 16 }}>
          <thead>
            <tr><th>Title</th><th>File</th><th>Status</th><th>Chunks</th><th></th></tr>
          </thead>
          <tbody>
            {policies.map((p) => (
              <tr key={p.id}>
                <td>{p.title}</td>
                <td>{p.filename}</td>
                <td><span className="badge">{p.ingested ? 'Indexed' : 'Pending'}</span></td>
                <td>{p.chunk_count}</td>
                <td><a onClick={() => removePolicy(p.id)} style={{ cursor: 'pointer', color: '#b91c1c' }}>Remove</a></td>
              </tr>
            ))}
            {policies.length === 0 && <tr><td colSpan={5}>No policy documents uploaded yet.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Ask a policy question</h3>
        <form onSubmit={ask} style={{ display: 'flex', gap: 12 }}>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What's the maximum discount I can offer without director approval?"
            style={{ flex: 1 }}
          />
          <button type="submit" disabled={asking}>{asking ? 'Searching…' : 'Ask'}</button>
        </form>

        {result && (
          <div style={{ marginTop: 16 }}>
            <div style={{
              padding: 12, borderRadius: 8,
              background: result.grounded ? '#f0fdf4' : '#fffbeb',
              border: `1px solid ${result.grounded ? '#bbf7d0' : '#fde68a'}`,
            }}>
              <strong>{result.grounded ? '✓ Grounded in policy library' : '⚠ No matching policy found'}</strong>
              <p style={{ marginTop: 8, whiteSpace: 'pre-wrap', fontSize: 14 }}>{result.answer}</p>
            </div>

            {result.sources.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: '#555' }}>Sources retrieved:</p>
                {result.sources.map((s, i) => (
                  <div key={i} style={{ fontSize: 12, padding: '8px 0', borderTop: '1px solid #e5e7eb' }}>
                    <strong>[{i + 1}] {s.document_title}</strong> — section {s.chunk_index}
                    {' '}<span className="badge">similarity {s.similarity}</span>
                    <p style={{ color: '#555', marginTop: 4 }}>{s.excerpt}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
