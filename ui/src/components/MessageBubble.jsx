import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const styles = {
  wrapper: {
    display: 'flex',
    padding: '16px 24px',
    gap: '16px',
    maxWidth: '860px',
    margin: '0 auto',
    width: '100%',
  },
  wrapperUser: {
    flexDirection: 'row-reverse',
  },
  avatar: {
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '14px',
    flexShrink: 0,
  },
  avatarUser: {
    background: '#0d9e65',
    color: '#fff',
    fontWeight: '700',
    fontSize: '12px',
  },
  avatarAssistant: {
    background: '#dddddd',
    color: '#333333',
  },
  bubble: {
    flex: 1,
    lineHeight: '1.6',
    fontSize: '14px',
  },
  bubbleUser: {
    background: '#e8f5f0',
    borderRadius: '12px 2px 12px 12px',
    padding: '12px 16px',
    color: '#111111',
  },
  bubbleAssistant: {
    color: '#222222',
  },
  timestamp: {
    fontSize: '11px',
    color: '#aaaaaa',
    marginTop: '4px',
    textAlign: 'right',
  },
}

// Custom markdown components for light theme
const markdownComponents = {
  code({ node, inline, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || '')
    if (!inline) {
      return (
        <div style={{
          background: '#f6f8fa',
          border: '1px solid #d0d7de',
          borderRadius: '8px',
          padding: '12px 16px',
          margin: '8px 0',
          overflowX: 'auto',
        }}>
          {match && (
            <div style={{ fontSize: '11px', color: '#888888', marginBottom: '6px', textTransform: 'uppercase' }}>
              {match[1]}
            </div>
          )}
          <pre style={{ margin: 0, fontFamily: "'Fira Code', 'Consolas', monospace", fontSize: '13px', color: '#24292f' }}>
            <code {...props}>{children}</code>
          </pre>
        </div>
      )
    }
    return (
      <code
        style={{
          background: '#f0f0f0',
          border: '1px solid #cccccc',
          borderRadius: '4px',
          padding: '1px 5px',
          fontSize: '12px',
          color: '#0d7a4e',
          fontFamily: "'Fira Code', 'Consolas', monospace",
        }}
        {...props}
      >
        {children}
      </code>
    )
  },
  table({ children }) {
    return (
      <div style={{ overflowX: 'auto', margin: '8px 0' }}>
        <table style={{
          borderCollapse: 'collapse',
          width: '100%',
          fontSize: '13px',
        }}>
          {children}
        </table>
      </div>
    )
  },
  th({ children }) {
    return (
      <th style={{
        border: '1px solid #cccccc',
        padding: '8px 12px',
        background: '#f0f0f0',
        color: '#111111',
        textAlign: 'left',
      }}>
        {children}
      </th>
    )
  },
  td({ children }) {
    return (
      <td style={{
        border: '1px solid #e0e0e0',
        padding: '7px 12px',
        color: '#333333',
      }}>
        {children}
      </td>
    )
  },
  p({ children }) {
    return <p style={{ margin: '4px 0' }}>{children}</p>
  },
  ul({ children }) {
    return <ul style={{ paddingLeft: '20px', margin: '4px 0' }}>{children}</ul>
  },
  ol({ children }) {
    return <ol style={{ paddingLeft: '20px', margin: '4px 0' }}>{children}</ol>
  },
  li({ children }) {
    return <li style={{ margin: '2px 0' }}>{children}</li>
  },
  h1({ children }) {
    return <h1 style={{ color: '#111111', margin: '8px 0 4px', fontSize: '18px' }}>{children}</h1>
  },
  h2({ children }) {
    return <h2 style={{ color: '#111111', margin: '8px 0 4px', fontSize: '16px' }}>{children}</h2>
  },
  h3({ children }) {
    return <h3 style={{ color: '#333333', margin: '6px 0 2px', fontSize: '14px' }}>{children}</h3>
  },
  blockquote({ children }) {
    return (
      <blockquote style={{
        borderLeft: '3px solid #0d9e65',
        paddingLeft: '12px',
        margin: '8px 0',
        color: '#666666',
        fontStyle: 'italic',
      }}>
        {children}
      </blockquote>
    )
  },
  hr() {
    return <hr style={{ border: 'none', borderTop: '1px solid #e0e0e0', margin: '12px 0' }} />
  },
  strong({ children }) {
    return <strong style={{ color: '#111111' }}>{children}</strong>
  },
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function MessageBubble({ role, content, timestamp, username }) {
  const isUser = role === 'user'

  return (
    <div style={{ ...styles.wrapper, ...(isUser ? styles.wrapperUser : {}) }}>
      <div style={{ ...styles.avatar, ...(isUser ? styles.avatarUser : styles.avatarAssistant) }}>
        {isUser ? (username?.[0]?.toUpperCase() || 'U') : '🤖'}
      </div>
      <div style={styles.bubble}>
        <div style={isUser ? styles.bubbleUser : styles.bubbleAssistant}>
          {isUser ? (
            <span style={{ whiteSpace: 'pre-wrap' }}>{content}</span>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {content}
            </ReactMarkdown>
          )}
        </div>
        <div style={{ ...styles.timestamp, textAlign: isUser ? 'right' : 'left' }}>
          {formatTime(timestamp)}
        </div>
      </div>
    </div>
  )
}