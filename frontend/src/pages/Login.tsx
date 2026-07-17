import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'

export default function Login() {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [tenantName, setTenantName] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      const url = mode === 'login' ? '/auth/login' : '/auth/signup'
      const payload = mode === 'login'
        ? { email, password }
        : { email, password, tenant_name: tenantName, full_name: fullName }
      const { data } = await client.post(url, payload)
      localStorage.setItem('access_token', data.access_token)
      navigate('/')
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Something went wrong')
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#10233f' }}>
      <form onSubmit={submit} className="card" style={{ width: 360 }}>
        <h2>{mode === 'login' ? 'Log in' : 'Create your workspace'}</h2>
        {mode === 'signup' && (
          <>
            <label>Company / Tenant name</label>
            <input value={tenantName} onChange={(e) => setTenantName(e.target.value)} required style={{ width: '100%' }} />
            <label>Full name</label>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required style={{ width: '100%' }} />
          </>
        )}
        <label>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required style={{ width: '100%' }} />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required style={{ width: '100%' }} />
        {error && <p style={{ color: 'crimson', fontSize: 13 }}>{error}</p>}
        <button type="submit" style={{ marginTop: 16, width: '100%' }}>
          {mode === 'login' ? 'Log in' : 'Sign up'}
        </button>
        <p style={{ fontSize: 13, marginTop: 12, cursor: 'pointer', color: '#1F4E78' }}
           onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}>
          {mode === 'login' ? "No account? Create one" : 'Already have an account? Log in'}
        </p>
      </form>
    </div>
  )
}
