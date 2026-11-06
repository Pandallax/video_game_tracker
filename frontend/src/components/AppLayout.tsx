import { Fragment } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

interface NavItem {
  to: string
  label: string
  children?: { to: string; label: string }[]
}

const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard' },
  { to: '/games', label: 'Game List', children: [{ to: '/games/imports', label: 'Imports' }] },
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
            <Fragment key={item.to}>
              <NavLink to={item.to} className={({ isActive }) => (isActive ? 'active' : '')} end>
                {item.label}
              </NavLink>
              {item.children?.map((child) => (
                <NavLink
                  key={child.to}
                  to={child.to}
                  className={({ isActive }) => `sub-link${isActive ? ' active' : ''}`}
                  end
                >
                  {child.label}
                </NavLink>
              ))}
            </Fragment>
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
