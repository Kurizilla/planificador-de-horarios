import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'

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

export default function Register() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { register } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await register(email, password, fullName || null)
      navigate('/')
    } catch (err) {
      setError(err.message || 'Error al registrarse')
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
      <h1 style={{ margin: '0 0 0.5rem' }}>Registrarse</h1>
      <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem', marginBottom: '1.5rem' }}>
        Creá una cuenta para gestionar tus proyectos y estructuras.
      </p>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <label>
          <strong>Email</strong> <span style={{ color: 'var(--color-text-muted)', fontWeight: 400 }}>(requerido)</span>
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
          <strong>Nombre</strong> <span style={{ color: 'var(--color-text-muted)', fontWeight: 400 }}>(opcional)</span>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            disabled={loading}
            placeholder="Tu nombre"
            style={inputStyle}
            onFocus={(e) => (e.target.style.borderColor = 'var(--color-btn-primary-bg)')}
            onBlur={(e) => (e.target.style.borderColor = 'var(--color-border)')}
          />
        </label>
        <label>
          <strong>Contraseña</strong> <span style={{ color: 'var(--color-text-muted)', fontWeight: 400 }}>(mín. 8 caracteres)</span>
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
        {error && (
          <p style={{ color: 'var(--color-status-error)', margin: 0, fontSize: '0.9rem' }}>{error}</p>
        )}
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
          {loading ? 'Creando cuenta…' : 'Crear cuenta'}
        </button>
      </form>
      <p style={{ marginTop: '1.5rem', fontSize: '0.95rem', color: 'var(--color-text-muted)' }}>
        ¿Ya tenés cuenta?{' '}
        <Link to="/login" style={{ color: 'var(--color-link)', textDecoration: 'underline', fontWeight: 500 }}>
          Iniciar sesión
        </Link>
      </p>
    </main>
  )
}
