import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { Key, CheckCircle, AlertCircle, ExternalLink, Cpu, Database, Zap } from 'lucide-react';
import './SettingsPage.css';

export default function SettingsPage() {
  const [provider, setProvider] = useState('groq');
  const [apiKey, setApiKey] = useState('');
  const [health, setHealth] = useState(null);
  const [saving, setSaving] = useState(false);

  const fetchHealth = () =>
    axios.get('/health').then(r => setHealth(r.data)).catch(() => {});

  useEffect(() => { fetchHealth(); }, []);

  const saveKey = async () => {
    if (!apiKey.trim()) { toast.error('Enter an API key'); return; }
    setSaving(true);
    try {
      const res = await axios.post('/settings/gemini-key', {
        api_key: apiKey.trim(),
        provider
      });
      if (res.data.active) {
        toast.success(res.data.message);
        setApiKey('');
      } else {
        toast.error(res.data.message);
      }
      fetchHealth();
    } catch (err) {
      toast.error('Failed to save key');
    } finally {
      setSaving(false);
    }
  };

  const llmMode = health?.llm_mode || 'unknown';
  const isAIActive = ['groq','gemini','ollama'].includes(llmMode);

  const PROVIDERS = [
    {
      id: 'groq',
      logo: 'GRQ',
      logoBg: '#f55036',
      name: 'Groq — 100% FREE ⭐',
      sub: '14,400 req/day · keys start with gsk_',
      url: 'https://console.groq.com/keys',
      urlLabel: 'Get Free Groq Key',
      placeholder: 'gsk_...',
      active: health?.groq_available,
      steps: [
        'Click "Get Free Groq Key" above',
        'Sign in / create account at console.groq.com',
        'Click "+ Create API Key"',
        'Copy the key (starts with gsk_)',
        'Paste it above and click Save & Activate'
      ],
      note: '✅ Completely free — 14,400 requests/day, no credit card needed'
    },
    {
      id: 'gemini',
      logo: 'G',
      logoBg: '#4285f4',
      name: 'Gemini (Google) — Free',
      sub: '1500 req/day · keys start with AIza',
      url: 'https://aistudio.google.com/app/apikey',
      urlLabel: 'Get Free Gemini Key',
      placeholder: 'AIza...',
      active: health?.gemini_available,
      steps: [
        'Click "Get Free Gemini Key" above',
        'Sign in with your Google account',
        'Click "Create API Key"',
        'Copy the key (starts with AIza)',
        'Paste it above and click Save & Activate'
      ],
      note: '✅ Free tier: 1500 req/day, 15/min — no credit card needed'
    }
  ];

  const currentProvider = PROVIDERS.find(p => p.id === provider) || PROVIDERS[0];

  return (
    <div className="settings-page">

      {/* Status cards */}
      {health && (
        <div className="status-grid">
          <div className="status-card">
            <div className="status-card-icon" style={{ background: isAIActive ? '#eef2ff' : '#fffbeb', color: isAIActive ? '#6366f1' : '#f59e0b' }}>
              <Cpu size={20} />
            </div>
            <div>
              <div className="status-card-label">LLM Mode</div>
              <div className="status-card-value" style={{ color: isAIActive ? '#6366f1' : '#f59e0b', textTransform: 'capitalize' }}>
                {llmMode}
              </div>
            </div>
            {isAIActive
              ? <CheckCircle size={16} style={{ color: '#10b981', marginLeft: 'auto' }} />
              : <AlertCircle size={16} style={{ color: '#f59e0b', marginLeft: 'auto' }} />
            }
          </div>

          <div className="status-card">
            <div className="status-card-icon" style={{ background: '#ecfdf5', color: '#10b981' }}>
              <Database size={20} />
            </div>
            <div>
              <div className="status-card-label">Documents Indexed</div>
              <div className="status-card-value" style={{ color: '#10b981' }}>
                {health.documents_indexed} chunks
              </div>
            </div>
            {health.documents_indexed > 0
              ? <CheckCircle size={16} style={{ color: '#10b981', marginLeft: 'auto' }} />
              : <AlertCircle size={16} style={{ color: '#f59e0b', marginLeft: 'auto' }} />
            }
          </div>

          <div className="status-card">
            <div className="status-card-icon" style={{ background: '#eef2ff', color: '#6366f1' }}>
              <Zap size={20} />
            </div>
            <div>
              <div className="status-card-label">API Status</div>
              <div className="status-card-value" style={{ color: '#6366f1' }}>Running</div>
            </div>
            <CheckCircle size={16} style={{ color: '#10b981', marginLeft: 'auto' }} />
          </div>
        </div>
      )}

      {/* AI Key Config */}
      <div className="card">
        <div className="card-header">
          <Key size={20} style={{ color: '#6366f1' }} />
          <div>
            <h3>AI Provider API Key</h3>
            <p>Configure your AI provider for accurate answers and document generation</p>
          </div>
        </div>

        <div className={`key-status ${isAIActive ? 'active' : 'inactive'}`}>
          {isAIActive
            ? <><CheckCircle size={16} /> <strong>{llmMode.toUpperCase()}</strong> is active — AI-powered answers enabled</>
            : <><AlertCircle size={16} /> No AI configured — add an API key below</>
          }
        </div>

        {/* Provider tabs */}
        <div className="provider-tabs">
          {PROVIDERS.map(p => (
            <button
              key={p.id}
              className={`provider-tab ${provider === p.id ? 'active' : ''}`}
              onClick={() => setProvider(p.id)}
            >
              <span className="provider-logo" style={{ background: p.logoBg, color: '#fff', fontSize: p.logo.length > 1 ? '.65rem' : '1rem' }}>
                {p.logo}
              </span>
              <div>
                <div className="provider-name">{p.name}</div>
                <div className="provider-sub">{p.sub}</div>
              </div>
              {p.active && <CheckCircle size={14} style={{ color: '#10b981', marginLeft: 'auto' }} />}
            </button>
          ))}
        </div>

        {/* Key input */}
        <div className="key-input-row">
          <input
            type="text"
            className="key-input"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder={currentProvider.placeholder}
          />
          <button className="btn-save" onClick={saveKey} disabled={saving || !apiKey.trim()}>
            {saving ? 'Saving...' : 'Save & Activate'}
          </button>
        </div>

        <div className="get-key-links">
          <a href={currentProvider.url} target="_blank" rel="noreferrer" className="get-key-btn">
            {currentProvider.urlLabel} <ExternalLink size={13} />
          </a>
        </div>

        <div className="key-steps">
          <h4>How to get your {currentProvider.name.split('—')[0].trim()} key:</h4>
          <ol>
            {currentProvider.steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
          <div className="key-note">{currentProvider.note}</div>
        </div>
      </div>

      {/* Manual config */}
      <div className="card">
        <h3 className="card-title">Manual Configuration</h3>
        <p className="card-desc">Add your key directly to <code>MiniProject/.env</code>:</p>
        <div className="code-block">
          <code style={{color:'#a5b4fc'}}># Groq (recommended — free, fast):</code><br />
          <code style={{color:'#6ee7b7'}}>GROQ_API_KEY=gsk_your_key_here</code><br /><br />
          <code style={{color:'#a5b4fc'}}># Gemini (backup):</code><br />
          <code style={{color:'#6ee7b7'}}>GEMINI_API_KEY=AIza_your_key_here</code>
        </div>
      </div>
    </div>
  );
}
