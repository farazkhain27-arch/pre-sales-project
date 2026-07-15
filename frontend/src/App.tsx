import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ProjectDetail from './pages/ProjectDetail'
import Sidebar from './components/Sidebar'

function isAuthed() {
  return !!localStorage.getItem('access_token')
}

function Protected({ children }: { children: JSX.Element }) {
  return isAuthed() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <Protected>
              <div className="app-shell">
                <Sidebar />
                <div className="main">
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/projects/:id" element={<ProjectDetail />} />
                  </Routes>
                </div>
              </div>
            </Protected>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}
