"""
Clean, professional casting solidification API
Simplified and focused on reliability
"""

from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
import os
import json
import logging
from simulation.mesher import generate_mesh
from simulation.fenics_solver import ProfessionalSolidificationSolver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='uploads', static_url_path='/uploads')
CORS(app)

# Configure
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Material database
MATERIALS = {
    'aluminum': {
        'name': 'Aluminum (Al)',
        'melting_point': 660,
        'density': 2700,
        'thermal_conductivity': 237,
        'specific_heat': 900,
        'latent_heat': 397000,
        'default_pour_temp': 700
    },
    'steel': {
        'name': 'Steel',
        'melting_point': 1495,
        'density': 7850,
        'thermal_conductivity': 50,
        'specific_heat': 490,
        'latent_heat': 260000,
        'default_pour_temp': 1550
    }
}

@app.route('/api/materials', methods=['GET'])
def get_materials():
    """Get available materials"""
    return jsonify(MATERIALS)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload and mesh a geometry file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate extension
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.stl', '.step', '.stp']:
            return jsonify({'error': 'Invalid file type. Use STL or STEP'}), 400
        
        # Save file
        filename = f"{os.urandom(16).hex()}{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        logger.info(f"File uploaded: {filename}")
        
        # Generate mesh
        logger.info(f"Generating mesh from {filename}...")
        mesh_data = generate_mesh(filepath)
        
        logger.info(f"Mesh generated: {len(mesh_data['nodes'])} nodes, {len(mesh_data['elements'])} elements")
        
        return jsonify({
            'success': True,
            'file_id': filename,
            'mesh': mesh_data,  # Return full mesh immediately
            'mesh_info': {
                'num_nodes': len(mesh_data['nodes']),
                'num_elements': len(mesh_data['elements']),
                'num_surface_triangles': len(mesh_data.get('surface_triangles', []))
            }
        })
        
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/mesh/<filename>', methods=['GET'])
def get_mesh(filename):
    """Get mesh data for a file (for testing)"""
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        mesh_data = generate_mesh(filepath)
        return jsonify(mesh_data)
    except Exception as e:
        logger.error(f"Mesh fetch error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/visualize/<filename>', methods=['GET'])
def visualize_mesh(filename):
    """Generate interactive PyVista HTML visualization"""
    try:
        import pyvista as pv
        import trimesh
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        # Load the STL surface (what frontend should display)
        stl_path = filepath.replace('.step', '_surface.stl').replace('.stp', '_surface.stl')
        
        if not os.path.exists(stl_path):
            # Generate mesh first
            logger.info(f"Generating mesh for {filename}")
            mesh_data = generate_mesh(filepath)
            # STL should now exist
        
        if os.path.exists(stl_path):
            logger.info(f"Creating PyVista visualization for {stl_path}")
            stl_mesh = trimesh.load(stl_path)
            
            # Create PyVista mesh
            mesh_pv = pv.wrap(stl_mesh)
            
            # Save as static HTML (trame backend)
            html_path = filepath.replace('.step', '_viz.html').replace('.stp', '_viz.html')
            
            # Use pyvista's built-in export (simpler, more reliable)
            plotter = pv.Plotter(off_screen=True)
            plotter.add_mesh(mesh_pv, color='orange', show_edges=True, 
                           edge_color='black', line_width=0.5)
            plotter.camera_position = 'iso'
            
            # Save screenshot first as fallback
            screenshot_path = filepath.replace('.step', '_screenshot.png').replace('.stp', '_screenshot.png')
            plotter.screenshot(screenshot_path)
            
            # Try to export HTML
            try:
                plotter.export_html(html_path)
                plotter.close()
                
                # Read and serve HTML
                with open(html_path, 'r') as f:
                    return f.read(), 200, {'Content-Type': 'text/html'}
            except Exception as e:
                logger.error(f"HTML export failed: {e}, serving screenshot")
                plotter.close()
                
                # Fallback: serve simple HTML with screenshot
                html = f'''
                <!DOCTYPE html>
                <html>
                <head><title>Mesh View</title></head>
                <body style="margin:0; background:#2a2a2a; display:flex; align-items:center; justify-content:center; height:100vh;">
                    <div style="text-align:center;">
                        <h2 style="color:white;">Mesh Preview</h2>
                        <img src="/api/screenshot/{os.path.basename(screenshot_path)}" style="max-width:90%; max-height:80vh;">
                        <p style="color:white;">{len(stl_mesh.faces):,} triangles</p>
                    </div>
                </body>
                </html>
                '''
                return html, 200, {'Content-Type': 'text/html'}
        else:
            return jsonify({'error': 'STL not generated'}), 500
            
    except Exception as e:
        logger.error(f"Visualization error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/screenshot/<filename>', methods=['GET'])
def serve_screenshot(filename):
    """Serve screenshot image"""
    screenshot_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(screenshot_path):
        return send_file(screenshot_path, mimetype='image/png')
    return jsonify({'error': 'Screenshot not found'}), 404

@app.route('/api/simulate', methods=['GET'])
def run_simulation():
    """Run simulation with Server-Sent Events (streaming)"""
    # Get parameters
    file_id = request.args.get('file_id')
    material = request.args.get('material', 'aluminum')
    initial_temp = float(request.args.get('initial_temperature', 700))
    ambient_temp = float(request.args.get('ambient_temperature', 25))
    
    if not file_id:
        return jsonify({'error': 'No file_id provided'}), 400
    
    filepath = os.path.join(UPLOAD_FOLDER, file_id)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    def generate():
        try:
            logger.info(f"Starting simulation: {file_id}, {material}, {initial_temp}°C")
            
            # Load mesh
            mesh_data = generate_mesh(filepath)
            
            # Validate mesh has volume elements
            if not mesh_data.get('elements') or len(mesh_data['elements']) == 0:
                raise Exception(
                    "Cannot run simulation: mesh has no volume elements. "
                    "This usually means the STEP file contains only surface geometry (not solid volumes). "
                    "Please export your CAD model as a solid body, not just surfaces."
                )
            
            # Send mesh first
            yield f"data: {json.dumps({'type': 'mesh', 'mesh': mesh_data})}\n\n"
            
            # Create solver
            solver = ProfessionalSolidificationSolver(
                mesh_data=mesh_data,
                material=material,
                initial_temp=initial_temp,
                ambient_temp=ambient_temp
            )
            
            # Run simulation with streaming
            for update in solver.solve(
                total_time=10,
                dt=0.1,
                save_interval=1,
                streaming=True,
                run_until_solid=True,
                dt_seconds=15.0,
                max_total_minutes=180,
                streaming_delay=0.1
            ):
                yield f"data: {json.dumps(update)}\n\n"
            
            logger.info("Simulation complete")
            
        except Exception as e:
            logger.error(f"Simulation error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

if __name__ == '__main__':
    print("\n" + "="*60)
    print("CASTING SOLIDIFICATION SIMULATOR - BACKEND")
    print("="*60)
    print(f"Uploads: {UPLOAD_FOLDER}")
    print(f"Materials: {', '.join(MATERIALS.keys())}")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5001, debug=True, threaded=True)

