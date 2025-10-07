import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Viewer3D from './components/Viewer3D';
import ControlPanel from './components/ControlPanel';
import Timeline from './components/Timeline';
import './App.css';

const API_BASE = 'http://localhost:5001/api';

function App() {
  // State
  const [materials, setMaterials] = useState({});
  const [selectedMaterial, setSelectedMaterial] = useState('aluminum');
  const [temperature, setTemperature] = useState(700);
  const [fileId, setFileId] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [results, setResults] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [currentTimestep, setCurrentTimestep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [simulationProgress, setSimulationProgress] = useState(null);
  
  // Load materials
  useEffect(() => {
    axios.get(`${API_BASE}/materials`)
      .then(response => {
        setMaterials(response.data);
      })
      .catch(error => {
        console.error('Error loading materials:', error);
      });
  }, []);
  
  // Update temperature when material changes
  useEffect(() => {
    if (materials[selectedMaterial]) {
      setTemperature(materials[selectedMaterial].default_pour_temp);
    }
  }, [selectedMaterial, materials]);
  
  // Handle file upload
  const handleFileUpload = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    
    setUploadProgress('Uploading and meshing...');
    
    try {
      const response = await axios.post(`${API_BASE}/upload`, formData);
      
      setFileId(response.data.file_id);
      
      // Set mesh immediately for visualization
      if (response.data.mesh) {
        console.log('Mesh received:', {
          nodes: response.data.mesh.nodes.length,
          elements: response.data.mesh.elements?.length,
          surfaceTriangles: response.data.mesh.surface_triangles?.length
        });
        
        setResults({
          timesteps: [],
          mesh: response.data.mesh
        });
      }
      
      setUploadProgress(null);
    } catch (error) {
      console.error('Upload error:', error);
      setUploadProgress(null);
      alert('Error: ' + (error.response?.data?.error || error.message));
    }
  };
  
  // Handle simulation
  const handleRunSimulation = async () => {
    if (!fileId) {
      alert('Please upload a file first');
      return;
    }
    
    setIsSimulating(true);
    setCurrentTimestep(0);
    setSimulationProgress({ status: 'Starting...', progress: 0 });
    
    const url = `${API_BASE}/simulate?` + new URLSearchParams({
      file_id: fileId,
      material: selectedMaterial,
      initial_temperature: temperature.toString(),
      ambient_temperature: '25'
    });
    
    try {
      const eventSource = new EventSource(url);
      let streamedResults = { timesteps: [], mesh: null };
      
      eventSource.onmessage = (event) => {
        const update = JSON.parse(event.data);
        console.log('SSE:', update.type);
        
        if (update.type === 'mesh') {
          streamedResults.mesh = update.mesh;
          setResults({ timesteps: [], mesh: update.mesh });
          setSimulationProgress({ status: 'Mesh loaded', progress: 5 });
        } else if (update.type === 'timestep') {
          streamedResults.timesteps.push(update.data);
          setResults({ ...streamedResults });
          setCurrentTimestep(streamedResults.timesteps.length - 1);
          
          const progress = Math.min(95, 10 + streamedResults.timesteps.length);
          setSimulationProgress({ 
            status: `Computing (${streamedResults.timesteps.length} frames)...`,
            progress 
          });
        } else if (update.type === 'complete') {
          streamedResults = update.data;
          setResults(streamedResults);
          setSimulationProgress({ status: 'Complete!', progress: 100 });
          eventSource.close();
          setIsSimulating(false);
        } else if (update.type === 'error') {
          console.error('Simulation error:', update.error);
          alert('Simulation error: ' + update.error);
          eventSource.close();
          setIsSimulating(false);
          setSimulationProgress(null);
        }
      };
      
      eventSource.onerror = (error) => {
        console.error('EventSource error:', error);
        eventSource.close();
        setIsSimulating(false);
        setSimulationProgress(null);
      };
      
    } catch (error) {
      console.error('Simulation error:', error);
      alert('Error starting simulation: ' + error.message);
      setIsSimulating(false);
      setSimulationProgress(null);
    }
  };
  
  // Play/pause animation
  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
  };
  
  // Animation loop
  useEffect(() => {
    if (isPlaying && results && results.timesteps.length > 0) {
      const interval = setInterval(() => {
        setCurrentTimestep(prev => {
          if (prev >= results.timesteps.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 100);  // 10 FPS
      
      return () => clearInterval(interval);
    }
  }, [isPlaying, results]);
  
  // Get current timestep data
  const currentData = results?.timesteps[currentTimestep];
  
  return (
    <div className="app">
      <header className="app-header">
        <h1>Casting Solidification Simulator</h1>
        <p>Professional casting analysis with thermal gradients and defect prediction</p>
      </header>
      
      <div className="app-content">
        <div className="sidebar">
          <ControlPanel
            materials={materials}
            selectedMaterial={selectedMaterial}
            setSelectedMaterial={setSelectedMaterial}
            temperature={temperature}
            setTemperature={setTemperature}
            onFileUpload={handleFileUpload}
            onRunSimulation={handleRunSimulation}
            isSimulating={isSimulating}
            uploadProgress={uploadProgress}
            fileId={fileId}
          />
          
          {simulationProgress && (
            <div className="simulation-progress">
              <div>{simulationProgress.status}</div>
              <div className="progress-bar">
                <div 
                  className="progress-fill" 
                  style={{ width: `${simulationProgress.progress}%` }}
                />
              </div>
            </div>
          )}
          
          {results && currentData && (
            <div className="stats-panel">
              <h3>Analysis (t = {currentData.time.toFixed(1)} min)</h3>
              
              <div className="stat-section">
                <h4>Temperature</h4>
                <div className="stat-item">
                  <span>Average:</span>
                  <span>{currentData.statistics.avg_temp.toFixed(1)}°C</span>
                </div>
                <div className="stat-item">
                  <span>Max:</span>
                  <span>{currentData.statistics.max_temp.toFixed(1)}°C</span>
                </div>
                <div className="stat-item">
                  <span>Min:</span>
                  <span>{currentData.statistics.min_temp.toFixed(1)}°C</span>
                </div>
              </div>
              
              <div className="stat-section">
                <h4>Phase Distribution</h4>
                <div className="stat-item">
                  <span>Liquid:</span>
                  <span>{currentData.phase_distribution.liquid}</span>
                </div>
                <div className="stat-item">
                  <span>Mushy:</span>
                  <span>{currentData.phase_distribution.mushy}</span>
                </div>
                <div className="stat-item">
                  <span>Solid:</span>
                  <span>{currentData.phase_distribution.solid}</span>
                </div>
              </div>
              
              <div className="stat-section">
                <h4>Defect Indicators</h4>
                <div className="stat-item">
                  <span>Hotspots:</span>
                  <span>{currentData.statistics.hotspot_count}</span>
                </div>
                <div className="stat-item">
                  <span>Porosity Risk:</span>
                  <span>{currentData.statistics.porosity_risk_nodes}</span>
                </div>
              </div>
            </div>
          )}
        </div>
        
        <div className="main-view">
          {!results?.mesh && (
            <div className="placeholder">
              <div className="placeholder-content">
                <h2>No Geometry Loaded</h2>
                <p>Upload a STEP file to begin</p>
              </div>
            </div>
          )}
          
          {results?.mesh && (
            <div className="dual-viewer-container">
              <div className="viewer-panel">
                <div className="viewer-label">Surface Mesh</div>
                <Viewer3D
                  mesh={results.mesh.surface_mesh}
                  temperatureData={currentData?.temperature}
                  material={selectedMaterial}
                />
              </div>
              
              <div className="viewer-panel">
                <div className="viewer-label">Voxel Mesh</div>
                <Viewer3D
                  mesh={results.mesh.voxel_mesh}
                  temperatureData={currentData?.temperature}
                  material={selectedMaterial}
                  isVoxelMesh={true}
                />
              </div>
            </div>
          )}
          
          {results && results.timesteps.length > 0 && (
            <Timeline
              timesteps={results.timesteps}
              currentTimestep={currentTimestep}
              setCurrentTimestep={setCurrentTimestep}
              isPlaying={isPlaying}
              onPlayPause={handlePlayPause}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default App;

