import { useState, useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { listUsers, createUser, updateUser, api } from '../api'

export default function UserManagement() {
  const { user } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [addForm, setAddForm] = useState({ email: '', password: '', full_name: '', role: 'PRODUCT_OWNER' })
  const [editForm, setEditForm] = useState({ full_name: '', role: 'PRODUCT_OWNER', is_active: true, password: '' })

  if (!user || user.role !== 'ADMIN') {
    return <Navigate to="/" replace />
  }

  const load = () => {
    setError('')
    setLoading(true)
    listUsers()
      .then(setUsers)
      .catch((err) => setError(err.message || 'Error loading users'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const handleAdd = (e) => {
    e.preventDefault()
    if (!addForm.email.trim() || !addForm.password) {
      setError('Email and password are required')
      return
    }
    setError('')
    createUser({
      email: addForm.email.trim(),
      password: addForm.password,
      full_name: addForm.full_name.trim() || null,
      role: addForm.role,
    })
      .then(() => {
        setShowAddModal(false)
        setAddForm({ email: '', password: '', full_name: '', role: 'PRODUCT_OWNER' })
        load()
      })
      .catch((err) => setError(err.message || 'Error creating user'))
  }

  const startEdit = (u) => {
    setEditingId(u.id)
    setEditForm({
      full_name: u.full_name || '',
      role: u.role,
      is_active: u.is_active,
      password: '',
    })
    setShowEditModal(true)
    setError('')
  }

  const handleEdit = (e) => {
    e.preventDefault()
    if (!editingId) return
    if (editForm.password && editForm.password.length > 0 && editForm.password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    setError('')
    const body = {}
    if (editForm.full_name !== undefined) body.full_name = editForm.full_name.trim() || null
    if (editForm.role !== undefined) body.role = editForm.role
    if (editForm.is_active !== undefined) body.is_active = editForm.is_active
    let promise = updateUser(editingId, body)
    if (editForm.password && editForm.password.length >= 8) {
      promise = promise.then(() =>
        api(`/users/${editingId}/password`, {
          method: 'POST',
          body: JSON.stringify({ password: editForm.password }),
        }),
      )
    }
    promise
      .then(() => {
        setEditingId(null)
        setEditForm({ full_name: '', role: 'PRODUCT_OWNER', is_active: true, password: '' })
        setShowEditModal(false)
        load()
      })
      .catch((err) => setError(err.message || 'Error updating user'))
  }

  const handleDelete = (userId) => {
    if (!window.confirm('Are you sure you want to delete this user?')) return
    setError('')
    api(`/users/${userId}`, { method: 'DELETE' })
      .then(() => {
        load()
      })
      .catch((err) => setError(err.message || 'Error deleting user'))
  }

  const inputStyle = {
    width: '100%',
    padding: '0.75rem 1rem',
    borderRadius: 8,
    border: '1px solid var(--color-border)',
    background: 'var(--color-bg)',
    color: 'var(--color-text)',
    fontSize: '1rem',
    boxSizing: 'border-box',
    marginBottom: '1rem',
  }

  const labelStyle = {
    display: 'block',
    marginBottom: '0.4rem',
    fontWeight: 600,
    fontSize: '0.9rem',
  }

  if (loading) return (
    <main style={{ maxWidth: 1000, margin: '0 auto', padding: '3rem 2rem', fontFamily: 'system-ui' }}>
      <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
        <p style={{ fontSize: '1.25rem', color: 'var(--color-text-muted)' }}>Cargando usuarios…</p>
      </div>
    </main>
  )

  return (
    <main style={{ maxWidth: 1000, margin: '0 auto', padding: '3rem 2rem', fontFamily: 'system-ui' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '3rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ margin: '0 0 0.5rem 0', fontSize: '2.5rem', fontWeight: 800, letterSpacing: '-0.05em' }}>User management</h1>
          <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '1.1rem' }}>Administra los accesos y roles a la plataforma</p>
        </div>
        <button
          type="button"
          onClick={() => { setShowAddModal(true); setError(''); }}
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
          Add user
        </button>
      </div>

      {error && !showAddModal && !showEditModal && (
        <div style={{ background: 'color-mix(in srgb, var(--color-status-error) 10%, var(--color-bg))', border: '1px solid color-mix(in srgb, var(--color-status-error) 30%, var(--color-bg))', padding: '1rem 1.5rem', borderRadius: 8, marginBottom: '2rem' }}>
          <p style={{ color: 'var(--color-status-error)', margin: 0, fontWeight: 500 }}>{error}</p>
        </div>
      )}

      {users.length === 0 ? (
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
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          </div>
          <div>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.25rem' }}>No hay usuarios</h3>
            <p style={{ margin: 0, color: 'var(--color-text-muted)' }}>El sistema no tiene usuarios registrados.</p>
          </div>
        </div>
      ) : (
        <div style={{
          background: 'var(--color-bg)',
          border: '1px solid var(--color-border)',
          borderRadius: 16,
          overflow: 'hidden',
          boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)'
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead style={{ background: 'var(--color-bg-subtle)', borderBottom: '1px solid var(--color-border)' }}>
              <tr>
                <th style={{ padding: '1rem 1.5rem', fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Email</th>
                <th style={{ padding: '1rem 1.5rem', fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Full name</th>
                <th style={{ padding: '1rem 1.5rem', fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Role</th>
                <th style={{ padding: '1rem 1.5rem', fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Status</th>
                <th style={{ padding: '1rem 1.5rem', fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u, i) => (
                <tr key={u.id} style={{ borderBottom: i === users.length - 1 ? 'none' : '1px solid var(--color-border)', transition: 'background 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-bg-subtle)'} onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                  <td style={{ padding: '1rem 1.5rem', fontWeight: 500 }}>{u.email}</td>
                  <td style={{ padding: '1rem 1.5rem', color: u.full_name ? 'inherit' : 'var(--color-text-muted)' }}>{u.full_name || '—'}</td>
                  <td style={{ padding: '1rem 1.5rem' }}>
                    <span style={{
                      background: u.role === 'ADMIN' ? 'color-mix(in srgb, var(--color-status-error) 15%, transparent)' : 'color-mix(in srgb, var(--color-link) 15%, transparent)',
                      color: u.role === 'ADMIN' ? 'var(--color-status-error)' : 'var(--color-link)',
                      padding: '0.25rem 0.75rem',
                      borderRadius: 9999,
                      fontSize: '0.8rem',
                      fontWeight: 700
                    }}>
                      {u.role}
                    </span>
                  </td>
                  <td style={{ padding: '1rem 1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: u.is_active ? 'var(--color-status-success)' : 'var(--color-text-muted)' }} />
                      <span style={{ fontSize: '0.9rem', color: u.is_active ? 'inherit' : 'var(--color-text-muted)' }}>{u.is_active ? 'Active' : 'Inactive'}</span>
                    </div>
                  </td>
                  <td style={{ padding: '1rem 1.5rem', textAlign: 'right' }}>
                    <button
                      type="button"
                      onClick={() => startEdit(u)}
                      style={{ padding: '0.4rem 0.8rem', cursor: 'pointer', background: 'transparent', border: '1px solid var(--color-border)', borderRadius: 6, fontSize: '0.9rem', marginRight: '0.5rem', color: 'var(--color-text)' }}
                    >
                      Edit
                    </button>
                    {u.id !== user.id && (
                      <button
                        type="button"
                        onClick={() => handleDelete(u.id)}
                        style={{ padding: '0.4rem 0.8rem', cursor: 'pointer', background: 'color-mix(in srgb, var(--color-status-error) 10%, transparent)', color: 'var(--color-status-error)', border: 'none', borderRadius: 6, fontSize: '0.9rem' }}
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add User Modal */}
      {showAddModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem' }}>
          <div style={{ background: 'var(--color-bg)', padding: '2rem', borderRadius: 16, width: '100%', maxWidth: 450, boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)', border: '1px solid var(--color-border)' }}>
            <h2 style={{ margin: '0 0 1.5rem 0', fontSize: '1.5rem' }}>New User</h2>
            {error && <p style={{ color: 'var(--color-status-error)', marginBottom: '1rem', padding: '0.75rem', background: 'color-mix(in srgb, var(--color-status-error) 10%, transparent)', borderRadius: 8 }}>{error}</p>}

            <form onSubmit={handleAdd}>
              <label style={labelStyle}>Email</label>
              <input type="email" placeholder="user@example.com" value={addForm.email} onChange={(e) => setAddForm((f) => ({ ...f, email: e.target.value }))} required style={inputStyle} />

              <label style={labelStyle}>Password</label>
              <input type="password" placeholder="Min 8 characters" value={addForm.password} onChange={(e) => setAddForm((f) => ({ ...f, password: e.target.value }))} required minLength={8} style={inputStyle} />

              <label style={labelStyle}>Full Name (Optional)</label>
              <input type="text" placeholder="John Doe" value={addForm.full_name} onChange={(e) => setAddForm((f) => ({ ...f, full_name: e.target.value }))} style={inputStyle} />

              <label style={labelStyle}>Role</label>
              <select value={addForm.role} onChange={(e) => setAddForm((f) => ({ ...f, role: e.target.value }))} style={inputStyle}>
                <option value="PRODUCT_OWNER">PRODUCT_OWNER</option>
                <option value="ADMIN">ADMIN</option>
              </select>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '2rem' }}>
                <button type="button" onClick={() => { setShowAddModal(false); setError(''); }} style={{ padding: '0.75rem 1.5rem', background: 'transparent', border: '1px solid var(--color-border)', cursor: 'pointer' }}>Cancel</button>
                <button type="submit" style={{ padding: '0.75rem 1.5rem', background: 'var(--color-link)', color: 'white', border: 'none', cursor: 'pointer', fontWeight: 600 }}>Create User</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {showEditModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem' }}>
          <div style={{ background: 'var(--color-bg)', padding: '2rem', borderRadius: 16, width: '100%', maxWidth: 450, boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)', border: '1px solid var(--color-border)' }}>
            <h2 style={{ margin: '0 0 1.5rem 0', fontSize: '1.5rem' }}>Edit User</h2>
            {error && <p style={{ color: 'var(--color-status-error)', marginBottom: '1rem', padding: '0.75rem', background: 'color-mix(in srgb, var(--color-status-error) 10%, transparent)', borderRadius: 8 }}>{error}</p>}

            <form onSubmit={handleEdit}>
              <label style={labelStyle}>Full Name</label>
              <input type="text" placeholder="John Doe" value={editForm.full_name} onChange={(e) => setEditForm((f) => ({ ...f, full_name: e.target.value }))} style={inputStyle} />

              <label style={labelStyle}>Role</label>
              <select value={editForm.role} onChange={(e) => setEditForm((f) => ({ ...f, role: e.target.value }))} style={inputStyle}>
                <option value="PRODUCT_OWNER">PRODUCT_OWNER</option>
                <option value="ADMIN">ADMIN</option>
              </select>

              <label style={{ ...labelStyle, display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', marginBottom: '1.5rem' }}>
                <input type="checkbox" checked={editForm.is_active} onChange={(e) => setEditForm((f) => ({ ...f, is_active: e.target.checked }))} style={{ width: 18, height: 18, cursor: 'pointer' }} />
                User is active
              </label>

              <div style={{ margin: '1.5rem 0', height: 1, background: 'var(--color-border)' }}></div>

              <label style={labelStyle}>Reset Password (Optional)</label>
              <input type="password" placeholder="Leave blank to keep unchanged" value={editForm.password} onChange={(e) => setEditForm((f) => ({ ...f, password: e.target.value }))} minLength={8} style={inputStyle} />

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '2rem' }}>
                <button type="button" onClick={() => { setShowEditModal(false); setEditingId(null); setError(''); }} style={{ padding: '0.75rem 1.5rem', background: 'transparent', border: '1px solid var(--color-border)', cursor: 'pointer' }}>Cancel</button>
                <button type="submit" style={{ padding: '0.75rem 1.5rem', background: 'var(--color-link)', color: 'white', border: 'none', cursor: 'pointer', fontWeight: 600 }}>Save Changes</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  )
}
