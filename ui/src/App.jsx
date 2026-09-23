import React, { useState, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar.jsx'
import ChatWindow from './components/ChatWindow.jsx'
import InputBar from './components/InputBar.jsx'
import UsernameModal from './components/UsernameModal.jsx'
import SetupScreen from './components/SetupScreen.jsx'
import {
  fetchConfig,
  fetchSessions,
  createSession,
  fetchSession,
  sendMessage,
} from './api/client.js'

const styles = {
  app: {
    display: 'flex',
    height: '100vh',
    background: '#ffffff',
    overflow: 'hidden',
  },
  main: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  topBar: {
    height: '50px',
    borderBottom: '1px solid #e0e0e0',
    display: 'flex',
    alignItems: 'center',
    padding: '0 24px',
    gap: '12px',
    flexShrink: 0,
    background: '#ffffff',
  },
  chatTitle: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#111111',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  containerBadge: {
    fontSize: '11px',
    color: '#0d9e65',
    background: 'rgba(13, 158, 101, 0.1)',
    border: '1px solid rgba(13, 158, 101, 0.25)',
    borderRadius: '20px',
    padding: '2px 10px',
    flexShrink: 0,
  },
  noSessionPlaceholder: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#999',
    gap: '12px',
  },
  loadingScreen: {
    position: 'fixed',
    inset: 0,
    background: '#ffffff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 400,
  },
}

const USERNAME_KEY = 'hdi_agent_username'

export default function App() {
  // "booting" → checking config | "setup" → showing setup screen
  // "ready" → normal chat UI
  const [phase, setPhase] = useState('booting')

  const [username, setUsername] = useState('')
  const [envContainer, setEnvContainer] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [activeSession, setActiveSession] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  // ── Boot: check /api/config for env username ──────────────────────────────
  useEffect(() => {
    async function boot() {
      try {
        const config = await fetchConfig()
        const envUser = config.username?.trim().toUpperCase()

        if (envUser) {
          // Username is in .env — use it directly, skip modal
          setUsername(envUser)
          setEnvContainer(config.container || `${envUser}_CONTAINER`)
          localStorage.setItem(USERNAME_KEY, envUser)

          // If setup is running or idle → show setup screen
          if (config.setup_status === 'running' || config.setup_status === 'idle') {
            setPhase('setup')
          } else {
            // done or error → go straight to chat
            setPhase('ready')
          }
        } else {
          // No env username → fall back to localStorage or modal
          const stored = localStorage.getItem(USERNAME_KEY) || ''
          if (stored) {
            setUsername(stored)
            setPhase('ready')
          } else {
            setShowModal(true)
            setPhase('ready')
          }
        }
      } catch (err) {
        // API not reachable yet — try localStorage
        console.error('Config fetch failed:', err)
        const stored = localStorage.getItem(USERNAME_KEY) || ''
        if (stored) {
          setUsername(stored)
        } else {
          setShowModal(true)
        }
        setPhase('ready')
      }
    }
    boot()
  }, [])

  // ── Load sessions list ─────────────────────────────────────────────────────
  const loadSessions = useCallback(async () => {
    try {
      const data = await fetchSessions()
      setSessions(data)
    } catch (err) {
      console.error('Failed to load sessions:', err)
    }
  }, [])

  useEffect(() => {
    if (phase === 'ready' && username) {
      loadSessions()
    }
  }, [phase, username, loadSessions])

  // ── Load active session detail ─────────────────────────────────────────────
  const loadSession = useCallback(async (sessionId) => {
    try {
      const data = await fetchSession(sessionId)
      setActiveSession(data)
    } catch (err) {
      console.error('Failed to load session:', err)
    }
  }, [])

  useEffect(() => {
    if (activeSessionId) {
      loadSession(activeSessionId)
    } else {
      setActiveSession(null)
    }
  }, [activeSessionId, loadSession])

  // ── Setup screen done → proceed to chat ───────────────────────────────────
  function handleSetupDone() {
    setPhase('ready')
  }

  // ── Username confirm (modal path) ──────────────────────────────────────────
  function handleUsernameConfirm(uname) {
    localStorage.setItem(USERNAME_KEY, uname)
    setUsername(uname)
    setShowModal(false)
  }

  // ── New chat ───────────────────────────────────────────────────────────────
  async function handleNewChat() {
    if (!username) {
      setShowModal(true)
      return
    }
    try {
      const session = await createSession(username)
      await loadSessions()
      setActiveSessionId(session.session_id)
    } catch (err) {
      console.error('Failed to create session:', err)
    }
  }

  // ── Select session ─────────────────────────────────────────────────────────
  function handleSelectSession(sessionId) {
    setActiveSessionId(sessionId)
  }

  // ── Sessions changed (delete/rename) ──────────────────────────────────────
  async function handleSessionsChanged() {
    const updatedSessions = await fetchSessions()
    setSessions(updatedSessions)
    const exists = updatedSessions.some(s => s.session_id === activeSessionId)
    if (!exists) {
      setActiveSessionId(null)
    }
  }

  // ── Send message ───────────────────────────────────────────────────────────
  async function handleSend(message) {
    if (!activeSessionId || isLoading) return

    const userMsg = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    }
    setActiveSession(prev => prev ? {
      ...prev,
      messages: [...(prev.messages || []), userMsg],
    } : prev)

    setIsLoading(true)
    try {
      await sendMessage(activeSessionId, message)
      await loadSession(activeSessionId)
      await loadSessions()
    } catch (err) {
      console.error('Chat error:', err)
      setActiveSession(prev => prev ? {
        ...prev,
        messages: [...(prev.messages || []), {
          role: 'assistant',
          content: '⚠️ Failed to reach the agent. Please check if the API server is running.',
          timestamp: new Date().toISOString(),
        }],
      } : prev)
    } finally {
      setIsLoading(false)
    }
  }

  // ── Suggestion click ───────────────────────────────────────────────────────
  async function handleSuggestionClick(text) {
    if (!activeSessionId) {
      const session = await createSession(username)
      await loadSessions()
      setActiveSessionId(session.session_id)
      setTimeout(() => handleSendWithSession(session.session_id, text), 100)
    } else {
      handleSend(text)
    }
  }

  async function handleSendWithSession(sessionId, message) {
    const userMsg = { role: 'user', content: message, timestamp: new Date().toISOString() }
    setActiveSession(prev => prev ? {
      ...prev,
      messages: [...(prev.messages || []), userMsg],
    } : { session_id: sessionId, messages: [userMsg] })

    setIsLoading(true)
    try {
      await sendMessage(sessionId, message)
      await loadSession(sessionId)
      await loadSessions()
    } catch (err) {
      console.error('Chat error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const activeSessionMeta = sessions.find(s => s.session_id === activeSessionId)
  const containerName = envContainer || (username ? `${username}_CONTAINER` : '')

  // ── Booting screen ─────────────────────────────────────────────────────────
  if (phase === 'booting') {
    return (
      <div style={styles.loadingScreen}>
        <div style={{ textAlign: 'center', color: '#888' }}>
          <div style={{ fontSize: '40px', marginBottom: '12px' }}>🤖</div>
          <div style={{ fontSize: '14px' }}>Starting HDI Agent...</div>
        </div>
      </div>
    )
  }

  // ── Setup screen ───────────────────────────────────────────────────────────
  if (phase === 'setup') {
    return (
      <SetupScreen
        username={username}
        container={containerName}
        onDone={handleSetupDone}
      />
    )
  }

  // ── Normal chat UI ─────────────────────────────────────────────────────────
  return (
    <div style={styles.app}>
      {showModal && <UsernameModal onConfirm={handleUsernameConfirm} />}

      <Sidebar
        sessions={sessions}
        activeSesId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onSessionsChanged={handleSessionsChanged}
        username={username}
      />

      <div style={styles.main}>
        <div style={styles.topBar}>
          {activeSessionMeta ? (
            <>
              <div style={styles.chatTitle}>{activeSessionMeta.title}</div>
              {containerName && (
                <div style={styles.containerBadge}>📦 {containerName}</div>
              )}
            </>
          ) : (
            <div style={{ fontSize: '14px', color: '#888' }}>
              {username ? 'Select a chat or start a new one' : 'HDI Agent'}
            </div>
          )}
        </div>

        {activeSessionId && activeSession ? (
          <ChatWindow
            messages={activeSession.messages || []}
            isLoading={isLoading}
            username={username}
            onSuggestionClick={handleSuggestionClick}
          />
        ) : (
          <div style={styles.noSessionPlaceholder}>
            <div style={{ fontSize: '40px' }}>🤖</div>
            <div style={{ fontSize: '18px', fontWeight: '600', color: '#444' }}>
              HDI Agent
            </div>
            <div style={{ fontSize: '13px', color: '#777', textAlign: 'center', maxWidth: '300px' }}>
              Click <strong style={{ color: '#333' }}>+ New Chat</strong> in the sidebar to start
            </div>
          </div>
        )}

        <InputBar
          onSend={handleSend}
          isLoading={isLoading}
          disabled={!activeSessionId}
        />
      </div>
    </div>
  )
}