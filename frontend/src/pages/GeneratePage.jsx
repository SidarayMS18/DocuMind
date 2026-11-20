import React, { useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { FileOutput, Search, Code, Download, CheckCircle, AlertCircle, Loader, Sparkles } from 'lucide-react';
import './GeneratePage.css';

const FORMATS = [
  { id: 'pdf',  icon: '📄', label: 'PDF',        ext: '.pdf' },
  { id: 'pptx', icon: '📊', label: 'PowerPoint', ext: '.pptx' },
  { id: 'xlsx', icon: '📈', label: 'Excel',       ext: '.xlsx' },
];

const SAMPLE = {
  title: "AI Research Report 2025",
  abstract: "This report presents key findings on AI adoption across industries.",
  introduction: "Artificial Intelligence is transforming every sector from healthcare to finance.",
  methodology: "We analyzed 100 research papers and surveyed 500 industry professionals.",
  results: "AI adoption grew by 300%. Productivity improved by 45% in early adopters.",
  conclusion: "AI will continue to dominate technology investment through 2030.",
  points: ["AI reduces costs by 30%", "Saves 2 hours per employee daily", "Improves decision accuracy by 60%"],
  tables: [
    { Industry: "Healthcare", "AI Adoption": "78%", ROI: "3.2x" },
    { Industry: "Finance",    "AI Adoption": "85%", ROI: "4.1x" },
  ]
};

export default function GeneratePage() {
  const [mode, setMode] = useState('query');   // 'query' | 'json' | 'upload'
  const [format, setFormat] = useState('pdf');
  const [query, setQuery] = useState('');
  const [jsonText, setJsonText] = useState('');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);

  const download = (blob, filename) => {
    const url = window.URL.createObjectURL(new Blob([blob]));
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    a.remove(); window.URL.revokeObjectURL(url);
  };

  const handleGenerate = async () => {
    setLoading(true); setError(null); setSuccess(null);

    try {
      if (mode === 'query') {
        if (!query.trim()) { toast.error('Enter a query'); setLoading(false); return; }
        const res = await axios.post('/generate/from-query', {
          query, output_format: format, use_n8n: false
        }, { responseType: 'blob', timeout: 90000 });
        download(res.data, `document.${format}`);
        setSuccess(`document.${format}`);
        toast.success('Document generated!');

      } else if (mode === 'json') {
        let data;
        try { data = JSON.parse(jsonText); } catch { toast.error('Invalid JSON'); setLoading(false); return; }
        const res = await axios.post('/generate/from-data', {
          data, output_format: format, use_n8n: false
        }, { responseType: 'blob', timeout: 90000 });
        const name = `${(data.title || 'document').replace(/\s+/g, '_').slice(0, 30)}.${format}`;
        download(res.data, name);
        setSuccess(name);
        toast.success('Document generated!');

      } else if (mode === 'upload') {
        if (!file) { toast.error('Select a PDF'); setLoading(false); return; }
        const fd = new FormData();
        fd.append('file', file);
        fd.append('output_format', format);
        const res = await axios.post('/generate/upload-and-generate', fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
          responseType: 'blob', timeout: 120000
        });
        const name = `${file.name.replace('.pdf', '')}.${format}`;
        download(res.data, name);
        setSuccess(name);
        toast.success('Document generated!');
      }
    } catch (err) {
      let msg = 'Generation failed';
      if (err.response?.data) {
        try {
          const t = await err.response.data.text();
          const p = JSON.parse(t);
          msg = p?.detail?.error?.message || p?.detail || msg;
        } catch { msg = `Server error ${err.response.status}`; }
      } else { msg = err.message; }
      setError(msg);
      toast.error('Generation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="generate-page">
      <div className="card">
        <h3 className="card-title">Generate Document</h3>
        <p className="card-desc">Choose your input method, pick an output format, and generate instantly.</p>

        {/* Mode tabs */}
        <div className="mode-tabs">
          {[
            { id: 'query',  icon: <Search size={16} />,     label: 'From Query' },
            { id: 'json',   icon: <Code size={16} />,       label: 'From JSON' },
            { id: 'upload', icon: <FileOutput size={16} />, label: 'From PDF' },
          ].map(m => (
            <button key={m.id} className={`mode-tab ${mode === m.id ? 'active' : ''}`} onClick={() => setMode(m.id)}>
              {m.icon} {m.label}
            </button>
          ))}
        </div>

        {/* Format selector */}
        <div className="format-row">
          {FORMATS.map(f => (
            <button key={f.id} className={`format-btn ${format === f.id ? 'active' : ''}`} onClick={() => setFormat(f.id)}>
              <span className="format-icon">{f.icon}</span>
              <span className="format-label">{f.label}</span>
              <span className="format-ext">{f.ext}</span>
            </button>
          ))}
        </div>

        {/* Input area */}
        {mode === 'query' && (
          <>
            <textarea
              className="gen-textarea"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="e.g. Summarize the methodology section from the uploaded documents..."
              rows={4}
            />
            <p style={{ fontSize: '.78rem', color: 'var(--text3)', marginBottom: '16px' }}>
              ⚠️ Requires documents to be indexed first — go to <strong>Upload PDF</strong> page.
            </p>
          </>
        )}

        {mode === 'json' && (
          <>
            <div className="json-actions">
              <button className="btn-sample" onClick={() => setJsonText(JSON.stringify(SAMPLE, null, 2))}>
                <Sparkles size={14} style={{ display: 'inline', marginRight: '4px' }} />
                Load Sample
              </button>
              <button className="btn-sample" onClick={() => setJsonText('')}>Clear</button>
            </div>
            <textarea
              className="json-textarea"
              value={jsonText}
              onChange={e => setJsonText(e.target.value)}
              placeholder={'{\n  "title": "My Document",\n  "abstract": "...",\n  "methodology": "...",\n  "results": "...",\n  "conclusion": "..."\n}'}
              rows={12}
              spellCheck={false}
            />
          </>
        )}

        {mode === 'upload' && (
          <>
            <input
              type="file" accept=".pdf"
              onChange={e => setFile(e.target.files[0])}
              style={{ marginBottom: '16px', width: '100%', padding: '10px', border: '2px dashed var(--border)', borderRadius: 'var(--radius)', cursor: 'pointer' }}
            />
            {file && <p style={{ fontSize: '.82rem', color: 'var(--text3)', marginBottom: '16px' }}>Selected: {file.name} ({(file.size/1024/1024).toFixed(2)} MB)</p>}
          </>
        )}

        <button className="btn-generate" onClick={handleGenerate} disabled={loading}>
          {loading ? <><Loader size={18} className="spin" /> Generating...</> : <><Download size={18} /> Generate {format.toUpperCase()}</>}
        </button>
      </div>

      {/* Status */}
      {loading && (
        <div className="loading-banner">
          <Loader size={22} className="spin" style={{ color: 'var(--primary)', flexShrink: 0 }} />
          <div><h4>Generating your document...</h4><p>This may take a few seconds</p></div>
        </div>
      )}

      {success && !loading && (
        <div className="success-banner">
          <CheckCircle size={28} className="success-banner-icon" />
          <div>
            <h4>Document Ready!</h4>
            <p>"{success}" has been generated and downloaded to your computer.</p>
          </div>
        </div>
      )}

      {error && !loading && (
        <div className="error-banner">
          <AlertCircle size={20} style={{ color: 'var(--danger)', flexShrink: 0 }} />
          <div><h4>Generation Failed</h4><p>{error}</p></div>
        </div>
      )}
    </div>
  );
}
