import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import './FileUpload.css';

function FileUpload({ outputFormat, customTemplate, onResult, onLoading, onError }) {
  const [file, setFile] = useState(null);

  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      onError(null); // clear previous errors
    }
  }, [onError]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1
  });

  const handleUpload = async () => {
    if (!file) return;

    onLoading(true);
    onError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('output_format', outputFormat);
    // NOTE: do NOT send template_file unless user explicitly provided one
    // n8n is NOT sent here — upload endpoint handles generation directly

    try {
      const response = await axios.post('/generate/upload-and-generate', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob',
        timeout: 60000
      });

      // Determine file extension
      const extMap = { pdf: 'pdf', pptx: 'pptx', xlsx: 'xlsx' };
      const ext = extMap[outputFormat] || outputFormat;
      const baseName = file.name.replace('.pdf', '');

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${baseName}.${ext}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      onResult({ type: 'download', message: `✅ "${baseName}.${ext}" generated and downloaded!` });
    } catch (err) {
      let msg = 'Generation failed';
      if (err.response) {
        // Try to parse blob error response
        try {
          const text = await err.response.data.text();
          const parsed = JSON.parse(text);
          msg = parsed?.detail?.error?.message || parsed?.detail || msg;
        } catch {
          msg = `Server error: ${err.response.status}`;
        }
      } else if (err.message) {
        msg = err.message;
      }
      onError(msg);
    } finally {
      onLoading(false);
    }
  };

  return (
    <div className="file-upload">
      <h3>📄 Upload PDF Document</h3>
      <p className="hint">Upload any PDF — the system will extract content and convert it to your chosen format.</p>
      <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
        <input {...getInputProps()} />
        {file ? (
          <div className="file-info">
            <p>✅ {file.name}</p>
            <p className="file-size">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
        ) : (
          <div>
            <p style={{fontSize:'1.5rem', marginBottom:'0.5rem'}}>📂</p>
            <p>{isDragActive ? 'Drop the PDF here...' : 'Drag & drop a PDF, or click to select'}</p>
          </div>
        )}
      </div>
      {file && (
        <button onClick={handleUpload} className="btn-primary">
          Process & Generate {outputFormat.toUpperCase()}
        </button>
      )}
    </div>
  );
}

export default FileUpload;
