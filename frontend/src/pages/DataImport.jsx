import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  uploadSchoolData, getSchoolDataSummary, deleteSchoolData,
  listTeachers, listSubjects, listSections,
} from '../api'
import FileInput from '../components/FileInput'

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

const btnPrimary = {
  padding: '0.75rem 1.5rem',
  background: 'var(--color-btn-primary-bg)',
  color: 'var(--color-btn-primary-text)',
  border: 'none',
  borderRadius: 10,
  cursor: 'pointer',
  fontSize: '1rem',
  fontWeight: 600,
  minWidth: 180,
  boxShadow: '0 4px 12px rgba(14, 165, 233, 0.2)',
}

const btnDanger = {
  padding: '0.6rem 1.25rem',
  background: 'color-mix(in srgb, var(--color-status-error) 15%, transparent)',
  color: 'var(--color-status-error)',
  border: '1px solid color-mix(in srgb, var(--color-status-error) 30%, transparent)',
  borderRadius: 8,
  cursor: 'pointer',
  fontSize: '0.9rem',
  fontWeight: 600,
}

const tabStyle = (active) => ({
  padding: '0.5rem 1.25rem',
  background: active ? 'var(--color-btn-primary-bg)' : 'var(--color-bg-subtle)',
  color: active ? 'var(--color-btn-primary-text)' : 'var(--color-text-muted)',
  border: 'none',
  borderRadius: '8px 8px 0 0',
  cursor: 'pointer',
  fontWeight: active ? 600 : 400,
  fontSize: '0.9rem',
})

function SummaryCards({ summary }) {
  const cards = [
    { label: 'Docentes', value: summary.teachers_count ?? 0 },
    { label: 'Materias', value: summary.subjects_count ?? 0 },
    { label: 'Secciones', value: summary.sections_count ?? 0 },
    { label: 'Bloques horarios', value: summary.time_slots_count ?? 0 },
  ]
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
      {cards.map((c) => (
        <div key={c.label} style={{ background: 'var(--color-bg-subtle)', borderRadius: 12, padding: '1.25rem', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--color-link)' }}>{c.value}</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>{c.label}</div>
        </div>
      ))}
    </div>
  )
}

function DataTable({ rows, columns }) {
  if (!rows || rows.length === 0) return <p style={{ color: 'var(--color-text-muted)', padding: '1rem' }}>Sin datos.</p>
  return (
    <div style={{ overflowX: 'auto', border: '1px solid var(--color-border)', borderRadius: 8 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} style={{ textAlign: 'left', padding: '0.6rem 0.75rem', borderBottom: '2px solid var(--color-border)', background: 'var(--color-bg-subtle)', fontWeight: 600, whiteSpace: 'nowrap' }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id ?? i} style={{ borderBottom: '1px solid var(--color-border)' }}>
              {columns.map((c) => (
                <td key={c.key} style={{ padding: '0.5rem 0.75rem', whiteSpace: 'nowrap' }}>
                  {c.render ? c.render(row[c.key], row) : (row[c.key] ?? '-')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const teacherCols = [
  { key: 'full_name', label: 'Nombre' },
  { key: 'nip', label: 'NIP' },
  { key: 'specialty', label: 'Especialidad' },
  { key: 'shift', label: 'Turno' },
  { key: 'max_hours_per_week', label: 'Carga max' },
]
const subjectCols = [
  { key: 'code', label: 'Codigo' },
  { key: 'name', label: 'Materia' },
  { key: 'is_remediation', label: 'Remediacion', render: (v) => v ? 'Si' : 'No' },
]
const sectionCols = [
  { key: 'code', label: 'Seccion' },
  { key: 'grade', label: 'Grado' },
  { key: 'shift', label: 'Turno' },
  { key: 'student_count', label: 'Estudiantes' },
]

export default function DataImport() {
  const { id: projectId } = useParams()
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [schoolCode, setSchoolCode] = useState('')
  const [file, setFile] = useState(null)

  // Preview data
  const [activeTab, setActiveTab] = useState('teachers')
  const [teachers, setTeachers] = useState([])
  const [subjects, setSubjects] = useState([])
  const [sections, setSections] = useState([])
  const [previewLoading, setPreviewLoading] = useState(false)

  const loadSummary = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const s = await getSchoolDataSummary(projectId)
      setSummary(s)
      if (!s || (s.teachers_count === 0 && s.subjects_count === 0 && s.sections_count === 0)) {
        setShowForm(true)
      }
    } catch (err) {
      // 404 means no data yet
      const msg = (err.message || '').toLowerCase()
      if (msg.includes('404') || msg.includes('not found') || msg.includes('no school data') || msg.includes('fetch')) {
        setSummary(null)
        setShowForm(true)
      } else {
        setError(err.message || 'Error al cargar resumen')
      }
    } finally {
      setLoading(false)
    }
  }, [projectId])

  const loadPreview = useCallback(async () => {
    setPreviewLoading(true)
    try {
      const [t, su, se] = await Promise.all([
        listTeachers(projectId).catch(() => []),
        listSubjects(projectId).catch(() => []),
        listSections(projectId).catch(() => []),
      ])
      setTeachers(Array.isArray(t) ? t : [])
      setSubjects(Array.isArray(su) ? su : [])
      setSections(Array.isArray(se) ? se : [])
    } finally {
      setPreviewLoading(false)
    }
  }, [projectId])

  useEffect(() => { loadSummary() }, [loadSummary])

  useEffect(() => {
    if (summary && (summary.teachers_count > 0 || summary.subjects_count > 0)) {
      loadPreview()
    }
  }, [summary, loadPreview])

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!file) { setError('Selecciona un archivo Excel.'); return }
    if (!schoolCode.trim()) { setError('Ingresa el codigo del centro.'); return }
    setError('')
    setUploading(true)
    try {
      const result = await uploadSchoolData(projectId, file, schoolCode.trim())
      // Show result as summary immediately
      if (result && result.teachers_count !== undefined) {
        setSummary({
          teachers_count: result.teachers_count,
          subjects_count: result.subjects_count,
          sections_count: result.sections_count,
          teacher_subjects_count: result.teacher_subjects_count,
          grade_subject_loads_count: result.grade_subject_loads_count,
          time_slots_count: result.time_slots_count,
          data_imports: [],
        })
      }
      if (result?.errors?.length) {
        setError(`Importado con ${result.errors.length} error(es): ${result.errors.join('; ')}`)
      }
      setShowForm(false)
      setFile(null)
      // Reload preview data
      loadPreview()
    } catch (err) {
      setError(err.message || 'Error al importar')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async () => {
    if (!window.confirm('Se eliminaran todos los datos importados. ¿Continuar?')) return
    setError('')
    try {
      await deleteSchoolData(projectId)
      setSummary(null)
      setTeachers([])
      setSubjects([])
      setSections([])
      setShowForm(true)
    } catch (err) {
      setError(err.message || 'Error al eliminar datos')
    }
  }

  if (loading) {
    return (
      <main style={{ maxWidth: 800, margin: '2rem auto', padding: '2rem', fontFamily: 'system-ui' }}>
        <p style={{ textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '1.1rem', padding: '3rem' }}>
          Cargando datos del proyecto...
        </p>
      </main>
    )
  }

  return (
    <main style={{ maxWidth: 800, margin: '2rem auto', padding: '2rem', fontFamily: 'system-ui', background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.05)' }}>
      <p style={{ marginBottom: '1rem' }}>
        <Link to="/projects" style={{ color: 'var(--color-text-muted)', textDecoration: 'none' }}>
          ← Proyectos
        </Link>
      </p>
      <h1 style={{ margin: '0 0 0.5rem' }}>Importar Datos Escolares</h1>
      <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem', marginBottom: '1.5rem' }}>
        Sube el archivo Excel con los datos del centro educativo (docentes, materias, secciones).
      </p>

      {error && (
        <div style={{ background: 'color-mix(in srgb, var(--color-status-error) 10%, var(--color-bg))', border: '1px solid color-mix(in srgb, var(--color-status-error) 30%, var(--color-bg))', padding: '0.75rem 1rem', borderRadius: 8, marginBottom: '1.25rem', color: 'var(--color-status-error)', fontSize: '0.95rem' }}>
          {error}
        </div>
      )}

      {/* Summary */}
      {summary && !showForm && (
        <>
          <SummaryCards summary={summary} />
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
            <Link to={`/projects/${projectId}/schedule`} style={{ ...btnPrimary, textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}>
              Ver Horario
            </Link>
            <button type="button" onClick={() => setShowForm(true)} style={btnPrimary}>
              Re-importar
            </button>
            <button type="button" onClick={handleDelete} style={btnDanger}>
              Eliminar datos
            </button>
          </div>

          {/* Tabs */}
          <div style={{ display: 'flex', gap: '0.25rem', borderBottom: '2px solid var(--color-border)' }}>
            {[
              { key: 'teachers', label: `Docentes (${teachers.length})` },
              { key: 'subjects', label: `Materias (${subjects.length})` },
              { key: 'sections', label: `Secciones (${sections.length})` },
            ].map((t) => (
              <button key={t.key} type="button" style={tabStyle(activeTab === t.key)} onClick={() => setActiveTab(t.key)}>
                {t.label}
              </button>
            ))}
          </div>
          <div style={{ marginTop: '1rem' }}>
            {previewLoading ? (
              <p style={{ color: 'var(--color-text-muted)', padding: '1rem' }}>Cargando vista previa...</p>
            ) : (
              <>
                {activeTab === 'teachers' && <DataTable rows={teachers} columns={teacherCols} />}
                {activeTab === 'subjects' && <DataTable rows={subjects} columns={subjectCols} />}
                {activeTab === 'sections' && <DataTable rows={sections} columns={sectionCols} />}
              </>
            )}
          </div>
        </>
      )}

      {/* Upload form */}
      {showForm && (
        <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginTop: summary ? '1.5rem' : 0 }}>
          {summary && (
            <div style={{ padding: '0.75rem 1rem', background: 'color-mix(in srgb, var(--color-status-warning, orange) 10%, var(--color-bg))', borderRadius: 8, fontSize: '0.9rem', color: 'var(--color-text-muted)' }}>
              Al re-importar se reemplazaran todos los datos existentes.
            </div>
          )}
          <label>
            <strong>Codigo del centro</strong> <span style={{ color: 'crimson' }}>*</span>
            <input
              type="text"
              value={schoolCode}
              onChange={(e) => setSchoolCode(e.target.value)}
              placeholder="ej. 28001234"
              required
              style={inputStyle}
              onFocus={(e) => (e.target.style.borderColor = 'var(--color-btn-primary-bg)')}
              onBlur={(e) => (e.target.style.borderColor = 'var(--color-border)')}
            />
          </label>
          <div>
            <strong>Archivo Excel</strong> <span style={{ color: 'crimson' }}>*</span>
            <FileInput
              accept=".xlsx,.xls"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              disabled={uploading}
              placeholder="Seleccionar archivo .xlsx"
            />
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginTop: '0.5rem' }}>
            <button type="submit" disabled={uploading} style={{ ...btnPrimary, opacity: uploading ? 0.7 : 1, cursor: uploading ? 'wait' : 'pointer' }}>
              {uploading ? 'Importando...' : 'Importar'}
            </button>
            {summary && (
              <button type="button" onClick={() => setShowForm(false)} style={{ padding: '0.75rem 1.25rem', background: 'none', color: 'var(--color-text-muted)', border: '1px solid var(--color-border)', borderRadius: 10, cursor: 'pointer', fontSize: '0.95rem' }}>
                Cancelar
              </button>
            )}
          </div>
        </form>
      )}
    </main>
  )
}
