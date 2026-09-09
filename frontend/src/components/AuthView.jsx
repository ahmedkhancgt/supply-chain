import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Database,
  Bell,
  BarChart3,
  Shield,
  User,
  Mail,
  Building,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { signUpUser, signInUser, signInWithProvider } from '../config/supabase';
import { API_BASE_URL } from '../config/api';

export default function AuthView({ onAuthSuccess, onBypassDemo, initialMode = 'login' }) {
  const [isSignUp, setIsSignUp] = useState(() => initialMode === 'signup' || window.location.hash === '#signup');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  // Auth form state

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    if (isSignUp && password !== confirmPassword) {
      setErrorMsg('Passwords do not match');
      return;
    }

    if (password.length < 6) {
      setErrorMsg('Password must be at least 6 characters');
      return;
    }

    setLoading(true);

    try {
      if (isSignUp) {
        const { data, error } = await signUpUser({
          email,
          password,
          fullName,
          companyName: companyName || 'Global Supply Chain Co.',
        });

        if (error) {
          setErrorMsg(error.message || 'Failed to sign up');
        } else {
          setSuccessMsg('Account created successfully! Launching your workspace...');
          setTimeout(() => {
            if (onAuthSuccess) {
              onAuthSuccess(data?.user || {
                email,
                user_metadata: { full_name: fullName, company_name: companyName }
              });
            }
          }, 800);
        }
      } else {
        const { data, error } = await signInUser({
          email,
          password,
        });

        if (error) {
          setErrorMsg(error.message || 'Invalid email or password');
        } else {
          setSuccessMsg('Welcome back! Logging in...');
          setTimeout(() => {
            if (onAuthSuccess) {
              onAuthSuccess(data?.user || {
                email,
                user_metadata: { full_name: 'Avery Johnson', company_name: 'Global Supply Chain Co.' }
              });
            }
          }, 800);
        }
      }
    } catch (err) {
      setErrorMsg(err.message || 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = async (provider) => {
    try {
      setLoading(true);
      setErrorMsg('');
      const { data, error } = await signInWithProvider(provider);
      if (error) {
        setErrorMsg(`Failed to sign in with ${provider}: ` + error.message);
      } else if (data?.user) {
        if (onAuthSuccess) onAuthSuccess(data.user);
      }
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDemoAccess = () => {
    if (onBypassDemo) {
      onBypassDemo();
    } else if (onAuthSuccess) {
      onAuthSuccess({
        id: 'demo-user-1',
        email: 'avery.johnson@gscc.com',
        user_metadata: {
          full_name: 'Avery Johnson',
          company_name: 'Global Supply Chain Co.',
          role: 'Admin'
        }
      });
    }
  };

  const readinessScore = 100;
  const criticalLines = 0;
  const otifPct = 98.5;
  const totalValueFormatted = '$0.00M';

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#f8fafc',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '40px 24px',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Background Subtle Swirl & Glow */}
      <div style={{
        position: 'absolute',
        top: '-10%',
        right: '-5%',
        width: '600px',
        height: '600px',
        background: 'radial-gradient(circle, rgba(99, 102, 241, 0.12), rgba(59, 130, 246, 0.08), transparent 70%)',
        borderRadius: '50%',
        pointerEvents: 'none'
      }} />

      <div style={{
        position: 'absolute',
        bottom: '-10%',
        left: '-5%',
        width: '500px',
        height: '500px',
        background: 'radial-gradient(circle, rgba(139, 92, 246, 0.1), rgba(6, 182, 212, 0.06), transparent 70%)',
        borderRadius: '50%',
        pointerEvents: 'none'
      }} />

      {/* Main Split Container */}
      <div style={{
        maxWidth: '1280px',
        width: '100%',
        display: 'grid',
        gridTemplateColumns: '1.15fr 0.85fr',
        gap: '48px',
        alignItems: 'center',
        position: 'relative',
        zIndex: 10
      }}>

        {/* LEFT COLUMN: Hero & Features & Preview */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <svg width="44" height="44" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="auth_w_grad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#8b5cf6" />
                  <stop offset="60%" stopColor="#3b82f6" />
                </linearGradient>
              </defs>
              <path
                d="M 14 20 L 34 80 L 52 38 L 68 80 L 86 32"
                stroke="url(#auth_w_grad)"
                strokeWidth="15"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <circle cx="88" cy="18" r="8" fill="#38bdf8" />
            </svg>
            <span style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.5px' }}>
              Wisualyst
            </span>
          </div>

          {/* Hero Headline */}
          <div>
            <h1 style={{
              fontSize: '2.75rem',
              fontWeight: 800,
              lineHeight: 1.15,
              color: '#0f172a',
              letterSpacing: '-1px',
              margin: '0 0 12px 0'
            }}>
              Unify. Analyze. Optimize.<br />
              <span style={{
                background: 'linear-gradient(135deg, #2563eb, #3b82f6, #8b5cf6)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent'
              }}>
                Your Supply Chain.
              </span>
            </h1>
            <p style={{
              fontSize: '1.05rem',
              color: '#64748b',
              lineHeight: 1.55,
              maxWidth: '540px',
              margin: 0
            }}>
              Wisualyst unifies your data, delivers AI-powered insights, and helps you make smarter, faster decisions across your network.
            </p>
          </div>

          {/* 4 Feature Cards */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '16px',
            maxWidth: '560px'
          }}>
            <div style={{ display: 'flex', gap: '12px' }}>
              <div style={{
                width: '36px', height: '36px', borderRadius: '10px',
                backgroundColor: '#f5f3ff', color: '#8b5cf6',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
              }}>
                <Sparkles size={18} />
              </div>
              <div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0f172a' }}>AI-Powered Insights</div>
                <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '2px', lineHeight: 1.4 }}>
                  Surface risks, opportunities, and recommendations in real time.
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <div style={{
                width: '36px', height: '36px', borderRadius: '10px',
                backgroundColor: '#eff6ff', color: '#2563eb',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
              }}>
                <Database size={18} />
              </div>
              <div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0f172a' }}>Data Unification</div>
                <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '2px', lineHeight: 1.4 }}>
                  Connect all your sources into a single, trusted supply chain view.
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <div style={{
                width: '36px', height: '36px', borderRadius: '10px',
                backgroundColor: '#fdf2f8', color: '#db2777',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
              }}>
                <Bell size={18} />
              </div>
              <div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0f172a' }}>Smart Alerts</div>
                <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '2px', lineHeight: 1.4 }}>
                  Get proactive notifications on risks, delays, and supply issues.
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <div style={{
                width: '36px', height: '36px', borderRadius: '10px',
                backgroundColor: '#f5f3ff', color: '#7c3aed',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
              }}>
                <BarChart3 size={18} />
              </div>
              <div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0f172a' }}>BI & Data Exports</div>
                <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '2px', lineHeight: 1.4 }}>
                  Export clean, governed data to your BI tools and data warehouse.
                </div>
              </div>
            </div>
          </div>

          {/* Dynamic Mini Dashboard Preview Card */}
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            padding: '16px 20px',
            boxShadow: '0 10px 25px -5px rgba(0,0,0,0.06)',
            maxWidth: '560px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981' }} />
                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#0f172a' }}>Wisualyst Supply Chain Intelligence</span>
              </div>
              <span style={{ fontSize: '0.72rem', color: '#2563eb', background: '#eff6ff', padding: '2px 8px', borderRadius: '6px', fontWeight: 600 }}>
                Live Platform Feed
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '12px' }}>
              <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.65rem', color: '#64748b' }}>Readiness</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#2563eb' }}>{Math.round(readinessScore)}/100</div>
              </div>
              <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.65rem', color: '#64748b' }}>Stockout Risk</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#8b5cf6' }}>{criticalLines} SKUs</div>
              </div>
              <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.65rem', color: '#64748b' }}>Supplier OTIF</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0284c7' }}>{otifPct}%</div>
              </div>
              <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.65rem', color: '#64748b' }}>Portfolio Value</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#059669' }}>{totalValueFormatted}</div>
              </div>
            </div>

            <div style={{
              background: '#f8fafc',
              borderRadius: '8px',
              padding: '8px 12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.75rem'
            }}>
              <span style={{ color: '#334155', fontWeight: 600 }}>Enterprise Decision Intelligence</span>
              <span style={{ color: '#059669', fontWeight: 700 }}>✓ Live DB Synced</span>
            </div>
          </div>

          {/* Footer Security Badges */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.8rem',
            color: '#64748b'
          }}>
            <Shield size={16} color="#3b82f6" />
            <span>Enterprise-grade security</span>
            <span>•</span>
            <span>SOC 2 Type II</span>
            <span>•</span>
            <span>GDPR Compliant</span>
          </div>
        </div>

        {/* RIGHT COLUMN: Auth Form Card */}
        <div style={{
          backgroundColor: '#ffffff',
          borderRadius: '24px',
          border: '1px solid #e2e8f0',
          padding: '36px',
          boxShadow: '0 20px 40px -10px rgba(0,0,0,0.08)'
        }}>
          <div style={{ marginBottom: '24px' }}>
            <h2 style={{
              fontSize: '1.65rem',
              fontWeight: 700,
              color: '#0f172a',
              margin: '0 0 6px 0',
              letterSpacing: '-0.3px'
            }}>
              {isSignUp ? 'Create Your Workspace' : 'Sign In to Your Workspace'}
            </h2>
            <p style={{
              fontSize: '0.88rem',
              color: '#64748b',
              margin: 0
            }}>
              {isSignUp ? 'Start your free trial. No credit card required.' : 'Enter your credentials to access your control tower.'}
            </p>
          </div>

          {errorMsg && (
            <div style={{
              padding: '10px 14px',
              borderRadius: '10px',
              backgroundColor: '#fef2f2',
              border: '1px solid #fecaca',
              color: '#b91c1c',
              fontSize: '0.82rem',
              marginBottom: '18px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div style={{
              padding: '10px 14px',
              borderRadius: '10px',
              backgroundColor: '#ecfdf5',
              border: '1px solid #a7f3d0',
              color: '#047857',
              fontSize: '0.82rem',
              marginBottom: '18px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
              <span>{successMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {isSignUp && (
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px' }}>
                  Full Name
                </label>
                <div style={{ position: 'relative' }}>
                  <User size={17} color="#94a3b8" style={{ position: 'absolute', left: '14px', top: '13px' }} />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Enter your full name"
                    className="ui-input"
                    style={{ paddingLeft: '40px' }}
                  />
                </div>
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px' }}>
                Work Email
              </label>
              <div style={{ position: 'relative' }}>
                <Mail size={17} color="#94a3b8" style={{ position: 'absolute', left: '14px', top: '13px' }} />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="ui-input"
                  style={{ paddingLeft: '40px' }}
                />
              </div>
            </div>

            {isSignUp && (
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px' }}>
                  Company Name
                </label>
                <div style={{ position: 'relative' }}>
                  <Building size={17} color="#94a3b8" style={{ position: 'absolute', left: '14px', top: '13px' }} />
                  <input
                    type="text"
                    required
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="Enter your company name"
                    className="ui-input"
                    style={{ paddingLeft: '40px' }}
                  />
                </div>
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px' }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <Lock size={17} color="#94a3b8" style={{ position: 'absolute', left: '14px', top: '13px' }} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a strong password"
                  className="ui-input"
                  style={{ paddingLeft: '40px', paddingRight: '40px' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute', right: '12px', top: '12px',
                    background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8'
                  }}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </div>

            {isSignUp && (
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px' }}>
                  Confirm Password
                </label>
                <div style={{ position: 'relative' }}>
                  <Lock size={17} color="#94a3b8" style={{ position: 'absolute', left: '14px', top: '13px' }} />
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm your password"
                    className="ui-input"
                    style={{ paddingLeft: '40px', paddingRight: '40px' }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    style={{
                      position: 'absolute', right: '12px', top: '12px',
                      background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8'
                    }}
                  >
                    {showConfirmPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary"
              style={{
                width: '100%',
                padding: '12px',
                fontSize: '0.95rem',
                marginTop: '6px',
                opacity: loading ? 0.7 : 1
              }}
            >
              {loading ? (
                <span>Processing...</span>
              ) : isSignUp ? (
                <>
                  <Building size={18} />
                  <span>Create Workspace</span>
                </>
              ) : (
                <>
                  <ArrowRight size={18} />
                  <span>Sign In</span>
                </>
              )}
            </button>
          </form>

          {/* Toggle Link */}
          <div style={{ marginTop: '24px', textAlign: 'center' }}>
            <button
              type="button"
              onClick={() => {
                const nextMode = !isSignUp;
                setIsSignUp(nextMode);
                window.location.hash = nextMode ? '#signup' : '#login';
                setErrorMsg('');
                setSuccessMsg('');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#2563eb',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              {isSignUp ? 'Already have an account? Sign in →' : "Don't have an account? Create workspace →"}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
