import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import toast from 'react-hot-toast';
import { Search, Send, FileText, BookOpen, Cpu, AlertCircle, Loader, Upload, CheckCircle } from 'lucide-react';
import './QueryPage.css';

const EXAMPLES = [
  'What is this document about?',
  'Summarize the methodology section',
  'What are the key findings?',
  'List the main conclusions',
  'What technologies are used?',
];

export default function QueryPage() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [indexStats, setIndexStats] = useState(null);

  // Check index status on load
  useEffect(() => {
    axios.get('/documents/stats')
      .then(r => setIndexStats(r.data))
      .catch(() => {});
  }, []);

  const handleQuery = async () => {
    if (!query.trim()) return;

    // Warn if nothing indexed
    if (indexStats?.total_chunks === 0) {
      toast('No documents indexed! Upload a PDF first.', { icon: '⚠️', duration: 4000 });
      return;
    }

    setLoading(true); setError(null); setResult(null);

    try {
      const res = await axios.post(
        `/query?query=${encodeURIComponent(query.trim())}&max_results=5`
      );
      setResult(res.data);
      // Refresh stats
      axios.get('/documents/stats').then(r => setIndexStats(r.data)).catch(() => {});
    } catch (err) {
      const detail = err.response?.data?.detail;
      let msg = 'Query failed';
      if (typeof detail === 'string') msg = detail;
      else if (detail?.error?.message) msg = detail.error.message;
      else msg = err.message || 'Query failed';
      setError(msg);
      toast.error('Query failed');
    } finally {
      setLoading(false);
    }
  };

  const isIndexed = indexStats?.total_chunks > 0;

  return (
    <div className="query-page">

      {/* Index status banner */}
      {indexStats !== null && (
        <div className={`index-banner ${isIndexed ? 'indexed' : 'empty'}`}>
          {isIndexed ? (
            <>
              <CheckCircle size={18} />
              <span><strong>{indexStats.total_chunks} chunks</strong> indexed and ready to query</span>
            </>
          ) : (
            <>
              <AlertCircle size={18} />
              <span>No documents indexed yet. <strong>You must upload a PDF first before querying.</strong></span>
              <Link to="/upload" className="banner-link">
                <Upload size={14} /> Upload PDF
              </Link>
            </>
          )}
        </div>
      )}

      {/* Input panel */}
      <div className="card query-card">
        <div className="query-header">
          <Search size={20} className="query-header-icon" />
          <div>
            <h3>Ask Your Documents</h3>
            <p>Uses FAISS + BM25 hybrid search to find relevant content, then generates an answer</p>
          </div>
        </div>

        <div className="query-input-wrap">
          <textarea
            className="query-textarea"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleQuery(); }
            }}
            placeholder={isIndexed
              ? "Ask anything about your uploaded documents..."
              : "Upload a PDF first, then ask questions here..."}
            rows={3}
            disabled={!isIndexed && indexStats !== null}
          />
          <button
            className="query-send-btn"
            onClick={handleQuery}
            disabled={!query.trim() || loading || !isIndexed}
          >
            {loading ? <Loader size={18} className="spin" /> : <Send size={18} />}
          </button>
        </div>

        {isIndexed && (
          <div className="examples-row">
            <span className="examples-label">Try:</span>
            {EXAMPLES.map(ex => (
              <button key={ex} className="example-chip" onClick={() => setQuery(ex)}>
                {ex}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="card loading-card">
          <Loader size={24} className="spin" style={{ color: 'var(--primary)' }} />
          <div>
            <h4>Searching documents...</h4>
            <p>Running hybrid FAISS + BM25 search and generating answer</p>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card error-card">
          <AlertCircle size={20} />
          <div><h4>Error</h4><p>{error}</p></div>
        </div>
      )}

      {/* Result */}
      {result && !loading && (
        <div className="result-grid">
          {/* Answer */}
          <div className="card answer-card">
            <div className="answer-header">
              <Cpu size={18} />
              <h3>Answer</h3>
              <span className="model-badge">{result.model || 'extractive'}</span>
              <span className="conf-badge">
                {Math.round((result.confidence_score || 0) * 100)}% confidence
              </span>
            </div>
            <div className="answer-text">{result.answer}</div>
            {result.processing_time_ms && (
              <div className="answer-meta">Generated in {result.processing_time_ms}ms</div>
            )}
          </div>

          {/* Sources */}
          {result.sources?.length > 0 && (
            <div className="card sources-card">
              <div className="sources-header">
                <BookOpen size={18} />
                <h3>Sources ({result.sources.length})</h3>
              </div>
              <div className="sources-list">
                {result.sources.map((src, i) => (
                  <div key={i} className="source-item">
                    <div className="source-top">
                      <FileText size={14} />
                      <span className="source-name">{src.document_name}</span>
                      <span className="source-page">Page {src.page_number}</span>
                      <span className="source-score">
                        {Math.round((src.relevance_score || 0) * 100)}%
                      </span>
                    </div>
                    <p className="source-excerpt">
                      "{src.text_excerpt?.slice(0, 250)}..."
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
