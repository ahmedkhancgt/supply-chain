import React, { useState, useRef, useEffect } from 'react';
import { X, Send, Bot, User, Cpu, Sparkles, AlertCircle, MessageSquare } from 'lucide-react';
import { API_BASE_URL } from '../config/api';

export default function AIAssistantDrawer({ isOpen, onClose }) {
  const [messages, setMessages] = useState([
    {
      sender: 'bot',
      text: "Hello! I am your Wisualyst AI Decision Assistant powered by ReAct & MCP Tools.\n\nYou can ask me questions like:\n• *'Which products are at risk of stockout in the next 7 days?'*\n• *'Why is SKU-ELEC-101 at risk?'*\n• *'What should we reorder for Bangalore warehouse?'*",
      tools_used: [],
      reasoning: "System initialized with live database MCP tools."
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (!isOpen) return null;

  const handleSend = async (textToSend) => {
    const query = textToSend || input;
    if (!query.trim() || loading) return;

    const userMsg = { sender: 'user', text: query };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/api/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query })
      });

      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, {
          sender: 'bot',
          text: data.response,
          tools_used: data.tools_used || [],
          reasoning: data.reasoning_summary
        }]);
      } else {
        setMessages(prev => [...prev, {
          sender: 'bot',
          text: "I encountered an issue connecting to the AI Agent service. Please ensure the backend server is running."
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        sender: 'bot',
        text: "Error communicating with AI service. Please check network connection."
      }]);
    } finally {
      setLoading(false);
    }
  };

  const samplePrompts = [
    "Which products are at risk of stockout in the next 7 days?",
    "Why is SKU-ELEC-101 at risk?",
    "What should we reorder for Bangalore warehouse?"
  ];

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      right: 0,
      width: '420px',
      height: '100vh',
      backgroundColor: '#ffffff',
      borderLeft: '1px solid #e2e8f0',
      zIndex: 1000,
      display: 'flex',
      flexDirection: 'column',
      boxShadow: '-10px 0 35px rgba(15, 23, 42, 0.12)'
    }}>
      {/* Drawer Header */}
      <div style={{
        padding: '20px 24px',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #f8fafc, #eff6ff)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #2563eb, #8b5cf6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
            boxShadow: '0 4px 10px rgba(37, 99, 235, 0.25)'
          }}>
            <Sparkles size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>
              Wisualyst AI Assistant
            </h3>
            <span style={{ fontSize: '0.72rem', color: '#2563eb', fontWeight: 600 }}>
              ReAct Agent + Live MCP Tools
            </span>
          </div>
        </div>

        <button
          onClick={onClose}
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            padding: '6px',
            color: '#64748b',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Messages List */}
      <div style={{
        flex: 1,
        padding: '20px',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
        backgroundColor: '#f8fafc'
      }}>
        {messages.map((m, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              gap: '10px',
              flexDirection: m.sender === 'user' ? 'row-reverse' : 'row'
            }}
          >
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              backgroundColor: m.sender === 'user' ? '#1e293b' : '#eff6ff',
              color: m.sender === 'user' ? '#ffffff' : '#2563eb',
              border: m.sender === 'user' ? 'none' : '1px solid #bfdbfe',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              fontWeight: 700,
              fontSize: '0.8rem'
            }}>
              {m.sender === 'user' ? <User size={15} /> : <Bot size={16} />}
            </div>

            <div style={{ maxWidth: '82%' }}>
              <div style={{
                backgroundColor: m.sender === 'user' ? '#2563eb' : '#ffffff',
                color: m.sender === 'user' ? '#ffffff' : '#1e293b',
                border: m.sender === 'user' ? 'none' : '1px solid #e2e8f0',
                padding: '12px 14px',
                borderRadius: '14px',
                borderTopRightRadius: m.sender === 'user' ? '4px' : '14px',
                borderTopLeftRadius: m.sender === 'user' ? '14px' : '4px',
                fontSize: '0.82rem',
                lineHeight: 1.5,
                boxShadow: m.sender === 'user' ? '0 4px 12px rgba(37, 99, 235, 0.2)' : '0 2px 6px rgba(0,0,0,0.03)',
                whiteSpace: 'pre-wrap'
              }}>
                {m.text}
              </div>

              {m.tools_used && m.tools_used.length > 0 && (
                <div style={{
                  fontSize: '0.68rem',
                  color: '#7c3aed',
                  marginTop: '4px',
                  fontFamily: 'var(--font-mono)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontWeight: 600
                }}>
                  <Cpu size={11} /> Tools: {m.tools_used.join(', ')}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: '#2563eb',
            fontSize: '0.78rem',
            fontWeight: 600,
            padding: '8px 12px',
            backgroundColor: '#eff6ff',
            borderRadius: '10px',
            width: 'fit-content'
          }}>
            <Sparkles size={14} className="spin" />
            <span>AI Reasoning & querying live database tools...</span>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Suggested Prompts */}
      <div style={{
        padding: '12px 20px',
        backgroundColor: '#ffffff',
        borderTop: '1px solid #e2e8f0'
      }}>
        <div style={{ fontSize: '0.68rem', color: '#64748b', fontWeight: 700, marginBottom: '6px', letterSpacing: '0.3px' }}>
          SUGGESTED QUESTIONS:
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {samplePrompts.map((p, i) => (
            <button
              key={i}
              onClick={() => handleSend(p)}
              style={{
                backgroundColor: '#f8fafc',
                border: '1px solid #e2e8f0',
                color: '#334155',
                padding: '6px 10px',
                borderRadius: '8px',
                textAlign: 'left',
                fontSize: '0.74rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#eff6ff';
                e.currentTarget.style.borderColor = '#bfdbfe';
                e.currentTarget.style.color = '#2563eb';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#f8fafc';
                e.currentTarget.style.borderColor = '#e2e8f0';
                e.currentTarget.style.color = '#334155';
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Chat Input */}
      <div style={{
        padding: '16px 20px',
        backgroundColor: '#ffffff',
        borderTop: '1px solid #e2e8f0',
        display: 'flex',
        gap: '8px',
        alignItems: 'center'
      }}>
        <input
          type="text"
          placeholder="Ask AI about stock risks, forecasts, suppliers..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          className="ui-input"
          style={{ flex: 1, fontSize: '0.82rem', padding: '10px 14px' }}
        />
        <button
          onClick={() => handleSend()}
          className="btn-primary"
          disabled={loading || !input.trim()}
          style={{
            padding: '10px 14px',
            opacity: loading || !input.trim() ? 0.6 : 1
          }}
        >
          <Send size={15} />
        </button>
      </div>
    </div>
  );
}
