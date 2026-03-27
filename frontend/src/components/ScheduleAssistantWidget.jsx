import { useState, useEffect, useRef, useCallback } from 'react'
import { sendAssistantMessage, applyAssistantActions, getAssistantHistory } from '../api'

const PANEL_W = 400
const PANEL_H = 500

const fabStyle = {
  position: 'fixed', bottom: 24, right: 24, zIndex: 1000,
  width: 56, height: 56, borderRadius: '50%',
  background: 'var(--color-btn-primary-bg, #0ea5e9)', color: '#fff',
  border: 'none', cursor: 'pointer', fontSize: '1.5rem',
  boxShadow: '0 4px 16px rgba(0,0,0,0.18)', display: 'flex',
  alignItems: 'center', justifyContent: 'center',
}

const panelStyle = (open) => ({
  position: 'fixed', bottom: 90, right: 24, zIndex: 1000,
  width: PANEL_W, height: PANEL_H,
  background: 'var(--color-bg, #fff)', border: '1px solid var(--color-border, #e2e8f0)',
  borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
  display: 'flex', flexDirection: 'column',
  opacity: open ? 1 : 0, transform: open ? 'translateY(0)' : 'translateY(16px)',
  pointerEvents: open ? 'auto' : 'none',
  transition: 'opacity 0.2s ease, transform 0.2s ease',
})

const headerStyle = {
  padding: '0.75rem 1rem', borderBottom: '1px solid var(--color-border, #e2e8f0)',
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  background: 'var(--color-bg-subtle, #f8fafc)', borderRadius: '12px 12px 0 0',
}

const messagesAreaStyle = {
  flex: 1, overflowY: 'auto', padding: '0.75rem',
  display: 'flex', flexDirection: 'column', gap: '0.5rem',
}

const inputAreaStyle = {
  padding: '0.5rem', borderTop: '1px solid var(--color-border, #e2e8f0)',
  display: 'flex', gap: '0.5rem', alignItems: 'flex-end',
}

const userBubble = {
  alignSelf: 'flex-end', background: 'var(--color-btn-primary-bg, #0ea5e9)',
  color: '#fff', borderRadius: '12px 12px 4px 12px', padding: '0.5rem 0.75rem',
  maxWidth: '85%', fontSize: '0.85rem', lineHeight: 1.4, wordBreak: 'break-word',
}

const assistantBubble = {
  alignSelf: 'flex-start', background: 'var(--color-bg-subtle, #f1f5f9)',
  color: 'var(--color-text, #1e293b)', borderRadius: '12px 12px 12px 4px',
  padding: '0.5rem 0.75rem', maxWidth: '85%', fontSize: '0.85rem',
  lineHeight: 1.4, wordBreak: 'break-word',
}

const actionBtnStyle = {
  padding: '0.35rem 0.75rem', border: 'none', borderRadius: 6,
  cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600,
}

export default function ScheduleAssistantWidget({ projectId, scheduleVersionId, onActionsApplied }) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [applyingId, setApplyingId] = useState(null)
  const [error, setError] = useState('')
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  // Load history when version changes or widget opens
  const loadHistory = useCallback(async () => {
    if (!projectId || !scheduleVersionId) return
    try {
      const history = await getAssistantHistory(projectId, scheduleVersionId)
      setMessages(Array.isArray(history) ? history : [])
    } catch {
      setMessages([])
    }
  }, [projectId, scheduleVersionId])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || sending) return
    setError('')
    setInput('')
    const userMsg = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setSending(true)
    try {
      const res = await sendAssistantMessage(projectId, text, scheduleVersionId)
      setMessages(prev => [...prev, { role: 'assistant', ...res }])
    } catch (err) {
      setError(err.message || 'Error al enviar mensaje')
    } finally {
      setSending(false)
    }
  }

  const handleApply = async (messageId, msgIndex) => {
    setApplyingId(messageId)
    setError('')
    try {
      await applyAssistantActions(projectId, messageId)
      setMessages(prev => prev.map((m, i) =>
        i === msgIndex ? { ...m, actions_applied: true } : m
      ))
      onActionsApplied?.()
    } catch (err) {
      setError(err.message || 'Error al aplicar cambios')
    } finally {
      setApplyingId(null)
    }
  }

  const handleReject = (msgIndex) => {
    setMessages(prev => prev.map((m, i) =>
      i === msgIndex ? { ...m, _rejected: true } : m
    ))
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <>
      {/* FAB */}
      <button style={fabStyle} onClick={() => setOpen(o => !o)} title="Asistente de Horarios">
        {open ? '\u2715' : '\uD83D\uDCAC'}
      </button>

      {/* Panel */}
      <div style={panelStyle(open)}>
        {/* Header */}
        <div style={headerStyle}>
          <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>Asistente de Horarios</span>
          <button onClick={() => setOpen(false)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.1rem', color: 'var(--color-text-muted, #64748b)' }}>
            \u2715
          </button>
        </div>

        {/* Messages */}
        <div style={messagesAreaStyle}>
          {messages.length === 0 && !sending && (
            <p style={{ color: 'var(--color-text-muted, #94a3b8)', fontSize: '0.85rem', textAlign: 'center', margin: 'auto 0' }}>
              Escribe un mensaje para comenzar. Puedes pedir cambios en el horario.
            </p>
          )}

          {messages.map((msg, i) => {
            if (msg.role === 'user') {
              return <div key={i} style={userBubble}>{msg.content}</div>
            }

            // Assistant message
            const actions = msg.proposed_actions || []
            const hasActions = actions.length > 0
            const applied = msg.actions_applied
            const rejected = msg._rejected

            return (
              <div key={i} style={assistantBubble}>
                <div>{msg.content}</div>

                {/* Reasoning */}
                {msg.reasoning && (
                  <details style={{ marginTop: '0.4rem', fontSize: '0.8rem' }}>
                    <summary style={{ cursor: 'pointer', color: 'var(--color-text-muted, #64748b)' }}>Razonamiento</summary>
                    <div style={{ marginTop: '0.25rem', padding: '0.4rem', background: 'var(--color-bg, #fff)', borderRadius: 6, whiteSpace: 'pre-wrap' }}>
                      {msg.reasoning}
                    </div>
                  </details>
                )}

                {/* Warnings */}
                {msg.warnings?.length > 0 && (
                  <div style={{ marginTop: '0.4rem', padding: '0.35rem 0.5rem', background: '#fef3c7', borderRadius: 6, fontSize: '0.8rem', color: '#92400e' }}>
                    {msg.warnings.map((w, wi) => <div key={wi}>{w}</div>)}
                  </div>
                )}

                {/* Proposed actions */}
                {hasActions && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.8rem', marginBottom: '0.25rem' }}>
                      {actions.length} cambio{actions.length !== 1 ? 's' : ''} propuesto{actions.length !== 1 ? 's' : ''}
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.8rem' }}>
                      {actions.map((a, ai) => (
                        <li key={ai} style={{ marginBottom: '0.15rem' }}>{a.description}</li>
                      ))}
                    </ul>

                    {applied ? (
                      <div style={{ marginTop: '0.4rem', color: '#16a34a', fontWeight: 600, fontSize: '0.8rem' }}>
                        Cambios aplicados
                      </div>
                    ) : rejected ? (
                      <div style={{ marginTop: '0.4rem', color: 'var(--color-text-muted, #64748b)', fontSize: '0.8rem' }}>
                        Cambios rechazados
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.4rem' }}>
                        <button
                          onClick={() => handleApply(msg.message_id, i)}
                          disabled={applyingId === msg.message_id}
                          style={{ ...actionBtnStyle, background: 'var(--color-btn-primary-bg, #0ea5e9)', color: '#fff', opacity: applyingId === msg.message_id ? 0.7 : 1 }}>
                          {applyingId === msg.message_id ? 'Aplicando...' : 'Aplicar cambios'}
                        </button>
                        <button
                          onClick={() => handleReject(i)}
                          style={{ ...actionBtnStyle, background: 'var(--color-bg-subtle, #f1f5f9)', color: 'var(--color-text, #1e293b)', border: '1px solid var(--color-border, #e2e8f0)' }}>
                          Rechazar
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}

          {/* Loading dots */}
          {sending && (
            <div style={{ ...assistantBubble, display: 'flex', gap: 4, padding: '0.6rem 1rem' }}>
              <span style={{ animation: 'pulse 1.2s infinite', fontSize: '1.2rem' }}>.</span>
              <span style={{ animation: 'pulse 1.2s infinite 0.2s', fontSize: '1.2rem' }}>.</span>
              <span style={{ animation: 'pulse 1.2s infinite 0.4s', fontSize: '1.2rem' }}>.</span>
            </div>
          )}

          {/* Error */}
          {error && (
            <div style={{ fontSize: '0.8rem', color: 'var(--color-status-error, #dc2626)', padding: '0.35rem 0.5rem', background: '#fef2f2', borderRadius: 6 }}>
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={inputAreaStyle}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe tu mensaje..."
            rows={1}
            style={{
              flex: 1, resize: 'none', border: '1px solid var(--color-border, #e2e8f0)',
              borderRadius: 8, padding: '0.5rem 0.65rem', fontSize: '0.85rem',
              outline: 'none', fontFamily: 'inherit', background: 'var(--color-bg, #fff)',
              color: 'var(--color-text, #1e293b)', maxHeight: 80, overflowY: 'auto',
            }}
          />
          <button
            onClick={handleSend}
            disabled={sending || !input.trim()}
            style={{
              padding: '0.5rem 0.75rem', background: 'var(--color-btn-primary-bg, #0ea5e9)',
              color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer',
              fontSize: '0.85rem', fontWeight: 600,
              opacity: (sending || !input.trim()) ? 0.5 : 1,
            }}>
            Enviar
          </button>
        </div>
      </div>

      {/* Keyframe animation for loading dots */}
      <style>{`
        @keyframes pulse {
          0%, 80%, 100% { opacity: 0.3; }
          40% { opacity: 1; }
        }
      `}</style>
    </>
  )
}
