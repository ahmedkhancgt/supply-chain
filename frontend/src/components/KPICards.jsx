import React from 'react';
import { DollarSign, ShieldAlert, TrendingUp, Award, ShoppingBag } from 'lucide-react';

export default function KPICards({ summaryData }) {
  const cards = [
    {
      title: 'Total Inventory Value',
      value: `AED ${(summaryData?.total_inventory_value || 0).toLocaleString()}`,
      change: 'Canonical DB Total',
      isPositive: true,
      icon: DollarSign,
      color: '#6366f1'
    },
    {
      title: 'Stockout Critical Risks',
      value: (summaryData?.stockout_critical_count || 0).toString(),
      change: summaryData?.stockout_critical_count > 0 ? 'Requires PO action' : 'Optimal levels',
      isPositive: (summaryData?.stockout_critical_count || 0) === 0,
      icon: ShieldAlert,
      color: '#f43f5e'
    },
    {
      title: 'Potential PO Savings (EOQ)',
      value: `AED ${(summaryData?.potential_savings || 0).toLocaleString()}`,
      change: 'EOQ optimization',
      isPositive: true,
      icon: TrendingUp,
      color: '#10b981'
    },
    {
      title: 'Avg Supplier OTIF Score',
      value: `${summaryData?.avg_supplier_otif || 0}%`,
      change: 'On-Time In-Full',
      isPositive: (summaryData?.avg_supplier_otif || 0) >= 90,
      icon: Award,
      color: '#06b6d4'
    },
    {
      title: 'Store Shelf Space GMROI',
      value: `${summaryData?.avg_store_gmroi || 0}x`,
      change: 'Gross Margin Return',
      isPositive: (summaryData?.avg_store_gmroi || 0) >= 1.5,
      icon: ShoppingBag,
      color: '#8b5cf6'
    }
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px', marginBottom: '24px' }}>
      {cards.map((c, i) => {
        const IconComp = c.icon;
        return (
          <div key={i} className="glass-panel glass-panel-hover" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 500 }}>{c.title}</span>
              <div style={{ padding: '8px', borderRadius: '10px', background: `${c.color}20`, color: c.color }}>
                <IconComp size={18} />
              </div>
            </div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#f8fafc', marginBottom: '4px', letterSpacing: '-0.5px' }}>
              {c.value}
            </div>
            <div style={{ fontSize: '0.72rem', color: c.isPositive ? '#6ee7b7' : '#fda4af', fontWeight: 500 }}>
              {c.change}
            </div>
          </div>
        );
      })}
    </div>
  );
}
