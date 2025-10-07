# Casting Solidification Simulator

A cloud-based casting solidification solver that analyzes thermal hotspots in metal casting processes. This tool simulates the cooling and solidification of molten metal in a part to identify potential defects.

## Features

- **STEP File Import**: Upload CAD models in STEP format
- **Material Selection**: Choose between Aluminum and Steel with realistic thermal properties
- **Adjustable Parameters**: Set pour temperature and ambient conditions
- **Physics-Based Simulation**: Finite element solver with phase change modeling
- **3D Visualization**: Interactive Three.js-based visualization with temperature coloring
- **Time Animation**: Watch the solidification process over time
- **Hotspot Detection**: Automatically identify regions prone to shrinkage defects

## Technology Stack

### Backend
- **Python/Flask**: REST API server
- **Gmsh**: Open-source mesh generator for STEP file processing
- **NumPy/SciPy**: Numerical computation and sparse matrix solving
- **Trimesh**: Geometry processing

### Frontend
- **React**: UI framework
- **Three.js**: 3D visualization via @react-three/fiber
- **Axios**: API communication

## Installation

### Prerequisites
- Python 3.8+ 
- Node.js 16+
- pip and npm

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend
npm install
```

## Running the Application

### Start Backend Server

```bash
cd backend
python app.py
```

The backend will start on `http://localhost:5000`

### Start Frontend Development Server

```bash
cd frontend
npm start
```

The frontend will start on `http://localhost:3000`

## Usage

1. **Upload a STEP File**: Click "Upload STEP File" and select a `.step` or `.stp` file
2. **Select Material**: Choose between Aluminum or Steel
3. **Set Temperature**: Adjust the pour temperature (defaults to recommended values)
4. **Run Simulation**: Click "Run Simulation" to start the analysis
5. **View Results**: 
   - Use the timeline to scrub through time
   - Click play to animate the solidification process
   - Red spheres indicate hotspot locations
   - Color gradient shows temperature distribution

## Physics Model

The simulator solves the transient heat equation with phase change:

```
ρ * c_eff * ∂T/∂t = ∇·(k∇T) + boundary conditions
```

Where:
- **ρ**: Density
- **c_eff**: Effective heat capacity (includes latent heat)
- **k**: Thermal conductivity
- **T**: Temperature

### Material Properties

**Aluminum:**
- Melting Point: 660°C
- Thermal Conductivity: 237 W/(m·K)
- Latent Heat: 397 kJ/kg

**Steel:**
- Melting Point: 1370°C
- Thermal Conductivity: 50 W/(m·K)
- Latent Heat: 247 kJ/kg

## Architecture

```
┌─────────────────┐         ┌──────────────────┐
│   React UI      │◄───────►│   Flask API      │
│   (Frontend)    │  HTTP   │   (Backend)      │
└─────────────────┘         └──────────────────┘
                                      │
                            ┌─────────┴─────────┐
                            │                   │
                      ┌─────▼────┐      ┌──────▼──────┐
                      │   Gmsh   │      │   Solver    │
                      │  Mesher  │      │   (FEM)     │
                      └──────────┘      └─────────────┘
```

## API Endpoints

- `POST /api/upload` - Upload STEP file
- `POST /api/simulate` - Run simulation
- `GET /api/results/<sim_id>` - Get simulation results
- `GET /api/materials` - Get material properties

## Limitations

- Mesh size is limited for performance (adjustable in `mesher.py`)
- Simplified convection boundary conditions
- Linear phase change model (mushy zone approximation)
- Does not account for mold material or complex cooling channels

## Future Enhancements

- Support for custom materials
- Advanced boundary conditions (radiation, complex cooling)
- Defect prediction (shrinkage, porosity)
- Multi-material simulations
- Cloud deployment with job queuing

## License

This project uses open-source tools and libraries. Consult individual library licenses for specific terms.

## Contributing

This is a demonstration project. For production use, consider:
- More sophisticated meshing algorithms
- Parallel computing for large models
- Database storage for simulation history
- User authentication
- Cloud deployment with auto-scaling

## Troubleshooting

**Mesh generation fails:**
- Ensure Gmsh is properly installed
- Check that STEP file is valid
- Falls back to simple cube geometry if import fails

**Simulation is slow:**
- Reduce mesh density in `mesher.py`
- Decrease number of timesteps
- Use smaller geometry

**Frontend not connecting to backend:**
- Ensure backend is running on port 5000
- Check CORS settings if running on different domains

## Credits

Built using:
- [Gmsh](https://gmsh.info/) - 3D finite element mesh generator
- [Three.js](https://threejs.org/) - 3D graphics library
- [Flask](https://flask.palletsprojects.com/) - Python web framework
- [React](https://react.dev/) - UI library

