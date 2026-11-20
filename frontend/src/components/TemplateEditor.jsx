import React, { useState } from 'react';
import axios from 'axios';
import './TemplateEditor.css';

function TemplateEditor({ value, onChange, format }) {
  const [showEditor, setShowEditor] = useState(false);
  const [loading, setLoading] = useState(false);

  const loadDefaultTemplate = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`/template/default/${format}`);
      const template = typeof response.data.template === 'string' 
        ? response.data.template 
        : JSON.stringify(response.data.template, null, 2);
      onChange(template);
    } catch (err) {
      console.error('Failed to load default template:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="template-editor">
      <div className="template-header">
        <h4>Custom Template (Optional)</h4>
        <div className="template-actions">
          <button onClick={loadDefaultTemplate} disabled={loading}>
            {loading ? 'Loading...' : 'Load Default'}
          </button>
          <button onClick={() => setShowEditor(!showEditor)}>
            {showEditor ? 'Hide' : 'Show'} Editor
          </button>
        </div>
      </div>
      
      {showEditor && (
        <div className="editor-container">
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Use {{placeholders}} like {{title}}, {{abstract}}, {{methodology}}, etc."
            rows={12}
          />
          <div className="template-help">
            <p><strong>Available placeholders:</strong></p>
            <code>
              {`{{title}} {{abstract}} {{introduction}} {{methodology}} {{results}} {{conclusion}} {{points}} {{tables}}`}
            </code>
          </div>
        </div>
      )}
    </div>
  );
}

export default TemplateEditor;
