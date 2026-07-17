import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import client, { Project } from '../api/client'

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [name, setName] = useState('')
  const [customer, setCustomer] = useState('')

  const load = () => client.get('/projects').then((r) => setProjects(r.data))

  useEffect(() => { load() }, [])

  const createProject = async (e: React.FormEvent) => {
    e.preventDefault()
    await client.post('/projects', { name, customer_name: customer, currency: 'SAR', margin_percent: 15 })
    setName(''); setCustomer('')
    load()
  }

  return (
    <div>
      <h2>Opportunities</h2>
      <div className="card">
        <form onSubmit={createProject} style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
          <div>
            <label>Project / Bid name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div>
            <label>Customer</label>
            <input value={customer} onChange={(e) => setCustomer(e.target.value)} />
          </div>
          <button type="submit">+ New Project</button>
        </form>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr><th>Name</th><th>Customer</th><th>Status</th><th>Created</th><th></th></tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.customer_name || '—'}</td>
                <td><span className="badge">{p.status}</span></td>
                <td>{new Date(p.created_at).toLocaleDateString()}</td>
                <td><Link to={`/projects/${p.id}`}>Open →</Link></td>
              </tr>
            ))}
            {projects.length === 0 && (
              <tr><td colSpan={5}>No projects yet — create one above.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
