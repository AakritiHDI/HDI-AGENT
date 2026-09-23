import React, { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble.jsx'

const styles = {
  container: {
    flex: 1,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
  },
  empty: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#555',
    gap: '12px',
  },
  emptyIcon: {
    fontSize: '48px',
  },
  emptyTitle: {
    fontSize: '20px',
    fontWeight: '600',
    color: '#444444',
  },
  emptySubtitle: {
    fontSize: '14px',
    color: '#777777',
    textAlign: 'center',
    maxWidth: '320px',
    lineHeight: '1.5',
  },
  suggestions: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
    justifyContent: 'center',
    marginTop: '8px',
    maxWidth: '600px',
  },
  suggestion: {
    background: '#f0f0f0',
    border: '1px solid #dddddd',
    borderRadius: '8px',
    padding: '8px 14px',
    fontSize: '13px',
    color: '#555555',
    cursor: 'pointer',
    transition: 'all 0.15s',
    textAlign: 'center',
  },
  messagesWrapper: {
    flex: 1,
    paddingTop: '8px',
    paddingBottom: '8px',
  },
  thinkingBubble: {
    display: 'flex',
    padding: '16px 24px',
    gap: '16px',
    maxWidth: '860px',
    margin: '0 auto',
    width: '100%',
  },
  thinkingDots: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    padding: '12px 4px',
  },
  dot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: '#aaaaaa',
    animation: 'pulse 1.4s ease-in-out infinite',
  },
}

const SUGGESTIONS = [
  'Create a SALES_ORDER table with order ID, amount, and status',
  'Create a calculation view joining EMPLOYEE and OFFICE tables',
  'Deploy a stored procedure to get trips by destination',
  'Show me all deployed artifacts in my container',
  'Create a synonym to access tables from another container',
]

export default function ChatWindow({ messages, isLoading, username, onSuggestionClick }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  if (!messages || messages.length === 0) {
    return (
      <div style={styles.container}>
        <div style={styles.empty}>
          <div style={styles.emptyIcon}>🤖</div>
          <div style={styles.emptyTitle}>HDI Agent</div>
          <div style={styles.emptySubtitle}>
            Create and deploy SAP HANA HDI artifacts using plain English.
          </div>
          <div style={styles.suggestions}>
            {SUGGESTIONS.map((s, i) => (
              <div
                key={i}
                style={styles.suggestion}
                onClick={() => onSuggestionClick?.(s)}
                onMouseEnter={e => {
                  e.currentTarget.style.background = '#e2e2e2'
                  e.currentTarget.style.color = '#222222'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = '#f0f0f0'
                  e.currentTarget.style.color = '#555555'
                }}
              >
                {s}
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      <div style={styles.messagesWrapper}>
        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            role={msg.role}
            content={msg.content}
            timestamp={msg.timestamp}
            username={username}
          />
        ))}
        {isLoading && (
          <div style={styles.thinkingBubble}>
            <div style={{
              width: '32px', height: '32px', borderRadius: '50%',
              background: '#dddddd', display: 'flex', alignItems: 'center',
              justifyContent: 'center', fontSize: '14px', flexShrink: 0,
            }}>
              🤖
            </div>
            <div style={styles.thinkingDots}>
              {[0, 1, 2].map(i => (
                <div
                  key={i}
                  style={{
                    ...styles.dot,
                    animationDelay: `${i * 0.2}s`,
                  }}
                />
              ))}
              <style>{`
                @keyframes pulse {
                  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
                  40% { opacity: 1; transform: scale(1); }
                }
              `}</style>
            </div>
          </div>
        )}
      </div>
      <div ref={bottomRef} />
    </div>
  )
}