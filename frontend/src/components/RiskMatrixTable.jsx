import React, { useState } from 'react';
import { ShieldAlert, Filter, Search, ChevronRight } from 'lucide-react';

export default function RiskMatrixTable({ risks, warehouses, onSelectProduct }) {
  const [selectedRisk, setSelectedRisk] = useState('ALL');
  const [selectedWarehouse, setSelectedWarehouse] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  const filteredRisks = risks.filter(item => {
    const matchRisk = selectedRisk === 'ALL' || item.stockout_risk_level === selectedRisk;
    const matchWh = selectedWarehouse === 'ALL' || item.warehouse_id === parseInt(selectedWarehouse);
    const matchSearch = item.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                        item.sku.toLowerCase().includes(searchTerm.toLowerCase());
    return matchRisk && matchWh && matchSearch;
  });

  return (
    <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <ShieldAlert size={20} color="var(--primary-indigo)" />
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Inventory Risk Intelligence Matrix</h3>
          <span style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.08)', padding: '0.2rem 0.6rem', borderRadius: '6px', color: 'var(--text-muted)' }}>
            {filteredRisks.length} SKUs evaluated
          </span>
        </div>

        {/* Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
            <input 
              type="text" 
              placeholder="Search SKU or Name..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input-dark"
              style={{ paddingLeft: '2rem', width: '180px' }}
            />
          </div>

          <select 
            value={selectedWarehouse} 
            onChange={(e) => setSelectedWarehouse(e.target.value)}
            className="input-dark"
          >
            <option value="ALL">All Warehouses</option>
            {warehouses.map(w => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>

          <select 
            value={selectedRisk} 
            onChange={(e) => setSelectedRisk(e.target.value)}
            className="input-dark"
          >
            <option value="ALL">All Risk Levels</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low / Excess</option>
          </select>
        </div>
      </div>

      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>SKU & Product Name</th>
              <th>Warehouse Hub</th>
              <th>Current Stock</th>
              <th>Safety Stock</th>
              <th>Reorder Point</th>
              <th>Days of Supply</th>
              <th>Risk Level</th>
              <th>Recommended Order</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredRisks.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                  No inventory risks match the selected filters.
                </td>
              </tr>
            ) : (
              filteredRisks.map((row, idx) => {
                const badgeClass = row.stockout_risk_level === 'CRITICAL' ? 'badge-critical' :
                                  row.stockout_risk_level === 'HIGH' ? 'badge-high' :
                                  row.stockout_risk_level === 'MEDIUM' ? 'badge-medium' : 'badge-low';
                return (
                  <tr key={idx}>
                    <td>
                      <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{row.product_name}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>{row.sku}</div>
                    </td>
                    <td>{row.warehouse_name}</td>
                    <td style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{row.current_stock} units</td>
                    <td style={{ color: 'var(--text-muted)' }}>{row.safety_stock}</td>
                    <td style={{ color: 'var(--text-muted)' }}>{row.reorder_point}</td>
                    <td style={{ fontWeight: 600, color: row.days_of_inventory < row.lead_time_days ? 'var(--color-critical)' : 'var(--text-main)' }}>
                      {row.days_of_inventory} days
                    </td>
                    <td>
                      <span className={`badge ${badgeClass}`}>
                        {row.stockout_risk_level}
                      </span>
                    </td>
                    <td style={{ fontWeight: 700, color: row.recommended_order_quantity > 0 ? 'var(--primary-cyan)' : 'var(--text-dim)' }}>
                      {row.recommended_order_quantity > 0 ? `${row.recommended_order_quantity} units` : 'None'}
                    </td>
                    <td>
                      <button 
                        onClick={() => onSelectProduct(row.product_id)}
                        className="btn-primary" 
                        style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
                      >
                        Forecast <ChevronRight size={12} />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
