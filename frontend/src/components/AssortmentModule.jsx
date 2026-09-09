import React, { useState, useEffect } from 'react';
import { ShoppingBag, Grid, Maximize2, Award, AlertCircle } from 'lucide-react';
import { API_BASE_URL } from '../config/api';

export default function AssortmentModule() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/modules/assortment`)
      .then(res => res.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ padding: '40px', color: '#94a3b8' }}>Loading Retail Assortment Intelligence...</div>;

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Banner */}
      <div className="glass-panel" style={{ padding: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: '0.75rem', color: '#8b5cf6', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px' }}>
            Module 8: Retail Assortment & Space Optimizer
          </span>
          <h2 style={{ fontSize: '1.4rem', color: '#f8fafc', margin: '4px 0 0 0' }}>
            Store Shelf Facing, GMROI & Space Productivity Analysis
          </h2>
        </div>
        <div style={{ display: 'flex', gap: '24px' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#818cf8' }}>{data?.avg_store_gmroi || 0}x</div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Avg Store GMROI</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#6ee7b7' }}>{data?.avg_sell_through_pct || 0}%</div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Sell-Through Rate</div>
          </div>
        </div>
      </div>

      {/* SKU Productivity & Space Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '16px', color: '#f8fafc' }}>Store Shelf Facing & Revenue per Sq. Meter</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8' }}>
              <th style={{ padding: '12px' }}>SKU</th>
              <th style={{ padding: '12px' }}>Product Name</th>
              <th style={{ padding: '12px' }}>Allocated Space</th>
              <th style={{ padding: '12px' }}>Display Units</th>
              <th style={{ padding: '12px' }}>GMROI</th>
              <th style={{ padding: '12px' }}>Sell-Through</th>
              <th style={{ padding: '12px' }}>Rev / sqm</th>
              <th style={{ padding: '12px' }}>Productivity Status</th>
            </tr>
          </thead>
          <tbody>
            {(data?.sku_assortment || []).map((item, idx) => (
              <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '12px', fontFamily: 'monospace', color: '#818cf8' }}>{item.sku}</td>
                <td style={{ padding: '12px', fontWeight: 600, color: '#f8fafc' }}>{item.product_name}</td>
                <td style={{ padding: '12px', color: '#e2e8f0' }}>{item.allocated_space_sqm} sqm</td>
                <td style={{ padding: '12px', color: '#e2e8f0' }}>{item.display_units} units</td>
                <td style={{ padding: '12px', fontWeight: 700, color: item.gmroi >= 2.0 ? '#6ee7b7' : '#fde047' }}>{item.gmroi}x</td>
                <td style={{ padding: '12px', color: '#67e8f9' }}>{item.sell_through_pct}%</td>
                <td style={{ padding: '12px', fontWeight: 700, color: '#f8fafc' }}>AED {item.revenue_per_sqm.toLocaleString()}</td>
                <td style={{ padding: '12px' }}>
                  <span className={`badge ${
                    item.classification === 'STAR_PRODUCT' ? 'badge-success' :
                    item.classification === 'CORE_STABLE' ? 'badge-medium' : 'badge-critical'
                  }`}>
                    {item.classification}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
