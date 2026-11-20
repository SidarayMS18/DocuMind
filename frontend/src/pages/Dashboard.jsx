import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Upload, Search, FileOutput, LayoutTemplate, FileText, Database, Cpu, ArrowRight } from 'lucide-react';
import './Dashboard.css';

const CARDS = [
  { to: '/upload',    icon: Upload,        color: '#6366f1', bg: '#eef2ff', label: 'Upload PDF',    desc: 'Index your documents into the local vector store' },
  { to: '/query',     icon: Search,        color: '#8b5cf6', bg: '#f5f3ff', label: 'Query RAG',     desc: 'Ask questions and get AI-powered answers' },
  { to: '/generate',  icon: FileOutput,    color: '#10b981', bg: '#ecfdf5', label: 'Generate Docs', desc: 'Create PDF, PowerPoint, or Excel documents' },
  { to: '/templates', icon: LayoutTemplate,color: '#f59e0b', bg: '#fffbeb', label: 'Templates',     desc: 'Manage and customize document templates' },
];

export default function Dashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    axios.get('/health').then(r => setStats(r.data)).catch(() => {});
  }, []);

  return (
    <div className="dashboard">
      {/* Hero */}
      <div className="hero-card">
        <div className="hero-left">
          <div className="hero-badge">🚀 Template-Driven Document Generator</div>
          <h2 className="hero-title">Turn Documents into<br /><span>Any Format Instantly</span></h2>
          <p className="hero-desc">
            Upload PDFs → Query with AI → Generate professional PDF, PowerPoint, or Excel documents.
            100% local — no cloud, no API keys needed.
          </p>
          <div className="hero-actions">
            <Link to="/upload" className="btn-hero-primary">
              <Upload size={16} /> Upload PDF
            </Link>
            <Link to="/generate" className="btn-hero-secondary">
              <FileOutput size={16} /> Generate Now
            </Link>
          </div>
        </div>
        <div className="hero-right">
          <div className="hero-visual">
            <div className="visual-item v1"><FileText size={20} /> PDF Input</div>
            <div className="visual-arrow">→</div>
            <div className="visual-item v2"><Cpu size={20} /> RAG Engine</div>
            <div className="visual-arrow">→</div>
            <div className="visual-item v3"><FileOutput size={20} /> Output</div>
          </div>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="stats-row">
          <div className="stat-card">
            <div className="stat-icon" style={{ background: '#eef2ff', color: '#6366f1' }}>
              <Database size={20} />
            </div>
            <div>
              <div className="stat-value">{stats.documents_indexed || 0}</div>
              <div className="stat-label">Chunks Indexed</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: '#ecfdf5', color: '#10b981' }}>
              <Cpu size={20} />
            </div>
            <div>
              <div className="stat-value">{stats.ollama_available ? 'Active' : 'Extractive'}</div>
              <div className="stat-label">LLM Mode</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: '#f5f3ff', color: '#8b5cf6' }}>
              <FileText size={20} />
            </div>
            <div>
              <div className="stat-value">Local</div>
              <div className="stat-label">Storage Mode</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: '#fffbeb', color: '#f59e0b' }}>
              <FileOutput size={20} />
            </div>
            <div>
              <div className="stat-value">PDF·PPT·XLS</div>
              <div className="stat-label">Output Formats</div>
            </div>
          </div>
        </div>
      )}

      {/* Feature cards */}
      <h3 className="section-title">Quick Actions</h3>
      <div className="feature-grid">
        {CARDS.map(({ to, icon: Icon, color, bg, label, desc }) => (
          <Link key={to} to={to} className="feature-card">
            <div className="feature-icon" style={{ background: bg, color }}>
              <Icon size={22} />
            </div>
            <div className="feature-body">
              <h4>{label}</h4>
              <p>{desc}</p>
            </div>
            <ArrowRight size={16} className="feature-arrow" style={{ color }} />
          </Link>
        ))}
      </div>

      {/* How it works */}
      <h3 className="section-title" style={{ marginTop: '2rem' }}>How It Works</h3>
      <div className="steps-row">
        {[
          { n: '1', title: 'Upload PDF', desc: 'Drop your PDF — it gets chunked, embedded, and stored in FAISS locally.' },
          { n: '2', title: 'Query or Write', desc: 'Ask a question (RAG) or paste your own JSON content directly.' },
          { n: '3', title: 'Pick Format', desc: 'Choose PDF, PowerPoint, or Excel as your output format.' },
          { n: '4', title: 'Download', desc: 'Your formatted document is generated and downloaded instantly.' },
        ].map(s => (
          <div key={s.n} className="step-card">
            <div className="step-num">{s.n}</div>
            <h4>{s.title}</h4>
            <p>{s.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
