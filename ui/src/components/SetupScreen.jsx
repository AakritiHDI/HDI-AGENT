import React, { useEffect, useState } from 'react'
import { fetchSetupStatus } from '../api/client.js'

const STEP_LABELS = {
  create_container_group: 'Creating Container Group',
  create_hdi_container: 'Creating HDI Container',
  grant_container_group_api: 'Granting Container Group API',
  grant_container_api_privileges: 'Granting Container API Privileges',
  grant_schema_privileges: 'Granting Schema Privileges',
}

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: '#ffffff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 500,
  },
  card: {
    background: '#ffffff',
    border: '1px solid #e0e0e0',
    borderRadius: '16px',
    padding: '40px 48px',
    width: '480px',
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
    alignItems: 'center',
    boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
  },
  logo: { fontSize: '48px' },
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
    lineHeight: '1.6',
    marginTop: '-12px',
  },
  stepsContainer: {
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  step: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '8px 12px',
    borderRadius: '8px',
    background: '#f5f5f5',
    fontSize: '13px',
  },
  stepIcon: { fontSize: '14px', width: '20px', textAlign: 'center', flexShrink: 0 },
  stepLabel: { color: '#444444', flex: 1 },
  stepDone: { color: '#0d9e65' },
  stepError: { color: '#cc3333' },
  stepPending: { color: '#aaaaaa' },
  spinner: {
    display: 'inline-block',
    width: '14px',
    height: '14px',
    border: '2px solid #cccccc',
    borderTopColor: '#0d9e65',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
    flexShrink: 0,
  },
  badge: {
    fontSize: '12px',
    color: '#0d9e65',
    background: 'rgba(13, 158, 101, 0.1)',
    border: '1px solid rgba(13, 158, 101, 0.25)',
    borderRadius: '20px',
    padding: '4px 14px',
  },
  errorBox: {
    width: '100%',
    background: 'rgba(220, 50, 50, 0.06)',
    border: '1px solid rgba(220, 50, 50, 0.25)',
    borderRadius: '8px',
    padding: '12px 16px',
    fontSize: '12px',
    color: '#cc3333',
  },
  doneMsg: {
    fontSize: '13px',
    color: '#0d9e65',
    textAlign: 'center',
  },
}

const ALL_STEPS = [
  'create_container_group',
  'create_hdi_container',
  'grant_container_group_api',
  'grant_container_api_privileges',
  'grant_schema_privileges',
]

export default function SetupScreen({ username, container, onDone }) {
  const [status, setStatus] = useState('running')
  const [steps, setSteps] = useState([])
  const [error, setError] = useState(null)
  const [countdown, setCountdown] = useState(3)

  // Poll setup status
  useEffect(() => {
    const poll = async () => {
      try {
        const data = await fetchSetupStatus()
        setStatus(data.status)
        setSteps(data.steps || [])
        setError(data.error)
        if (data.status === 'done' || data.status === 'error') {
          clearInterval(timer)
          if (data.status === 'done') {
            // Countdown then auto-proceed
            let c = 3
            const cd = setInterval(() => {
              c--
              setCountdown(c)
              if (c <= 0) {
                clearInterval(cd)
                onDone()
              }
            }, 1000)
          }
        }
      } catch (e) {
        // API might not be ready yet
      }
    }
    const timer = setInterval(poll, 1500)
    poll()
    return () => clearInterval(timer)
  }, [onDone])

  // Determine each step's state
  const completedStepNames = steps.map(s => s.step)
  const currentRunningIdx = completedStepNames.length

  return (
    <div style={styles.overlay}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
      <div style={styles.card}>
        <div style={styles.logo}>⚙️</div>
        <div>
          <div style={styles.title}>Setting up your HDI Environment</div>
          <div style={styles.subtitle}>
            Creating resources for <strong style={{ color: '#111111' }}>{username}</strong>
          </div>
        </div>

        <div style={styles.badge}>📦 {container}</div>

        <div style={styles.stepsContainer}>
          {ALL_STEPS.map((stepName, idx) => {
            const done = steps.find(s => s.step === stepName)
            const isRunning = status === 'running' && idx === currentRunningIdx
            const isPending = !done && !isRunning

            return (
              <div key={stepName} style={styles.step}>
                {done ? (
                  <span style={{ ...styles.stepIcon, ...(done.ok ? styles.stepDone : styles.stepError) }}>
                    {done.ok ? '✅' : '⚠️'}
                  </span>
                ) : isRunning ? (
                  <span style={styles.spinner} />
                ) : (
                  <span style={{ ...styles.stepIcon, ...styles.stepPending }}>○</span>
                )}
                <span style={{
                  ...styles.stepLabel,
                  ...(done ? (done.ok ? styles.stepDone : styles.stepError) : isPending ? styles.stepPending : {}),
                }}>
                  {STEP_LABELS[stepName] || stepName}
                </span>
              </div>
            )
          })}
        </div>

        {status === 'done' && (
          <div style={styles.doneMsg}>
            ✅ Environment ready! Starting in {countdown}s...
          </div>
        )}

        {status === 'error' && error && (
          <div style={styles.errorBox}>
            ⚠️ Setup encountered an error: {error}
            <br /><br />
            <span
              style={{ color: '#0d9e65', cursor: 'pointer', textDecoration: 'underline' }}
              onClick={onDone}
            >
              Continue anyway →
            </span>
          </div>
        )}

        {status === 'running' && (
          <div style={{ fontSize: '12px', color: '#aaaaaa' }}>
            This runs once — subsequent starts are instant.
          </div>
        )}
      </div>
    </div>
  )
}