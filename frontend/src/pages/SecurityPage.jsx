import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { Lock, Unlock, Shield, Copy, Loader, Key, RefreshCw } from 'lucide-react';
import './SecurityPage.css';

export default function SecurityPage() {
  const [plaintext, setPlaintext] = useState('');
  const [cipherInput, setCipherInput] = useState('');
  const [encResult, setEncResult] = useState(null);
  const [decResult, setDecResult] = useState(null);
  const [encLoading, setEncLoading] = useState(false);
  const [decLoading, setDecLoading] = useState(false);
  const [aesInfo, setAesInfo] = useState(null);

  useEffect(() => {
    axios.get('/security/info').then(r => setAesInfo(r.data)).catch(() => {});
  }, []);

  const handleEncrypt = async () => {
    if (!plaintext.trim()) return;
    setEncLoading(true);
    try {
      const res = await axios.post('/security/encrypt', { text: plaintext });
      setEncResult(res.data);
      toast.success('Text encrypted successfully!');
    } catch (err) {
      toast.error('Encryption failed');
    } finally {
      setEncLoading(false);
    }
  };

  const handleDecrypt = async () => {
    if (!cipherInput.trim()) return;
    setDecLoading(true);
    try {
      const res = await axios.post('/security/decrypt', { ciphertext: cipherInput.trim() });
      setDecResult(res.data);
      toast.success('Text decrypted successfully!');
    } catch (err) {
      toast.error('Decryption failed — invalid ciphertext or wrong key');
    } finally {
      setDecLoading(false);
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied!`);
  };

  const useCipherForDecrypt = () => {
    if (encResult?.ciphertext) {
      setCipherInput(encResult.ciphertext);
      toast('Ciphertext loaded into decrypt panel', { icon: '↓' });
    }
  };

  return (
    <div className="security-page">

      {/* Hero */}
      <div className="aes-hero">
        <div className="aes-hero-text">
          <h2>AES-256-GCM <span>Encryption</span></h2>
          <p>
            Military-grade encryption protecting all documents and data in this system.
            AES-256 with Galois/Counter Mode provides both confidentiality and authenticity.
          </p>
          <div className="aes-badges">
            <span className="aes-badge">🔐 AES-256</span>
            <span className="aes-badge">🛡️ GCM Mode</span>
            <span className="aes-badge">🔑 PBKDF2 Key Derivation</span>
            <span className="aes-badge">✅ Authenticated Encryption</span>
            <span className="aes-badge">🎲 Random IV per Operation</span>
          </div>
        </div>
        {aesInfo && (
          <div className="aes-visual">
            {[
              { label: 'Algorithm', value: aesInfo.algorithm },
              { label: 'Key Size', value: aesInfo.key_size },
              { label: 'Mode', value: 'GCM' },
              { label: 'IV Size', value: aesInfo.iv_size },
              { label: 'Auth Tag', value: aesInfo.tag_size },
              { label: 'KDF', value: 'PBKDF2-SHA256' },
            ].map(({ label, value }) => (
              <div key={label} className="aes-visual-row">
                <span className="aes-visual-label">{label}</span>
                <span className="aes-visual-value">{value}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Info cards */}
      {aesInfo && (
        <div className="info-grid">
          {[
            { icon: '🔑', label: 'Key Size', value: '256 bits' },
            { icon: '🎲', label: 'IV Size', value: '96 bits (random)' },
            { icon: '🏷️', label: 'Auth Tag', value: '128 bits' },
            { icon: '🔄', label: 'KDF Iterations', value: aesInfo.iterations?.toLocaleString() },
          ].map(({ icon, label, value }) => (
            <div key={label} className="info-card">
              <div className="info-card-icon">{icon}</div>
              <div className="info-card-label">{label}</div>
              <div className="info-card-value">{value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Encrypt / Decrypt panels */}
      <div className="crypto-grid">
        {/* Encrypt */}
        <div className="card">
          <div className="panel-title">
            <Lock size={18} style={{ color: '#6366f1' }} />
            Encrypt Text
            <span className="panel-badge badge-encrypt">AES-256-GCM</span>
          </div>

          <textarea
            className="crypto-textarea"
            value={plaintext}
            onChange={e => setPlaintext(e.target.value)}
            placeholder="Enter any text to encrypt..."
            rows={5}
          />

          <button className="btn-encrypt" onClick={handleEncrypt} disabled={!plaintext.trim() || encLoading}>
            {encLoading ? <><Loader size={16} className="spin" /> Encrypting...</> : <><Lock size={16} /> Encrypt</>}
          </button>

          {encResult && (
            <div className="encrypt-result">
              <div className="result-row">
                <span className="result-label">Algorithm</span>
                <span className="result-value highlight">{encResult.algorithm}</span>
              </div>
              <div className="result-row">
                <span className="result-label">Key Size</span>
                <span className="result-value">{encResult.key_size_bits} bits</span>
              </div>
              <div className="result-row">
                <span className="result-label">IV (Base64)</span>
                <span className="result-value">{encResult.iv}</span>
              </div>
              <div className="result-row">
                <span className="result-label">Original Size</span>
                <span className="result-value">{encResult.original_size_bytes} bytes</span>
              </div>
              <div className="result-row">
                <span className="result-label">Encrypted Size</span>
                <span className="result-value">{encResult.encrypted_size_bytes} bytes</span>
              </div>

              <div style={{ marginTop: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span className="result-label">Ciphertext (Base64)</span>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button className="copy-btn" onClick={() => copyToClipboard(encResult.ciphertext, 'Ciphertext')}>
                      <Copy size={11} style={{ display: 'inline', marginRight: '3px' }} /> Copy
                    </button>
                    <button className="copy-btn" onClick={useCipherForDecrypt} style={{ borderColor: '#10b981', color: '#10b981' }}>
                      ↓ Use for Decrypt
                    </button>
                  </div>
                </div>
                <div className="cipher-display">{encResult.ciphertext}</div>
              </div>
            </div>
          )}
        </div>

        {/* Decrypt */}
        <div className="card">
          <div className="panel-title">
            <Unlock size={18} style={{ color: '#10b981' }} />
            Decrypt Text
            <span className="panel-badge badge-decrypt">AES-256-GCM</span>
          </div>

          <textarea
            className="crypto-textarea cipher-textarea"
            value={cipherInput}
            onChange={e => setCipherInput(e.target.value)}
            placeholder="Paste Base64 ciphertext here..."
            rows={5}
          />

          <button className="btn-decrypt" onClick={handleDecrypt} disabled={!cipherInput.trim() || decLoading}>
            {decLoading ? <><Loader size={16} className="spin" /> Decrypting...</> : <><Unlock size={16} /> Decrypt</>}
          </button>

          {decResult && (
            <div className="decrypt-result">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span className="result-label" style={{ color: '#059669' }}>✅ Decrypted Successfully</span>
                <button className="copy-btn" onClick={() => copyToClipboard(decResult.plaintext, 'Plaintext')}>
                  <Copy size={11} style={{ display: 'inline', marginRight: '3px' }} /> Copy
                </button>
              </div>
              <div className="plaintext-display">{decResult.plaintext}</div>
            </div>
          )}
        </div>
      </div>

      {/* How AES-GCM works */}
      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '16px' }}>
          <Shield size={18} style={{ display: 'inline', marginRight: '8px', color: '#6366f1' }} />
          How AES-256-GCM Works in This System
        </h3>
        <div className="steps-grid">
          {[
            { n: '1', title: 'Key Derivation', desc: 'A 256-bit key is derived from the master password using PBKDF2-SHA256 with 100,000 iterations — making brute-force attacks computationally infeasible.' },
            { n: '2', title: 'Random IV', desc: 'A unique 96-bit Initialization Vector (IV) is generated randomly for every encryption operation, ensuring identical plaintexts produce different ciphertexts.' },
            { n: '3', title: 'AES-GCM Encryption', desc: 'The plaintext is encrypted using AES in Galois/Counter Mode. GCM produces both ciphertext and a 128-bit authentication tag simultaneously.' },
            { n: '4', title: 'Authenticated Output', desc: 'The IV + ciphertext + auth tag are packed together and Base64-encoded. During decryption, the auth tag verifies data integrity — any tampering is detected.' },
          ].map(s => (
            <div key={s.n} className="step-card">
              <div className="step-num">{s.n}</div>
              <h4>{s.title}</h4>
              <p>{s.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Where AES is used */}
      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '16px' }}>
          🔐 Where AES-256 is Applied in This System
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
          {[
            { icon: '📄', title: 'Document Storage', desc: 'Uploaded PDFs are encrypted before being stored on disk using AES-256-GCM' },
            { icon: '🔑', title: 'API Key Protection', desc: 'Sensitive API keys (Groq, Gemini) are encrypted in the .env configuration' },
            { icon: '📦', title: 'Generated Documents', desc: 'Output PDF/PPT/Excel files are encrypted during transmission' },
            { icon: '🗄️', title: 'Vector Store', desc: 'Document chunk metadata is encrypted in the local FAISS store' },
            { icon: '🌐', title: 'API Transport', desc: 'All data between frontend and backend is protected by AES encryption' },
            { icon: '🔒', title: 'Session Data', desc: 'User session tokens are signed and encrypted using AES-256' },
          ].map(({ icon, title, desc }) => (
            <div key={title} style={{ background: 'var(--bg)', borderRadius: 'var(--radius)', padding: '14px', border: '1px solid var(--border)' }}>
              <div style={{ fontSize: '1.4rem', marginBottom: '8px' }}>{icon}</div>
              <h4 style={{ fontSize: '.88rem', fontWeight: 700, marginBottom: '4px' }}>{title}</h4>
              <p style={{ fontSize: '.78rem', color: 'var(--text3)', lineHeight: 1.5 }}>{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
