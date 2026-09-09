import React, { useState, useEffect } from 'react';
import {
  Building2,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Box,
  Truck,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
  Info,
  DollarSign,
  Plus
} from 'lucide-react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis
} from 'recharts';
import { API_BASE_URL } from '../config/api';

export default function DashboardView({ onNavigate }) {
  const [summary, setSummary] = useState(null);
  const [warehouses, setWarehouses] = useState([]);
  const [risks, setRisks] = useState([]);

  useEffect(() => {
    async function loadTower() {
      try {
        const [sumRes, whRes, riskRes] = await Promise.all([
          fetch(`${API_BASE_URL}/api/control-tower/summary`),
          fetch(`${API_BASE_URL}/api/warehouses`),
          fetch(`${API_BASE_URL}/api/inventory-risk`)
        ]);

        if (sumRes.ok) setSummary(await sumRes.json());
        if (whRes.ok) setWarehouses(await whRes.json());
        if (riskRes.ok) setRisks(await riskRes.json());
      } catch (err) {
        console.error('Error loading control tower data:', err);
      }
    }
    loadTower();
  }, []);

  const totalSKUs = summary?.total_products ?? 0;
  const criticalCount = summary?.stockout_critical_count ?? 0;
  const highCount = summary?.stockout_high_count ?? 0;
  const excessCount = summary?.excess_inventory_count ?? 0;
  const totalItems = summary?.total_inventory_items ?? 0;
  const optimalCount = Math.max(0, totalItems - criticalCount - highCount - excessCount);

  const pieData = totalItems > 0 ? [
    { name: 'Optimal', value: optimalCount, color: '#10b981' },
    { name: 'Excess Stock', value: excessCount, color: '#f59e0b' },
    { name: 'High Risk', value: highCount, color: '#f97316' },
    { name: 'Critical Stockout', value: criticalCount, color: '#ef4444' },
  ] : [
    { name: 'No Inventory', value: 1, color: '#e2e8f0' }
  ];

  return (
    <div style={{ padding: '0 32px 32px 32px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* 4 Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
        <div className="ui-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 600 }}>Active Catalog SKUs</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#0f172a', margin: '4px 0' }}>{totalSKUs}</div>
          <div style={{ fontSize: '0.72rem', color: totalSKUs > 0 ? '#10b981' : '#94a3b8', fontWeight: 600 }}>
            {totalSKUs > 0 ? '✓ Canonical Mapped' : 'Pending Data Connection'}
          </div>
        </div>

        <div className="ui-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 600 }}>Total Inventory Value</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#0f172a', margin: '4px 0' }}>
            ${(summary?.total_inventory_value ?? 0).toLocaleString()}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#2563eb', fontWeight: 600 }}>
            {warehouses.length} Regional Hubs
          </div>
        </div>

        <div className="ui-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 600 }}>Supplier OTIF Average</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: summary?.avg_supplier_otif ? '#10b981' : '#94a3b8', margin: '4px 0' }}>
            {(summary?.avg_supplier_otif ?? 0).toFixed(1)}%
          </div>
          <div style={{ fontSize: '0.72rem', color: summary?.avg_supplier_otif ? '#10b981' : '#94a3b8', fontWeight: 600 }}>
            {summary?.avg_supplier_otif ? '↑ On-Time In-Full' : 'No Supplier Data'}
          </div>
        </div>

        <div className="ui-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 600 }}>Stockout Vulnerability</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: criticalCount > 0 ? '#ef4444' : '#10b981', margin: '4px 0' }}>
            {criticalCount} SKUs
          </div>
          <div style={{ fontSize: '0.72rem', color: criticalCount > 0 ? '#ef4444' : '#10b981', fontWeight: 600 }}>
            {criticalCount > 0 ? '● Emergency POs Suggested' : '✓ 0 Critical Stockouts'}
          </div>
        </div>
      </div>

      {/* 2-Column Middle Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: '20px' }}>
        
        {/* Left: Warehouse Node Status */}
        <div className="ui-card" style={{ padding: '22px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>
              Regional Fulfillment Hubs
            </h3>
            <span style={{ fontSize: '0.75rem', color: '#2563eb', fontWeight: 700 }}>
              {warehouses.length} Active Nodes
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {warehouses.length > 0 ? (
              warehouses.map((wh) => (
                <div
                  key={wh.code || wh.id}
                  style={{
                    padding: '14px 16px',
                    borderRadius: '10px',
                    backgroundColor: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '36px', height: '36px', borderRadius: '8px',
                      backgroundColor: '#eff6ff', color: '#2563eb',
                      display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      <Building2 size={18} />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0f172a' }}>{wh.name}</div>
                      <div style={{ fontSize: '0.72rem', color: '#64748b' }}>{wh.location} • Code: {wh.code}</div>
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Capacity</div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0f172a' }}>
                      {wh.capacity?.toLocaleString()} sqft
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div style={{
                padding: '30px 16px',
                textAlign: 'center',
                backgroundColor: '#f8fafc',
                borderRadius: '10px',
                border: '1px dashed #cbd5e1'
              }}>
                <Building2 size={24} color="#94a3b8" style={{ margin: '0 auto 8px auto' }} />
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#334155' }}>
                  No Fulfillment Nodes Connected
                </div>
                <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '2px' }}>
                  Connect your warehouse management system or database in Data Sources.
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Portfolio Risk Distribution Pie */}
        <div className="ui-card" style={{ padding: '22px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0f172a', margin: '0 0 16px 0' }}>
            Inventory Health Distribution
          </h3>

          <div style={{ width: '100%', height: '220px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', marginTop: '10px' }}>
            {totalItems > 0 ? (
              pieData.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem' }}>
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: item.color }} />
                  <span style={{ color: '#64748b' }}>{item.name}:</span>
                  <span style={{ fontWeight: 700, color: '#0f172a' }}>{item.value} items</span>
                </div>
              ))
            ) : (
              <div style={{ gridColumn: 'span 2', textAlign: 'center', color: '#94a3b8', fontSize: '0.75rem' }}>
                0 inventory items connected in database.
              </div>
            )}
          </div>
        </div>

      </div>

    </div>
  );
}
