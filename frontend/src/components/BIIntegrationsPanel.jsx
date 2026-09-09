import React, { useState, useEffect } from 'react';
import { Download, ExternalLink, Database, FileSpreadsheet, CheckCircle2, Cpu, Copy, Check, Terminal, Zap } from 'lucide-react';
import { API_BASE_URL } from '../config/api';

export default function BIIntegrationsPanel() {
  const [downloaded, setDownloaded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [mcpData, setMcpData] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/mcp/tools`)
      .then(res => res.json())
      .then(d => setMcpData(d))
      .catch(() => console.log("MCP fetch offline"));
  }, []);

  const handleDownloadCsv = () => {
    window.open(`${API_BASE_URL}/api/bi/google-sheets`, '_blank');
    setDownloaded(true);
  };

  const serverPath = mcpData?.server_path || "mcp/server.py";
  const baseDir = mcpData?.base_dir || ".";

  const mcpConfigSnippet = `{
  "mcpServers": {
    "wisualyst-supplychain": {
      "command": "python",
      "args": [
        "${serverPath}"
      ],
      "cwd": "${baseDir}",
      "env": {
        "PYTHONPATH": "${baseDir}"
      }
    }
  }
}`;

  const handleCopyConfig = () => {
    navigator.clipboard.writeText(mcpConfigSnippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* 1. MCP SERVER CONNECTION PANEL */}
      <div className="glass-panel" style={{ padding: '24px', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ padding: '12px', borderRadius: '12px', background: 'rgba(99, 102, 241, 0.2)', color: '#818cf8' }}>
              <Cpu size={26} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h3 style={{ fontSize: '1.25rem', color: '#f8fafc', margin: 0 }}>Model Context Protocol (MCP) Server</h3>
                <span className="badge badge-success">ONLINE</span>
              </div>
              <p style={{ color: '#94a3b8', fontSize: '0.85rem', margin: '4px 0 0 0' }}>
                Connect Antigravity IDE, Claude Desktop, Cursor, or custom LLM agents to Wisualyst AI Decision Engines.
              </p>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.85rem', color: '#818cf8', fontWeight: 700 }}>Protocol: JSON-RPC stdio</div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Registered Tools: {mcpData?.tools?.length || 9}</div>
          </div>
        </div>

        {/* MCP Configuration Snippet */}
        <div style={{ background: '#0f172a', borderRadius: '12px', padding: '16px', border: '1px solid rgba(255,255,255,0.08)', marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Terminal size={14} color="#818cf8" /> Client Connection Config (Dynamically Detected for current host)
            </span>
            <button 
              onClick={handleCopyConfig} 
              style={{
                padding: '6px 12px', borderRadius: '6px', background: 'rgba(255,255,255,0.08)', 
                border: '1px solid rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer',
                fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px'
              }}
            >
              {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
              {copied ? 'Copied to Clipboard!' : 'Copy Config'}
            </button>
          </div>
          <pre style={{ margin: 0, fontFamily: 'monospace', fontSize: '0.82rem', color: '#38bdf8', overflowX: 'auto' }}>
            {mcpConfigSnippet}
          </pre>
        </div>

        {/* Registered Tools Grid */}
        <div>
          <h4 style={{ fontSize: '0.9rem', color: '#f8fafc', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Zap size={16} color="#eab308" /> Registered MCP Intelligence Tools ({mcpData?.tools?.length || 9})
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            {(mcpData?.tools || [
              { name: 'get_control_tower_summary', description: 'Executive summary metrics' },
              { name: 'get_inventory_risk', description: 'Stockout risk matrix & safety stock' },
              { name: 'get_demand_forecast', description: 'AI statistical forecast (7, 14, 30d)' },
              { name: 'get_inventory_recommendations', description: 'EOQ purchase order quantities' },
              { name: 'get_products', description: 'Product catalog & lead times' },
              { name: 'get_suppliers', description: 'Supplier OTIF scores & ratings' }
            ]).map((t, idx) => (
              <div key={idx} style={{ padding: '12px 14px', borderRadius: '8px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontFamily: 'monospace', fontWeight: 600, color: '#818cf8', fontSize: '0.82rem', marginBottom: '4px' }}>
                  {t.name}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  {t.description}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 2. BI EXPORT ADAPTERS */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h2 style={{ fontSize: '1.4rem', color: '#f8fafc', marginBottom: '8px' }}>BI & Analytics Export Adapters</h2>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '24px' }}>
          Connect Wisualyst canonical datasets directly to Power BI, Qlik Sense, and Google Sheets for enterprise reporting.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
          {/* Power BI */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
              <div style={{ padding: '10px', borderRadius: '10px', background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
                <Database size={24} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.05rem', color: '#f8fafc' }}>Power BI Desktop</h3>
                <span className="badge badge-success">DirectQuery Enabled</span>
              </div>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '16px' }}>
              REST API dataset stream formatted for Power BI Dataflows & DirectQuery connections.
            </p>
            <a 
              href={`${API_BASE_URL}/api/bi/powerbi`} 
              target="_blank" 
              rel="noreferrer"
              style={{ textDecoration: 'none' }}
              className="glow-btn-primary"
            >
              <ExternalLink size={14} /> Open Power BI JSON Endpoint
            </a>
          </div>

          {/* Qlik Sense */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
              <div style={{ padding: '10px', borderRadius: '10px', background: 'rgba(6, 182, 212, 0.15)', color: '#06b6d4' }}>
                <Database size={24} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.05rem', color: '#f8fafc' }}>Qlik Sense REST</h3>
                <span className="badge badge-medium">REST Connector</span>
              </div>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '16px' }}>
              qTable formatted JSON dataset stream for Qlik Sense Cloud and Qlik Enterprise.
            </p>
            <a 
              href={`${API_BASE_URL}/api/bi/qlik`} 
              target="_blank" 
              rel="noreferrer"
              style={{ textDecoration: 'none' }}
              className="glow-btn-primary"
            >
              <ExternalLink size={14} /> Open Qlik REST Endpoint
            </a>
          </div>

          {/* Google Sheets */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
              <div style={{ padding: '10px', borderRadius: '10px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
                <FileSpreadsheet size={24} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.05rem', color: '#f8fafc' }}>Google Sheets / CSV</h3>
                <span className="badge badge-success">CSV Stream</span>
              </div>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '16px' }}>
              Download flattened CSV dataset or link using Google Sheets IMPORTDATA formula.
            </p>
            <button onClick={handleDownloadCsv} className="glow-btn-primary">
              <Download size={14} /> Download CSV Dataset
            </button>
            {downloaded && (
              <div style={{ marginTop: '8px', fontSize: '0.75rem', color: '#6ee7b7', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={12} /> Dataset downloaded
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
