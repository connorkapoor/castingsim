# Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Install Dependencies

**Backend (Python):**
```bash
cd backend
pip install -r requirements.txt
cd ..
```

**Frontend (Node.js):**
```bash
cd frontend
npm install
cd ..
```

### Step 2: Start the Application

**Option A - Using the startup script (Mac/Linux):**
```bash
./start.sh
```

**Option B - Manual startup:**

Terminal 1 (Backend):
```bash
cd backend
python app.py
```

Terminal 2 (Frontend):
```bash
cd frontend
npm start
```

### Step 3: Access the Application

Open your browser and navigate to:
```
http://localhost:3000
```

### Step 4: Run Your First Simulation

1. Click **"Upload STEP File"** and select a `.step` or `.stp` file
   - Don't have a STEP file? The system will use a fallback geometry
2. Select a **Material** (Aluminum or Steel)
3. Adjust the **Pour Temperature** using the slider
4. Click **"Run Simulation"**
5. Watch the solidification animation and explore hotspots!

## 🐳 Docker Alternative

If you prefer Docker:

```bash
docker-compose up
```

Then access at `http://localhost:3000`

## 🧪 Testing Without a STEP File

The simulator includes a fallback mode that generates a simple cube geometry if STEP import fails. This is useful for:
- Testing the simulation engine
- Verifying installation
- Quick demonstrations

Simply upload any file or let the import fail, and the system will automatically generate a test geometry.

## 📊 Understanding the Results

- **Color Gradient**: Blue (cold) → Red (hot)
- **Red Spheres**: Hotspot locations (potential defects)
- **Timeline**: Scrub through simulation time or press play
- **Statistics Panel**: Real-time temperature metrics

## ⚙️ Adjusting Simulation Parameters

Edit `backend/simulation/solver.py`:
- `total_time`: Simulation duration (seconds)
- `dt`: Time step size (seconds)
- `save_interval`: How often to save frames

Edit `backend/simulation/mesher.py`:
- `mesh_size`: Element size (smaller = more accurate but slower)

## 🔧 Troubleshooting

**Problem**: Can't import STEP files
- **Solution**: Ensure Gmsh is installed. System will fall back to cube geometry.

**Problem**: Simulation is too slow
- **Solution**: Increase `mesh_size` in `mesher.py` or reduce geometry complexity

**Problem**: Port 3000 or 5000 already in use
- **Solution**: Change ports in `package.json` (frontend) or `app.py` (backend)

**Problem**: Backend not connecting
- **Solution**: Check that Flask is running on port 5000 and CORS is enabled

## 📚 Next Steps

- Upload complex geometries to analyze
- Compare Aluminum vs Steel solidification
- Experiment with different pour temperatures
- Modify material properties in `solver.py`
- Add custom materials

## 🎯 Example Use Cases

1. **Casting Design Validation**: Check for hotspots before manufacturing
2. **Process Optimization**: Find optimal pour temperature
3. **Material Comparison**: Evaluate different alloys
4. **Educational Tool**: Learn about solidification physics

## 💡 Tips

- Higher pour temperatures take longer to solidify
- Thicker sections solidify last (hotspots)
- Steel solidifies slower than aluminum due to lower thermal conductivity
- Use the play button to see solidification progression clearly

Enjoy simulating! 🔥

