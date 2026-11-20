import React, { useCallback, useState, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import toast from 'react-hot-toast';
import { Upload, FileText, X, CheckCircle, AlertCircle, Database, Zap, Shield, Trash2 } from 'lucide-react';
import './UploadPage.css';

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);
  const [docList, setDocList] = useState([]);

  const fetchStats = () => {
    axios.get('/documents/stats').then(r => setStats(r.data)).catch(() => {});
    axios.get('/documents/list').then(r => setDocList(r.data.documents || [])).catch(() => {});
  };

  // Fetch on mount AND every time we come back to this page
  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 5000); // refresh every 5s
    return () => clearInterval(interval);
  }, []);

  const onDrop = useCallback((accepted) => {
    if (accepted[0]) { setFile(accepted[0]); setResult(null); setError(null); }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { 'application/pdf': ['.pdf'] }, maxFiles: 1
  });

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true); setError(null); setResult(null); setProgress(5);

    const fd = new FormData();
    fd.append('file', file);

    let current = 5;
    const progressTimer = setInterval(() => {
      current += current < 40 ? 3 : current < 70 ? 2 : current < 90 ? 1 : 0.3;
      if (current > 92) current = 92;
      setProgress(Math.round(current));
    }, 600);

    try {
      const res = await axios.post('/documents/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000
      });
      clearInterval(progressTimer);
      setProgress(100);
      setResult(res.data);
      fetchStats(); // refresh list immediately
      toast.success(`✅ Indexed ${res.data.chunks_created} chunks from "${file.name}"`);
    } catch (err) {
      clearInterval(progressTimer);
      setProgress(0);
      const msg = err.response?.data?.detail?.error?.message || err.message || 'Upload failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="upload-page">
      <div className="upload-grid">
        {/* Left: Upload */}
        <div className="card">
          <h3 className="card-title">Upload & Index PDF</h3>
          <p className="card-desc">Your PDF will be chunked, embedded with sentence-transformers, and stored in FAISS locally.</p>

          <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
            <input {...getInputProps()} />
            <div className="dropzone-icon"><Upload size={40} /></div>
            <h4>{isDragActive ? 'Drop it here!' : 'Drag & drop your PDF'}</h4>
            <p>or <span className="browse">browse files</span> · Max 50MB</p>
          </div>

          {file && (
            <div className="file-preview">
              <FileText size={22} className="file-preview-icon" />
              <div className="file-preview-info">
                <div className="file-preview-name">{file.name}</div>
                <div className="file-preview-size">{(file.size / 1024 / 1024).toFixed(2)} MB</div>
              </div>
              <button className="file-remove" onClick={() => { setFile(null); setResult(null); setError(null); }}>
                <X size={16} />
              </button>
            </div>
          )}

          {loading && (
            <div className="progress-bar-wrap">
              <div className="progress-label">
                <span>
                  {progress < 20 ? '📄 Extracting text...' :
                   progress < 50 ? '🧠 Loading embedding model...' :
                   progress < 75 ? '⚡ Generating embeddings...' :
                   progress < 95 ? '💾 Saving to FAISS index...' :
                   '✅ Done!'}
                </span>
                <span>{progress}%</span>
              </div>
              <div className="progress-bar"><div className="progress-fill" style={{ width: `${progress}%` }} /></div>
            </div>
          )}

          {result && (
            <div className="success-box">
              <CheckCircle size={18} className="success-box-icon" />
              <div>
                <h4>Successfully Encrypted & Indexed!</h4>
                <p>{result.chunks_created} chunks from "{result.filename}" in {result.processing_time_ms}ms</p>
                {result.encrypted && (
                  <p style={{ marginTop: '6px', fontSize: '.78rem', color: '#059669', fontWeight: 600 }}>
                    🔐 AES-256-GCM encrypted · {result.original_size_bytes} → {result.encrypted_size_bytes} bytes
                  </p>
                )}
              </div>
            </div>
          )}

          {error && (
            <div className="error-box">
              <AlertCircle size={18} className="error-box-icon" />
              <div><h4>Upload Failed</h4><p>{error}</p></div>
            </div>
          )}

          <button className="btn-upload" onClick={handleUpload} disabled={!file || loading}>
            <Upload size={18} />
            {loading ? 'Processing...' : 'Upload & Index'}
          </button>
        </div>

        {/* Right panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {/* Index Status */}
          <div className="card">
            <h3 className="card-title">Index Status</h3>
            {stats ? (
              <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
                <div style={{ flex: 1, background: '#eef2ff', borderRadius: '10px', padding: '14px', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#6366f1' }}>{stats.total_chunks}</div>
                  <div style={{ fontSize: '.72rem', color: '#6366f1', marginTop: '2px' }}>Total Chunks</div>
                </div>
                <div style={{ flex: 1, background: '#ecfdf5', borderRadius: '10px', padding: '14px', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#10b981' }}>{docList.length}</div>
                  <div style={{ fontSize: '.72rem', color: '#10b981', marginTop: '2px' }}>Documents</div>
                </div>
                <div style={{ flex: 1, background: stats.index_ready ? '#ecfdf5' : '#fffbeb', borderRadius: '10px', padding: '14px', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: stats.index_ready ? '#10b981' : '#f59e0b' }}>
                    {stats.index_ready ? '✓' : '✗'}
                  </div>
                  <div style={{ fontSize: '.72rem', color: stats.index_ready ? '#10b981' : '#f59e0b', marginTop: '2px' }}>Ready</div>
                </div>
              </div>
            ) : (
              <div className="empty-state">Loading stats...</div>
            )}
          </div>

          {/* Indexed Documents List */}
          <div className="card">
            <h3 className="card-title" style={{ marginBottom: '12px' }}>
              Indexed Documents
              {docList.length > 0 && (
                <span style={{ marginLeft: '8px', background: '#eef2ff', color: '#6366f1', fontSize: '.72rem', padding: '2px 8px', borderRadius: '10px', fontWeight: 600 }}>
                  {docList.length}
                </span>
              )}
            </h3>

            {docList.length === 0 ? (
              <div className="empty-state">
                <Database size={28} style={{ color: 'var(--text3)', marginBottom: '8px' }} />
                <p>No documents indexed yet.</p>
                <p style={{ fontSize: '.78rem', marginTop: '4px' }}>Upload a PDF to get started.</p>
              </div>
            ) : (
              <div className="indexed-list">
                {docList.map((doc, i) => (
                  <div key={i} className="indexed-item">
                    <FileText size={16} className="indexed-item-icon" />
                    <div className="indexed-item-info">
                      <div className="indexed-item-name">{doc.name}</div>
                      <div className="indexed-item-meta">{doc.chunks} chunks · {doc.pages} pages</div>
                    </div>
                    <span className="indexed-item-badge">✓ Indexed</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* What happens */}
          <div className="card">
            <h3 className="card-title">What happens?</h3>
            <div className="info-list">
              {[
                { icon: FileText, color: '#6366f1', bg: '#eef2ff', title: 'Text Extraction', desc: 'PyMuPDF extracts text with page coordinates' },
                { icon: Shield, color: '#ef4444', bg: '#fef2f2', title: 'AES-256-GCM Encrypt', desc: 'PDF encrypted before saving to disk — plaintext never stored' },
                { icon: Zap, color: '#8b5cf6', bg: '#f5f3ff', title: 'Embedding', desc: 'sentence-transformers converts text to vectors' },
                { icon: Database, color: '#10b981', bg: '#ecfdf5', title: 'FAISS Index', desc: 'Vectors stored locally for fast similarity search' },
              ].map(({ icon: Icon, color, bg, title, desc }) => (
                <div key={title} className="info-item">
                  <div className="info-item-icon" style={{ background: bg, color }}><Icon size={16} /></div>
                  <div><h5>{title}</h5><p>{desc}</p></div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
