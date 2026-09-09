import React from 'react';
import { Sparkles, Bot, RefreshCw, CheckCircle2, ChevronDown, Layers, Database } from 'lucide-react';

export default function Navbar({ onOpenChat, onRelaunchOnboarding, activeTab }) {
  return (
    <header className="glass-panel" style={{ borderRadius: 0, borderTop: 0, borderLeft: 0, borderRight: 0, padding: '12px 24px', position: 'sticky', top: 0, zIndex: 50 }}>
      <div style={{ maxWidth: '1400px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        
        {/* Brand & Workspace Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
            <div style={{ padding: '8px', borderRadius: '10px', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff', display: 'flex', alignItems: 'center' }}>
              <Sparkles size={20} />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: '1.15rem', letterSpacing: '-0.5px', color: '#f8fafc' }}>
                WISUALYST
              </div>
              <div style={{ fontSize: '0.68rem', color: '#818cf8', fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                Decision-Intelligence Platform
              </div>
            </div>
          </div>

          <div style={{ height: '24px', width: '1px', background: 'rgba(255,255,255,0.1)' }} />

          {/* Workspace Pill */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', cursor: 'pointer' }}>
            <Database size={14} color="#06b6d4" />
            <span style={{ fontSize: '0.82rem', fontWeight: 500, color: '#e2e8f0' }}>Wisualyst Middle East Retail</span>
            <ChevronDown size={14} color="#94a3b8" />
          </div>
        </div>

        {/* Status Indicators & Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {/* Data Quality Health Pill */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '20px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.25)', fontSize: '0.78rem', color: '#6ee7b7' }}>
            <CheckCircle2 size={14} />
            <span>Canonical Data Sync: 91% Ready</span>
          </div>

          <button 
            onClick={onRelaunchOnboarding}
            style={{ padding: '8px 14px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={14} /> Re-run Onboarding
          </button>

          {/* AI Assistant Button */}
          <button 
            onClick={onOpenChat}
            className="glow-btn-primary"
            style={{ padding: '8px 16px', fontSize: '0.85rem' }}
          >
            <Bot size={16} /> Ask Wisualyst AI
          </button>
        </div>

      </div>
    </header>
  );
}
