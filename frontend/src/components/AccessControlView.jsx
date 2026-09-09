import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Users,
  KeyRound,
  FileText,
  Search,
  SlidersHorizontal,
  Plus,
  Edit2,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  Shield,
  Lock,
  Network,
  Code,
  BarChart2,
  Briefcase,
  Eye,
  ArrowRight,
  CheckCircle2,
  UserPlus,
  Trash2,
  AlertTriangle,
  Check,
  Clock,
  Globe
} from 'lucide-react';
import { API_BASE_URL } from '../config/api';

export default function AccessControlView({ onOpenNewRoleModal }) {
  const [activeSubTab, setActiveSubTab] = useState('roles');
  const [searchQuery, setSearchQuery] = useState('');

  // Data states
  const [roles, setRoles] = useState([]);
  const [users, setUsers] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  // Invite User Modal state
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [inviteForm, setInviteForm] = useState({ email: '', role: 'Data Analyst' });
  const [inviteSuccessMsg, setInviteSuccessMsg] = useState('');

  useEffect(() => {
    async function loadAccessControlData() {
      setLoading(true);
      try {
        const [rolesRes, usersRes, permRes, auditRes] = await Promise.all([
          fetch(`${API_BASE_URL}/api/access-control/roles`),
          fetch(`${API_BASE_URL}/api/access-control/users`),
          fetch(`${API_BASE_URL}/api/access-control/permissions`),
          fetch(`${API_BASE_URL}/api/access-control/audit-logs`)
        ]);

        if (rolesRes.ok) setRoles(await rolesRes.json());
        if (usersRes.ok) setUsers(await usersRes.json());
        if (permRes.ok) setPermissions(await permRes.json());
        if (auditRes.ok) setAuditLogs(await auditRes.json());
      } catch (err) {
        console.error('Error fetching access control data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadAccessControlData();
  }, []);

  const getRoleIcon = (id) => {
    switch (id) {
      case 'admin': return { icon: ShieldCheck, color: '#7c3aed', bg: '#f5f3ff' };
      case 'de': return { icon: Code, color: '#2563eb', bg: '#eff6ff' };
      case 'da': return { icon: BarChart2, color: '#059669', bg: '#ecfdf5' };
      case 'om': return { icon: Briefcase, color: '#d97706', bg: '#fffbeb' };
      default: return { icon: Eye, color: '#475569', bg: '#f1f5f9' };
    }
  };

  const handleInviteSubmit = async (e) => {
    e.preventDefault();
    if (!inviteForm.email) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/access-control/users/invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inviteForm)
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(prev => [data.invited_user, ...prev]);
        setInviteSuccessMsg(`Invite link sent to ${inviteForm.email}!`);
        setTimeout(() => {
          setIsInviteModalOpen(false);
          setInviteSuccessMsg('');
          setInviteForm({ email: '', role: 'Data Analyst' });
        }, 1500);
      }
    } catch (err) {
      console.error('Error inviting user:', err);
    }
  };

  const handleRevokeUser = async (userId) => {
    if (!window.confirm('Are you sure you want to revoke this user access?')) return;
    try {
      await fetch(`${API_BASE_URL}/api/access-control/users/${userId}`, { method: 'DELETE' });
      setUsers(prev => prev.filter(u => u.id !== userId));
    } catch (err) {
      console.error('Error revoking user:', err);
    }
  };

  const handleUserRoleChange = (userId, newRole) => {
    setUsers(prev => prev.map(u => u.id === userId ? { ...u, role: newRole } : u));
  };

  const handleUserStatusToggle = (userId) => {
    setUsers(prev => prev.map(u => u.id === userId ? {
      ...u,
      status: u.status === 'Active' ? 'Inactive' : 'Active'
    } : u));
  };

  const handlePermissionToggle = (permKey, roleKey) => {
    setPermissions(prev => prev.map(p => {
      if (p.key === permKey) {
        return { ...p, [roleKey]: !p[roleKey] };
      }
      return p;
    }));
  };

  const filteredRoles = roles.filter(r =>
    r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (r.desc && r.desc.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const filteredUsers = users.filter(u =>
    u.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    u.role.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredAuditLogs = auditLogs.filter(a =>
    a.action.toLowerCase().includes(searchQuery.toLowerCase()) ||
    a.user.toLowerCase().includes(searchQuery.toLowerCase()) ||
    a.details.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ padding: '0 32px 32px 32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Sub Tabs: Roles, Users, Permissions, Audit Logs */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '24px',
        borderBottom: '1px solid #e2e8f0',
        paddingBottom: '4px'
      }}>
        <button
          onClick={() => setActiveSubTab('roles')}
          style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '10px 4px', background: 'none', border: 'none',
            borderBottom: activeSubTab === 'roles' ? '2.5px solid #2563eb' : '2.5px solid transparent',
            color: activeSubTab === 'roles' ? '#2563eb' : '#64748b',
            fontWeight: activeSubTab === 'roles' ? 700 : 500,
            fontSize: '0.9rem', cursor: 'pointer'
          }}
        >
          <ShieldCheck size={17} />
          <span>Roles</span>
          <span style={{ fontSize: '0.72rem', backgroundColor: activeSubTab === 'roles' ? '#eff6ff' : '#f1f5f9', color: activeSubTab === 'roles' ? '#2563eb' : '#64748b', padding: '2px 8px', borderRadius: '12px', fontWeight: 700 }}>
            {roles.length}
          </span>
        </button>

        <button
          onClick={() => setActiveSubTab('users')}
          style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '10px 4px', background: 'none', border: 'none',
            borderBottom: activeSubTab === 'users' ? '2.5px solid #2563eb' : '2.5px solid transparent',
            color: activeSubTab === 'users' ? '#2563eb' : '#64748b',
            fontWeight: activeSubTab === 'users' ? 700 : 500,
            fontSize: '0.9rem', cursor: 'pointer'
          }}
        >
          <Users size={17} />
          <span>Users</span>
          <span style={{ fontSize: '0.72rem', backgroundColor: activeSubTab === 'users' ? '#eff6ff' : '#f1f5f9', color: activeSubTab === 'users' ? '#2563eb' : '#64748b', padding: '2px 8px', borderRadius: '12px', fontWeight: 700 }}>
            {users.length}
          </span>
        </button>

        <button
          onClick={() => setActiveSubTab('permissions')}
          style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '10px 4px', background: 'none', border: 'none',
            borderBottom: activeSubTab === 'permissions' ? '2.5px solid #2563eb' : '2.5px solid transparent',
            color: activeSubTab === 'permissions' ? '#2563eb' : '#64748b',
            fontWeight: activeSubTab === 'permissions' ? 700 : 500,
            fontSize: '0.9rem', cursor: 'pointer'
          }}
        >
          <KeyRound size={17} />
          <span>Permissions Matrix</span>
        </button>

        <button
          onClick={() => setActiveSubTab('audit')}
          style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '10px 4px', background: 'none', border: 'none',
            borderBottom: activeSubTab === 'audit' ? '2.5px solid #2563eb' : '2.5px solid transparent',
            color: activeSubTab === 'audit' ? '#2563eb' : '#64748b',
            fontWeight: activeSubTab === 'audit' ? 700 : 500,
            fontSize: '0.9rem', cursor: 'pointer'
          }}
        >
          <FileText size={17} />
          <span>Audit Logs</span>
        </button>
      </div>

      {/* ================= TAB 1: ROLES ================= */}
      {activeSubTab === 'roles' && (
        <div className="ui-card" style={{ padding: '24px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '20px',
            gap: '16px',
            flexWrap: 'wrap'
          }}>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>
                System & Custom Roles
              </h3>
              <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '4px 0 0 0' }}>
                Define user roles and control access to data pipelines, tools, and workspace resources.
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ position: 'relative', width: '240px' }}>
                <Search size={16} color="#94a3b8" style={{ position: 'absolute', left: '12px', top: '11px' }} />
                <input
                  type="text"
                  placeholder="Search roles..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="ui-input"
                  style={{ paddingLeft: '36px', paddingRight: '12px', fontSize: '0.82rem' }}
                />
              </div>

              <button
                onClick={onOpenNewRoleModal}
                className="btn-primary"
                style={{ padding: '8px 16px', fontSize: '0.82rem' }}
              >
                <Plus size={15} />
                <span>New Role</span>
              </button>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ color: '#64748b', textAlign: 'left', borderBottom: '1px solid #e2e8f0', fontSize: '0.78rem' }}>
                  <th style={{ padding: '12px 14px', fontWeight: 600 }}>Role Name</th>
                  <th style={{ padding: '12px 14px', fontWeight: 600 }}>Description</th>
                  <th style={{ padding: '12px 14px', fontWeight: 600 }}>Assigned Users</th>
                  <th style={{ padding: '12px 14px', fontWeight: 600 }}>Permission Scope</th>
                  <th style={{ padding: '12px 14px', fontWeight: 600 }}>Last Modified</th>
                  <th style={{ padding: '12px 14px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredRoles.map((role) => {
                  const iconInfo = getRoleIcon(role.id);
                  const Icon = iconInfo.icon;
                  return (
                    <tr
                      key={role.id}
                      style={{ borderBottom: '1px solid #f1f5f9' }}
                    >
                      <td style={{ padding: '14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div style={{
                            width: '34px', height: '34px', borderRadius: '8px',
                            backgroundColor: iconInfo.bg, color: iconInfo.color,
                            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                          }}>
                            <Icon size={18} />
                          </div>
                          <span style={{ fontWeight: 700, color: '#0f172a' }}>{role.name}</span>
                        </div>
                      </td>
                      <td style={{ padding: '14px', color: '#475569', fontSize: '0.82rem', maxWidth: '300px' }}>
                        {role.desc}
                      </td>
                      <td style={{ padding: '14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#475569', fontWeight: 600 }}>
                          <Users size={15} color="#94a3b8" />
                          <span>{role.usersCount} users</span>
                        </div>
                      </td>
                      <td style={{ padding: '14px' }}>
                        <span style={{
                          fontSize: '0.74rem', fontWeight: 600,
                          color: role.scopeColor || '#2563eb',
                          backgroundColor: role.scopeBg || '#eff6ff',
                          padding: '3px 10px', borderRadius: '6px', display: 'inline-block'
                        }}>
                          {role.scope}
                        </span>
                      </td>
                      <td style={{ padding: '14px', fontSize: '0.78rem' }}>
                        <div style={{ color: '#0f172a', fontWeight: 500 }}>{role.lastModified}</div>
                        <div style={{ color: '#64748b', fontSize: '0.72rem' }}>by {role.author}</div>
                      </td>
                      <td style={{ padding: '14px', textAlign: 'right' }}>
                        <button
                          onClick={onOpenNewRoleModal}
                          className="btn-secondary"
                          style={{ padding: '6px 12px', fontSize: '0.76rem' }}
                        >
                          <Edit2 size={13} />
                          <span>Edit</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ================= TAB 2: USERS ================= */}
      {activeSubTab === 'users' && (
        <div className="ui-card" style={{ padding: '24px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: '20px', gap: '16px', flexWrap: 'wrap'
          }}>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>
                Workspace Members & Team Access
              </h3>
              <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '4px 0 0 0' }}>
                Manage team members, assign workspace roles, and control active user permissions.
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ position: 'relative', width: '240px' }}>
                <Search size={16} color="#94a3b8" style={{ position: 'absolute', left: '12px', top: '11px' }} />
                <input
                  type="text"
                  placeholder="Search users..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="ui-input"
                  style={{ paddingLeft: '36px', paddingRight: '12px', fontSize: '0.82rem' }}
                />
              </div>

              <button
                onClick={() => setIsInviteModalOpen(true)}
                className="btn-primary"
                style={{ padding: '8px 16px', fontSize: '0.82rem' }}
              >
                <UserPlus size={15} />
                <span>Invite Member</span>
              </button>
            </div>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ color: '#64748b', textAlign: 'left', borderBottom: '1px solid #e2e8f0', fontSize: '0.78rem' }}>
                <th style={{ padding: '12px 14px', fontWeight: 600 }}>User</th>
                <th style={{ padding: '12px 14px', fontWeight: 600 }}>Assigned Role</th>
                <th style={{ padding: '12px 14px', fontWeight: 600 }}>Status</th>
                <th style={{ padding: '12px 14px', fontWeight: 600 }}>Last Active</th>
                <th style={{ padding: '12px 14px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((user) => (
                <tr key={user.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{
                        width: '36px', height: '36px', borderRadius: '50%',
                        backgroundColor: user.avatarBg || '#2563eb', color: '#ffffff',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontWeight: 700, fontSize: '0.85rem'
                      }}>
                        {user.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <div>
                        <div style={{ fontWeight: 700, color: '#0f172a' }}>{user.name}</div>
                        <div style={{ fontSize: '0.76rem', color: '#64748b' }}>{user.email}</div>
                      </div>
                    </div>
                  </td>

                  <td style={{ padding: '14px' }}>
                    <select
                      value={user.role}
                      onChange={(e) => handleUserRoleChange(user.id, e.target.value)}
                      className="ui-input"
                      style={{ width: '180px', padding: '6px 10px', fontSize: '0.78rem', fontWeight: 600 }}
                    >
                      <option value="Admin">Admin</option>
                      <option value="Data Engineer">Data Engineer</option>
                      <option value="Data Analyst">Data Analyst</option>
                      <option value="Operations Manager">Operations Manager</option>
                      <option value="Viewer">Viewer</option>
                    </select>
                  </td>

                  <td style={{ padding: '14px' }}>
                    <button
                      onClick={() => handleUserStatusToggle(user.id)}
                      style={{
                        padding: '4px 10px', borderRadius: '12px', border: 'none',
                        cursor: 'pointer', fontSize: '0.72rem', fontWeight: 700,
                        backgroundColor: user.status === 'Active' ? '#ecfdf5' : '#f1f5f9',
                        color: user.status === 'Active' ? '#059669' : '#64748b'
                      }}
                    >
                      {user.status === 'Active' ? '● Active' : '○ Inactive'}
                    </button>
                  </td>

                  <td style={{ padding: '14px', fontSize: '0.78rem', color: '#64748b' }}>
                    {user.lastActive}
                  </td>

                  <td style={{ padding: '14px', textAlign: 'right' }}>
                    <button
                      onClick={() => handleRevokeUser(user.id)}
                      style={{
                        padding: '6px 10px', borderRadius: '6px', border: '1px solid #fecaca',
                        backgroundColor: '#fff5f5', color: '#ef4444', cursor: 'pointer',
                        fontSize: '0.74rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px'
                      }}
                    >
                      <Trash2 size={13} />
                      <span>Revoke</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ================= TAB 3: PERMISSIONS MATRIX ================= */}
      {activeSubTab === 'permissions' && (
        <div className="ui-card" style={{ padding: '24px' }}>
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>
              Module Permission Matrix
            </h3>
            <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '4px 0 0 0' }}>
              Configure feature access per user role across all 6 core supply chain modules.
            </p>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ color: '#64748b', textAlign: 'left', borderBottom: '1px solid #e2e8f0', fontSize: '0.78rem' }}>
                <th style={{ padding: '12px 14px', fontWeight: 600 }}>Feature / Module</th>
                <th style={{ padding: '12px 14px', fontWeight: 600, textAlign: 'center' }}>Admin</th>
                <th style={{ padding: '12px 14px', fontWeight: 600, textAlign: 'center' }}>Data Engineer</th>
                <th style={{ padding: '12px 14px', fontWeight: 600, textAlign: 'center' }}>Data Analyst</th>
                <th style={{ padding: '12px 14px', fontWeight: 600, textAlign: 'center' }}>Ops Manager</th>
                <th style={{ padding: '12px 14px', fontWeight: 600, textAlign: 'center' }}>Viewer</th>
              </tr>
            </thead>
            <tbody>
              {permissions.map((p) => (
                <tr key={p.key} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '14px', fontWeight: 700, color: '#0f172a' }}>
                    {p.module}
                  </td>
                  {['admin', 'data_engineer', 'data_analyst', 'ops_manager', 'viewer'].map(roleKey => (
                    <td key={roleKey} style={{ padding: '14px', textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={Boolean(p[roleKey])}
                        onChange={() => handlePermissionToggle(p.key, roleKey)}
                        style={{ width: '16px', height: '16px', cursor: 'pointer', accentColor: '#2563eb' }}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ================= TAB 4: AUDIT LOGS ================= */}
      {activeSubTab === 'audit' && (
        <div className="ui-card" style={{ padding: '24px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: '20px', gap: '16px', flexWrap: 'wrap'
          }}>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>
                Real-Time Security Audit Logs
              </h3>
              <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '4px 0 0 0' }}>
                Complete immutable trail of user logins, role changes, and database connector executions.
              </p>
            </div>

            <div style={{ position: 'relative', width: '260px' }}>
              <Search size={16} color="#94a3b8" style={{ position: 'absolute', left: '12px', top: '11px' }} />
              <input
                type="text"
                placeholder="Search audit trail..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="ui-input"
                style={{ paddingLeft: '36px', paddingRight: '12px', fontSize: '0.82rem' }}
              />
            </div>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ color: '#64748b', textAlign: 'left', borderBottom: '1px solid #e2e8f0', fontSize: '0.76rem' }}>
                <th style={{ padding: '12px 14px', fontWeight: 600 }}>Timestamp</th>
                <th style={{ padding: '12px 14px', fontWeight: 600 }}>User</th>
                <th style={{ padding: '12px 14px', fontWeight: 600 }}>Action</th>
                <th style={{ padding: '12px 14px', fontWeight: 600 }}>Category</th>
                <th style={{ padding: '12px 14px', fontWeight: 600 }}>Details</th>
                <th style={{ padding: '12px 14px', fontWeight: 600, textAlign: 'right' }}>IP Address</th>
              </tr>
            </thead>
            <tbody>
              {filteredAuditLogs.map((log) => (
                <tr key={log.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '12px 14px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Clock size={13} color="#94a3b8" />
                    <span>{log.timestamp}</span>
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    <div style={{ fontWeight: 700, color: '#0f172a' }}>{log.user}</div>
                    <div style={{ fontSize: '0.7rem', color: '#64748b' }}>{log.email}</div>
                  </td>
                  <td style={{ padding: '12px 14px', fontWeight: 700, color: '#0f172a' }}>
                    {log.action}
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    <span style={{ fontSize: '0.72rem', backgroundColor: '#eff6ff', color: '#2563eb', padding: '2px 8px', borderRadius: '6px', fontWeight: 600 }}>
                      {log.category}
                    </span>
                  </td>
                  <td style={{ padding: '12px 14px', color: '#475569', maxWidth: '320px' }}>
                    {log.details}
                  </td>
                  <td style={{ padding: '12px 14px', textAlign: 'right', fontFamily: 'monospace', color: '#64748b' }}>
                    {log.ip}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Invite Member Modal */}
      {isInviteModalOpen && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          backgroundColor: 'rgba(15, 23, 42, 0.45)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'
        }}>
          <div className="ui-card" style={{ maxWidth: '460px', width: '100%', padding: '28px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a', margin: '0 0 8px 0' }}>
              Invite Team Member
            </h3>
            <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '0 0 20px 0' }}>
              Send an invitation email to grant access to this workspace.
            </p>

            {inviteSuccessMsg && (
              <div style={{ padding: '10px 14px', backgroundColor: '#ecfdf5', color: '#059669', borderRadius: '8px', fontSize: '0.8rem', fontWeight: 600, marginBottom: '16px' }}>
                {inviteSuccessMsg}
              </div>
            )}

            <form onSubmit={handleInviteSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>Email Address</label>
                <input
                  type="email"
                  placeholder="e.g. colleague@company.com"
                  required
                  value={inviteForm.email}
                  onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                  className="ui-input"
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>Role</label>
                <select
                  value={inviteForm.role}
                  onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value })}
                  className="ui-input"
                >
                  <option value="Admin">Admin</option>
                  <option value="Data Engineer">Data Engineer</option>
                  <option value="Data Analyst">Data Analyst</option>
                  <option value="Operations Manager">Operations Manager</option>
                  <option value="Viewer">Viewer</option>
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px', marginTop: '16px' }}>
                <button type="button" onClick={() => setIsInviteModalOpen(false)} className="btn-secondary" style={{ padding: '8px 16px', fontSize: '0.82rem' }}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" style={{ padding: '8px 18px', fontSize: '0.82rem' }}>
                  Send Invite
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Access Governance (5 Cards) */}
      <div>
        <div style={{ marginBottom: '14px' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>
            Access Governance & Security Controls
          </h3>
          <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '4px 0 0 0' }}>
            Enterprise-grade security standards protecting your database pipelines and workspace data.
          </p>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, 1fr)',
          gap: '14px'
        }}>
          {/* Card 1 */}
          <div className="ui-card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ width: '36px', height: '36px', borderRadius: '10px', backgroundColor: '#f5f3ff', color: '#7c3aed', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '12px' }}>
                <Shield size={18} />
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0f172a' }}>Granular Roles</div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '4px', lineHeight: 1.4 }}>
                Assign RBAC permissions at feature, workspace, and row level.
              </div>
            </div>
            <button onClick={() => setActiveSubTab('permissions')} style={{ background: 'none', border: 'none', color: '#2563eb', fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '14px', padding: 0 }}>
              <span>Manage Matrix</span>
              <ArrowRight size={13} />
            </button>
          </div>

          {/* Card 2 */}
          <div className="ui-card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ width: '36px', height: '36px', borderRadius: '10px', backgroundColor: '#eff6ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '12px' }}>
                <FileText size={18} />
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0f172a' }}>Audit Trail</div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '4px', lineHeight: 1.4 }}>
                Track logins, schema changes, and PO approvals in real time.
              </div>
            </div>
            <button onClick={() => setActiveSubTab('audit')} style={{ background: 'none', border: 'none', color: '#2563eb', fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '14px', padding: 0 }}>
              <span>View Logs</span>
              <ArrowRight size={13} />
            </button>
          </div>

          {/* Card 3 */}
          <div className="ui-card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ width: '36px', height: '36px', borderRadius: '10px', backgroundColor: '#ecfdf5', color: '#059669', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '12px' }}>
                <Lock size={18} />
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0f172a' }}>Data Encryption</div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '4px', lineHeight: 1.4 }}>
                AES-256 encryption at rest and TLS 1.3 in transit.
              </div>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#059669', fontWeight: 700, marginTop: '14px' }}>
              ✓ Enforced
            </div>
          </div>

          {/* Card 4 */}
          <div className="ui-card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ width: '36px', height: '36px', borderRadius: '10px', backgroundColor: '#fffbeb', color: '#d97706', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '12px' }}>
                <Network size={18} />
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0f172a' }}>Network Rule</div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '4px', lineHeight: 1.4 }}>
                Restrict DB access by IP allowlists & VPC endpoints.
              </div>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#d97706', fontWeight: 700, marginTop: '14px' }}>
              ● 3 Rules Active
            </div>
          </div>

          {/* Card 5 */}
          <div style={{ padding: '18px', borderRadius: '16px', backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ width: '36px', height: '36px', borderRadius: '10px', backgroundColor: '#dbeafe', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '12px' }}>
                <ShieldCheck size={20} />
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1e3a8a' }}>SOC2 Compliant</div>
              <div style={{ fontSize: '0.72rem', color: '#3b82f6', marginTop: '4px', lineHeight: 1.4 }}>
                Enterprise security controls & automated posture checks.
              </div>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#2563eb', fontWeight: 700, marginTop: '14px' }}>
              ✓ Verified
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
