import { Link, useNavigate } from 'react-router-dom'

export default function Sidebar() {
  const navigate = useNavigate()
  const logout = () => {
    localStorage.removeItem('access_token')
    navigate('/login')
  }
  return (
    <div className="sidebar">
      <h1>AI Presales</h1>
      <Link to="/">Dashboard</Link>
      <Link to="/policies">Policy Library</Link>
      <a onClick={logout} style={{ cursor: 'pointer', marginTop: 24 }}>Log out</a>
    </div>
  )
}
