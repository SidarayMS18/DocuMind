import React from 'react';
import './FormatSelector.css';

function FormatSelector({ selected, onChange }) {
  const formats = [
    { value: 'pdf', label: 'PDF', icon: '📄' },
    { value: 'pptx', label: 'PowerPoint', icon: '📊' },
    { value: 'xlsx', label: 'Excel', icon: '📈' }
  ];

  return (
    <div className="format-selector">
      <h4>Output Format</h4>
      <div className="format-options">
        {formats.map(fmt => (
          <button
            key={fmt.value}
            className={selected === fmt.value ? 'active' : ''}
            onClick={() => onChange(fmt.value)}
          >
            <span className="icon">{fmt.icon}</span>
            <span>{fmt.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default FormatSelector;
