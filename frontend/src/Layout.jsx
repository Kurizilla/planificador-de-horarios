import { Link, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'

export default function Layout() {
  const { user, logout } = useAuth()

  return (
    <div style={{ height: '100vh', overflow: 'hidden', display: 'flex', flexDirection: 'column', fontFamily: 'system-ui', color: 'var(--color-text)' }}>
      <header style={{
        background: 'var(--color-bg)',
        borderBottom: '1px solid var(--color-border)',
        padding: '0.8rem 1.75rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
        zIndex: 50,
        position: 'relative'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <Link to="/projects" style={{
            fontWeight: 800,
            fontSize: '1.2rem',
            textDecoration: 'none',
            color: 'var(--color-text)',
            letterSpacing: '-0.02em',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem'
          }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 6H20M4 12H12M4 18H20" stroke="var(--color-btn-primary-bg)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Planificador de <span style={{ color: 'var(--color-btn-primary-bg)', opacity: 0.9 }}>Horarios</span>
          </Link>
          <Link to="/projects/new" style={{
            padding: '0.5rem 1rem',
            background: 'var(--color-btn-primary-bg)',
            color: 'white',
            textDecoration: 'none',
            borderRadius: 8,
            fontSize: '0.9rem',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            boxShadow: '0 2px 4px color-mix(in srgb, var(--color-btn-primary-bg) 25%, transparent)',
            transition: 'transform 0.15s, box-shadow 0.15s'
          }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-1px)'
              e.currentTarget.style.boxShadow = '0 4px 8px color-mix(in srgb, var(--color-btn-primary-bg) 35%, transparent)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = '0 2px 4px color-mix(in srgb, var(--color-btn-primary-bg) 25%, transparent)'
            }}
          >
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Crear proyecto
          </Link>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          {user?.role === 'ADMIN' && (
            <Link to="/users" style={{
              color: 'var(--color-text-muted)',
              textDecoration: 'none',
              fontSize: '0.9rem',
              fontWeight: 600,
              padding: '0.4rem 0.6rem',
              borderRadius: 6,
              background: 'transparent',
              transition: 'background 0.2s, color 0.2s'
            }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-bg-subtle)'; e.currentTarget.style.color = 'var(--color-text)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--color-text-muted)'; }}
            >
              Usuarios
            </Link>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', background: 'var(--color-bg-subtle)', padding: '0.3rem 0.3rem 0.3rem 0.6rem', borderRadius: 24, border: '1px solid var(--color-border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{
                width: 24,
                height: 24,
                borderRadius: '50%',
                background: 'color-mix(in srgb, var(--color-text-muted) 20%, transparent)',
                color: 'var(--color-text)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.8rem',
                fontWeight: 700,
                textTransform: 'uppercase'
              }}>
                {user?.email?.[0] || '?'}
              </div>
              <span style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--color-text)' }}>
                {user?.email}
              </span>
            </div>
            <div style={{ width: 1, height: 16, background: 'var(--color-border)', margin: '0 0.2rem' }} />
            <button
              type="button"
              onClick={logout}
              style={{
                padding: '0.3rem 0.6rem',
                background: 'transparent',
                border: 'none',
                color: 'var(--color-text-muted)',
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontWeight: 600,
                borderRadius: 16,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-border)'; e.currentTarget.style.color = 'var(--color-text)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--color-text-muted)'; }}
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
        <Outlet />
      </div>
    </div>
  )
}
