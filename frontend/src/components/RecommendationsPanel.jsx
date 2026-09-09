import React from 'react';
import { ShoppingBag, ArrowRight, ShieldAlert, CheckCircle2, AlertTriangle, Lightbulb } from 'lucide-react';

export default function RecommendationsPanel({ recommendations }) {
  return (
    <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ padding: '8px', borderRadius: '10px', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8' }}>
            <Lightbulb size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.15rem', color: '#f8fafc', margin: 0 }}>Unified Cross-Module Recommendations</h3>
            <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Standardized actionable insights across Inventory, Demand, Procurement, and Assortment</span>
          </div>
        </div>
        <span className="badge badge-medium">{recommendations.length} Active Insights</span>
      </div>

      {recommendations.length === 0 ? (
        <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>
          <CheckCircle2 size={36} color="#10b981" style={{ marginBottom: '8px' }} />
          <div>All operations optimal. No open recommendations.</div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '16px' }}>
          {recommendations.map((rec, idx) => (
            <div 
              key={idx}
              style={{
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '12px',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                  <span className={`badge ${
                    rec.severity === 'critical' ? 'badge-critical' :
                    rec.severity === 'high' ? 'badge-high' : 'badge-medium'
                  }`}>
                    {rec.module.toUpperCase()} — {rec.severity.toUpperCase()}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 600 }}>
                    +AED {(rec.financial_impact || 0).toLocaleString()} Impact
                  </span>
                </div>
                <h4 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc', marginBottom: '6px' }}>
                  {rec.title}
                </h4>
                <p style={{ fontSize: '0.82rem', color: '#94a3b8', marginBottom: '12px', lineHeight: '1.4' }}>
                  {rec.summary}
                </p>
                <div style={{ fontSize: '0.78rem', color: '#cbd5e1', background: 'rgba(255,255,255,0.03)', padding: '8px 12px', borderRadius: '6px', marginBottom: '14px', borderLeft: '3px solid #6366f1' }}>
                  <strong>Reason:</strong> {rec.reason}
                </div>
              </div>

              <div style={{ paddingTop: '12px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontSize: '0.8rem', color: '#6ee7b7', fontWeight: 600, marginBottom: '4px' }}>
                  Action: {rec.recommended_action}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: '12px' }}>
                  Alt: {rec.alternative_action}
                </div>
                <button 
                  onClick={() => alert(`Action executed for ${rec.recommendation_id}: ${rec.recommended_action}`)}
                  className="glow-btn-primary" 
                  style={{ width: '100%', justifyContent: 'center', padding: '8px 14px', fontSize: '0.8rem' }}
                >
                  Execute Recommendation <ArrowRight size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
