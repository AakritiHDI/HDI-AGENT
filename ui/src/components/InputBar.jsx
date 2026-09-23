import React, { useState, useRef, useEffect } from 'react'

const styles = {
  container: {
    padding: '16px 24px 20px',
    background: '#ffffff',
  },
  inner: {
    maxWidth: '860px',
    margin: '0 auto',
    position: 'relative',
  },
  form: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: '8px',
    background: '#f5f5f5',
    border: '1px solid #cccccc',
    borderRadius: '12px',
    padding: '10px 12px',
    transition: 'border-color 0.15s',
  },
  textarea: {
    flex: 1,
    background: 'transparent',
    border: 'none',
    outline: 'none',
    color: '#111111',
    fontSize: '14px',
    lineHeight: '1.5',
    resize: 'none',
    maxHeight: '200px',
    minHeight: '24px',
    overflowY: 'auto',
    fontFamily: 'inherit',
  },
  sendBtn: {
    width: '32px',
    height: '32px',
    background: '#0d9e65',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    transition: 'background 0.15s',
    fontSize: '14px',
  },
  sendBtnDisabled: {
    background: '#dddddd',
    cursor: 'not-allowed',
  },
  hint: {
    fontSize: '11px',
    color: '#aaaaaa',
    textAlign: 'center',
    marginTop: '8px',
    maxWidth: '860px',
    margin: '8px auto 0',
  },
}

export default function InputBar({ onSend, isLoading, disabled }) {
  const [text, setText] = useState('')
  const textareaRef = useRef(null)

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
  }, [text])

  function handleSubmit(e) {
    e?.preventDefault()
    const msg = text.trim()
    if (!msg || isLoading || disabled) return
    onSend(msg)
    setText('')
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const canSend = text.trim().length > 0 && !isLoading && !disabled

  return (
    <div style={styles.container}>
      <div style={styles.inner}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            style={styles.textarea}
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={disabled ? 'Select or create a chat to start...' : isLoading ? 'Agent is thinking...' : 'Message HDI Agent... (Shift+Enter for new line)'}
            rows={1}
            disabled={disabled || isLoading}
          />
          <button
            type="submit"
            style={{ ...styles.sendBtn, ...(canSend ? {} : styles.sendBtnDisabled) }}
            disabled={!canSend}
          >
            {isLoading ? '⏳' : '↑'}
          </button>
        </form>
        <div style={styles.hint}>
          Enter to send · Shift+Enter for new line
        </div>
      </div>
    </div>
  )
}