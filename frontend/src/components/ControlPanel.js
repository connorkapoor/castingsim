import React, { useRef } from 'react';
import './ControlPanel.css';

function ControlPanel({
  materials,
  selectedMaterial,
  setSelectedMaterial,
  temperature,
  setTemperature,
  onFileUpload,
  onRunSimulation,
  isSimulating,
  fileId,
  uploadProgress
}) {
  const fileInputRef = useRef();

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      onFileUpload(file);
    }
  };

  const materialData = materials[selectedMaterial];

  return (
    <div className="control-panel">
      <h2>Simulation Setup</h2>
      
      <div className="control-section">
        <h3>1. Import Part</h3>
        <button 
          className="file-button"
          onClick={() => fileInputRef.current.click()}
          disabled={isSimulating}
        >
{fileId ? 'File Loaded' : 'Upload STEP/STL File'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".step,.stp,.stl"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        {uploadProgress && <div className="upload-progress">{uploadProgress}</div>}
      </div>

      <div className="control-section">
        <h3>2. Material Selection</h3>
        <select 
          value={selectedMaterial} 
          onChange={(e) => setSelectedMaterial(e.target.value)}
          disabled={isSimulating}
        >
          {Object.keys(materials).map(key => (
            <option key={key} value={key}>
              {materials[key].name}
            </option>
          ))}
        </select>
        
        {materialData && (
          <div className="material-info">
            <div className="info-row">
              <span>Melting Point:</span>
              <span>{materialData.melting_point}°C</span>
            </div>
            <div className="info-row">
              <span>Density:</span>
              <span>{materialData.density} kg/m³</span>
            </div>
            <div className="info-row">
              <span>Thermal Cond.:</span>
              <span>{materialData.thermal_conductivity} W/(m·K)</span>
            </div>
          </div>
        )}
      </div>

      <div className="control-section">
        <h3>3. Pour Temperature</h3>
        <div className="temperature-control">
          <input
            type="range"
            min={materialData ? materialData.melting_point : 500}
            max={materialData ? materialData.melting_point + 500 : 2000}
            value={temperature}
            onChange={(e) => setTemperature(Number(e.target.value))}
            disabled={isSimulating}
          />
          <div className="temperature-display">{temperature}°C</div>
        </div>
        <div className="temperature-hint">
          Recommended: {materialData?.default_pour_temp}°C
        </div>
      </div>

      <div className="control-section">
        <h3>4. Run Simulation</h3>
        <button 
          className={`run-button ${isSimulating ? 'simulating' : ''}`}
          onClick={onRunSimulation}
          disabled={!fileId || isSimulating}
        >
{isSimulating ? 'Running Simulation...' : 'Run Simulation'}
        </button>
      </div>

      <div className="info-box">
        <strong>About</strong>
        <p>Professional solidification analysis for metal casting. Identifies thermal hotspots, porosity risk zones, and feeding problems using Niyama criterion.</p>
      </div>
    </div>
  );
}

export default ControlPanel;

