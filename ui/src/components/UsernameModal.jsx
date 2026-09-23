import React, { useState } from 'react'

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.4)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modal: {
    background: '#ffffff',
    border: '1px solid #e0e0e0',
    borderRadius: '16px',
    padding: '32px',
    width: '380px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
  },
  title: {
    fontSize: '20px',
    fontWeight: '700',
    color: '#111111',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: '13px',
    color: '#666666',
    textAlign: 'center',
    lineHeight: '1.5',
  },
  input: {
    width: '100%',
    background: '#f5f5f5',
    border: '1px solid #cccccc',
    borderRadius: '8px',
    color: '#111111',
    fontSize: '14px',
    padding: '10px 14px',
    outline: 'none',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    fontFamily: 'monospace',
    textAlign: 'center',
  },
  btn: {
    width: '100%',
    padding: '12px',
    background: '#0d9e65',
    border: 'none',
    borderRadius: '8px',
    color: '#fff',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'background 0.15s',
  },
  logo: {
    textAlign: 'center',
    fontSize: '40px',
    marginBottom: '4px',
  },
}

export default function UsernameModal({ onConfirm }) {
  const [value, setValue] = useState('')
  const [error, setError] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    const username = value.trim().toUpperCase()
    if (!username) {
      setError('Username cannot be empty')
      return
    }
    if (!/^[A-Z0-9_]+$/.test(username)) {
      setError('Only letters, numbers, and underscores allowed')
      return
    }
    onConfirm(username)
  }

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <div style={styles.logo}>🤖</div>
        <div style={styles.title}>HDI Agent</div>
        <div style={styles.subtitle}>
          Enter your username to get started.<br />
          This is used to name your HDI container<br />
          (e.g. AAKRITI → AAKRITI_CONTAINER)
        </div>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <input
            style={{
              ...styles.input,
              borderColor: error ? '#cc3333' : '#cccccc',
            }}
            placeholder="e.g. AAKRITI"
            value={value}
            onChange={e => {
              setValue(e.target.value.toUpperCase())
              setError('')
            }}
            autoFocus
          />
          {error && (
            <div style={{ fontSize: '12px', color: '#cc3333', textAlign: 'center' }}>{error}</div>
          )}
          <button
            type="submit"
            style={styles.btn}
            onMouseEnter={e => e.currentTarget.style.background = '#0b8a58'}
            onMouseLeave={e => e.currentTarget.style.background = '#0d9e65'}
          >
            Start Chatting →
          </button>
        </form>
      </div>
    </div>
  )
}