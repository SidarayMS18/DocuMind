import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { LayoutTemplate, CheckCircle, AlertCircle, Copy, RefreshCw } from 'lucide-react';
import './TemplatePage.css';

const PLACEHOLDERS = ['{{title}}','{{abstract}}','{{introduction}}','{{methodology}}','{{results}}','{{conclusion}}','{{points}}','{{tables}}'];

export default function TemplatePage() {
  const [format, setFormat] = useState('pdf');
  const [template, setTemplate] = useState('');
  const [validation, setValidation] = useState(null);
  const [sampleData, setSampleData] = useState(JSON.stringify({
    title: "Sample Document",
    abstract: "This is a sample abstract.",
    methodology: "Sample methodology.",
    results: "Sample results.",
    conclusion: "Sample conclusion."
  }, null, 2));

  const loadDefault = async () => {
    try {
      const res = await axios.get(`/template/default/${format}`);
      const t = typeof res.data.template === 'string' ? res.data.template : JSON.stringify(res.data.template, null, 2);
      setTemplate(t);
      toast.success('Default template loaded');
    } catch { toast.error('Failed to load template'); }
  };

  const validate = async () => {
    try {
      const data = JSON.parse(sampleData);
      const res = await axios.post('/template/validate', { template, data });
      setValidation(res.data);
      if (res.data.valid) toast.success('Template is valid!');
      else toast.error('Template has missing fields');
    } catch (e) {
      if (e.message.includes('JSON')) toast.error('Invalid JSON in sample data');
      else toast.error('Validation failed');
    }
  };

  const insertPlaceholder = (ph) => {
    setTemplate(prev => prev + ph);
  };

  return (
    <div className="template-page">
      <div className="template-grid">
        {/* Editor */}
        <div className="card">
          <div className="template-header">
            <LayoutTemplate size={20} style={{ color: 'var(--primary)' }} />
            <div>
              <h3 className="card-title">Template Editor</h3>
              <p className="card-desc">Write HTML templates with placeholders for dynamic content</p>
            </div>
          </div>

          <div className="format-tabs">
            {['pdf','ppt','excel'].map(f => (
              <button key={f} className={`format-tab ${format === f ? 'active' : ''}`} onClick={() => setFormat(f)}>
                {f.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="placeholder-chips">
            <span className="chips-label">Insert:</span>
            {PLACEHOLDERS.map(ph => (
              <button key={ph} className="ph-chip" onClick={() => insertPlaceholder(ph)}>{ph}</button>
            ))}
          </div>

          <textarea
            className="template-textarea"
            value={template}
            onChange={e => setTemplate(e.target.value)}
            placeholder="Write your template here using {{placeholders}}..."
            rows={16}
            spellCheck={false}
          />

          <div className="template-actions">
            <button className="btn-load" onClick={loadDefault}>
              <RefreshCw size={15} /> Load Default
            </button>
            <button className="btn-copy" onClick={() => { navigator.clipboard.writeText(template); toast.success('Copied!'); }}>
              <Copy size={15} /> Copy
            </button>
            <button className="btn-validate" onClick={validate} disabled={!template.trim()}>
              <CheckCircle size={15} /> Validate
            </button>
          </div>

          {validation && (
            <div className={`validation-result ${validation.valid ? 'valid' : 'invalid'}`}>
              {validation.valid
                ? <><CheckCircle size={16} /> <span>Valid! All placeholders matched.</span></>
                : <><AlertCircle size={16} /> <span>Missing: {validation.missing_fields.join(', ')}</span></>
              }
            </div>
          )}
        </div>

        {/* Right panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Sample data */}
          <div className="card">
            <h3 className="card-title">Sample Data (JSON)</h3>
            <p className="card-desc">Used for validation — edit to match your template</p>
            <textarea
              className="sample-textarea"
              value={sampleData}
              onChange={e => setSampleData(e.target.value)}
              rows={10}
              spellCheck={false}
            />
          </div>

          {/* Placeholder reference */}
          <div className="card">
            <h3 className="card-title">Placeholder Reference</h3>
            <div className="ph-reference">
              {[
                { ph: '{{title}}',        desc: 'Document title / heading' },
                { ph: '{{abstract}}',     desc: 'Summary / abstract section' },
                { ph: '{{introduction}}', desc: 'Introduction paragraph' },
                { ph: '{{methodology}}',  desc: 'Methods / approach used' },
                { ph: '{{results}}',      desc: 'Results and findings' },
                { ph: '{{conclusion}}',   desc: 'Conclusion / closing remarks' },
                { ph: '{{points}}',       desc: 'Bullet points list (array)' },
                { ph: '{{tables}}',       desc: 'Data tables (array of objects)' },
              ].map(({ ph, desc }) => (
                <div key={ph} className="ph-ref-item">
                  <code className="ph-code">{ph}</code>
                  <span className="ph-ref-desc">{desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
