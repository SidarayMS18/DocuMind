import React, { useState } from 'react';
import axios from 'axios';
import './QueryInput.css';

function QueryInput({ outputFormat, customTemplate, useN8n, onResult, onLoading, onError }) {
  const [query, setQuery] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    onLoading(true);
    onError(null);

    try {
      const response = await axios.post('/generate/from-query', {
        query: query,
        output_format: outputFormat,
        template: customTemplate || null,
        use_n8n: useN8n,
        max_results: 5
      }, {
        responseType: useN8n ? 'json' : 'blob'
      });

      if (useN8n) {
        onResult({ type: 'n8n', data: response.data });
      } else {
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `document.${outputFormat}`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        onResult({ type: 'download', message: 'Document downloaded successfully!' });
      }
    } catch (err) {
      onError(err.response?.data?.detail?.message || err.message || 'Generation failed');
    } finally {
      onLoading(false);
    }
  };

  return (
    <div className="query-input">
      <h3>🔍 Ask a Question About Your Documents</h3>
      <form onSubmit={handleSubmit}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g., Summarize the methodology section from the research papers..."
          rows={4}
        />
        <button type="submit" className="btn-primary" disabled={!query.trim()}>
          Generate Document
        </button>
      </form>
    </div>
  );
}

export default QueryInput;
