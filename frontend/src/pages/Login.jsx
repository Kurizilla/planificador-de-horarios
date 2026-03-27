import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import ErrorModal from '../components/ErrorModal'

const inputStyle = {
  display: 'block',
  width: '100%',
  padding: '0.75rem 1rem',
  marginTop: '0.35rem',
  boxSizing: 'border-box',
  border: '1px solid var(--color-border)',
  borderRadius: 10,
  background: 'var(--color-bg)',
  outline: 'none',
  transition: 'border-color 0.15s ease',
}

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [errorTitle, setErrorTitle] = useState('Error al iniciar sesión')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      const msg = err.message || 'Error al iniciar sesión'
      if (msg === 'Failed to fetch' || msg.includes('fetch')) {
        setError('No se pudo conectar con el backend. ¿Está corriendo? (uvicorn en http://localhost:8001)')
        setErrorTitle('Error de conexión')
      } else if (msg.includes('base de datos') || msg.includes('PostgreSQL') || msg.includes('SQLite')) {
        setError(msg)
        setErrorTitle('Base de datos no disponible')
      } else {
        setError(msg)
        setErrorTitle('Error al iniciar sesión')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <main
      style={{
        maxWidth: 420,
        margin: '3rem auto',
        padding: '2rem',
        fontFamily: 'system-ui',
        background: 'var(--color-bg)',
        border: '1px solid var(--color-border)',
        borderRadius: 12,
        boxShadow: '0 4px 20px rgba(0,0,0,0.05)',
      }}
    >
      <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text)' }}>
          Planificador de <span style={{ color: 'var(--color-btn-primary-bg)', opacity: 0.95 }}>Horarios</span>
        </h1>
      </div>
      <h2 style={{ margin: '0 0 0.5rem', fontSize: '1.25rem', fontWeight: 600 }}>Iniciar sesión</h2>
      <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem', marginBottom: '1.5rem' }}>
        Ingresá con tu email y contraseña para acceder a tus proyectos.
      </p>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <label>
          <strong>Email</strong>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={loading}
            placeholder="tu@email.com"
            style={inputStyle}
            onFocus={(e) => (e.target.style.borderColor = 'var(--color-btn-primary-bg)')}
            onBlur={(e) => (e.target.style.borderColor = 'var(--color-border)')}
          />
        </label>
        <label>
          <strong>Contraseña</strong>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={loading}
            placeholder="••••••••"
            style={inputStyle}
            onFocus={(e) => (e.target.style.borderColor = 'var(--color-btn-primary-bg)')}
            onBlur={(e) => (e.target.style.borderColor = 'var(--color-border)')}
          />
        </label>
        <button
          type="submit"
          disabled={loading}
          style={{
            padding: '0.75rem 1.5rem',
            background: loading ? 'var(--color-btn-disabled-bg)' : 'var(--color-btn-primary-bg)',
            color: loading ? 'var(--color-text-muted)' : 'var(--color-btn-primary-text)',
            border: 'none',
            borderRadius: 10,
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '1rem',
            fontWeight: 600,
            marginTop: '0.25rem',
            boxShadow: '0 4px 12px rgba(14, 165, 233, 0.2)',
            transition: 'background 0.15s ease, color 0.15s ease',
          }}
        >
          {loading ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
      <p style={{ marginTop: '1.5rem', fontSize: '0.95rem', color: 'var(--color-text-muted)' }}>
        ¿No tenés cuenta?{' '}
        <Link to="/register" style={{ color: 'var(--color-link)', textDecoration: 'underline', fontWeight: 500 }}>
          Registrarse
        </Link>
      </p>
      <ErrorModal
        message={error}
        title={errorTitle}
        onClose={() => { setError(''); setErrorTitle('Error al iniciar sesión') }}
      />
    </main>
  )
}
