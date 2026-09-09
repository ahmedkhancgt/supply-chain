import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import HeaderBar from './components/HeaderBar';
import AuthView from './components/AuthView';
import OverviewView from './components/OverviewView';
import WorkspacesView from './components/WorkspacesView';
import DataSourcesView from './components/DataSourcesView';
import AlertsView from './components/AlertsView';
import AccessControlView from './components/AccessControlView';
import IntelligenceEnginesView from './components/IntelligenceEnginesView';
import RecommendationsView from './components/RecommendationsView';
import DashboardView from './components/DashboardView';
import BIIntegrationsPanel from './components/BIIntegrationsPanel';
import AIAssistantDrawer from './components/AIAssistantDrawer';
import {
  NewRoleModal,
  InviteMemberModal,
  RecommendationSimulationModal,
  HelpModal
} from './components/Modals';
import { getSessionUser, signOutUser } from './config/supabase';

export default function App() {
  // Session / User state - defaults to null until authenticated or session restored
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [activeTab, setActiveTab] = useState(() => {
    const hash = window.location.hash.replace('#', '').toLowerCase();
    if (['overview', 'workspaces', 'datasources', 'intelligence', 'recommendations', 'alerts', 'dashboard', 'mcp', 'access-control'].includes(hash)) {
      return hash;
    }
    return 'overview';
  });
  const [dateRange, setDateRange] = useState('May 12 – May 18, 2024');

  // Modal & Drawer states
  const [isNewRoleModalOpen, setIsNewRoleModalOpen] = useState(false);
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [isHelpModalOpen, setIsHelpModalOpen] = useState(false);
  const [isAIChatOpen, setIsAIChatOpen] = useState(false);
  const [simulationRec, setSimulationRec] = useState(null);

  // Sync state with hash on mount and hashchange event
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '').toLowerCase();
      if (['overview', 'workspaces', 'datasources', 'intelligence', 'recommendations', 'alerts', 'dashboard', 'mcp', 'access-control'].includes(hash)) {
        setActiveTab(hash);
      } else if (hash === 'login' || hash === 'signin' || hash === 'signup' || hash === 'register') {
        if (!user) {
          // Stay in auth view with corresponding mode
        }
      }
    };

    handleHashChange();
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [user]);

  const changeTab = (tab) => {
    setActiveTab(tab);
    window.location.hash = '#' + tab;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Check Supabase session on startup
  useEffect(() => {
    async function checkAuth() {
      try {
        const sessUser = await getSessionUser();
        if (sessUser) {
          setUser(sessUser);
        }
      } catch (err) {
        console.error('Session check note:', err);
      } finally {
        setAuthChecked(true);
      }
    }
    checkAuth();
  }, []);

  const handleSignOut = async () => {
    await signOutUser();
    setUser(null);
    window.location.hash = '#login';
  };

  const handleAuthSuccess = (authedUser) => {
    setUser(authedUser);
    window.location.hash = '#overview';
  };

  const getHeaderProps = () => {
    switch (activeTab) {
      case 'overview':
        return {
          title: (
            <span>
              Wisualyst <span style={{ color: '#2563eb' }}>Supply Chain Intelligence</span>
            </span>
          ),
          subtitle: 'AI-powered insights to optimize performance across your network.',
          showFilters: true
        };
      case 'workspaces':
        return {
          title: 'Onboard Your Workspace',
          subtitle: 'Complete these steps to set up your workspace and unlock intelligent insights.',
          showFilters: true
        };
      case 'datasources':
        return {
          title: 'Connect & Standardize Your Data',
          subtitle: 'Unify and prepare your data for accurate insights and intelligent decisions.',
          showFilters: false
        };
      case 'intelligence':
        return {
          title: 'Intelligence Engines',
          subtitle: 'Autonomous forecasting, multi-echelon inventory, and procurement optimization models.',
          showFilters: true
        };
      case 'recommendations':
        return {
          title: 'AI Recommendations & Actions',
          subtitle: 'Proactive prescriptive interventions with financial ROI modeling.',
          showFilters: true
        };
      case 'alerts':
        return {
          title: (
            <span>
              Connect <span style={{ color: '#2563eb' }}>Microsoft Teams</span> for Alerts & Recommendations
            </span>
          ),
          subtitle: 'Send real-time alerts and AI-powered recommendations to your Teams channels.',
          showFilters: false
        };
      case 'dashboard':
        return {
          title: 'Executive Control Tower',
          subtitle: 'Holistic network telemetry across global hubs, suppliers, and fulfillment nodes.',
          showFilters: true
        };
      case 'access-control':
        return {
          title: 'Access Control',
          subtitle: 'Manage roles, permissions, and user access across Wisualyst.',
          showFilters: false
        };
      default:
        return {
          title: 'Wisualyst Intelligence Platform',
          subtitle: 'Supply Chain Decision Intelligence',
          showFilters: true
        };
    }
  };

  // If user is not authenticated, redirect root access to #login and show Login screen!
  if (!user) {
    const currentHash = window.location.hash.replace('#', '').toLowerCase();
    const mode = (currentHash === 'signup' || currentHash === 'register') ? 'signup' : 'login';

    if (!window.location.hash || window.location.hash === '#') {
      window.location.hash = '#login';
    }

    return (
      <AuthView
        initialMode={mode}
        onAuthSuccess={handleAuthSuccess}
        onBypassDemo={() => {
          setUser({
            id: 'demo-user',
            email: 'avery.johnson@gscc.com',
            user_metadata: {
              full_name: 'Avery Johnson',
              company_name: 'Global Supply Chain Co.',
              role: 'Admin'
            }
          });
          window.location.hash = '#overview';
        }}
      />
    );
  }

  const headerProps = getHeaderProps();

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#f8fafc' }}>
      
      {/* Left Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={(tab) => changeTab(tab)}
        user={user}
        onSignOut={handleSignOut}
        onOpenAuth={() => {
          setUser(null);
          window.location.hash = '#login';
        }}
      />

      {/* Main Content Area */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        
        {/* Top Header Bar */}
        <HeaderBar
          title={headerProps.title}
          subtitle={headerProps.subtitle}
          dateRange={dateRange}
          onDateChange={setDateRange}
          showFilters={headerProps.showFilters}
          onFilterClick={() => alert('Filters: Filtering data for ' + dateRange)}
          onOpenHelp={() => setIsHelpModalOpen(true)}
        />

        {/* Dynamic Main Body View */}
        <main style={{ flex: 1, position: 'relative', zIndex: 10 }}>
          {activeTab === 'overview' && (
            <OverviewView
              onNavigate={(tab) => changeTab(tab)}
              onOpenRecommendationModal={(rec) => setSimulationRec(rec)}
            />
          )}

          {activeTab === 'workspaces' && (
            <WorkspacesView
              onNavigate={(tab) => changeTab(tab)}
              onOpenInviteModal={() => setIsInviteModalOpen(true)}
            />
          )}

          {activeTab === 'datasources' && (
            <DataSourcesView
              onNavigate={(tab) => changeTab(tab)}
            />
          )}

          {activeTab === 'intelligence' && (
            <IntelligenceEnginesView />
          )}

          {activeTab === 'recommendations' && (
            <RecommendationsView
              onOpenSimulationModal={(rec) => setSimulationRec(rec)}
            />
          )}

          {activeTab === 'alerts' && (
            <AlertsView />
          )}

          {activeTab === 'dashboard' && (
            <DashboardView
              onNavigate={(tab) => setActiveTab(tab)}
            />
          )}

          {activeTab === 'mcp' && (
            <div style={{ padding: '0 32px 32px 32px' }}>
              <BIIntegrationsPanel />
            </div>
          )}

          {activeTab === 'access-control' && (
            <AccessControlView
              onOpenNewRoleModal={() => setIsNewRoleModalOpen(true)}
            />
          )}
        </main>

      </div>

      {/* Global Modals */}
      <NewRoleModal
        isOpen={isNewRoleModalOpen}
        onClose={() => setIsNewRoleModalOpen(false)}
        onSave={(newRole) => {
          alert(`Role "${newRole.name}" created successfully!`);
        }}
      />

      <InviteMemberModal
        isOpen={isInviteModalOpen}
        onClose={() => setIsInviteModalOpen(false)}
        onInvite={(invite) => {
          alert(`Invitation sent to ${invite.email} as ${invite.role}!`);
        }}
      />

      <RecommendationSimulationModal
        isOpen={Boolean(simulationRec)}
        recommendation={simulationRec}
        onClose={() => setSimulationRec(null)}
      />

      <HelpModal
        isOpen={isHelpModalOpen}
        onClose={() => setIsHelpModalOpen(false)}
      />

      {/* Floating Ask Wisualyst AI Launcher Button */}
      <button
        onClick={() => setIsAIChatOpen(true)}
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '28px',
          padding: '12px 20px',
          borderRadius: '999px',
          background: 'linear-gradient(135deg, #2563eb, #8b5cf6)',
          color: '#ffffff',
          border: 'none',
          boxShadow: '0 8px 24px rgba(37, 99, 235, 0.35)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '0.88rem',
          fontWeight: 700,
          cursor: 'pointer',
          zIndex: 100,
          transition: 'all 0.2s ease',
          fontFamily: 'var(--font-main)'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'translateY(-2px) scale(1.03)';
          e.currentTarget.style.boxShadow = '0 12px 28px rgba(37, 99, 235, 0.45)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0) scale(1)';
          e.currentTarget.style.boxShadow = '0 8px 24px rgba(37, 99, 235, 0.35)';
        }}
      >
        <span style={{ fontSize: '1.1rem' }}>✨</span>
        <span>Ask Wisualyst AI</span>
      </button>

      {/* Step 10: Live AI Assistant Drawer */}
      <AIAssistantDrawer
        isOpen={isAIChatOpen}
        onClose={() => setIsAIChatOpen(false)}
      />

    </div>
  );
}
