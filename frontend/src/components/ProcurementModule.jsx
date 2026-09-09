import React, { useState, useEffect } from 'react';
import { ShoppingCart, Award, TrendingUp, AlertTriangle, ShieldCheck } from 'lucide-react';
import { API_BASE_URL } from '../config/api';

export default function ProcurementModule() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/modules/procurement`)
      .then(res => res.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ padding: '40px', color: '#94a3b8' }}>Loading Procurement Intelligence...</div>;

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Module Banner */}
      <div className="glass-panel" style={{ padding: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px' }}>
            Module 4: Intelligent Procurement Optimizer
          </span>
          <h2 style={{ fontSize: '1.4rem', color: '#f8fafc', margin: '4px 0 0 0' }}>
            Economic Order Quantity (EOQ) & Supplier OTIF Tracking
          </h2>
        </div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#6ee7b7' }}>AED {(data?.potential_savings || 0).toLocaleString()}</div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Potential Cost Savings</div>
          </div>
        </div>
      </div>

      {/* Supplier Performance Grid */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '16px', color: '#f8fafc' }}>Supplier Performance & OTIF Scores</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8' }}>
              <th style={{ padding: '12px' }}>Supplier Code</th>
              <th style={{ padding: '12px' }}>Supplier Name</th>
              <th style={{ padding: '12px' }}>Rating</th>
              <th style={{ padding: '12px' }}>OTIF Score (%)</th>
              <th style={{ padding: '12px' }}>Avg Lead Time</th>
              <th style={{ padding: '12px' }}>Risk Level</th>
            </tr>
          </thead>
          <tbody>
            {(data?.supplier_performance || []).map((s, idx) => (
              <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '12px', fontFamily: 'monospace', color: '#818cf8' }}>{s.code}</td>
                <td style={{ padding: '12px', fontWeight: 600, color: '#f8fafc' }}>{s.name}</td>
                <td style={{ padding: '12px', color: '#fde047' }}>⭐ {s.rating}</td>
                <td style={{ padding: '12px', fontWeight: 700, color: s.otif_score_pct >= 90 ? '#6ee7b7' : '#fde047' }}>{s.otif_score_pct}%</td>
                <td style={{ padding: '12px', color: '#e2e8f0' }}>{s.avg_lead_time_days} days</td>
                <td style={{ padding: '12px' }}>
                  <span className={`badge ${s.risk_level === 'LOW' ? 'badge-success' : 'badge-high'}`}>{s.risk_level}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* PO Order Recommendations */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '16px', color: '#f8fafc' }}>Automated Reorder PO Recommendations</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8' }}>
              <th style={{ padding: '12px' }}>SKU</th>
              <th style={{ padding: '12px' }}>Product Name</th>
              <th style={{ padding: '12px' }}>Current Stock</th>
              <th style={{ padding: '12px' }}>Rec. Order Qty (EOQ)</th>
              <th style={{ padding: '12px' }}>Est. Cost</th>
              <th style={{ padding: '12px' }}>Potential Savings</th>
              <th style={{ padding: '12px' }}>Urgency</th>
            </tr>
          </thead>
          <tbody>
            {(data?.order_recommendations || []).map((o, idx) => (
              <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '12px', fontFamily: 'monospace', color: '#06b6d4' }}>{o.sku}</td>
                <td style={{ padding: '12px', fontWeight: 500, color: '#f8fafc' }}>{o.product_name}</td>
                <td style={{ padding: '12px', color: '#e2e8f0' }}>{o.current_stock}</td>
                <td style={{ padding: '12px', fontWeight: 700, color: '#818cf8' }}>{o.recommended_po_qty} units</td>
                <td style={{ padding: '12px', color: '#f8fafc' }}>AED {o.estimated_order_cost.toLocaleString()}</td>
                <td style={{ padding: '12px', color: '#6ee7b7', fontWeight: 600 }}>AED {o.potential_savings.toLocaleString()}</td>
                <td style={{ padding: '12px' }}>
                  <span className={`badge ${o.urgency === 'CRITICAL' ? 'badge-critical' : 'badge-high'}`}>{o.urgency}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
