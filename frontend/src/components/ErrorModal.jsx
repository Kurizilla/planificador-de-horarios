/**
 * Modal global para mostrar errores al usuario (sin tener que hacer scroll).
 * Usar en todas las páginas/flujos donde un error de validación o API deba mostrarse.
 */
export default function ErrorModal({ message, onClose, title = 'Error' }) {
  if (!message) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="error-modal-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
        background: 'rgba(0,0,0,0.4)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--color-bg)',
          border: '1px solid var(--color-border)',
          borderRadius: 8,
          padding: '1.25rem 1.5rem',
          maxWidth: 420,
          width: '100%',
          boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="error-modal-title" style={{ margin: '0 0 0.75rem', fontSize: '1.1rem', color: 'var(--color-status-error)' }}>
          {title}
        </h3>
        <p style={{ margin: 0, color: 'var(--color-text)', lineHeight: 1.45 }}>
          {message}
        </p>
        <button
          type="button"
          onClick={onClose}
          style={{
            marginTop: '1rem',
            padding: '0.5rem 1rem',
            background: 'var(--color-btn-dark-bg)',
            color: 'var(--color-btn-dark-text)',
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer',
            fontWeight: 500,
          }}
        >
          Cerrar
        </button>
      </div>
    </div>
  )
}
