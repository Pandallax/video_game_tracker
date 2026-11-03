import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/games', label: 'Games' },
  { to: '/copies', label: 'Copies' },
  { to: '/sales', label: 'Sales' },
]

export function AppLayout() {
  const { logout } = useAuth()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>Game Tracker</h1>
        <nav>
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? 'active' : '')} end>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button className="logout-btn" onClick={() => logout()}>
          Log out
        </button>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
