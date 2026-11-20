import React from 'react';
import './ResultDisplay.css';

function ResultDisplay({ result }) {
  if (!result) return null;

  if (result.type === 'download') {
    return (
      <div className="result-display success">
        <h3>✅ Success!</h3>
        <p>{result.message}</p>
      </div>
    );
  }

  if (result.type === 'n8n') {
    return (
      <div className="result-display n8n">
        <h3>🔄 n8n Workflow Triggered</h3>
        <div className="result-details">
          <p><strong>Status:</strong> {result.data.n8n_success ? '✅ Success' : '❌ Failed'}</p>
          {result.data.execution_id && (
            <p><strong>Execution ID:</strong> <code>{result.data.execution_id}</code></p>
          )}
          <p><strong>Message:</strong> {result.data.message}</p>
        </div>
        {result.data.structured_data && (
          <details className="structured-data">
            <summary>View Structured Data</summary>
            <pre>{JSON.stringify(result.data.structured_data, null, 2)}</pre>
          </details>
        )}
      </div>
    );
  }

  return null;
}

export default ResultDisplay;
