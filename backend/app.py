from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import os
import json
from simulation.step_importer import import_step_file
from simulation.mesher import generate_mesh
from simulation.fenics_solver import ProfessionalSolidificationSolver
import tempfile
import shutil

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Cache-Control"],
        "expose_headers": ["Content-Type"]
    }
})

# Configure upload settings
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Store active simulations
simulations = {}

@app.route('/api/upload', methods=['POST', 'OPTIONS'])
def upload_file():
    """Upload a STEP file and prepare it for simulation"""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return '', 204
    
    print("Upload request received")
    print(f"Files in request: {request.files}")
    print(f"Form data: {request.form}")
    
    if 'file' not in request.files:
        print("Error: No file in request")
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    print(f"File received: {file.filename}")
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith(('.step', '.stp', '.stl')):
        return jsonify({'error': 'File must be a STEP or STL file'}), 400
    
    # Save the file with correct extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if not file_ext:
        file_ext = '.step'
    filename = f"{os.urandom(16).hex()}{file_ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        file.save(filepath)
        print(f"File saved to: {filepath}")
    except Exception as e:
        print(f"Error saving file: {e}")
        return jsonify({'error': f'Failed to save file: {str(e)}'}), 500
    
    try:
        # Import and process the STEP file
        geometry = import_step_file(filepath)
        
        # Generate mesh
        mesh_data = generate_mesh(filepath)
        
        return jsonify({
            'success': True,
            'file_id': filename,
            'geometry': geometry,
            'mesh_info': {
                'num_nodes': len(mesh_data['nodes']),
                'num_elements': len(mesh_data['elements'])
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/simulate_stream', methods=['POST', 'GET'])
def run_simulation_stream():
    """Run solidification simulation with Server-Sent Events"""
    if request.method == 'POST':
        data = request.json
    else:
        data = request.args
    file_id = data.get('file_id')
    material = data.get('material', 'aluminum')
    initial_temp = float(data.get('initial_temperature', 700))
    ambient_temp = float(data.get('ambient_temperature', 25))

    if not file_id:
        return jsonify({'error': 'No file_id provided'}), 400

    filepath = os.path.join(UPLOAD_FOLDER, file_id)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    def generate():
        try:
            print(f"\n{'='*60}")
            print(f"STREAMING SIMULATION START")
            print(f"File: {file_id}, Material: {material}")
            print(f"Initial: {initial_temp}°C, Ambient: {ambient_temp}°C")
            print(f"{'='*60}\n")
            
            # Generate mesh
            mesh_data = generate_mesh(filepath)
            using_fallback = (len(mesh_data['nodes']) == 1000 and
                             len(mesh_data['elements']) == 3645)

            # Send initial mesh to frontend
            init_data = {
                'type': 'mesh',  # Changed from 'init' to 'mesh' 
                'mesh': {
                    'nodes': mesh_data['nodes'], 
                    'surface_triangles': mesh_data['surface_triangles']
                }
            }
            print(f"✓ Sending mesh with {len(mesh_data['nodes'])} nodes")
            yield f"data: {json.dumps(init_data)}\n\n"

            # Create solver
            solver = ProfessionalSolidificationSolver(
                mesh_data=mesh_data,
                material=material,
                initial_temp=initial_temp,
                ambient_temp=ambient_temp
            )

            # Run simulation with streaming - delays happen IN the solver!
            print("✓ Starting streaming solver (live computation)...")
            import sys
            frame_count = 0
            for i, update in enumerate(solver.solve(total_time=10, dt=0.1, save_interval=1, streaming=True, run_until_solid=True, dt_seconds=15.0, max_total_minutes=180, streaming_delay=0.0)):
                if update['type'] == 'timestep':
                    frame_count += 1
                    avg_temp = sum(update['data']['temperature']) / len(update['data']['temperature'])
                    print(f"  → Sending frame {frame_count}: T_avg={avg_temp:.1f}°C", flush=True)
                    
                yield f"data: {json.dumps(update)}\n\n"
                sys.stdout.flush()
            
            print(f"\n{'='*60}")
            print(f"STREAMING COMPLETE")
            print(f"{'='*60}\n")

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

@app.route('/api/simulate', methods=['POST'])
def run_simulation():
    """Run solidification simulation"""
    data = request.json
    file_id = data.get('file_id')
    material = data.get('material', 'aluminum')
    initial_temp = data.get('initial_temperature', 700)
    ambient_temp = data.get('ambient_temperature', 25)
    
    if not file_id:
        return jsonify({'error': 'No file_id provided'}), 400
    
    filepath = os.path.join(UPLOAD_FOLDER, file_id)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Generate mesh from the uploaded file
        print(f"\n{'='*60}")
        print(f"Processing file: {file_id}")
        print(f"{'='*60}")
        mesh_data = generate_mesh(filepath)
        
        # Check if fallback was used (cube has exactly 1000 nodes)
        using_fallback = (len(mesh_data['nodes']) == 1000 and 
                         len(mesh_data['elements']) == 3645)
        
        # Use professional-grade solidification solver
        solver = ProfessionalSolidificationSolver(
            mesh_data=mesh_data,
            material=material,
            initial_temp=initial_temp,
            ambient_temp=ambient_temp
        )
        
        # Run solidification analysis - 10 minute simulation
        # Fast but visible solidification for demonstration
        results = solver.solve(total_time=10, dt=0.1, save_interval=1, run_until_solid=True, dt_seconds=15.0, max_total_minutes=180)
        
        # Add warning if fallback was used
        if using_fallback:
            results['summary']['warning'] = (
                "Your STEP file had geometry issues and couldn't be meshed. "
                "Simulation ran on a simplified cube geometry instead. "
                "For best results, export your STEP file with: "
                "(1) No overlapping surfaces, (2) Closed volumes, (3) Simplified geometry. "
                "Or try exporting as STL format."
            )
        
        # Store results
        sim_id = f"{os.urandom(16).hex()}"
        simulations[sim_id] = results
        
        # Save results to file
        result_file = os.path.join(RESULTS_FOLDER, f"{sim_id}.json")
        with open(result_file, 'w') as f:
            json.dump(results, f)
        
        return jsonify({
            'success': True,
            'simulation_id': sim_id,
            'num_timesteps': len(results['timesteps']),
            'summary': results['summary']
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze_cast', methods=['POST'])
def analyze_cast_endpoint():
    data = request.json or {}
    file_id = data.get('file_id')
    if not file_id:
        return jsonify({'error': 'No file_id provided'}), 400
    filepath = os.path.join(UPLOAD_FOLDER, file_id)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    alloy = data.get('alloy', {
        'T_liq': 615.0,
        'T_sol': 555.0,
        'L': 3.89e5,
        'k': 140.0,
        'rho': 2685.0,
        'cp': 1000.0,
    })
    bc = data.get('bc', {
        'T0': alloy.get('T_liq', 615.0) + 40.0,
        'T_inf': 300.0,
        'h': 400.0,
        'min_gate_diam': 8.0,
        'h_min': 5.0,
        'h_max': 15.0,
    })
    time_cfg = data.get('time', {
        'dt': 0.5,
        't_end': 60.0
    })

    outdir = os.path.join(RESULTS_FOLDER, os.urandom(8).hex())
    try:
        # Lazy import to avoid top-level failures affecting unrelated endpoints
        from simulation.pipeline import analyze_cast as _analyze_cast
        result = _analyze_cast(filepath, alloy, bc, time_cfg, outdir)
        return jsonify({
            'success': True,
            'clusters': result['clusters'],
            'gates': result['gates'],
            'outdir': outdir
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/results/<sim_id>', methods=['GET'])
def get_results(sim_id):
    """Get simulation results"""
    result_file = os.path.join(RESULTS_FOLDER, f"{sim_id}.json")
    
    if not os.path.exists(result_file):
        return jsonify({'error': 'Simulation not found'}), 404
    
    with open(result_file, 'r') as f:
        results = json.load(f)
    
    return jsonify(results)

@app.route('/api/materials', methods=['GET'])
def get_materials():
    """Get available materials and their properties"""
    materials = {
        'aluminum': {
            'name': 'Aluminum (Al)',
            'melting_point': 660,  # °C
            'density': 2700,  # kg/m³
            'thermal_conductivity': 237,  # W/(m·K)
            'specific_heat': 900,  # J/(kg·K)
            'latent_heat': 397000,  # J/kg
            'default_pour_temp': 700
        },
        'steel': {
            'name': 'Steel',
            'melting_point': 1370,  # °C
            'density': 7850,  # kg/m³
            'thermal_conductivity': 50,  # W/(m·K)
            'specific_heat': 490,  # J/(kg·K)
            'latent_heat': 247000,  # J/kg
            'default_pour_temp': 1500
        }
    }
    return jsonify(materials)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

