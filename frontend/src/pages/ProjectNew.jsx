import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { createProject } from '../api'
import ErrorModal from '../components/ErrorModal'

function slugFromName(name) {
  return name
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .slice(0, 64) || 'proyecto'
}

export default function ProjectNew() {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [schoolName, setSchoolName] = useState('')
  const [schoolCode, setSchoolCode] = useState('')
  const [academicYear, setAcademicYear] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    const projectName = name.trim()
    if (!projectName) {
      setError('El nombre del proyecto es obligatorio.')
      setSubmitting(false)
      return
    }
    const projectKey = slugFromName(projectName)
    try {
      const p = await createProject({
        name: projectName,
        key: projectKey,
        description: description.trim() || null,
        school_name: schoolName.trim() || null,
        school_code: schoolCode.trim() || null,
        academic_year: academicYear.trim() || null,
      })
      navigate(`/projects/${p.id}`)
    } catch (err) {
      const msg = err.message || ''
      if (msg.includes('key already exists') || msg.includes('already exists')) {
        setError(`El proyecto llamado "${projectName}" ya existe.`)
      } else {
        setError(msg || 'Error al crear proyecto')
      }
    } finally {
      setSubmitting(false)
    }
  }

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

  return (
    <main style={{ maxWidth: 560, margin: '2rem auto', padding: '2rem', fontFamily: 'system-ui', background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.05)' }}>
      <p style={{ marginBottom: '1rem' }}>
        <Link to="/projects" style={{ color: 'var(--color-text-muted)', textDecoration: 'none' }}>← Proyectos</Link>
      </p>
      <h1 style={{ margin: '0 0 0.5rem' }}>Crear proyecto</h1>
      <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem', marginBottom: '1.5rem' }}>
        Completa el nombre y los datos del centro educativo.
      </p>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <label>
          <strong>Nombre del proyecto</strong> <span style={{ color: 'crimson' }}>*</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ej. Horarios 2026-2027"
            required
            style={inputStyle}
            onFocus={(e) => e.target.style.borderColor = 'var(--color-btn-primary-bg)'}
            onBlur={(e) => e.target.style.borderColor = 'var(--color-border)'}
          />
        </label>
        <label>
          Descripcion (opcional)
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="Breve descripcion del proyecto"
            style={{ ...inputStyle, resize: 'vertical' }}
            onFocus={(e) => e.target.style.borderColor = 'var(--color-btn-primary-bg)'}
            onBlur={(e) => e.target.style.borderColor = 'var(--color-border)'}
          />
        </label>
        <label>
          Nombre del centro educativo (opcional)
          <input
            type="text"
            value={schoolName}
            onChange={(e) => setSchoolName(e.target.value)}
            placeholder="ej. IES Miguel de Cervantes"
            style={inputStyle}
            onFocus={(e) => e.target.style.borderColor = 'var(--color-btn-primary-bg)'}
            onBlur={(e) => e.target.style.borderColor = 'var(--color-border)'}
          />
        </label>
        <label>
          Codigo del centro (opcional)
          <input
            type="text"
            value={schoolCode}
            onChange={(e) => setSchoolCode(e.target.value)}
            placeholder="ej. 28001234"
            style={inputStyle}
            onFocus={(e) => e.target.style.borderColor = 'var(--color-btn-primary-bg)'}
            onBlur={(e) => e.target.style.borderColor = 'var(--color-border)'}
          />
        </label>
        <label>
          Curso academico (opcional)
          <input
            type="text"
            value={academicYear}
            onChange={(e) => setAcademicYear(e.target.value)}
            placeholder="ej. 2026-2027"
            style={inputStyle}
            onFocus={(e) => e.target.style.borderColor = 'var(--color-btn-primary-bg)'}
            onBlur={(e) => e.target.style.borderColor = 'var(--color-border)'}
          />
        </label>
        <ErrorModal
          message={error}
          onClose={() => setError('')}
          title="Error al crear proyecto"
        />
        <button type="submit" disabled={submitting} style={{ padding: '0.75rem 1.5rem', background: 'var(--color-btn-primary-bg)', color: 'var(--color-btn-primary-text)', border: 'none', borderRadius: 10, cursor: 'pointer', fontSize: '1rem', fontWeight: 600, marginTop: '0.5rem', alignSelf: 'center', minWidth: 200, boxShadow: '0 4px 12px rgba(14, 165, 233, 0.2)' }}>
          {submitting ? 'Creando...' : 'Crear proyecto'}
        </button>
      </form>
    </main>
  )
}
