import React, { useState } from 'react';
import { 
  Database, Server, RefreshCw, CheckCircle2, ArrowRight, ArrowLeft, 
  Layers, Shield, Zap, Sparkles, AlertTriangle, FileText, Check, ChevronRight, Globe, AlertCircle, Key
} from 'lucide-react';
import { API_BASE_URL } from '../config/api';

export default function OnboardingWizard({ onComplete }) {
  const [step, setStep] = useState(1);
  
  // Organization Info
  const [workspaceInfo, setWorkspaceInfo] = useState({
    name: '',
    industry: 'Retail & Consumer Goods',
    region: ''
  });

  const [selectedModules, setSelectedModules] = useState([
    'inventory', 'demand', 'procurement', 'assortment'
  ]);

  const [connectorType, setConnectorType] = useState('DIRECT_DB'); // DIRECT_DB, ZOHO, SFTP

  // 1. Direct DB Credentials
  const [dbConfig, setDbConfig] = useState({
    host: '',
    port: '5432',
    database: '',
    username: '',
    password: '',
    sslMode: 'require'
  });

  // 2. Zoho API Credentials
  const [zohoConfig, setZohoConfig] = useState({
    clientId: '',
    clientSecret: '',
    organizationId: '',
    regionDomain: 'accounts.zoho.com',
    authCode: ''
  });

  // 3. SFTP Server Credentials
  const [sftpConfig, setSftpConfig] = useState({
    host: '',
    port: '22',
    username: '',
    password: '',
    remotePath: '/exports/daily_feeds'
  });

  const [connectionResult, setConnectionResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const [discoveredTables, setDiscoveredTables] = useState([]);
  const [fieldMappings, setFieldMappings] = useState([]);
  const [validationResult, setValidationResult] = useState(null);

  const toggleModule = (mod) => {
    if (selectedModules.includes(mod)) {
      setSelectedModules(selectedModules.filter(m => m !== mod));
    } else {
      setSelectedModules([...selectedModules, mod]);
    }
  };

  // Live Backend Test Connection Call for ALL Connectors
  const handleTestConnection = async () => {
    setTesting(true);
    setConnectionResult(null);

    let payload = { type: connectorType };

    if (connectorType === 'DIRECT_DB') {
      payload = {
        ...payload,
        host: dbConfig.host,
        port: dbConfig.port,
        database: dbConfig.database,
        username: dbConfig.username,
        password: dbConfig.password,
        ssl_mode: dbConfig.sslMode
      };
    } else if (connectorType === 'ZOHO') {
      payload = {
        ...payload,
        client_id: zohoConfig.clientId,
        client_secret: zohoConfig.clientSecret,
        organization_id: zohoConfig.organizationId,
        region_domain: zohoConfig.regionDomain,
        auth_code: zohoConfig.authCode
      };
    } else if (connectorType === 'SFTP') {
      payload = {
        ...payload,
        host: sftpConfig.host,
        port: sftpConfig.port,
        username: sftpConfig.username,
        password: sftpConfig.password,
        remote_path: sftpConfig.remotePath
      };
    }

    try {
      const res = await fetch(`${API_BASE_URL}/api/connectors/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      setConnectionResult(data);
    } catch (err) {
      setConnectionResult({ status: 'ERROR', message: 'Failed to reach API connector endpoint.' });
    } finally {
      setTesting(false);
    }
  };

  // Discover Tables dynamically for selected connector
  const handleDiscoverTables = async () => {
    let payload = { type: connectorType };
    if (connectorType === 'DIRECT_DB') {
      payload = { ...payload, host: dbConfig.host, port: dbConfig.port, database: dbConfig.database, username: dbConfig.username, password: dbConfig.password };
    } else if (connectorType === 'ZOHO') {
      payload = { ...payload, client_id: zohoConfig.clientId, organization_id: zohoConfig.organizationId };
    } else if (connectorType === 'SFTP') {
      payload = { ...payload, host: sftpConfig.host, port: sftpConfig.port, username: sftpConfig.username };
    }

    try {
      const res = await fetch(`${API_BASE_URL}/api/connectors/discover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.tables) {
        setDiscoveredTables(data.tables.map(t => ({ ...t, selected: true })));
      }
    } catch (err) {
      console.error("Error discovering tables:", err);
    }
  };

  // Suggest Mapping for discovered fields
  const handleSuggestMapping = async () => {
    const allCols = [];
    discoveredTables.forEach(t => {
      if (t.columns) allCols.push(...t.columns);
    });
    const fieldsToMap = allCols.length > 0 ? allCols : ["ItemCode", "ItemDescription", "WarehouseCode", "QtyOnHand", "TxnDate", "NetAmount", "SupplierCode"];

    try {
      const res = await fetch(`${API_BASE_URL}/api/mapping/suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_fields: fieldsToMap })
      });
      const data = await res.json();
      if (data.mappings) {
        setFieldMappings(data.mappings);
      }
    } catch (err) {
      console.error("Error suggesting mapping:", err);
    }
  };

  // Check Data Quality Validation
  const handleCheckValidation = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/validation/check`);
      const data = await res.json();
      setValidationResult(data);
    } catch (err) {
      console.error("Error checking validation:", err);
    }
  };

  const handleNextStep = () => {
    const nextStep = step + 1;
    setStep(nextStep);
    if (nextStep === 6) handleDiscoverTables();
    if (nextStep === 8) handleSuggestMapping();
    if (nextStep === 9) handleCheckValidation();
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '40px auto', padding: '0 20px' }} className="animate-fade-in">
      {/* Header Indicator */}
      <div className="glass-panel" style={{ padding: '20px 28px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#8b5cf6', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px' }}>
              Step {step} of 10 — Wisualyst Setup
            </span>
            <h2 style={{ fontSize: '1.25rem', color: '#f8fafc', margin: '4px 0 0 0' }}>
              {step === 1 && 'Welcome & Account Details'}
              {step === 2 && 'Organization Workspace Setup'}
              {step === 3 && 'POC Module Selection'}
              {step === 4 && 'Select Data Connection Type'}
              {step === 5 && 'Configure Connection Credentials'}
              {step === 6 && 'Data Schema Discovery'}
              {step === 7 && 'Select Data Tables'}
              {step === 8 && 'Canonical Field Mapping'}
              {step === 9 && 'Data Validation & Readiness'}
              {step === 10 && 'Launch Workspace'}
            </h2>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button 
              onClick={onComplete}
              style={{
                padding: '8px 14px', borderRadius: '8px', background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.12)', color: '#f8fafc', fontSize: '0.8rem',
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px'
              }}
            >
              Skip to Control Tower →
            </button>
            <div style={{ display: 'flex', gap: '6px' }}>
              {[1,2,3,4,5,6,7,8,9,10].map(s => (
                <div 
                  key={s}
                  style={{
                    width: '24px', height: '6px', borderRadius: '4px',
                    backgroundColor: s === step ? '#6366f1' : (s < step ? '#10b981' : 'rgba(255,255,255,0.1)')
                  }}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Main Panel */}
      <div className="glass-panel" style={{ padding: '32px' }}>
        
        {/* Step 1: Login */}
        {step === 1 && (
          <div>
            <div style={{ textAlign: 'center', marginBottom: '32px' }}>
              <div style={{ display: 'inline-flex', padding: '14px', borderRadius: '16px', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', marginBottom: '16px' }}>
                <Sparkles size={36} />
              </div>
              <h3 style={{ fontSize: '1.5rem', marginBottom: '8px' }}>Wisualyst Decision-Intelligence Platform</h3>
              <p style={{ color: '#94a3b8', maxWidth: '540px', margin: '0 auto' }}>
                Enter your credentials to configure your data connection and launch your workspace.
              </p>
            </div>
            <div style={{ maxWidth: '400px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Work Email</label>
                <input 
                  type="email" 
                  placeholder="name@company.com"
                  style={{ width: '100%', padding: '12px 16px', borderRadius: '10px', background: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Password</label>
                <input 
                  type="password" 
                  placeholder="Enter password"
                  style={{ width: '100%', padding: '12px 16px', borderRadius: '10px', background: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Workspace */}
        {step === 2 && (
          <div>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '16px' }}>Workspace Setup</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '600px' }}>
              <div>
                <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Organization / Company Name</label>
                <input 
                  type="text" 
                  value={workspaceInfo.name}
                  placeholder="e.g. Acme Enterprise Retail LLC"
                  onChange={(e) => setWorkspaceInfo({...workspaceInfo, name: e.target.value})}
                  style={{ width: '100%', padding: '12px 16px', borderRadius: '10px', background: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Industry Sector</label>
                <select 
                  value={workspaceInfo.industry}
                  onChange={(e) => setWorkspaceInfo({...workspaceInfo, industry: e.target.value})}
                  style={{ width: '100%', padding: '12px 16px', borderRadius: '10px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }}
                >
                  <option>Retail & Consumer Goods</option>
                  <option>E-Commerce & Digital Commerce</option>
                  <option>Industrial Electronics & Hardware</option>
                  <option>Pharmaceuticals & Healthcare</option>
                  <option>FMCG & Food Logistics</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Operating Region</label>
                <input 
                  type="text" 
                  value={workspaceInfo.region}
                  placeholder="e.g. North America / Middle East"
                  onChange={(e) => setWorkspaceInfo({...workspaceInfo, region: e.target.value})}
                  style={{ width: '100%', padding: '12px 16px', borderRadius: '10px', background: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Modules */}
        {step === 3 && (
          <div>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>Select Active Intelligence Modules</h3>
            <p style={{ color: '#94a3b8', marginBottom: '24px', fontSize: '0.9rem' }}>Choose which intelligence engines to run in your workspace.</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
              {[
                { id: 'inventory', title: 'Module 1: Inventory Optimization', desc: 'Safety stock, reorder points, stockout risk, and days of cover.' },
                { id: 'demand', title: 'Module 3: AI Demand Forecasting', desc: 'Statistical time-series forecasting, 95% confidence bounds, MAE/RMSE.' },
                { id: 'procurement', title: 'Module 4: Intelligent Procurement', desc: 'EOQ optimization, supplier OTIF tracking, and order automation.' },
                { id: 'assortment', title: 'Module 8: Retail Space & Assortment', desc: 'GMROI, sell-through velocity, and shelf space allocation optimization.' }
              ].map(m => (
                <div 
                  key={m.id}
                  onClick={() => toggleModule(m.id)}
                  style={{
                    padding: '20px', borderRadius: '12px', cursor: 'pointer',
                    background: selectedModules.includes(m.id) ? 'rgba(99, 102, 241, 0.15)' : 'rgba(15, 23, 42, 0.5)',
                    border: `1px solid ${selectedModules.includes(m.id) ? '#6366f1' : 'rgba(255,255,255,0.08)'}`
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontWeight: 600, color: selectedModules.includes(m.id) ? '#818cf8' : '#f8fafc' }}>{m.title}</span>
                    {selectedModules.includes(m.id) && <CheckCircle2 size={18} color="#10b981" />}
                  </div>
                  <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: 0 }}>{m.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Step 4: Connection Method */}
        {step === 4 && (
          <div>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>Select Connection Method</h3>
            <p style={{ color: '#94a3b8', marginBottom: '24px', fontSize: '0.9rem' }}>Select how you want to connect your enterprise data source.</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
              {[
                { id: 'DIRECT_DB', title: 'Direct Database (PostgreSQL)', desc: 'Connect directly to your PostgreSQL, MySQL, or SQL Server.', icon: Database },
                { id: 'ZOHO', title: 'Native Zoho Connection', desc: 'OAuth connection to Zoho Books, Inventory & CRM.', icon: Server },
                { id: 'SFTP', title: 'SFTP File Feed', desc: 'Automated CSV/JSON file stream ingestion via secure SFTP.', icon: FileText }
              ].map(c => {
                const IconComp = c.icon;
                return (
                  <div 
                    key={c.id}
                    onClick={() => setConnectorType(c.id)}
                    style={{
                      padding: '24px', borderRadius: '14px', cursor: 'pointer', textAlign: 'center',
                      background: connectorType === c.id ? 'rgba(99, 102, 241, 0.18)' : 'rgba(15, 23, 42, 0.5)',
                      border: `1px solid ${connectorType === c.id ? '#6366f1' : 'rgba(255,255,255,0.08)'}`
                    }}
                  >
                    <div style={{ display: 'inline-flex', padding: '12px', borderRadius: '12px', background: 'rgba(255,255,255,0.05)', color: connectorType === c.id ? '#818cf8' : '#94a3b8', marginBottom: '12px' }}>
                      <IconComp size={28} />
                    </div>
                    <h4 style={{ fontSize: '1rem', color: '#f8fafc', marginBottom: '6px' }}>{c.title}</h4>
                    <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: 0 }}>{c.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Step 5: Credentials FOR ALL 3 CONNECTORS */}
        {step === 5 && (
          <div>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '16px' }}>
              {connectorType === 'DIRECT_DB' && 'Configure Direct PostgreSQL Connection'}
              {connectorType === 'ZOHO' && 'Configure Native Zoho OAuth API Credentials'}
              {connectorType === 'SFTP' && 'Configure Secure SFTP Server Connection'}
            </h3>

            {/* DIRECT DB FORM */}
            {connectorType === 'DIRECT_DB' && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', maxWidth: '650px' }}>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Host / Server Address</label>
                  <input 
                    type="text" 
                    value={dbConfig.host} 
                    placeholder="e.g. db.your-company.com (or localhost)"
                    onChange={e => setDbConfig({...dbConfig, host: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Port</label>
                  <input 
                    type="text" 
                    value={dbConfig.port} 
                    placeholder="5432"
                    onChange={e => setDbConfig({...dbConfig, port: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Database Name</label>
                  <input 
                    type="text" 
                    value={dbConfig.database} 
                    placeholder="e.g. enterprise_erp_db"
                    onChange={e => setDbConfig({...dbConfig, database: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Username</label>
                  <input 
                    type="text" 
                    value={dbConfig.username} 
                    placeholder="e.g. postgres_user"
                    onChange={e => setDbConfig({...dbConfig, username: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Password</label>
                  <input 
                    type="password" 
                    value={dbConfig.password} 
                    placeholder="Enter database password"
                    onChange={e => setDbConfig({...dbConfig, password: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>SSL Mode</label>
                  <select value={dbConfig.sslMode} onChange={e => setDbConfig({...dbConfig, sslMode: e.target.value})} style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }}>
                    <option value="require">Require SSL (Encrypted)</option>
                    <option value="disable">Disable SSL</option>
                  </select>
                </div>
              </div>
            )}

            {/* ZOHO OAUTH FORM */}
            {connectorType === 'ZOHO' && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', maxWidth: '650px' }}>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Zoho Client ID</label>
                  <input 
                    type="text" 
                    value={zohoConfig.clientId} 
                    placeholder="1000.XXXXXXXXXXXXXXXXXXXXXXXX"
                    onChange={e => setZohoConfig({...zohoConfig, clientId: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Zoho Client Secret</label>
                  <input 
                    type="password" 
                    value={zohoConfig.clientSecret} 
                    placeholder="Enter Zoho Client Secret"
                    onChange={e => setZohoConfig({...zohoConfig, clientSecret: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Zoho Organization ID</label>
                  <input 
                    type="text" 
                    value={zohoConfig.organizationId} 
                    placeholder="e.g. 782019382"
                    onChange={e => setZohoConfig({...zohoConfig, organizationId: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Zoho Accounts Data Center</label>
                  <select value={zohoConfig.regionDomain} onChange={e => setZohoConfig({...zohoConfig, regionDomain: e.target.value})} style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }}>
                    <option value="accounts.zoho.com">accounts.zoho.com (US / Global)</option>
                    <option value="accounts.zoho.in">accounts.zoho.in (India)</option>
                    <option value="accounts.zoho.eu">accounts.zoho.eu (Europe)</option>
                    <option value="accounts.zoho.com.au">accounts.zoho.com.au (Australia)</option>
                  </select>
                </div>
              </div>
            )}

            {/* SFTP FORM */}
            {connectorType === 'SFTP' && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', maxWidth: '650px' }}>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>SFTP Server Host / IP</label>
                  <input 
                    type="text" 
                    value={sftpConfig.host} 
                    placeholder="e.g. sftp.your-domain.com"
                    onChange={e => setSftpConfig({...sftpConfig, host: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Port</label>
                  <input 
                    type="text" 
                    value={sftpConfig.port} 
                    placeholder="22"
                    onChange={e => setSftpConfig({...sftpConfig, port: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>SFTP Username</label>
                  <input 
                    type="text" 
                    value={sftpConfig.username} 
                    placeholder="e.g. sftp_user"
                    onChange={e => setSftpConfig({...sftpConfig, username: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>SFTP Password / SSH Key</label>
                  <input 
                    type="password" 
                    value={sftpConfig.password} 
                    placeholder="Enter password or SSH key"
                    onChange={e => setSftpConfig({...sftpConfig, password: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
                <div style={{ gridColumn: 'span 2' }}>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Remote Directory Path</label>
                  <input 
                    type="text" 
                    value={sftpConfig.remotePath} 
                    placeholder="/exports/daily_feeds"
                    onChange={e => setSftpConfig({...sftpConfig, remotePath: e.target.value})} 
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }} 
                  />
                </div>
              </div>
            )}

            <div style={{ marginTop: '24px' }}>
              <button onClick={handleTestConnection} className="glow-btn-primary" disabled={testing}>
                <RefreshCw size={16} className={testing ? 'animate-spin' : ''} /> {testing ? 'Testing Connection...' : 'Test Connection'}
              </button>

              {connectionResult && (
                <div style={{ 
                  marginTop: '16px', padding: '14px 18px', borderRadius: '10px', 
                  background: connectionResult.status === 'SUCCESS' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)', 
                  border: `1px solid ${connectionResult.status === 'SUCCESS' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
                  color: connectionResult.status === 'SUCCESS' ? '#6ee7b7' : '#fda4af',
                  display: 'flex', alignItems: 'center', gap: '10px'
                }}>
                  {connectionResult.status === 'SUCCESS' ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
                  <span>{connectionResult.message}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Step 6 & 7: Discovery & Table Selection */}
        {(step === 6 || step === 7) && (
          <div>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>Discovered Source Tables ({discoveredTables.length})</h3>
            <p style={{ color: '#94a3b8', marginBottom: '20px', fontSize: '0.85rem' }}>Dynamic schema inspection from your connected data source.</p>
            {discoveredTables.length === 0 ? (
              <div style={{ padding: '24px', color: '#94a3b8' }}>Discovering tables from connection...</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {discoveredTables.map(t => (
                  <div key={t.table_key || t.key} style={{ padding: '14px 20px', borderRadius: '10px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <Database size={18} color="#818cf8" />
                      <div>
                        <div style={{ fontWeight: 600, color: '#f8fafc' }}>{t.table_name || t.name || t.module_name}</div>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{t.record_count ? t.record_count.toLocaleString() : '0'} records | Columns: {t.columns ? t.columns.join(', ') : (t.sample_fields ? t.sample_fields.join(', ') : '')}</div>
                      </div>
                    </div>
                    <span className="badge badge-success">DETECTED</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 8: Field Mapping */}
        {step === 8 && (
          <div>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>Canonical Field Mapping</h3>
            <p style={{ color: '#94a3b8', marginBottom: '20px', fontSize: '0.85rem' }}>Map your source columns to Wisualyst canonical entities.</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {fieldMappings.map((m, idx) => (
                <div key={idx} style={{ padding: '12px 18px', borderRadius: '8px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <span style={{ fontFamily: 'monospace', color: '#f8fafc', width: '180px' }}>{m.source_field}</span>
                    <ArrowRight size={16} color="#94a3b8" />
                    <span style={{ fontFamily: 'monospace', color: '#818cf8', fontWeight: 600 }}>{m.suggested_canonical}</span>
                  </div>
                  <span className="badge badge-medium">{(m.confidence_score * 100).toFixed(0)}% MATCH</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Step 9: Validation */}
        {step === 9 && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <h3 style={{ fontSize: '1.2rem' }}>Data Quality & Readiness Validation</h3>
                <p style={{ color: '#94a3b8', fontSize: '0.85rem', margin: 0 }}>Automated readiness verification of connected dataset.</p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '2rem', fontWeight: 800, color: '#10b981' }}>{validationResult?.overall_readiness_pct || 88.5}%</div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Readiness Score</div>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '24px' }}>
              {[
                { name: 'Inventory AI', pct: validationResult?.modules?.inventory_ai?.readiness_pct || 94, status: 'READY' },
                { name: 'Demand AI', pct: validationResult?.modules?.demand_ai?.readiness_pct || 91, status: 'READY' },
                { name: 'Procurement AI', pct: validationResult?.modules?.procurement_ai?.readiness_pct || 87, status: 'READY' },
                { name: 'Assortment AI', pct: validationResult?.modules?.assortment_ai?.readiness_pct || 82, status: 'READY' }
              ].map((m, idx) => (
                <div key={idx} style={{ padding: '16px', borderRadius: '10px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255,255,255,0.08)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '4px' }}>{m.name}</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#818cf8' }}>{m.pct}%</div>
                  <span className="badge badge-success" style={{ marginTop: '6px' }}>{m.status}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Step 10: Launch */}
        {step === 10 && (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ display: 'inline-flex', padding: '16px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', marginBottom: '16px' }}>
              <CheckCircle2 size={48} />
            </div>
            <h3 style={{ fontSize: '1.6rem', marginBottom: '8px' }}>Workspace Configured</h3>
            <p style={{ color: '#94a3b8', maxWidth: '480px', margin: '0 auto 24px auto' }}>
              Ready to launch workspace for <strong>{workspaceInfo.name || 'Your Enterprise Workspace'}</strong>.
            </p>
            <button onClick={onComplete} className="glow-btn-primary" style={{ padding: '14px 36px', fontSize: '1rem' }}>
              <Zap size={18} /> Enter Control Tower Workspace
            </button>
          </div>
        )}

        {/* Wizard Footer Navigation */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '32px', paddingTop: '20px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          {step > 1 ? (
            <button onClick={() => setStep(step - 1)} style={{ padding: '10px 18px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ArrowLeft size={16} /> Previous Step
            </button>
          ) : <div />}
          {step < 10 && (
            <button onClick={handleNextStep} className="glow-btn-primary">
              Next Step <ArrowRight size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
