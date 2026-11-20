import React, { useState } from 'react';
import axios from 'axios';
import './DataInput.css';

const SAMPLE = {
  title: "AI Research Report 2025",
  abstract: "This report presents key findings on AI adoption across industries in 2025.",
  introduction: "Artificial Intelligence is transforming every sector from healthcare to finance.",
  methodology: "We analyzed 100 research papers and surveyed 500 industry professionals.",
  results: "AI adoption grew by 300%. Productivity improved by 45% in early adopters.",
  conclusion: "AI will continue to dominate technology investment through 2030.",
  points: [
    "AI reduces operational costs by 30%",
    "Automated systems save 2 hours per employee daily",
    "Predictive models improve decision accuracy by 60%"
  ],
  tables: [
    { "Industry": "Healthcare", "AI Adoption": "78%", "ROI": "3.2x" },
    { "Industry": "Finance", "AI Adoption": "85%", "ROI": "4.1x" },
    { "Industry": "Education", "AI Adoption": "52%", "ROI": "2.8x" }
  ]
};

function DataInput({ outputFormat, customTemplate, onResult, onLoading, onError }) {
  const [jsonText, setJsonText] = useState('');

  const loadSample = () => {
    setJsonText(JSON.stringify(SAMPLE, null, 2));
  };

  const handleGenerate = async () => {
    if (!jsonText.trim()) {
      onError('Please paste JSON data or click "Load Sample"');
      return;
    }

    let data;
    try {
      data = JSON.parse(jsonText);
    } catch {
      onError('Invalid JSON — please check your syntax');
      return;
    }

    onLoading(true);
    onError(null);

    try {
      const response = await axios.post('/generate/from-data', {
        data,
        output_format: outputFormat,
        template: customTemplate || null,
        use_n8n: false
      }, {
        responseType: 'blob',
        timeout: 60000
      });

      const extMap = { pdf: 'pdf', pptx: 'pptx', xlsx: 'xlsx' };
      const ext = extMap[outputFormat] || outputFormat;
      const title = (data.title || 'document').replace(/\s+/g, '_').slice(0, 40);

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${title}.${ext}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      onResult({ type: 'download', message: `✅ "${title}.${ext}" generated and downloaded!` });
    } catch (err) {
      let msg = 'Generation failed';
      if (err.response) {
        try {
          const text = await err.response.data.text();
          const parsed = JSON.parse(text);
          msg = parsed?.detail?.error?.message || parsed?.detail || `Server error: ${err.response.status}`;
        } catch {
          msg = `Server error: ${err.response.status}`;
        }
      } else {
        msg = err.message;
      }
      onError(msg);
    } finally {
      onLoading(false);
    }
  };

  return (
    <div className="data-input">
      <div className="data-input-header">
        <h3>📋 Paste Structured JSON Data</h3>
        <button className="btn-sample" onClick={loadSample}>Load Sample Data</button>
      </div>
      <p className="hint">Provide your document content as JSON. Click "Load Sample" to see the format.</p>
      <textarea
        value={jsonText}
        onChange={(e) => setJsonText(e.target.value)}
        placeholder={`{\n  "title": "My Document",\n  "abstract": "Summary...",\n  "introduction": "...",\n  "methodology": "...",\n  "results": "...",\n  "conclusion": "...",\n  "points": ["Point 1", "Point 2"]\n}`}
        rows={12}
        spellCheck={false}
      />
      <button
        className="btn-primary"
        onClick={handleGenerate}
        disabled={!jsonText.trim()}
      >
        Generate {outputFormat.toUpperCase()} Document
      </button>
    </div>
  );
}

export default DataInput;
