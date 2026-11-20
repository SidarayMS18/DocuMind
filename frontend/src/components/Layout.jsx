import React, { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Upload, Search, FileOutput,
  LayoutTemplate, Menu, X, Zap, ChevronRight, Settings, Shield
} from 'lucide-react';
import './Layout.css';

const NAV = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard',  desc: 'Overview & stats' },
  { to: '/upload',    icon: Upload,          label: 'Upload PDF',  desc: 'Index documents' },
  { to: '/query',     icon: Search,          label: 'Query RAG',   desc: 'Ask questions' },
  { to: '/generate',  icon: FileOutput,      label: 'Generate',    desc: 'Create documents' },
  { to: '/templates', icon: LayoutTemplate,  label: 'Templates',   desc: 'Manage templates' },
  { to: '/security',  icon: Shield,          label: 'Security',    desc: 'AES-256 encryption' },
  { to: '/settings',  icon: Settings,        label: 'Settings',    desc: 'API keys & config' },
];

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const current = NAV.find(n => n.to === location.pathname) || NAV[0];

  return (
    <div className={`layout ${collapsed ? 'collapsed' : ''}`}>
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <div className="logo-icon"><Zap size={18} /></div>
            {!collapsed && <span className="logo-text">DocGen AI</span>}
          </div>
          <button className="collapse-btn" onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <Menu size={16} /> : <X size={16} />}
          </button>
        </div>

        {!collapsed && (
          <div className="sidebar-badge">
            <span className="badge-dot" />
            <span>Local Mode · No Cloud</span>
          </div>
        )}

        <nav className="sidebar-nav">
          {NAV.map(({ to, icon: Icon, label, desc }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <div className="nav-icon"><Icon size={18} /></div>
              {!collapsed && (
                <div className="nav-text">
                  <span className="nav-label">{label}</span>
                  <span className="nav-desc">{desc}</span>
                </div>
              )}
              {!collapsed && <ChevronRight size={14} className="nav-arrow" />}
            </NavLink>
          ))}
        </nav>

        {!collapsed && (
          <div className="sidebar-footer">
            <div className="footer-info">
              <p className="footer-title">Powered by</p>
              <p className="footer-stack">FAISS · sentence-transformers · Ollama</p>
            </div>
          </div>
        )}
      </aside>

      {/* Main */}
      <main className="main">
        <div className="topbar">
          <div className="topbar-left">
            <h1 className="page-title">{current.label}</h1>
            <p className="page-desc">{current.desc}</p>
          </div>
          <div className="topbar-right">
            <div className="status-pill">
              <span className="status-dot" />
              <span>API Running</span>
            </div>
          </div>
        </div>
        <div className="page-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
