# Casting Simulation Workflow Documentation

## System Overview

This application simulates solidification in metal casting using finite element analysis. The workflow has been implemented exactly as specified:

## Workflow Steps

### 1. User Uploads STEP File
- User uploads a STEP CAD file through the web interface
- File is validated (must be .step or .stp format)

### 2. Surface Mesh Generation
- STEP file is imported using GMSH
- Adaptive surface tessellation is performed
- Result: High-quality triangulated surface mesh (STL)
- **Purpose**: Clean visualization of the original part geometry

### 3. Voxel Mesh Generation
- Surface mesh is used to compute signed distance field
- Regular 3D grid is created over bounding box
- Hexahedral voxels are generated for nodes inside the part
- Hexes are decomposed into tetrahedra for FEM simulation
- **Purpose**: Robust volumetric mesh for simulation

### 4. Dual Mesh Display (Side-by-Side)
The frontend displays **both meshes simultaneously**:

#### Left Panel: Surface Mesh
- Shows original CAD geometry
- Clean, smooth representation
- ~57K vertices, ~115K triangles (for typical parts)
- Displays in **gray** (no temperature data mapped)

#### Right Panel: Voxel Mesh  
- Shows volumetric simulation mesh
- ~608K vertices, ~97K hexes (for typical parts)
- Displays **temperature colors** during simulation
- Color gradient: Blue (cold) → Cyan → Green → Yellow → Orange → Red (hot)

### 5. Simulation Execution
- Runs on the **voxel mesh nodes**
- Uses Professional Solidification Solver with:
  - Implicit time integration
  - Phase change via enthalpy method
  - Heat transfer with boundary conditions
  - Niyama criterion for porosity prediction
- Streams results in real-time to frontend

### 6. Results Visualization
- **Voxel Mesh**: Shows temperature distribution overlayed on mesh
- **Surface Mesh**: Shows geometry only (gray, for reference)
- Timeline slider allows scrubbing through simulation timesteps
- Play/pause animation controls
- Real-time statistics panel showing:
  - Temperature (avg, min, max)
  - Phase distribution (liquid, mushy, solid)
  - Defect indicators (hotspots, porosity risk)

## Technical Architecture

### Backend (`/backend`)
- **Framework**: Flask with CORS
- **API Endpoints**:
  - `POST /api/upload` - Upload STEP file, generate meshes
  - `GET /api/simulate` - Run simulation (Server-Sent Events streaming)
  - `GET /api/materials` - Get available materials

#### Key Modules (`/backend/simulation/`)
1. **`mesher.py`** - Mesh generation
   - `step_to_stl()` - STEP → Surface mesh
   - `voxelize_stl_to_hex()` - Surface → Voxel mesh
   - `generate_hex_mesh_from_step()` - Complete pipeline
   - Returns both surface_mesh and voxel_mesh

2. **`fenics_solver.py`** - FEM simulation
   - `ProfessionalSolidificationSolver` - Main solver class
   - Runs on voxel mesh nodes
   - Returns temperature field at each timestep

### Frontend (`/frontend`)
- **Framework**: React with Three.js/React Three Fiber
- **Components**:
  - `App.js` - Main application, state management
  - `Viewer3D.js` - 3D mesh rendering with temperature colors
  - `ControlPanel.js` - Material selection, upload, simulation controls
  - `Timeline.js` - Animation timeline and playback controls

#### Dual Viewer Layout
```javascript
<div className="dual-viewer-container">
  <div className="viewer-panel">
    <div className="viewer-label">Surface Mesh</div>
    <Viewer3D mesh={results.mesh.surface_mesh} ... />
  </div>
  
  <div className="viewer-panel">
    <div className="viewer-label">Voxel Mesh</div>
    <Viewer3D mesh={results.mesh.voxel_mesh} ... />
  </div>
</div>
```

## Data Flow

```
STEP File
    ↓
[mesher.py]
    ├─→ Surface Mesh (STL) ──→ Frontend Left Panel (geometry only)
    └─→ Voxel Mesh (Hex) ────→ Frontend Right Panel (with temperatures)
            ↓
    [fenics_solver.py]
            ↓
    Temperature Field (per voxel node)
            ↓
    Frontend (overlay on voxel mesh)
```

## Mesh Data Structure

### Returned from `generate_mesh()`:
```python
{
    'nodes': [...],              # Voxel nodes (for simulation)
    'elements': [...],           # Tetrahedral elements
    'boundary_nodes': [...],     # Surface node indices
    'surface_triangles': [...],  # (legacy, for compatibility)
    
    'surface_mesh': {
        'nodes': [...],          # STL vertices
        'triangles': [...]       # STL faces
    },
    
    'voxel_mesh': {
        'nodes': [...],          # Voxel grid vertices
        'triangles': [...],      # Voxel surface faces
        'hexes': [...]           # Hexahedral elements
    }
}
```

## Temperature Data Mapping

- **Simulation**: Runs on voxel_mesh nodes (608K nodes)
- **Temperature Array**: Length matches voxel nodes
- **Voxel Viewer**: Temperatures map 1:1 to mesh vertices ✅
- **Surface Viewer**: No matching temperatures (shows gray) ✅

> **Note**: Surface and voxel meshes have different node sets. Currently, temperatures are only displayed on the voxel mesh. Future enhancement could add interpolation to map temperatures to surface mesh nodes.

## Materials Supported

### Aluminum (A356)
- Liquidus: 615°C
- Solidus: 555°C
- Default pour temp: 700°C
- Good for: General casting

### Steel (Carbon Steel)
- Liquidus: 1495°C
- Solidus: 1450°C
- Default pour temp: 1550°C
- Good for: High-temperature applications

## Current Status

✅ **Implemented & Working**:
1. STEP file upload and meshing
2. Dual mesh generation (surface + voxel)
3. Side-by-side visualization
4. Simulation on voxel mesh
5. Real-time result streaming
6. Temperature visualization on voxel mesh
7. Timeline animation controls
8. Statistics and defect detection

⚠️ **Known Limitations**:
- Surface mesh shows gray (no temperature mapping)
- Simulation requires solid STEP geometry (not just surfaces)
- Large meshes (>1M nodes) may be slow

## Running the Application

### Backend:
```bash
cd backend
source venv/bin/activate
python app.py
```
Server runs on `http://localhost:5001`

### Frontend:
```bash
cd frontend
npm start
```
UI opens at `http://localhost:3000`

## Testing

The system has been validated with integration tests:
- Mesh generation: ✅ Pass
- Dual mesh structure: ✅ Pass  
- Simulation initialization: ✅ Pass
- Temperature data mapping: ✅ Pass

## File Structure (Simplified)

```
CastingSim/
├── backend/
│   ├── app.py                    # Flask API server
│   ├── simulation/
│   │   ├── mesher.py             # Mesh generation (STEP→Surface→Voxel)
│   │   └── fenics_solver.py     # FEM solidification solver
│   ├── uploads/                  # Uploaded STEP files
│   └── venv/                     # Python virtual environment
│
├── frontend/
│   ├── src/
│   │   ├── App.js                # Main React app
│   │   ├── App.css               # Styling inc. dual-viewer layout
│   │   └── components/
│   │       ├── Viewer3D.js       # 3D mesh renderer
│   │       ├── ControlPanel.js   # UI controls
│   │       └── Timeline.js       # Animation timeline
│   └── package.json
│
└── README.md
```

## Dependencies

### Backend:
- Flask, Flask-CORS
- NumPy, SciPy
- GMSH (CAD import, meshing)
- PyVista (visualization, voxelization)
- meshio (mesh I/O)
- trimesh (STL processing)

### Frontend:
- React
- Three.js, @react-three/fiber, @react-three/drei
- axios (API calls)

---

**Last Updated**: October 7, 2025
**System Version**: 2.0 (Dual Mesh Implementation)

