import React, { useState } from 'react';
import {
  Bell,
  HelpCircle,
  Calendar,
  SlidersHorizontal,
  ChevronDown,
  CheckCircle2,
  AlertTriangle,
  Info,
  X
} from 'lucide-react';

export default function HeaderBar({
  title,
  subtitle,
  dateRange = 'May 12 – May 18, 2024',
  onDateChange,
  showFilters = true,
  onFilterClick,
  onOpenHelp,
  customAction
}) {
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [dateDropdownOpen, setDateDropdownOpen] = useState(false);
  const [selectedDateRange, setSelectedDateRange] = useState(dateRange);

  const notifications = [
    { id: 1, type: 'warning', title: 'High stockout risk for SKU B23', desc: '5 locations affected across West Region', time: '10m ago' },
    { id: 2, type: 'info', title: 'Supplier ABC OTIF drop', desc: 'OTIF fell below 85% threshold', time: '42m ago' },
    { id: 3, type: 'success', title: 'Data Ingestion Complete', desc: '5.2M records synced from PostgreSQL & Zoho', time: '2h ago' },
  ];

  const dateOptions = [
    'May 12 – May 18, 2024',
    'Last 7 Days',
    'Last 30 Days',
    'Current Quarter (Q2 2024)',
    'Year to Date (2024)'
  ];

  return (
    <header style={{
      position: 'relative',
      padding: '24px 32px 18px 32px',
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: '20px',
      zIndex: 20
    }}>
      {/* Background Ambient Swirl */}
      <div className="ambient-header-swirl" />

      {/* Left: Titles */}
      <div style={{ position: 'relative', zIndex: 2 }}>
        <h1 style={{
          fontSize: '1.75rem',
          fontWeight: 700,
          color: '#0f172a',
          letterSpacing: '-0.5px',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          {title}
        </h1>
        {subtitle && (
          <p style={{
            fontSize: '0.9rem',
            color: '#64748b',
            margin: '4px 0 0 0',
            fontWeight: 400
          }}>
            {subtitle}
          </p>
        )}
      </div>

      {/* Right: Controls & Actions */}
      <div style={{
        position: 'relative',
        zIndex: 2,
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}>
        {/* Custom page action if provided */}
        {customAction}

        {/* Date Range Picker */}
        {selectedDateRange && (
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setDateDropdownOpen(!dateDropdownOpen)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 14px',
                borderRadius: '10px',
                backgroundColor: '#ffffff',
                border: '1px solid #e2e8f0',
                fontSize: '0.85rem',
                fontWeight: 500,
                color: '#334155',
                cursor: 'pointer',
                boxShadow: 'var(--shadow-sm)',
                fontFamily: 'var(--font-main)'
              }}
            >
              <Calendar size={15} color="#64748b" />
              <span>{selectedDateRange}</span>
              <ChevronDown size={14} color="#94a3b8" />
            </button>

            {dateDropdownOpen && (
              <div style={{
                position: 'absolute',
                top: '100%',
                right: 0,
                marginTop: '6px',
                backgroundColor: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '12px',
                boxShadow: 'var(--shadow-lg)',
                padding: '6px',
                width: '210px',
                zIndex: 50
              }}>
                {dateOptions.map(opt => (
                  <div
                    key={opt}
                    onClick={() => {
                      setSelectedDateRange(opt);
                      if (onDateChange) onDateChange(opt);
                      setDateDropdownOpen(false);
                    }}
                    style={{
                      padding: '8px 12px',
                      borderRadius: '8px',
                      fontSize: '0.82rem',
                      color: selectedDateRange === opt ? '#2563eb' : '#334155',
                      fontWeight: selectedDateRange === opt ? 600 : 500,
                      backgroundColor: selectedDateRange === opt ? '#eff6ff' : 'transparent',
                      cursor: 'pointer'
                    }}
                    onMouseEnter={(e) => {
                      if (selectedDateRange !== opt) e.currentTarget.style.backgroundColor = '#f8fafc';
                    }}
                    onMouseLeave={(e) => {
                      if (selectedDateRange !== opt) e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    {opt}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Filters Button */}
        {showFilters && (
          <button
            onClick={onFilterClick}
            className="btn-primary"
            style={{
              padding: '8px 16px',
              fontSize: '0.85rem',
              fontWeight: 600
            }}
          >
            <SlidersHorizontal size={15} />
            <span>Filters</span>
          </button>
        )}

        {/* Notifications Icon with Red Dot */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setNotificationsOpen(!notificationsOpen)}
            style={{
              width: '38px',
              height: '38px',
              borderRadius: '50%',
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              position: 'relative',
              boxShadow: 'var(--shadow-sm)'
            }}
            title="Notifications"
          >
            <Bell size={18} color="#475569" />
            {/* Red Badge Dot */}
            <span style={{
              position: 'absolute',
              top: '7px',
              right: '8px',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: '#ef4444',
              border: '1.5px solid #ffffff'
            }} />
          </button>

          {/* Notifications Dropdown */}
          {notificationsOpen && (
            <div style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: '8px',
              width: '320px',
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '16px',
              boxShadow: 'var(--shadow-xl)',
              padding: '16px',
              zIndex: 50
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#0f172a' }}>Recent Alerts & Updates</div>
                <button
                  onClick={() => setNotificationsOpen(false)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
                >
                  <X size={16} />
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {notifications.map(n => (
                  <div key={n.id} style={{
                    padding: '10px 12px',
                    borderRadius: '10px',
                    backgroundColor: n.type === 'warning' ? '#fffbeb' : n.type === 'success' ? '#ecfdf5' : '#eff6ff',
                    border: `1px solid ${n.type === 'warning' ? '#fde68a' : n.type === 'success' ? '#a7f3d0' : '#dbeafe'}`,
                    display: 'flex',
                    gap: '10px'
                  }}>
                    {n.type === 'warning' && <AlertTriangle size={16} color="#d97706" style={{ flexShrink: 0, marginTop: '2px' }} />}
                    {n.type === 'success' && <CheckCircle2 size={16} color="#059669" style={{ flexShrink: 0, marginTop: '2px' }} />}
                    {n.type === 'info' && <Info size={16} color="#2563eb" style={{ flexShrink: 0, marginTop: '2px' }} />}
                    <div>
                      <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#0f172a' }}>{n.title}</div>
                      <div style={{ fontSize: '0.75rem', color: '#475569', marginTop: '2px' }}>{n.desc}</div>
                      <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '4px' }}>{n.time}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Help / Guide Icon */}
        <button
          onClick={onOpenHelp}
          style={{
            width: '38px',
            height: '38px',
            borderRadius: '50%',
            backgroundColor: '#ffffff',
            border: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            boxShadow: 'var(--shadow-sm)'
          }}
          title="Platform Help & Docs"
        >
          <HelpCircle size={18} color="#475569" />
        </button>
      </div>
    </header>
  );
}
