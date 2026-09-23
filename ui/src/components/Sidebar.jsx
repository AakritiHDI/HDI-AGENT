import React, { useState } from 'react'
import { deleteSession, renameSession } from '../api/client.js'

const styles = {
  sidebar: {
    width: '260px',
    minWidth: '260px',
    background: '#f4f4f4',
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    borderRight: '1px solid #e0e0e0',
  },
  header: {
    padding: '16px',
    borderBottom: '1px solid #e0e0e0',
  },
  logo: {
    fontSize: '15px',
    fontWeight: '700',
    color: '#111111',
    letterSpacing: '0.3px',
    marginBottom: '12px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  newChatBtn: {
    width: '100%',
    padding: '10px 14px',
    background: '#e8e8e8',
    color: '#111111',
    border: '1px solid #cccccc',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '13px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    transition: 'background 0.15s',
  },
  sessionList: {
    flex: 1,
    overflowY: 'auto',
    padding: '8px',
  },
  sessionItem: {
    padding: '10px 12px',
    borderRadius: '8px',
    cursor: 'pointer',
    marginBottom: '2px',
    position: 'relative',
    transition: 'background 0.1s',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '8px',
  },
  sessionTitle: {
    fontSize: '13px',
    color: '#333333',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    flex: 1,
  },
  sessionMeta: {
    fontSize: '11px',
    color: '#888888',
    marginTop: '2px',
  },
  activeSession: {
    background: '#e0e0e0',
  },
  actions: {
    display: 'flex',
    gap: '4px',
    flexShrink: 0,
  },
  iconBtn: {
    background: 'none',
    border: 'none',
    color: '#999999',
    cursor: 'pointer',
    padding: '2px 4px',
    borderRadius: '4px',
    fontSize: '12px',
    lineHeight: 1,
    transition: 'color 0.1s',
  },
  sectionLabel: {
    fontSize: '11px',
    color: '#888888',
    padding: '8px 12px 4px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  userBadge: {
    padding: '10px 16px',
    borderTop: '1px solid #e0e0e0',
    fontSize: '12px',
    color: '#888888',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now - d
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffDays === 0) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } else if (diffDays === 1) {
    return 'Yesterday'
  } else if (diffDays < 7) {
    return d.toLocaleDateString([], { weekday: 'short' })
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

export default function Sidebar({ sessions, activeSesId, onSelectSession, onNewChat, onSessionsChanged, username }) {
  const [hoverId, setHoverId] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')

  async function handleDelete(e, sessionId) {
    e.stopPropagation()
    if (!confirm('Delete this chat?')) return
    await deleteSession(sessionId)
    onSessionsChanged()
  }

  function handleRenameStart(e, session) {
    e.stopPropagation()
    setEditingId(session.session_id)
    setEditTitle(session.title)
  }

  async function handleRenameSubmit(sessionId) {
    if (editTitle.trim()) {
      await renameSession(sessionId, editTitle.trim())
      onSessionsChanged()
    }
    setEditingId(null)
  }

  return (
    <div style={styles.sidebar}>
      <div style={styles.header}>
        <div style={styles.logo}>
          🤖 HDI Agent
        </div>
        <button
          style={styles.newChatBtn}
          onClick={onNewChat}
          onMouseEnter={e => e.currentTarget.style.background = '#d8d8d8'}
          onMouseLeave={e => e.currentTarget.style.background = '#e8e8e8'}
        >
          <span style={{ fontSize: '16px' }}>+</span>
          New Chat
        </button>
      </div>

      <div style={styles.sessionList}>
        {sessions.length === 0 && (
          <div style={{ ...styles.sectionLabel, textAlign: 'center', marginTop: '20px' }}>
            No chats yet
          </div>
        )}
        {sessions.length > 0 && (
          <div style={styles.sectionLabel}>Recent Chats</div>
        )}
        {sessions.map(session => (
          <div
            key={session.session_id}
            style={{
              ...styles.sessionItem,
              ...(session.session_id === activeSesId ? styles.activeSession : {}),
              background: session.session_id === activeSesId
                ? '#e0e0e0'
                : hoverId === session.session_id ? '#ebebeb' : 'transparent',
            }}
            onClick={() => onSelectSession(session.session_id)}
            onMouseEnter={() => setHoverId(session.session_id)}
            onMouseLeave={() => setHoverId(null)}
          >
            <div style={{ flex: 1, overflow: 'hidden' }}>
              {editingId === session.session_id ? (
                <input
                  autoFocus
                  value={editTitle}
                  onChange={e => setEditTitle(e.target.value)}
                  onBlur={() => handleRenameSubmit(session.session_id)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') handleRenameSubmit(session.session_id)
                    if (e.key === 'Escape') setEditingId(null)
                  }}
                  onClick={e => e.stopPropagation()}
                  style={{
                    width: '100%',
                    background: '#ffffff',
                    border: '1px solid #aaaaaa',
                    borderRadius: '4px',
                    color: '#111111',
                    fontSize: '13px',
                    padding: '2px 6px',
                    outline: 'none',
                  }}
                />
              ) : (
                <>
                  <div style={styles.sessionTitle}>{session.title}</div>
                  <div style={styles.sessionMeta}>
                    {session.message_count > 0 ? `${Math.floor(session.message_count / 2)} msg${Math.floor(session.message_count / 2) !== 1 ? 's' : ''}` : 'Empty'}
                    {' · '}
                    {formatDate(session.updated_at)}
                  </div>
                </>
              )}
            </div>
            {(hoverId === session.session_id || session.session_id === activeSesId) && editingId !== session.session_id && (
              <div style={styles.actions}>
                <button
                  style={styles.iconBtn}
                  title="Rename"
                  onClick={e => handleRenameStart(e, session)}
                  onMouseEnter={e => e.currentTarget.style.color = '#333'}
                  onMouseLeave={e => e.currentTarget.style.color = '#999'}
                >
                  ✏️
                </button>
                <button
                  style={styles.iconBtn}
                  title="Delete"
                  onClick={e => handleDelete(e, session.session_id)}
                  onMouseEnter={e => e.currentTarget.style.color = '#cc3333'}
                  onMouseLeave={e => e.currentTarget.style.color = '#999'}
                >
                  🗑️
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={styles.userBadge}>
        <span>👤</span>
        <span>{username ? username.toUpperCase() : 'No user set'}</span>
      </div>
    </div>
  )
}