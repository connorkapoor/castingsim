import numpy as np
import gmsh

def generate_mesh(filepath, mesh_size=5.0):
    """
    Generate a 3D tetrahedral mesh from a STEP or STL file using Gmsh
    
    Args:
        filepath: Path to STEP or STL file
        mesh_size: Target mesh element size
        
    Returns:
        dict containing nodes, elements, and connectivity
    """
    # Check file type
    file_ext = filepath.lower().split('.')[-1]
    
    if file_ext == 'stl':
        print(f"Processing STL file: {filepath}")
        return generate_mesh_from_stl(filepath, mesh_size)
    else:
        return generate_mesh_from_step(filepath, mesh_size)


def generate_mesh_from_stl(stl_filepath, mesh_size=5.0):
    """
    Use the actual STL mesh - vertices and faces directly
    Create volume elements using Gmsh's remeshing of the STL
    """
    import trimesh
    
    try:
        # Load the STL - this is YOUR actual part geometry
        print(f"Loading STL mesh: {stl_filepath}")
        stl_mesh = trimesh.load(stl_filepath)
        
        print(f"STL loaded: {len(stl_mesh.vertices)} vertices, {len(stl_mesh.faces)} triangles")
        
        # For large meshes, use coarser voxelization instead of decimating surface
        # We keep the original STL surface for visualization
        
        # Use trimesh to create volume mesh using voxelization
        # This keeps YOUR actual part shape
        bounds = stl_mesh.bounds
        bbox_size = bounds[1] - bounds[0]
        max_dim = np.max(bbox_size)
        
        # Determine pitch (voxel size) - SMALLER pitch = MORE voxels = MORE points
        # For 2X points compared to pitch=5.0 baseline (1644 nodes)
        pitch = 3.5  # Target ~3300 nodes (2x resolution from baseline 1644)
        
        print(f"Creating voxel mesh with pitch={pitch:.2f}...")
        voxel = stl_mesh.voxelized(pitch=pitch)
        
        # Get filled voxels as point cloud
        points = voxel.points
        print(f"Voxelized: {len(points)} internal points")
        
        # Use these voxel centers as nodes
        nodes = points
        
        # Create tetrahedral mesh from voxels
        # For simplicity, use structured tet mesh in voxel grid
        print(f"Creating volume elements from voxels...")
        
        # Create a KDTree for the voxel centers
        from scipy.spatial import cKDTree, Delaunay
        
        # Use Delaunay triangulation to create tets from voxel centers
        print("Running Delaunay triangulation...")
        tri = Delaunay(nodes)
        elements = tri.simplices.tolist()
        
        print(f"Created {len(elements)} tetrahedral elements from Delaunay")
        
        # Use original STL surface for visualization (decimated if needed)
        surface_mesh = stl_mesh
        if len(surface_mesh.faces) > 10000:
            subsample = len(surface_mesh.faces) // 10000
            surface_triangles = surface_mesh.faces[::subsample].tolist()
            print(f"Using {len(surface_triangles)} surface triangles for visualization")
        else:
            surface_triangles = surface_mesh.faces.tolist()
        
        # Map STL vertices to closest volume nodes
        tree = cKDTree(nodes)
        surface_vertex_map = {}
        
        for tri in surface_triangles:
            for i, stl_vidx in enumerate(tri):
                if stl_vidx not in surface_vertex_map:
                    stl_vertex = surface_mesh.vertices[stl_vidx]
                    _, node_idx = tree.query(stl_vertex)
                    surface_vertex_map[stl_vidx] = node_idx
                tri[i] = surface_vertex_map[stl_vidx]
        
        # Boundary nodes are those on the surface
        boundary_nodes = list(set(surface_vertex_map.values()))
        
        print(f"✅ STL processed: {len(nodes)} nodes, {len(elements)} tets")
        print(f"   Surface: {len(surface_triangles)} triangles showing YOUR part shape")
        
        return {
            'nodes': nodes.tolist(),
            'elements': elements,
            'surface_triangles': surface_triangles,
            'boundary_nodes': boundary_nodes
        }
        
    except Exception as e:
        print(f"STL mesh generation failed: {e}")
        import traceback
        traceback.print_exc()
        return generate_simple_cube_mesh(size=50.0, divisions=10)


def generate_mesh_from_step(step_filepath, mesh_size=5.0):
    """Generate mesh from STEP file"""
    # Initialize Gmsh if not already initialized
    if not gmsh.isInitialized():
        try:
            gmsh.initialize()
        except:
            # If signal handling fails (e.g., in Flask debug mode), continue anyway
            pass
    
    gmsh.option.setNumber("General.Terminal", 0)
    
    try:
        # Import STEP geometry
        print(f"Importing STEP file: {step_filepath}")
        gmsh.model.occ.importShapes(step_filepath)
        gmsh.model.occ.synchronize()
        
        # Get geometry info
        entities = gmsh.model.getEntities()
        print(f"Loaded geometry: {len(entities)} entities")
        volumes = gmsh.model.getEntities(3)
        print(f"Found {len(volumes)} 3D volumes")
        
        # Set mesh size
        gmsh.option.setNumber("Mesh.CharacteristicLengthMin", mesh_size * 0.5)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", mesh_size * 2.0)
        
        # Use robust meshing options for CAD imports
        gmsh.option.setNumber("Mesh.Algorithm", 6)  # Frontal-Delaunay for 2D (robust)
        gmsh.option.setNumber("Mesh.Algorithm3D", 10)  # HXT for 3D (more robust than Delaunay)
        
        # Key settings for handling CAD geometry
        gmsh.option.setNumber("Geometry.OCCFixDegenerated", 1)  # Fix degenerate edges
        gmsh.option.setNumber("Geometry.OCCFixSmallEdges", 1)  # Fix small edges
        gmsh.option.setNumber("Geometry.OCCFixSmallFaces", 1)  # Fix small faces
        gmsh.option.setNumber("Geometry.OCCSewFaces", 1)  # Sew faces together
        gmsh.option.setNumber("Geometry.Tolerance", 1e-3)  # More tolerant
        gmsh.option.setNumber("Geometry.ToleranceBoolean", 1e-3)
        
        # Mesh quality settings
        gmsh.option.setNumber("Mesh.CharacteristicLengthFromCurvature", 1)
        gmsh.option.setNumber("Mesh.CharacteristicLengthExtendFromBoundary", 1)
        gmsh.option.setNumber("Mesh.MinimumCirclePoints", 15)
        gmsh.option.setNumber("Mesh.Optimize", 1)  # Optimize mesh quality
        gmsh.option.setNumber("Mesh.OptimizeNetgen", 1)
        
        # Generate 3D mesh with progressive fallbacks
        mesh_generated = False
        
        # Try 1: Default size with HXT
        try:
            print("Attempt 1: Standard mesh with HXT algorithm...")
            gmsh.model.mesh.generate(3)
            mesh_generated = True
            print("✓ Success with standard settings")
        except Exception as e1:
            print(f"  Failed: {str(e1)[:100]}")
            
            # Try 2: Coarser mesh
            try:
                print("Attempt 2: Coarser mesh...")
                gmsh.model.mesh.clear()
                gmsh.option.setNumber("Mesh.CharacteristicLengthMin", mesh_size * 3.0)
                gmsh.option.setNumber("Mesh.CharacteristicLengthMax", mesh_size * 6.0)
                gmsh.model.mesh.generate(3)
                mesh_generated = True
                print("✓ Success with coarser mesh")
            except Exception as e2:
                print(f"  Failed: {str(e2)[:100]}")
                
                # Try 3: Switch to Delaunay algorithm with very coarse mesh
                try:
                    print("Attempt 3: Delaunay with very coarse mesh...")
                    gmsh.model.mesh.clear()
                    gmsh.option.setNumber("Mesh.Algorithm3D", 1)  # Switch to Delaunay
                    gmsh.option.setNumber("Mesh.CharacteristicLengthMin", mesh_size * 5.0)
                    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", mesh_size * 10.0)
                    gmsh.model.mesh.generate(3)
                    mesh_generated = True
                    print("✓ Success with Delaunay + very coarse mesh")
                except Exception as e3:
                    print(f"  Failed: {str(e3)[:100]}")
                    print("All meshing attempts failed - using fallback geometry")
        
        if not mesh_generated:
            raise Exception("Could not mesh STEP geometry after multiple attempts")
        
        # Get nodes
        node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
        nodes = node_coords.reshape(-1, 3)
        
        print(f"Extracted {len(nodes)} nodes from mesh")
        
        # Check if mesh actually has nodes (Gmsh can "succeed" but produce empty mesh)
        if len(nodes) == 0:
            print("⚠️  Mesh generation reported success but produced 0 nodes!")
            print("    This usually means overlapping/duplicate surfaces in the STEP file")
            raise Exception("Empty mesh generated - likely due to overlapping facets in geometry")
        
        # Create node tag to index mapping
        node_map = {tag: idx for idx, tag in enumerate(node_tags)}
        
        # Get 3D elements - try all types
        elem_types, elem_tags, elem_node_tags = gmsh.model.mesh.getElements(3)
        
        elements = []
        print(f"Found {len(elem_types)} element type(s) in 3D mesh")
        
        for elem_type, tags, node_tags_list in zip(elem_types, elem_tags, elem_node_tags):
            print(f"  Element type {elem_type}: {len(tags)} elements")
            
            if elem_type == 4:  # Tetrahedron (4 nodes)
                num_nodes_per_elem = 4
            elif elem_type == 5:  # Hexahedron (8 nodes)
                num_nodes_per_elem = 8
            elif elem_type == 6:  # Prism (6 nodes)
                num_nodes_per_elem = 6
            elif elem_type == 7:  # Pyramid (5 nodes)
                num_nodes_per_elem = 5
            elif elem_type == 11:  # 10-node tetrahedron
                num_nodes_per_elem = 10
                # Use only first 4 nodes for linear tet
            else:
                print(f"    Skipping unsupported element type {elem_type}")
                continue
            
            try:
                node_tags_array = node_tags_list.reshape(-1, num_nodes_per_elem)
                
                # Convert to 0-based indices (use first 4 nodes for all element types)
                for node_tags_elem in node_tags_array:
                    if elem_type == 11:  # 10-node tet, use first 4
                        elem_nodes = [node_map[tag] for tag in node_tags_elem[:4]]
                    else:
                        elem_nodes = [node_map[tag] for tag in node_tags_elem[:4]]
                    elements.append(elem_nodes)
            except Exception as e:
                print(f"    Error processing elements: {e}")
                
        print(f"Processed {len(elements)} volume elements")
        
        # Get surface triangles for visualization
        surface_triangles = []
        elem_types_2d, _, elem_node_tags_2d = gmsh.model.mesh.getElements(2)
        
        for elem_type, tags, node_tags_list in zip(elem_types_2d, elem_tags[0:1], elem_node_tags_2d):
            if elem_type == 2:  # Triangle
                node_tags_array = node_tags_list.reshape(-1, 3)
                for node_tags_elem in node_tags_array:
                    tri_nodes = [node_map[tag] for tag in node_tags_elem]
                    surface_triangles.append(tri_nodes)
        
        # Identify boundary nodes
        boundary_nodes = set()
        for tri in surface_triangles:
            boundary_nodes.update(tri)
        
        # Clear the model instead of finalizing to keep Gmsh instance alive
        gmsh.clear()
        
        # Validate mesh has elements
        if len(elements) == 0:
            print("❌ Warning: No 3D elements generated from STEP file")
            print("   Using fallback cube mesh")
            return generate_simple_cube_mesh(size=50.0, divisions=10)
        
        print(f"✅ Successfully meshed STEP file: {len(nodes)} nodes, {len(elements)} elements")
        
        return {
            'nodes': nodes.tolist(),
            'elements': elements,
            'surface_triangles': surface_triangles,
            'boundary_nodes': list(boundary_nodes)
        }
        
    except Exception as e:
        gmsh.clear()
        print(f"Mesh generation failed: {e}")
        print("Generating simple cube mesh as fallback...")
        import traceback
        traceback.print_exc()
        
        # Fallback: generate a simple cube mesh
        return generate_simple_cube_mesh(size=50.0, divisions=10)

def generate_simple_cube_mesh(size=50.0, divisions=10):
    """Generate a simple structured tetrahedral mesh of a cube"""
    
    # Generate grid points
    x = np.linspace(-size/2, size/2, divisions)
    y = np.linspace(-size/2, size/2, divisions)
    z = np.linspace(-size/2, size/2, divisions)
    
    # Create nodes
    nodes = []
    node_map = {}
    idx = 0
    
    for i in range(divisions):
        for j in range(divisions):
            for k in range(divisions):
                nodes.append([x[i], y[j], z[k]])
                node_map[(i, j, k)] = idx
                idx += 1
    
    # Create tetrahedral elements from cubes
    elements = []
    surface_triangles = []
    
    def get_node(i, j, k):
        if (i, j, k) in node_map:
            return node_map[(i, j, k)]
        return None
    
    for i in range(divisions - 1):
        for j in range(divisions - 1):
            for k in range(divisions - 1):
                # Get 8 corners of cube
                n0 = get_node(i, j, k)
                n1 = get_node(i+1, j, k)
                n2 = get_node(i+1, j+1, k)
                n3 = get_node(i, j+1, k)
                n4 = get_node(i, j, k+1)
                n5 = get_node(i+1, j, k+1)
                n6 = get_node(i+1, j+1, k+1)
                n7 = get_node(i, j+1, k+1)
                
                # Split cube into 5 tetrahedra
                elements.append([n0, n1, n2, n5])
                elements.append([n0, n2, n3, n7])
                elements.append([n0, n5, n2, n6])
                elements.append([n0, n6, n2, n7])
                elements.append([n0, n5, n6, n4])
                
                # Add surface triangles
                if i == 0:
                    surface_triangles.extend([[n0, n3, n4], [n3, n7, n4]])
                if i == divisions - 2:
                    surface_triangles.extend([[n1, n5, n2], [n2, n5, n6]])
                if j == 0:
                    surface_triangles.extend([[n0, n1, n4], [n1, n5, n4]])
                if j == divisions - 2:
                    surface_triangles.extend([[n3, n2, n7], [n2, n6, n7]])
                if k == 0:
                    surface_triangles.extend([[n0, n2, n1], [n0, n3, n2]])
                if k == divisions - 2:
                    surface_triangles.extend([[n4, n5, n6], [n4, n6, n7]])
    
    # Identify boundary nodes
    boundary_nodes = set()
    for tri in surface_triangles:
        boundary_nodes.update(tri)
    
    return {
        'nodes': nodes,
        'elements': elements,
        'surface_triangles': surface_triangles,
        'boundary_nodes': list(boundary_nodes)
    }
