import React, { useState, useEffect } from 'react';
import { TrendingUp, Calendar, Target, CheckCircle2 } from 'lucide-react';
import { API_BASE_URL } from '../config/api';

export default function ForecastChart({ products, selectedProductId, onSelectProduct }) {
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [horizon, setHorizon] = useState(30);

  useEffect(() => {
    if (!selectedProductId && products.length > 0) {
      onSelectProduct(products[0].id);
    }
  }, [products]);

  useEffect(() => {
    if (selectedProductId) {
      fetchForecast(selectedProductId, horizon);
    }
  }, [selectedProductId, horizon]);

  const fetchForecast = async (prodId, days) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/forecast/${prodId}?horizon_days=${days}`);
      if (res.ok) {
        const data = await res.json();
        setForecast(data);
      }
    } catch (err) {
      console.error("Failed to fetch forecast:", err);
    } finally {
      setLoading(false);
    }
  };

  const selectedProd = products.find(p => p.id === selectedProductId);

  // SVG Chart rendering helper
  const renderSvgChart = () => {
    if (!forecast || !forecast.forecast_data || forecast.forecast_data.length === 0) return null;

    const data = forecast.forecast_data;
    const maxVal = Math.max(...data.map(d => d.upper_bound)) * 1.1 || 10;
    const height = 180;
    const width = 600;

    const points = data.map((d, idx) => {
      const x = (idx / (data.length - 1)) * width;
      const y = height - (d.forecasted_demand / maxVal) * height;
      return `${x},${y}`;
    }).join(' ');

    const upperPoints = data.map((d, idx) => {
      const x = (idx / (data.length - 1)) * width;
      const y = height - (d.upper_bound / maxVal) * height;
      return `${x},${y}`;
    });

    const lowerPoints = data.map((d, idx) => {
      const x = ((data.length - 1 - idx) / (data.length - 1)) * width;
      const dRev = data[data.length - 1 - idx];
      const y = height - (dRev.lower_bound / maxVal) * height;
      return `${x},${y}`;
    });

    const areaPath = [...upperPoints, ...lowerPoints].join(' L ');

    return (
      <div style={{ position: 'relative', width: '100%', overflowX: 'auto' }}>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: '220px', overflow: 'visible' }}>
          {/* Confidence interval area */}
          <path d={`M ${areaPath} Z`} fill="rgba(99, 102, 241, 0.12)" />

          {/* Main Forecast Line */}
          <polyline
            fill="none"
            stroke="var(--primary-indigo)"
            strokeWidth="3"
            points={points}
          />

          {/* Data Points */}
          {data.filter((_, i) => i % 5 === 0).map((d, idx) => {
            const x = (idx * 5 / (data.length - 1)) * width;
            const y = height - (d.forecasted_demand / maxVal) * height;
            return (
              <g key={idx}>
                <circle cx={x} cy={y} r="4" fill="var(--primary-cyan)" stroke="#ffffff" strokeWidth="2" />
                <text x={x} y={y - 10} fill="var(--text-muted)" fontSize="9" textAnchor="middle" fontFamily="var(--font-mono)">
                  {Math.round(d.forecasted_demand)}
                </text>
              </g>
            );
          })}
        </svg>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-dim)' }}>
          <span>{data[0]?.date}</span>
          <span>Forecast Horizon: {horizon} Days</span>
          <span>{data[data.length - 1]?.date}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <TrendingUp size={20} color="var(--primary-cyan)" />
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>AI Demand Forecasting Engine</h3>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <select 
            value={selectedProductId || ''} 
            onChange={(e) => onSelectProduct(parseInt(e.target.value))}
            className="input-dark"
            style={{ maxWidth: '280px' }}
          >
            {products.map(p => (
              <option key={p.id} value={p.id}>{p.sku} — {p.name}</option>
            ))}
          </select>

          <div style={{ display: 'flex', background: 'rgba(14, 21, 38, 0.9)', borderRadius: '10px', padding: '2px', border: '1px solid var(--border-glass)' }}>
            {[7, 14, 30].map(d => (
              <button 
                key={d}
                onClick={() => setHorizon(d)}
                style={{
                  background: horizon === d ? 'var(--primary-indigo)' : 'transparent',
                  color: horizon === d ? '#ffffff' : 'var(--text-muted)',
                  border: 'none',
                  padding: '0.4rem 0.8rem',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontSize: '0.75rem',
                  fontWeight: 600
                }}
              >
                {d}D
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          Computing statistical demand model...
        </div>
      ) : forecast ? (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.8rem 1rem', borderRadius: '10px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>FORECASTED DEMAND</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--primary-cyan)', fontFamily: 'var(--font-mono)' }}>
                {forecast.total_forecasted_demand} units
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.8rem 1rem', borderRadius: '10px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>CONFIDENCE INTERVAL</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
                {forecast.confidence_interval_pct}%
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.8rem 1rem', borderRadius: '10px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>MEAN ABS ERROR (MAE)</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
                {forecast.mae}
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.8rem 1rem', borderRadius: '10px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>RMSE ACCURACY</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
                {forecast.rmse}
              </div>
            </div>
          </div>

          {renderSvgChart()}
        </div>
      ) : null}
    </div>
  );
}
