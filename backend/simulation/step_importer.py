import trimesh
import numpy as np
import tempfile
import os

def import_step_file(filepath):
    """
    Import a STEP file and convert to mesh data for visualization
    Uses trimesh which can handle STEP files through various backends
    """
    try:
        # Try to load with trimesh (may require additional dependencies)
        # For STEP files, we'll convert to a more common format first
        mesh = load_step_as_mesh(filepath)
        
        # Extract vertices and faces for Three.js
        vertices = mesh.vertices.tolist()
        faces = mesh.faces.tolist()
        
        # Calculate bounding box
        bounds = mesh.bounds
        
        return {
            'vertices': vertices,
            'faces': faces,
            'bounds': {
                'min': bounds[0].tolist(),
                'max': bounds[1].tolist()
            },
            'volume': float(mesh.volume),
            'area': float(mesh.area)
        }
    except Exception as e:
        raise Exception(f"Failed to import STEP file: {str(e)}")

def load_step_as_mesh(filepath):
    """
    Load STEP file using available tools
    Fallback to creating a simple geometry if STEP import is not available
    """
    try:
        # Try using gmsh to convert STEP to mesh
        import gmsh
        
        # Initialize Gmsh if not already initialized
        if not gmsh.isInitialized():
            try:
                gmsh.initialize()
            except:
                # If signal handling fails, continue anyway
                pass
        
        gmsh.option.setNumber("General.Terminal", 0)
        
        # Load STEP file
        gmsh.model.occ.importShapes(filepath)
        gmsh.model.occ.synchronize()
        
        # Generate mesh
        gmsh.model.mesh.generate(3)
        
        # Get nodes and elements
        node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
        nodes = node_coords.reshape(-1, 3)
        
        # Get tetrahedra (3D elements)
        elem_types, elem_tags, elem_node_tags = gmsh.model.mesh.getElements(3)
        
        # Convert to trimesh format
        if len(elem_types) > 0:
            # Get surface mesh for visualization
            gmsh.model.mesh.generate(2)
            node_tags_2d, node_coords_2d, _ = gmsh.model.mesh.getNodes()
            nodes_2d = node_coords_2d.reshape(-1, 3)
            
            # Get triangles
            elem_types_2d, _, elem_node_tags_2d = gmsh.model.mesh.getElements(2)
            
            if len(elem_types_2d) > 0:
                triangles = elem_node_tags_2d[0].reshape(-1, 3) - 1  # Convert to 0-based indexing
                
                # Clear the model instead of finalizing
                gmsh.clear()
                
                # Create trimesh
                mesh = trimesh.Trimesh(vertices=nodes_2d, faces=triangles)
                return mesh
        
        gmsh.clear()
        raise Exception("No valid elements found in STEP file")
        
    except Exception as e:
        print(f"Warning: Could not import STEP file with gmsh: {e}")
        print("Creating a simple box geometry as fallback...")
        
        # Fallback: create a simple box
        mesh = trimesh.creation.box(extents=[100, 50, 30])
        return mesh

def step_to_stl(step_path, stl_path):
    """Convert STEP to STL using gmsh"""
    import gmsh
    
    if not gmsh.isInitialized():
        try:
            gmsh.initialize()
        except:
            pass
    
    gmsh.option.setNumber("General.Terminal", 0)
    
    gmsh.model.occ.importShapes(step_path)
    gmsh.model.occ.synchronize()
    
    gmsh.model.mesh.generate(2)
    gmsh.write(stl_path)
    gmsh.clear()

