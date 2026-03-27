import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, deleteProject } from '../api'

export default function ProjectList() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deletingId, setDeletingId] = useState(null)
  const navigate = useNavigate()

  const load = () => {
    setError('')
    setLoading(true)
    api('/projects')
      .then(setProjects)
      .catch((err) => {
        const msg = err.message || ''
        setError(msg === 'Failed to fetch' || msg.includes('fetch')
          ? 'No se pudo conectar con el backend. ¿Está corriendo en http://localhost:8001?'
          : msg)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  if (loading) {
    return (
      <main style={{ maxWidth: 1000, margin: '0 auto', padding: '3rem 2rem', fontFamily: 'system-ui' }}>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
          <p style={{ fontSize: '1.25rem', color: 'var(--color-text-muted)' }}>Cargando proyectos…</p>
        </div>
      </main>
    )
  }

  if (error) {
    return (
      <main style={{ maxWidth: 1000, margin: '0 auto', padding: '3rem 2rem', fontFamily: 'system-ui' }}>
        <div style={{ background: 'color-mix(in srgb, var(--color-status-error) 10%, var(--color-bg))', border: '1px solid color-mix(in srgb, var(--color-status-error) 30%, var(--color-bg))', padding: '2rem', borderRadius: 12, textAlign: 'center' }}>
          <h2 style={{ color: 'var(--color-status-error)', margin: '0 0 1rem 0' }}>Error</h2>
          <p style={{ color: 'var(--color-status-error)', margin: '0 0 1.5rem 0' }}>{error}</p>
          <button type="button" onClick={load} style={{ padding: '0.75rem 1.5rem', background: 'var(--color-status-error)', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}>
            Reintentar
          </button>
        </div>
      </main>
    )
  }

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '3rem 2rem', fontFamily: 'system-ui' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '3rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ margin: '0 0 0.5rem 0', fontSize: '2.5rem', fontWeight: 800, letterSpacing: '-0.05em' }}>Mis Proyectos</h1>
          <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '1.1rem' }}>Gestiona los horarios de tus centros educativos</p>
        </div>
        <button
          onClick={() => navigate('/projects/new')}
          style={{
            background: 'var(--color-link)',
            color: 'white',
            border: 'none',
            padding: '0.75rem 1.5rem',
            borderRadius: 8,
            fontSize: '1rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
          }}
        >
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Nuevo Proyecto
        </button>
      </div>

      {projects.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '5rem 2rem',
          background: 'var(--color-bg-subtle)',
          borderRadius: 16,
          border: '1px dashed var(--color-border)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '1.5rem'
        }}>
          <div style={{ width: 64, height: 64, background: 'color-mix(in srgb, var(--color-link) 15%, var(--color-bg))', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-link)' }}>
            <svg width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <div>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.25rem' }}>No hay proyectos aún</h3>
            <p style={{ margin: 0, color: 'var(--color-text-muted)' }}>Crea tu primer proyecto para empezar a planificar horarios.</p>
          </div>
          <button
            onClick={() => navigate('/projects/new')}
            style={{
              background: 'var(--color-bg)',
              color: 'var(--color-link)',
              border: '1px solid var(--color-border)',
              padding: '0.75rem 1.5rem',
              borderRadius: 8,
              fontSize: '1rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Crear Proyecto
          </button>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '1.5rem'
        }}>
          {projects.map((p) => (
            <div
              key={p.id}
              style={{
                background: 'var(--color-bg)',
                border: '1px solid var(--color-border)',
                borderRadius: 16,
                padding: '1.5rem',
                display: 'flex',
                flexDirection: 'column',
                transition: 'transform 0.2s, box-shadow 0.2s',
                boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)',
                position: 'relative',
                overflow: 'hidden'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-4px)'
                e.currentTarget.style.boxShadow = '0 10px 15px -3px rgb(0 0 0 / 0.1)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.boxShadow = '0 1px 3px 0 rgb(0 0 0 / 0.1)'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                <Link
                  to={`/projects/${p.id}/import`}
                  style={{ textDecoration: 'none', color: 'inherit', flex: 1, minWidth: 0 }}
                >
                  <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, lineHeight: 1.3 }}>{p.name}</h3>
                </Link>
              </div>

              <p style={{ margin: '0 0 1.5rem 0', fontSize: '0.95rem', color: 'var(--color-text-muted)', lineHeight: 1.5, flex: 1 }}>
                {p.description ? p.description : <span style={{ fontStyle: 'italic', opacity: 0.7 }}>Sin descripción</span>}
              </p>

              <div style={{ paddingTop: '1rem', borderTop: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', fontWeight: 500 }}>PID: {p.id}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <button
                    type="button"
                    title="Eliminar proyecto"
                    disabled={deletingId === p.id}
                    onClick={async (e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      const projectId = p?.id
                      if (!projectId) {
                        setError('ID del proyecto no disponible')
                        return
                      }
                      if (!window.confirm(`¿Eliminar el proyecto "${p.name}"? Esta accion es irreversible.`)) return
                      setDeletingId(projectId)
                      setError('')
                      try {
                        await deleteProject(projectId)
                        load()
                      } catch (err) {
                        setError(err.message || 'Error al eliminar')
                      } finally {
                        setDeletingId(null)
                      }
                    }}
                    style={{
                      padding: '0.4rem',
                      color: 'var(--color-status-error)',
                      background: 'color-mix(in srgb, var(--color-status-error) 15%, transparent)',
                      border: 'none',
                      borderRadius: 6,
                      cursor: deletingId === p.id ? 'wait' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      opacity: deletingId === p.id ? 0.7 : 1,
                    }}
                  >
                    {deletingId === p.id ? (
                      <span style={{ fontSize: '0.75rem' }}>…</span>
                    ) : (
                      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    )}
                  </button>
                  <Link
                    to={`/projects/${p.id}/import`}
                    style={{
                      background: 'transparent',
                      color: 'var(--color-link)',
                      padding: '0.5rem 1rem',
                      borderRadius: 6,
                      fontSize: '0.9rem',
                      fontWeight: 600,
                      textDecoration: 'none',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      transition: 'background 0.2s',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-bg-subtle)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    Abrir
                    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                    </svg>
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}
