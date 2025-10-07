import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import Viewer3D from './components/Viewer3D';
import ControlPanel from './components/ControlPanel';
import Timeline from './components/Timeline';

const API_BASE = '/api';

function App() {
  const [fileId, setFileId] = useState(null);
  const [uploadedGeometry, setUploadedGeometry] = useState(null);
  const [results, setResults] = useState(null);
  const [materials, setMaterials] = useState({});
  const [selectedMaterial, setSelectedMaterial] = useState('aluminum');
  const [temperature, setTemperature] = useState(700);
  const [currentTimestep, setCurrentTimestep] = useState(0);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);

  // Load available materials
  useEffect(() => {
    axios.get(`${API_BASE}/materials`)
      .then(response => {
        setMaterials(response.data);
      })
      .catch(error => {
        console.error('Error loading materials:', error);
      });
  }, []);

  // Update default temperature when material changes
  useEffect(() => {
    if (materials[selectedMaterial]) {
      setTemperature(materials[selectedMaterial].default_pour_temp);
    }
  }, [selectedMaterial, materials]);

  const handleFileUpload = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    
    setUploadProgress('Uploading...');
    
    try {
      const response = await axios.post(`${API_BASE}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      setFileId(response.data.file_id);
      setUploadedGeometry(response.data.geometry);
      setUploadProgress(null);
    } catch (error) {
      console.error('Upload error:', error);
      setUploadProgress(null);
      alert('Error uploading file: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleRunSimulation = async () => {
    if (!fileId) {
      alert('Please upload a file first');
      return;
    }
    
    setIsSimulating(true);
    setResults(null);
    setCurrentTimestep(0);
    
    // Try streaming first
    const streamUrl = `${API_BASE}/simulate_stream?` + new URLSearchParams({
      file_id: fileId,
      material: selectedMaterial,
      initial_temperature: temperature.toString(),
      ambient_temperature: '25'
    });
    
    try {
      const eventSource = new EventSource(streamUrl);
      let streamedResults = { timesteps: [], mesh: null };
      let hasReceivedData = false;
      
      eventSource.onmessage = (event) => {
        hasReceivedData = true;
        const update = JSON.parse(event.data);
        console.log('SSE received:', update.type, update);
        
        if (update.type === 'mesh') {
          console.log('✓ Streaming mesh - has', update.mesh.nodes.length, 'nodes');
          streamedResults.mesh = update.mesh;
          // Render the mesh immediately even before first timestep
          setResults({ timesteps: [], mesh: update.mesh });
        } else if (update.type === 'init') {
          console.log('✓ Streaming init:', update);
        } else if (update.type === 'timestep') {
          console.log(`✓ Streaming frame ${update.step}/${update.progress}% - T_avg=${update.data.temperature ? (update.data.temperature.reduce((a,b)=>a+b)/update.data.temperature.length).toFixed(1) : '?'}°C`);
          streamedResults.timesteps.push(update.data);
          // Update visualization LIVE!
          const liveResults = {
            ...streamedResults,
            material: selectedMaterial,
            defect_analysis: { hotspots: [], porosity_zones: [], feeding_issues: [], shrinkage_estimate: null },
            summary: { num_timesteps: streamedResults.timesteps.length }
          };
          setResults(liveResults);
          setCurrentTimestep(streamedResults.timesteps.length - 1);
        } else if (update.type === 'complete') {
          console.log('✓ Streaming complete - final results');
          setResults(update.data);
          setCurrentTimestep(0);
          setIsSimulating(false);
          eventSource.close();
        } else if (update.type === 'error') {
          console.error('✗ Streaming error:', update.error);
          alert('Simulation error: ' + update.error);
          setIsSimulating(false);
          eventSource.close();
        }
      };
      
      eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        eventSource.close();
        
        if (!hasReceivedData) {
          // SSE not supported, fallback to batch API
          console.log('Falling back to batch API');
          axios.post(`${API_BASE}/simulate`, {
            file_id: fileId,
            material: selectedMaterial,
            initial_temperature: temperature,
            ambient_temperature: 25
          }).then(response => {
            return axios.get(`${API_BASE}/results/${response.data.simulation_id}`);
          }).then(resultsResponse => {
            setResults(resultsResponse.data);
            setCurrentTimestep(0);
            setIsSimulating(false);
            if (resultsResponse.data.summary?.warning) {
              alert('⚠️ Geometry Warning:\n\n' + resultsResponse.data.summary.warning);
            }
          }).catch(err => {
            console.error('Batch simulation error:', err);
            setIsSimulating(false);
            alert('Error: ' + (err.response?.data?.error || err.message));
          });
        } else {
          setIsSimulating(false);
        }
      };
      
      // Timeout after 5 minutes
      setTimeout(() => {
        if (eventSource.readyState !== EventSource.CLOSED) {
          eventSource.close();
          setIsSimulating(false);
          alert('Simulation timeout');
        }
      }, 300000);
      
    } catch (error) {
      console.error('Simulation error:', error);
      setIsSimulating(false);
      alert('Error: ' + (error.response?.data?.error || error.message));
    }
  };

  // Auto-play animation
  useEffect(() => {
    if (!isPlaying || !results) return;
    
    const interval = setInterval(() => {
      setCurrentTimestep(prev => {
        if (prev >= results.timesteps.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 200); // 200ms per frame
    
    return () => clearInterval(interval);
  }, [isPlaying, results]);

  const handlePlayPause = () => {
    if (currentTimestep >= results?.timesteps.length - 1) {
      setCurrentTimestep(0);
    }
    setIsPlaying(!isPlaying);
  };

  const currentData = results?.timesteps[currentTimestep];

  return (
    <div className="App">
      <header className="App-header">
        <h1>Casting Solidification Simulator</h1>
        <p>Engineering Analysis for Metal Casting Processes</p>
      </header>
      
      <div className="App-content">
        <ControlPanel
          materials={materials}
          selectedMaterial={selectedMaterial}
          setSelectedMaterial={setSelectedMaterial}
          temperature={temperature}
          setTemperature={setTemperature}
          onFileUpload={handleFileUpload}
          onRunSimulation={handleRunSimulation}
          isSimulating={isSimulating}
          fileId={fileId}
          uploadProgress={uploadProgress}
        />
        
        <div className="viewer-container">
          {results ? (
            // Show simulation results
            <>
              <Viewer3D
                mesh={results.mesh}
                temperatureData={currentData?.temperature}
                hotspotNodes={currentData?.hotspot_nodes}
                porosityNodes={currentData?.porosity_nodes}
                material={materials[selectedMaterial]}
              />
              
              <Timeline
                timesteps={results.timesteps}
                currentTimestep={currentTimestep}
                setCurrentTimestep={setCurrentTimestep}
                isPlaying={isPlaying}
                onPlayPause={handlePlayPause}
              />
              
              <div className="stats-panel">
                <h3>Analysis (t = {currentData?.time.toFixed(1)} min)</h3>
                
                <div className="stat-section">
                  <h4>Temperature</h4>
                  <div className="stat-item">
                    <span>Average:</span>
                    <span>{currentData?.statistics.avg_temp.toFixed(1)}°C</span>
                  </div>
                  <div className="stat-item">
                    <span>Max:</span>
                    <span>{currentData?.statistics.max_temp.toFixed(1)}°C</span>
                  </div>
                  <div className="stat-item">
                    <span>Min:</span>
                    <span>{currentData?.statistics.min_temp.toFixed(1)}°C</span>
                  </div>
                </div>
                
                <div className="stat-section">
                  <h4>Phase Distribution</h4>
                  <div className="stat-item">
                    <span>Liquid:</span>
                    <span>{currentData?.phase_distribution?.liquid || 0}</span>
                  </div>
                  <div className="stat-item">
                    <span>Mushy:</span>
                    <span>{currentData?.phase_distribution?.mushy || 0}</span>
                  </div>
                  <div className="stat-item">
                    <span>Solid:</span>
                    <span>{currentData?.phase_distribution?.solid || 0}</span>
                  </div>
                </div>
                
                <div className="stat-section">
                  <h4>Defect Prediction</h4>
                  <div className="stat-item">
                    <span>Hotspots:</span>
                    <span className={currentData?.statistics.hotspot_count > 0 ? 'warning' : ''}>
                      {currentData?.statistics.hotspot_count || 0}
                    </span>
                  </div>
                  <div className="stat-item">
                    <span>Porosity Risk:</span>
                    <span className={currentData?.statistics.porosity_risk_nodes > 0 ? 'warning' : ''}>
                      {currentData?.statistics.porosity_risk_nodes || 0}
                    </span>
                  </div>
                </div>
                
                {results?.defect_analysis && (
                  <div className="stat-section">
                    <h4>Final Defects</h4>
                    <div className="stat-item">
                      <span>Shrinkage Zones:</span>
                      <span className="error">{results.defect_analysis.porosity_zones.length}</span>
                    </div>
                    <div className="stat-item">
                      <span>Feeding Issues:</span>
                      <span className="error">{results.defect_analysis.feeding_issues.length}</span>
                    </div>
                    <div className="stat-item">
                      <span>Volume Shrinkage:</span>
                      <span>{results.defect_analysis.shrinkage_estimate?.shrinkage_percentage.toFixed(2)}%</span>
                    </div>
                    <p style={{fontSize: '0.65rem', color: '#6c757d', marginTop: '0.5rem', lineHeight: '1.3', fontStyle: 'italic'}}>
                      Metal contracts {results.defect_analysis.shrinkage_estimate?.shrinkage_percentage.toFixed(1)}% by volume as it solidifies (liquid→solid phase change).
                    </p>
                  </div>
                )}
              </div>
            </>
          ) : uploadedGeometry ? (
            // Show uploaded part preview
            <div className="preview-container">
              <div className="preview-info">
                <h3>Part Loaded</h3>
                <p>Volume: {uploadedGeometry.volume?.toFixed(0)} mm³</p>
                <p>Ready for simulation</p>
              </div>
            </div>
          ) : (
            <div className="placeholder">
              <div className="placeholder-content">
                {isSimulating ? (
                  <>
                    <div className="spinner"></div>
                    <h2>Running Simulation</h2>
                    <p>Calculating thermal analysis...</p>
                  </>
                ) : (
                  <>
                    <h2>Upload Part File</h2>
                    <p>Supported formats: STEP, STL</p>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;

