import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  listScheduleVersions, getScheduleEntries, generateSchedule,
  validateSchedule, validateAndApprove, listSections, getProject,
  exportScheduleExcel, listTimeSlots, moveScheduleEntry,
} from '../api'
import ScheduleAssistantWidget from '../components/ScheduleAssistantWidget'

const DAY_NAMES = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes']
// day_of_week comes as int from API: 0=Mon, 1=Tue, etc.

const SUBJECT_COLORS = {
  LEN: '#4A90D9', MAT: '#E74C3C', CIE: '#2ECC71', SOC: '#F39C12',
  ART: '#9B59B6', EDF: '#95A5A6', ING: '#1ABC9C', RE_LEN: '#85C1E9', RE_MAT: '#F1948A',
}

const FALLBACK_COLORS = ['#3498DB','#E67E22','#27AE60','#8E44AD','#E74C3C','#1ABC9C','#D35400','#2980B9','#16A085','#C0392B']

function subjectColor(code, color) {
  if (color) return color
  if (code && SUBJECT_COLORS[code]) return SUBJECT_COLORS[code]
  if (!code) return '#95A5A6'
  let hash = 0
  for (let i = 0; i < code.length; i++) hash = code.charCodeAt(i) + ((hash << 5) - hash)
  return FALLBACK_COLORS[Math.abs(hash) % FALLBACK_COLORS.length]
}

function abbreviate(name) {
  if (!name) return ''
  const parts = name.split(' ')
  if (parts.length <= 2) return name
  return parts.map((p, i) => i === 0 ? p : p[0] + '.').join(' ')
}

// Styles
const btnPrimary = {
  padding: '0.6rem 1.25rem', background: 'var(--color-btn-primary-bg)',
  color: 'var(--color-btn-primary-text)', border: 'none', borderRadius: 8,
  cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600,
  boxShadow: '0 2px 8px rgba(14,165,233,0.15)',
}
const btnSecondary = {
  padding: '0.6rem 1.25rem', background: 'var(--color-bg-subtle)',
  color: 'var(--color-text)', border: '1px solid var(--color-border)', borderRadius: 8,
  cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500,
}
const selectStyle = {
  padding: '0.5rem 0.75rem', border: '1px solid var(--color-border)', borderRadius: 8,
  background: 'var(--color-bg)', fontSize: '0.9rem', outline: 'none',
}
const tabStyle = (active) => ({
  padding: '0.5rem 1.25rem',
  background: active ? 'var(--color-btn-primary-bg)' : 'var(--color-bg-subtle)',
  color: active ? 'var(--color-btn-primary-text)' : 'var(--color-text-muted)',
  border: 'none', borderRadius: '8px 8px 0 0', cursor: 'pointer',
  fontWeight: active ? 600 : 400, fontSize: '0.85rem',
})

function StatCard({ label, value, color }) {
  return (
    <div style={{ background: 'var(--color-bg-subtle)', borderRadius: 10, padding: '0.75rem 1rem', textAlign: 'center', minWidth: 90 }}>
      <div style={{ fontSize: '1.5rem', fontWeight: 800, color: color || 'var(--color-link)' }}>{value}</div>
      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '0.15rem' }}>{label}</div>
    </div>
  )
}

function ScheduleGrid({ entries, viewMode, projectId, versionId, onEntriesChanged, allTimeSlots }) {
  const [draggedEntryId, setDraggedEntryId] = useState(null)
  const [dragOverCell, setDragOverCell] = useState(null)
  const [movingCell, setMovingCell] = useState(null)
  const [justDroppedCells, setJustDroppedCells] = useState(new Set())

  const isDragEnabled = viewMode === 'section' && !!projectId && !!versionId && !!onEntriesChanged

  // Build a lookup: (day_of_week, slot_order) -> time_slot_id from allTimeSlots
  const timeSlotLookup = useMemo(() => {
    const lookup = {}
    if (allTimeSlots) {
      allTimeSlots.forEach(ts => {
        const key = `${ts.start_time}-${ts.end_time}-${ts.day_of_week}`
        lookup[key] = ts.id
      })
    }
    return lookup
  }, [allTimeSlots])

  const { slotLabels, grid } = useMemo(() => {
    if (!entries || entries.length === 0) return { slotLabels: [], grid: {} }

    // Build unique time slots sorted by slot_order then start_time
    const slotMap = new Map()
    entries.forEach(e => {
      const key = `${e.start_time}-${e.end_time}`
      if (!slotMap.has(key)) {
        slotMap.set(key, { start: e.start_time, end: e.end_time, order: e.slot_order ?? 0 })
      }
    })
    const slots = [...slotMap.entries()].sort((a, b) => a[1].order - b[1].order || a[1].start.localeCompare(b[1].start))
    const labels = slots.map(([key, v]) => ({ key, label: `${v.start?.slice(0, 5)} - ${v.end?.slice(0, 5)}` }))

    // Build grid: grid[slotKey][dayIndex] = entry
    const g = {}
    labels.forEach(s => { g[s.key] = {} })
    entries.forEach(e => {
      const slotKey = `${e.start_time}-${e.end_time}`
      const dayIdx = typeof e.day_of_week === 'number' ? e.day_of_week : -1
      if (dayIdx >= 0 && g[slotKey]) {
        g[slotKey][dayIdx] = e
      }
    })

    return { slotLabels: labels, grid: g }
  }, [entries])

  const handleDragStart = useCallback((ev, entry) => {
    if (!isDragEnabled || entry.is_locked) return
    ev.dataTransfer.setData('text/plain', JSON.stringify({
      entryId: entry.id,
      timeSlotId: entry.time_slot_id,
    }))
    ev.dataTransfer.effectAllowed = 'move'
    setDraggedEntryId(entry.id)
  }, [isDragEnabled])

  const handleDragEnd = useCallback(() => {
    setDraggedEntryId(null)
    setDragOverCell(null)
  }, [])

  const handleDragOver = useCallback((ev) => {
    ev.preventDefault()
    ev.dataTransfer.dropEffect = 'move'
  }, [])

  const handleDragEnter = useCallback((cellKey) => {
    setDragOverCell(cellKey)
  }, [])

  const handleDragLeave = useCallback((ev, cellKey) => {
    // Only clear if leaving the cell entirely (not entering a child)
    if (!ev.currentTarget.contains(ev.relatedTarget)) {
      setDragOverCell(prev => prev === cellKey ? null : prev)
    }
  }, [])

  const handleDrop = useCallback(async (ev, slotKey, dayIdx) => {
    ev.preventDefault()
    setDragOverCell(null)
    setDraggedEntryId(null)

    if (!isDragEnabled) return

    let data
    try {
      data = JSON.parse(ev.dataTransfer.getData('text/plain'))
    } catch { return }

    // Find the target time_slot_id
    const targetEntry = grid[slotKey]?.[dayIdx]
    let targetTimeSlotId = targetEntry?.time_slot_id

    // If empty cell, look up from allTimeSlots
    if (!targetTimeSlotId) {
      const lookupKey = `${slotKey}-${dayIdx}`
      targetTimeSlotId = timeSlotLookup[lookupKey]
    }

    if (!targetTimeSlotId || targetTimeSlotId === data.timeSlotId) return

    // Don't drop onto a locked entry
    if (targetEntry?.is_locked) return

    const cellKey = `${slotKey}-${dayIdx}`
    setMovingCell(cellKey)

    try {
      await moveScheduleEntry(projectId, versionId, data.entryId, targetTimeSlotId)
      setJustDroppedCells(new Set([cellKey]))
      setTimeout(() => setJustDroppedCells(new Set()), 1500)
      if (onEntriesChanged) onEntriesChanged()
    } catch (err) {
      console.error('Move failed:', err)
    } finally {
      setMovingCell(null)
    }
  }, [isDragEnabled, grid, timeSlotLookup, projectId, versionId, onEntriesChanged])

  if (slotLabels.length === 0) {
    return <p style={{ color: 'var(--color-text-muted)', padding: '2rem', textAlign: 'center' }}>No hay bloques horarios para mostrar.</p>
  }

  return (
    <div style={{ overflowX: 'auto', border: '1px solid var(--color-border)', borderRadius: 10 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', tableLayout: 'fixed' }}>
        <thead>
          <tr>
            <th style={{ width: 100, padding: '0.6rem 0.5rem', background: 'var(--color-bg-subtle)', borderBottom: '2px solid var(--color-border)', fontSize: '0.8rem', fontWeight: 600 }}>Hora</th>
            {DAY_NAMES.map(d => (
              <th key={d} style={{ padding: '0.6rem 0.5rem', background: 'var(--color-bg-subtle)', borderBottom: '2px solid var(--color-border)', fontSize: '0.8rem', fontWeight: 600, textAlign: 'center' }}>{d}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {slotLabels.map(slot => (
            <tr key={slot.key}>
              <td style={{ padding: '0.4rem 0.5rem', borderBottom: '1px solid var(--color-border)', fontSize: '0.75rem', color: 'var(--color-text-muted)', whiteSpace: 'nowrap', fontWeight: 500 }}>
                {slot.label}
              </td>
              {DAY_NAMES.map((_, dayIdx) => {
                const entry = grid[slot.key]?.[dayIdx]
                const cellKey = `${slot.key}-${dayIdx}`
                const isDragOver = dragOverCell === cellKey
                const isMoving = movingCell === cellKey
                const isJustDropped = justDroppedCells.has(cellKey)

                const tdDropStyles = isDragEnabled && isDragOver ? {
                  outline: '2px dashed #3498DB',
                  outlineOffset: -2,
                  background: 'rgba(52, 152, 219, 0.08)',
                } : {}

                const tdSuccessStyles = isJustDropped ? {
                  outline: '2px solid #2ECC71',
                  outlineOffset: -2,
                  transition: 'outline-color 1.5s ease',
                } : {}

                if (!entry) {
                  return (
                    <td
                      key={dayIdx}
                      onDragOver={isDragEnabled ? handleDragOver : undefined}
                      onDragEnter={isDragEnabled ? () => handleDragEnter(cellKey) : undefined}
                      onDragLeave={isDragEnabled ? (ev) => handleDragLeave(ev, cellKey) : undefined}
                      onDrop={isDragEnabled ? (ev) => handleDrop(ev, slot.key, dayIdx) : undefined}
                      style={{
                        padding: '0.4rem 0.3rem', borderBottom: '1px solid var(--color-border)',
                        textAlign: 'center', background: 'var(--color-bg-subtle)',
                        color: 'var(--color-text-muted)',
                        ...tdDropStyles, ...tdSuccessStyles,
                      }}
                    >
                      {isMoving ? '...' : '\u2014'}
                    </td>
                  )
                }
                const bg = subjectColor(entry.subject_code, entry.subject_color)
                const hasConflict = entry.conflict_flags && entry.conflict_flags.length > 0
                const isDragged = draggedEntryId === entry.id
                const canDrag = isDragEnabled && !entry.is_locked
                const secondLine = viewMode === 'teacher'
                  ? (entry.section_code || entry.section_grade || '')
                  : abbreviate(entry.teacher_name)
                return (
                  <td
                    key={dayIdx}
                    onDragOver={isDragEnabled ? handleDragOver : undefined}
                    onDragEnter={isDragEnabled ? () => handleDragEnter(cellKey) : undefined}
                    onDragLeave={isDragEnabled ? (ev) => handleDragLeave(ev, cellKey) : undefined}
                    onDrop={isDragEnabled ? (ev) => handleDrop(ev, slot.key, dayIdx) : undefined}
                    style={{
                      padding: '0.3rem', borderBottom: '1px solid var(--color-border)', textAlign: 'center',
                      ...tdDropStyles, ...tdSuccessStyles,
                    }}
                  >
                    <div
                      draggable={canDrag}
                      onDragStart={canDrag ? (ev) => handleDragStart(ev, entry) : undefined}
                      onDragEnd={canDrag ? handleDragEnd : undefined}
                      style={{
                        background: bg, color: '#fff', borderRadius: 6, padding: '0.35rem 0.25rem',
                        fontSize: '0.78rem', lineHeight: 1.3, position: 'relative', minHeight: 38,
                        display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
                        border: hasConflict ? '2px solid #E74C3C' : '1px solid rgba(0,0,0,0.1)',
                        boxShadow: hasConflict ? '0 0 6px rgba(231,76,60,0.4)' : 'none',
                        opacity: isDragged ? 0.4 : (isMoving ? 0.6 : 1),
                        cursor: canDrag ? 'grab' : 'default',
                        transition: 'opacity 0.2s ease',
                    }}>
                      {hasConflict && (
                        <span style={{ position: 'absolute', top: 1, right: 3, fontSize: '0.65rem' }} title={entry.conflict_flags.join(', ')}>!</span>
                      )}
                      {entry.is_locked && (
                        <span style={{ position: 'absolute', top: 1, left: 3, fontSize: '0.6rem' }} title="Bloqueado">L</span>
                      )}
                      <div style={{ fontWeight: 700, fontSize: '0.8rem' }}>{entry.subject_name || entry.subject_code || '?'}</div>
                      {secondLine && <div style={{ fontSize: '0.7rem', opacity: 0.9, marginTop: 1 }}>{secondLine}</div>}
                    </div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ValidationPanel({ result, onClose }) {
  if (!result) return null
  return (
    <div style={{
      background: result.valid ? 'color-mix(in srgb, var(--color-status-success, #2ecc71) 10%, var(--color-bg))' : 'color-mix(in srgb, var(--color-status-error) 10%, var(--color-bg))',
      border: `1px solid ${result.valid ? 'color-mix(in srgb, var(--color-status-success, #2ecc71) 30%, var(--color-bg))' : 'color-mix(in srgb, var(--color-status-error) 30%, var(--color-bg))'}`,
      borderRadius: 8, padding: '1rem', marginBottom: '1rem',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <strong>{result.valid ? 'Horario valido' : 'Se encontraron problemas'}</strong>
        <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.1rem', color: 'var(--color-text-muted)' }}>x</button>
      </div>
      {result.conflicts?.length > 0 && (
        <div style={{ marginBottom: '0.5rem' }}>
          <strong style={{ fontSize: '0.85rem', color: 'var(--color-status-error)' }}>Conflictos ({result.conflicts.length}):</strong>
          <ul style={{ margin: '0.25rem 0 0 1.25rem', fontSize: '0.85rem', paddingLeft: 0, listStyle: 'disc' }}>
            {result.conflicts.slice(0, 10).map((c, i) => <li key={i}>{c.description || c.type}</li>)}
            {result.conflicts.length > 10 && <li>...y {result.conflicts.length - 10} mas</li>}
          </ul>
        </div>
      )}
      {result.warnings?.length > 0 && (
        <div>
          <strong style={{ fontSize: '0.85rem', color: 'var(--color-status-warning, orange)' }}>Advertencias ({result.warnings.length}):</strong>
          <ul style={{ margin: '0.25rem 0 0 1.25rem', fontSize: '0.85rem', paddingLeft: 0, listStyle: 'disc' }}>
            {result.warnings.slice(0, 10).map((w, i) => <li key={i}>{w.description || w.type}</li>)}
            {result.warnings.length > 10 && <li>...y {result.warnings.length - 10} mas</li>}
          </ul>
        </div>
      )}
    </div>
  )
}

export default function ScheduleView() {
  const { id: projectId } = useParams()
  const [project, setProject] = useState(null)
  const [versions, setVersions] = useState([])
  const [selectedVersion, setSelectedVersion] = useState(null)
  const [entries, setEntries] = useState([])
  const [sections, setSections] = useState([])
  const [selectedSection, setSelectedSection] = useState('')
  const [shift, setShift] = useState('morning')
  const [viewMode, setViewMode] = useState('section') // section | teacher
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
  const [allTimeSlots, setAllTimeSlots] = useState([])

  // Load project info
  useEffect(() => {
    getProject(projectId).then(setProject).catch(() => {})
  }, [projectId])

  // Load versions
  const loadVersions = useCallback(async () => {
    try {
      const v = await listScheduleVersions(projectId)
      const list = Array.isArray(v) ? v : []
      setVersions(list)
      return list
    } catch {
      setVersions([])
      return []
    }
  }, [projectId])

  // Load sections
  const loadSections = useCallback(async () => {
    try {
      const s = await listSections(projectId, shift)
      setSections(Array.isArray(s) ? s : [])
    } catch {
      setSections([])
    }
  }, [projectId, shift])

  // Load time slots for drag-and-drop (empty cell targets)
  const loadTimeSlots = useCallback(async () => {
    try {
      const ts = await listTimeSlots(projectId, shift)
      setAllTimeSlots(Array.isArray(ts) ? ts : [])
    } catch {
      setAllTimeSlots([])
    }
  }, [projectId, shift])

  // Load entries
  const loadEntries = useCallback(async (versionId, sectionId) => {
    if (!versionId) { setEntries([]); return }
    try {
      const e = await getScheduleEntries(projectId, versionId, sectionId || undefined)
      setEntries(Array.isArray(e) ? e : [])
    } catch {
      setEntries([])
    }
  }, [projectId])

  // Initial load
  useEffect(() => {
    setLoading(true)
    Promise.all([loadVersions(), loadSections(), loadTimeSlots()]).then(([vList]) => {
      const shiftVersions = vList.filter(v => v.shift === shift)
      if (shiftVersions.length > 0) {
        const latest = shiftVersions[shiftVersions.length - 1]
        setSelectedVersion(latest.id)
      } else {
        setSelectedVersion(null)
      }
    }).finally(() => setLoading(false))
  }, [loadVersions, loadSections, loadTimeSlots, shift])

  // Load entries when version or section changes
  useEffect(() => {
    if (selectedVersion) {
      loadEntries(selectedVersion, selectedSection || null)
    } else {
      setEntries([])
    }
  }, [selectedVersion, selectedSection, loadEntries])

  // Filtered versions by shift
  const filteredVersions = useMemo(() => versions.filter(v => v.shift === shift), [versions, shift])

  // Filtered sections by shift
  const filteredSections = useMemo(() => sections, [sections])

  // Unique teachers from entries (for teacher view)
  const teachers = useMemo(() => {
    const map = new Map()
    entries.forEach(e => {
      if (e.teacher_id && e.teacher_name) map.set(e.teacher_id, e.teacher_name)
    })
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [entries])

  // Stats
  const stats = useMemo(() => {
    const ver = versions.find(v => v.id === selectedVersion)
    return {
      entries: entries.length,
      conflicts: ver?.conflicts_count ?? entries.filter(e => e.conflict_flags?.length > 0).length,
      warnings: ver?.warnings_count ?? 0,
      unassigned: ver?.unassigned_slots ?? 0,
    }
  }, [entries, versions, selectedVersion])

  const handleGenerate = async () => {
    setError('')
    setGenerating(true)
    try {
      const label = `${shift === 'morning' ? 'Matutino' : 'Vespertino'} - Auto`
      const result = await generateSchedule(projectId, shift, label)
      const vList = await loadVersions()
      const newVersion = result?.version?.id || vList[vList.length - 1]?.id
      if (newVersion) setSelectedVersion(newVersion)
      setSelectedSection('')
    } catch (err) {
      setError(err.message || 'Error al generar horario')
    } finally {
      setGenerating(false)
    }
  }

  const handleValidate = async (approve) => {
    if (!selectedVersion) return
    setValidating(true)
    setError('')
    try {
      const result = approve
        ? await validateAndApprove(projectId, selectedVersion)
        : await validateSchedule(projectId, selectedVersion)
      setValidationResult(result)
      if (approve) await loadVersions()
    } catch (err) {
      setError(err.message || 'Error al validar')
    } finally {
      setValidating(false)
    }
  }

  if (loading) {
    return (
      <main style={{ maxWidth: 1100, margin: '2rem auto', padding: '2rem', fontFamily: 'system-ui' }}>
        <p style={{ textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '1.1rem', padding: '3rem' }}>
          Cargando horarios...
        </p>
      </main>
    )
  }

  return (
    <main style={{ maxWidth: 1100, margin: '1.5rem auto', padding: '1.5rem', fontFamily: 'system-ui', background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.05)' }}>
      {/* Breadcrumb */}
      <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <Link to="/projects" style={{ color: 'var(--color-text-muted)', textDecoration: 'none', fontSize: '0.9rem' }}>Proyectos</Link>
        <span style={{ color: 'var(--color-text-muted)' }}>/</span>
        <Link to={`/projects/${projectId}/import`} style={{ color: 'var(--color-text-muted)', textDecoration: 'none', fontSize: '0.9rem' }}>Datos</Link>
        <span style={{ color: 'var(--color-text-muted)' }}>/</span>
        <span style={{ fontSize: '0.9rem' }}>Horario</span>
      </div>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem' }}>{project?.name || 'Horario'}</h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', margin: '0.25rem 0 0' }}>Planificacion de horarios</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Shift toggle */}
          <div style={{ display: 'flex', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--color-border)' }}>
            {[{ key: 'morning', label: 'Matutino' }, { key: 'afternoon', label: 'Vespertino' }].map(s => (
              <button key={s.key} onClick={() => { setShift(s.key); setSelectedSection(''); setValidationResult(null) }}
                style={{ padding: '0.45rem 1rem', border: 'none', cursor: 'pointer', fontSize: '0.85rem', fontWeight: shift === s.key ? 600 : 400, background: shift === s.key ? 'var(--color-btn-primary-bg)' : 'var(--color-bg)', color: shift === s.key ? 'var(--color-btn-primary-text)' : 'var(--color-text-muted)' }}>
                {s.label}
              </button>
            ))}
          </div>
          {/* Version selector */}
          {filteredVersions.length > 0 && (
            <select value={selectedVersion || ''} onChange={e => { setSelectedVersion(e.target.value); setValidationResult(null) }} style={selectStyle}>
              {filteredVersions.map(v => (
                <option key={v.id} value={v.id}>v{v.version_number} {v.label ? `- ${v.label}` : ''} ({v.status})</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{ background: 'color-mix(in srgb, var(--color-status-error) 10%, var(--color-bg))', border: '1px solid color-mix(in srgb, var(--color-status-error) 30%, var(--color-bg))', padding: '0.75rem 1rem', borderRadius: 8, marginBottom: '1rem', color: 'var(--color-status-error)', fontSize: '0.9rem', display: 'flex', justifyContent: 'space-between' }}>
          <span>{error}</span>
          <button onClick={() => setError('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-status-error)' }}>x</button>
        </div>
      )}

      {/* Validation */}
      <ValidationPanel result={validationResult} onClose={() => setValidationResult(null)} />

      {/* No schedule state */}
      {filteredVersions.length === 0 && (
        <div style={{ textAlign: 'center', padding: '3rem 1rem', background: 'var(--color-bg-subtle)', borderRadius: 10, marginBottom: '1rem' }}>
          <p style={{ fontSize: '1.1rem', marginBottom: '1rem', color: 'var(--color-text-muted)' }}>
            No hay horarios generados para el turno {shift === 'morning' ? 'matutino' : 'vespertino'}.
          </p>
          <button onClick={handleGenerate} disabled={generating} style={{ ...btnPrimary, fontSize: '1rem', padding: '0.75rem 2rem', opacity: generating ? 0.7 : 1 }}>
            {generating ? 'Generando...' : 'Generar Horario'}
          </button>
        </div>
      )}

      {/* Schedule content */}
      {filteredVersions.length > 0 && selectedVersion && (
        <>
          {/* Stats */}
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
            <StatCard label="Bloques" value={stats.entries} />
            <StatCard label="Sin asignar" value={stats.unassigned} color={stats.unassigned > 0 ? 'var(--color-status-warning, orange)' : undefined} />
            <StatCard label="Conflictos" value={stats.conflicts} color={stats.conflicts > 0 ? 'var(--color-status-error)' : undefined} />
            <StatCard label="Advertencias" value={stats.warnings} color={stats.warnings > 0 ? 'var(--color-status-warning, orange)' : undefined} />
          </div>

          {/* View mode tabs + Section/Teacher selector */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', gap: '0.25rem', borderBottom: '2px solid var(--color-border)' }}>
              <button onClick={() => { setViewMode('section'); setSelectedSection('') }} style={tabStyle(viewMode === 'section')}>Por Seccion</button>
              <button onClick={() => { setViewMode('teacher'); setSelectedSection('') }} style={tabStyle(viewMode === 'teacher')}>Por Docente</button>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              {viewMode === 'section' && filteredSections.length > 0 && (
                <select value={selectedSection} onChange={e => setSelectedSection(e.target.value)} style={selectStyle}>
                  <option value="">Todas las secciones</option>
                  {filteredSections.map(s => (
                    <option key={s.id} value={s.id}>{s.grade} - {s.code || s.name}</option>
                  ))}
                </select>
              )}
              {viewMode === 'teacher' && teachers.length > 0 && (
                <select value={selectedSection} onChange={e => setSelectedSection(e.target.value)} style={selectStyle}>
                  <option value="">Todos los docentes</option>
                  {teachers.map(([tid, tname]) => (
                    <option key={tid} value={tid}>{tname}</option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Grid */}
          {viewMode === 'section' ? (
            selectedSection ? (
              <ScheduleGrid entries={entries} viewMode={viewMode} projectId={projectId} versionId={selectedVersion} onEntriesChanged={() => loadEntries(selectedVersion, selectedSection)} allTimeSlots={allTimeSlots} />
            ) : (
              /* Show grids for each section */
              filteredSections.length > 0 ? (
                <SectionGrids sections={filteredSections} projectId={projectId} versionId={selectedVersion} viewMode={viewMode} onEntriesChanged={() => loadEntries(selectedVersion, selectedSection)} allTimeSlots={allTimeSlots} />
              ) : (
                <ScheduleGrid entries={entries} viewMode={viewMode} projectId={projectId} versionId={selectedVersion} onEntriesChanged={() => loadEntries(selectedVersion, selectedSection)} allTimeSlots={allTimeSlots} />
              )
            )
          ) : (
            selectedSection ? (
              <ScheduleGrid entries={entries.filter(e => e.teacher_id === selectedSection)} viewMode={viewMode} />
            ) : (
              /* Show all entries in a single grid when no teacher selected */
              teachers.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  {teachers.map(([tid, tname]) => {
                    const teacherEntries = entries.filter(e => e.teacher_id === tid)
                    return (
                      <div key={tid}>
                        <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>{tname}</h3>
                        <ScheduleGrid entries={teacherEntries} viewMode={viewMode} />
                      </div>
                    )
                  })}
                </div>
              ) : (
                <ScheduleGrid entries={entries} viewMode={viewMode} />
              )
            )
          )}

          {/* Toolbar */}
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1.25rem', flexWrap: 'wrap' }}>
            <button onClick={handleGenerate} disabled={generating} style={{ ...btnSecondary, opacity: generating ? 0.7 : 1 }}>
              {generating ? 'Generando...' : 'Regenerar'}
            </button>
            <button onClick={() => handleValidate(false)} disabled={validating} style={{ ...btnSecondary, opacity: validating ? 0.7 : 1 }}>
              {validating ? 'Validando...' : 'Validar'}
            </button>
            <button onClick={() => handleValidate(true)} disabled={validating} style={{ ...btnPrimary, opacity: validating ? 0.7 : 1 }}>
              Validar y Aprobar
            </button>
            <button
              onClick={async () => {
                if (!selectedVersion) return
                setExporting(true)
                setError('')
                try {
                  await exportScheduleExcel(projectId, selectedVersion)
                } catch (err) {
                  setError(err.message || 'Error al exportar')
                } finally {
                  setExporting(false)
                }
              }}
              disabled={!selectedVersion || exporting}
              style={{ ...btnSecondary, opacity: (!selectedVersion || exporting) ? 0.7 : 1 }}
            >
              {exporting ? 'Exportando...' : 'Exportar Excel'}
            </button>
          </div>
        </>
      )}

      {selectedVersion && (
        <ScheduleAssistantWidget
          projectId={projectId}
          scheduleVersionId={selectedVersion}
          onActionsApplied={() => loadEntries(selectedVersion, selectedSection || null)}
        />
      )}
    </main>
  )
}

/* Sub-component: loads entries per section and renders individual grids */
function SectionGrids({ sections, projectId, versionId, viewMode, onEntriesChanged, allTimeSlots }) {
  const [sectionEntries, setSectionEntries] = useState({})
  const [loading, setLoading] = useState(true)

  const reloadAll = useCallback(() => {
    setLoading(true)
    Promise.all(
      sections.map(s =>
        getScheduleEntries(projectId, versionId, s.id)
          .then(entries => ({ id: s.id, entries: Array.isArray(entries) ? entries : [] }))
          .catch(() => ({ id: s.id, entries: [] }))
      )
    ).then(results => {
      const map = {}
      results.forEach(r => { map[r.id] = r.entries })
      setSectionEntries(map)
    }).finally(() => setLoading(false))
  }, [sections, projectId, versionId])

  useEffect(() => {
    reloadAll()
  }, [reloadAll])

  if (loading) {
    return <p style={{ color: 'var(--color-text-muted)', padding: '1rem', textAlign: 'center' }}>Cargando secciones...</p>
  }

  // Only show sections that have entries
  const populated = sections.filter(s => sectionEntries[s.id]?.length > 0)
  if (populated.length === 0) {
    return <p style={{ color: 'var(--color-text-muted)', padding: '2rem', textAlign: 'center' }}>No hay entradas asignadas.</p>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {populated.map(s => (
        <div key={s.id}>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>{s.grade} - {s.code || s.name} {s.student_count ? `(${s.student_count} est.)` : ''}</h3>
          <ScheduleGrid entries={sectionEntries[s.id]} viewMode={viewMode} projectId={projectId} versionId={versionId} onEntriesChanged={() => { reloadAll(); if (onEntriesChanged) onEntriesChanged() }} allTimeSlots={allTimeSlots} />
        </div>
      ))}
    </div>
  )
}
