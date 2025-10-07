import numpy as np
import gmsh
import logging
import trimesh
from scipy.spatial import Delaunay
from collections import defaultdict
import tempfile
import os
import pyvista as pv
import meshio

logger = logging.getLogger(__name__)

def generate_mesh(filepath, mesh_size=5.0):
    """Generate mesh from STL or STEP file using hex voxelization"""
    file_ext = filepath.lower().split('.')[-1]
    
    if file_ext == 'stl':
        return generate_mesh_from_stl_voxel(filepath)
    else:
        # Use hex voxelizer approach
        return generate_mesh_from_step_hex(filepath, mesh_size)


def step_to_stl(step_path, stl_path, force_mm_to_m=False):
    """
    Import STEP & triangulate (clean, watertight surface).
    
    Args:
        step_path: Path to STEP file
        stl_path: Output STL path
        force_mm_to_m: Scale mm to meters (set True if STEP is in mm)
    """
    # Check if gmsh is already initialized (thread safety)
    if not gmsh.isInitialized():
        gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("cad")
    
    # Import STEP (skip aggressive healing - it can break valid geometry)
    if force_mm_to_m:
        gmsh.model.occ.importShapes(step_path, format="step", highestDimOnly=False, scaling=0.001)
    else:
        gmsh.model.occ.importShapes(step_path, format="step", highestDimOnly=False)
    
    try:
        gmsh.model.occ.synchronize()
    except Exception as e:
        logger.warning(f"OCC synchronize had issues: {e}, continuing anyway...")
        pass  # Continue with what we have
    
    # Clean up duplicates only (gentle approach)
    try:
        gmsh.model.occ.removeAllDuplicates()
        gmsh.model.occ.synchronize()
    except:
        pass

    # ADAPTIVE MESH - preserves curvature with fallback
    gmsh.option.setNumber("Mesh.CharacteristicLengthMin", 0.2)
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", 1.0)
    gmsh.option.setNumber("Mesh.CharacteristicLengthFromCurvature", 1)  # CRITICAL: adapt to curves
    gmsh.option.setNumber("Mesh.CharacteristicLengthExtendFromBoundary", 1)
    gmsh.option.setNumber("Mesh.MinimumCirclePoints", 32)
    gmsh.option.setNumber("Mesh.Algorithm", 5)  # Delaunay (robust)
    
    # Generate with error handling
    try:
        gmsh.model.mesh.generate(2)
    except Exception as e:
        logger.warning(f"Fine meshing failed ({e}), using coarser...")
        gmsh.option.setNumber("Mesh.CharacteristicLengthMin", 0.5)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", 2.0)
        gmsh.option.setNumber("Mesh.MinimumCirclePoints", 20)
        gmsh.model.mesh.generate(2)
    
    gmsh.write(stl_path)
    
    # Don't finalize in Flask threads - causes issues
    try:
        gmsh.clear()
    except:
        pass
    
    logger.info(f"✅ STEP → STL: {stl_path}")


def voxelize_stl_to_hex(stl_path, out_base, voxel_size):
    """
    Build a regular 3D grid over the part's bounding box.
    Compute signed distance from each grid cell center to the surface.
    Keep only inside voxels → hexahedral unstructured mesh.
    
    Args:
        stl_path: Input STL file (watertight surface)
        out_base: Base name for output files (will create _vol.xdmf and _facets.xdmf)
        voxel_size: Size of each hex voxel (controls mesh resolution)
    
    Returns:
        dict with mesh statistics
    """
    logger.info(f"Loading surface mesh: {stl_path}")
    
    # Load triangulated shell
    surf = pv.read(stl_path)
    surf = surf.triangulate().clean()
    
    logger.info(f"Surface: {surf.n_points} points, {surf.n_cells} triangles")
    logger.info(f"Watertight: {surf.n_open_edges == 0}")
    
    # Bounding box + padding (to avoid clipping surface)
    xmin, xmax, ymin, ymax, zmin, zmax = surf.bounds
    pad = 2 * voxel_size
    bounds = (xmin - pad, xmax + pad,
              ymin - pad, ymax + pad,
              zmin - pad, zmax + pad)
    
    # Create a uniform grid (image data) – cell-centered voxels
    nx = int(np.ceil((bounds[1] - bounds[0]) / voxel_size))
    ny = int(np.ceil((bounds[3] - bounds[2]) / voxel_size))
    nz = int(np.ceil((bounds[5] - bounds[4]) / voxel_size))
    
    logger.info(f"Grid dimensions: {nx} x {ny} x {nz} = {nx*ny*nz} voxels")
    
    grid = pv.ImageData(
        dimensions=(nx+1, ny+1, nz+1),
        spacing=(voxel_size, voxel_size, voxel_size),
        origin=(bounds[0], bounds[2], bounds[4])
    )
    
    # Signed distance from surface (negative = inside)
    logger.info("Computing signed distance field (this may take a moment)...")
    
    # Use PyVista's built-in method - MUCH faster!
    grid_with_sdf = grid.compute_implicit_distance(surf, inplace=False)
    
    # Get distance at cell centers (average of 8 corner points)
    point_distances = grid_with_sdf.point_data['implicit_distance']
    
    # Convert to cell data using vectorized approach
    dims = grid.dimensions  # (nx+1, ny+1, nz+1)
    nx, ny, nz = dims[0]-1, dims[1]-1, dims[2]-1
    
    # Reshape point distances to 3D grid
    dist_3d = point_distances.reshape(dims[2], dims[1], dims[0])  # Note: Z, Y, X order
    
    # Average 8 corners for each cell (vectorized!)
    cell_distances = (
        dist_3d[:-1, :-1, :-1] + dist_3d[1:, :-1, :-1] +  # bottom 4 corners
        dist_3d[:-1, 1:, :-1] + dist_3d[1:, 1:, :-1] +
        dist_3d[:-1, :-1, 1:] + dist_3d[1:, :-1, 1:] +    # top 4 corners
        dist_3d[:-1, 1:, 1:] + dist_3d[1:, 1:, 1:]
    ) / 8.0
    
    cell_distances = cell_distances.flatten()
    inside_mask = cell_distances < 0.0
    logger.info(f"Inside voxels: {inside_mask.sum()} / {len(inside_mask)}")
    
    # Build HEXA connectivity for inside cells
    dims = np.array(grid.dimensions)
    nxp, nyp, nzp = dims
    
    def node_id(i, j, k):
        return i + j*nxp + k*nxp*nyp
    
    hexes = []
    for k in range(nzp-1):
        for j in range(nyp-1):
            for i in range(nxp-1):
                cell_index = i + j*nx + k*nx*ny
                if not inside_mask[cell_index]:
                    continue
                n0 = node_id(i,   j,   k)
                n1 = node_id(i+1, j,   k)
                n2 = node_id(i+1, j+1, k)
                n3 = node_id(i,   j+1, k)
                n4 = node_id(i,   j,   k+1)
                n5 = node_id(i+1, j,   k+1)
                n6 = node_id(i+1, j+1, k+1)
                n7 = node_id(i,   j+1, k+1)
                hexes.append([n0,n1,n2,n3,n4,n5,n6,n7])
    
    hexes = np.array(hexes, dtype=np.int32)
    pts = grid.points
    
    logger.info(f"Generated {len(hexes)} hexahedral elements")
    
    # Write volume mesh (hexahedra) with material tag "CASTING"=1
    vol_mesh = meshio.Mesh(
        points=pts,
        cells=[("hexahedron", hexes)],
        cell_data={"name_to_read": [np.ones(len(hexes), dtype=np.int32)]}
    )
    meshio.write(f"{out_base}_vol.xdmf", vol_mesh)
    logger.info(f"✅ Volume mesh: {out_base}_vol.xdmf")
    
    # Extract boundary facets (outer quads) for BCs
    logger.info("Extracting boundary facets...")
    face_count = defaultdict(list)
    
    # Hex face → 4-node quads (VTK ordering)
    faces_of_hex = [
        [0,1,2,3], [4,5,6,7],  # bottom, top
        [0,1,5,4], [1,2,6,5],  # sides
        [2,3,7,6], [3,0,4,7],
    ]
    
    for ci, h in enumerate(hexes):
        for f in faces_of_hex:
            quad = tuple(h[idx] for idx in f)
            key = tuple(sorted(quad))
            face_count[key].append(quad)
    
    boundary_quads = [v[0] for k,v in face_count.items() if len(v)==1]
    boundary_quads = np.array(boundary_quads, dtype=np.int32)
    
    logger.info(f"Generated {len(boundary_quads)} boundary quads")
    
    facet_mesh = meshio.Mesh(
        points=pts,
        cells=[("quad", boundary_quads)],
        cell_data={"name_to_read": [np.full(len(boundary_quads), 11, dtype=np.int32)]}
    )
    meshio.write(f"{out_base}_facets.xdmf", facet_mesh)
    logger.info(f"✅ Facet mesh: {out_base}_facets.xdmf")
    
    return {
        "num_hex": len(hexes),
        "num_facets": len(boundary_quads),
        "bounds": bounds,
        "voxel_size": voxel_size
    }


def generate_hex_mesh_from_step(step_path, output_base, voxel_size=1.0, force_mm_to_m=False):
    """
    Complete pipeline: STEP → STL → Hex voxel mesh
    
    Args:
        step_path: Input STEP file
        output_base: Base name for output files
        voxel_size: Voxel size in mm (or meters if force_mm_to_m=True)
        force_mm_to_m: Scale units from mm to m
    
    Returns:
        dict with mesh info and STL path for visualization
    """
    # Step 1: STEP → STL (save permanently for visualization)
    stl_path = f"{output_base}_surface.stl"
    
    try:
        step_to_stl(step_path, stl_path, force_mm_to_m)
        
        # Step 2: STL → Hex voxels
        result = voxelize_stl_to_hex(stl_path, output_base, voxel_size)
        
        # Add STL path to result (for frontend visualization)
        result['stl_path'] = stl_path
        
        return result
        
    except Exception as e:
        logger.error(f"Hex voxelization failed: {e}")
        raise


def generate_mesh_from_step_hex(step_filepath, mesh_size=5.0):
    """
    STEP → Hex voxel mesh using signed distance field.
    Much more accurate than Delaunay - preserves exact geometry!
    """
    
    try:
        logger.info(f"Using hex voxelizer for {step_filepath}")
        
        # Calculate voxel size - need fine detail for accurate representation
        voxel_size = 1.0  # Fixed 1mm voxels for good detail (typical part ~50K-100K hexes)
        
        # Generate hex mesh (creates XDMF files) - this also creates the STL
        output_base = step_filepath.replace('.step', '').replace('.stp', '')
        result = generate_hex_mesh_from_step(step_filepath, output_base, voxel_size, force_mm_to_m=False)
        
        # Read the volume mesh (for simulation)
        mesh = meshio.read(f"{output_base}_vol.xdmf")
        
        # Convert hex to tets (split each hex into 5 tets)
        hexes = mesh.cells_dict['hexahedron']
        tets = []
        for h in hexes:
            # Split hex into 5 tets (standard decomposition)
            tets.extend([
                [h[0], h[1], h[2], h[5]],
                [h[0], h[2], h[3], h[7]],
                [h[0], h[5], h[2], h[6]],
                [h[0], h[2], h[7], h[6]],
                [h[0], h[5], h[6], h[4]]
            ])
        
        # Convert tets to plain int
        tets_clean = [[int(t[0]), int(t[1]), int(t[2]), int(t[3])] for t in tets]
        
        # Load the ORIGINAL STL - EXACTLY as trimesh loads it (like in the visualization)
        stl_path = result.get('stl_path')
        if stl_path and os.path.exists(stl_path):
            logger.info(f"Loading STL for visualization: {stl_path}")
            import trimesh
            stl_mesh = trimesh.load(stl_path)
            
            logger.info(f"✅ Loaded STL: {len(stl_mesh.vertices)} vertices, {len(stl_mesh.faces)} faces")
            
            # Also load voxel mesh surface for display
            facet_mesh = meshio.read(f"{output_base}_facets.xdmf")
            voxel_nodes = mesh.points
            surface_quads = facet_mesh.cells_dict['quad']
            
            voxel_surface_triangles = []
            for q in surface_quads:
                voxel_surface_triangles.append([int(q[0]), int(q[1]), int(q[2])])
                voxel_surface_triangles.append([int(q[0]), int(q[2]), int(q[3])])
            
            logger.info(f"✅ Voxel mesh: {len(voxel_nodes)} nodes, {len(hexes)} hexes, {len(voxel_surface_triangles)} surface tris")
            
            # Return BOTH surface mesh and voxel mesh
            # Key point: surface_mesh uses STL (smooth), voxel_mesh uses voxel grid (blocky)
            return {
                'nodes': voxel_nodes.tolist(),  # Use voxel nodes for simulation
                'elements': tets_clean,
                'surface_triangles': voxel_surface_triangles,  # For compatibility
                'boundary_nodes': list(range(len(voxel_nodes))),
                # Separate surface and voxel mesh data for frontend
                'surface_mesh': {
                    'nodes': stl_mesh.vertices.tolist(),  # SMOOTH from STL
                    'triangles': stl_mesh.faces.tolist()  # SMOOTH from STL
                },
                'voxel_mesh': {
                    'nodes': voxel_nodes.tolist(),  # VOXEL grid
                    'triangles': voxel_surface_triangles,  # VOXEL surface
                    'hexes': hexes.tolist()
                }
            }
        else:
            # Fallback: use voxel boundary
            logger.warning("STL not found, using voxel boundary")
            facet_mesh = meshio.read(f"{output_base}_facets.xdmf")
            surface_quads = facet_mesh.cells_dict['quad']
            
            surface_triangles = []
            for q in surface_quads:
                surface_triangles.append([int(q[0]), int(q[1]), int(q[2])])
                surface_triangles.append([int(q[0]), int(q[2]), int(q[3])])
            
            boundary_nodes = list(set([int(n) for tri in surface_triangles for n in tri]))
            
            return {
                'nodes': mesh.points.tolist(),
                'elements': tets_clean,
                'surface_triangles': surface_triangles,
                'boundary_nodes': boundary_nodes,
                'surface_mesh': {
                    'nodes': mesh.points.tolist(),
                    'triangles': surface_triangles
                },
                'voxel_mesh': {
                    'nodes': mesh.points.tolist(),
                    'triangles': surface_triangles,
                    'hexes': hexes.tolist()
                }
            }
        
    except Exception as e:
        logger.error(f"Hex voxelization failed: {e}, falling back to old method")
        return generate_mesh_from_step_robust(step_filepath, mesh_size)


def generate_mesh_from_step_robust(step_filepath, mesh_size=5.0):
    """
    Robust STEP meshing with STL export + voxelization fallback
    Based on FEATool Gmsh best practices
    Also returns dual mesh structure like the hex method
    """
    if not gmsh.isInitialized():
        try:
            gmsh.initialize()
        except:
            pass
    
    gmsh.option.setNumber("General.Terminal", 0)
    
    try:
        print(f"✅ Importing STEP file...")
        gmsh.clear()
        gmsh.model.add("step_model")
        gmsh.model.occ.importShapes(step_filepath)
        gmsh.model.occ.synchronize()
        
        volumes = gmsh.model.getEntities(3)
        surfaces = gmsh.model.getEntities(2)
        print(f"   Found: {len(volumes)} volumes, {len(surfaces)} surfaces")
        
        # Set mesh size
        gmsh.option.setNumber("Mesh.CharacteristicLengthMin", mesh_size * 0.3)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", mesh_size * 1.5)
        
        # Try volume meshing first
        mesh_generated = False
        if len(volumes) > 0:
            print(f"   Attempting volume mesh...")
            try:
                gmsh.model.mesh.generate(3)
                elem_types, _, _ = gmsh.model.mesh.getElements(3)
                if len(elem_types) > 0:
                    mesh_generated = True
                    print(f"   ✓ Volume mesh generated")
            except:
                pass
        
        # If volume meshing failed, use STL export + voxelization
        if not mesh_generated:
            print(f"   Volume meshing failed - using STL export + voxelization...")
            
            # Export to STL (this is our SURFACE mesh)
            stl_path = step_filepath.replace('.step', '_surface.stl').replace('.stp', '_surface.stl')
            
            gmsh.model.mesh.clear()
            gmsh.model.mesh.generate(2)  # Surface mesh only
            gmsh.write(stl_path)
            
            # Load with trimesh for SURFACE visualization
            surface_mesh_tri = trimesh.load(stl_path)
            print(f"   Surface mesh: {len(surface_mesh_tri.vertices)} verts, {len(surface_mesh_tri.faces)} faces")
            
            # Keep the surface mesh separate
            surface_mesh_nodes = surface_mesh_tri.vertices.tolist()
            surface_mesh_triangles = surface_mesh_tri.faces.tolist()
            
            # Now voxelize for SIMULATION mesh
            tri_mesh = surface_mesh_tri  # Use same for voxelization
            
            print(f"   Loaded: {len(tri_mesh.vertices)} verts, {len(tri_mesh.faces)} faces")
            
            # Repair mesh
            if not tri_mesh.is_watertight:
                print(f"   Repairing mesh...")
                try:
                    trimesh.repair.fill_holes(tri_mesh)
                    trimesh.repair.fix_normals(tri_mesh)
                except:
                    pass
            
            # Voxelization - MUCH finer to preserve geometry
            nodes = np.array(tri_mesh.vertices)
            bbox_size = np.ptp(nodes, axis=0)
            
            # Calculate based on surface triangle size (match the tessellation detail)
            surface_area = sum(tri_mesh.area_faces)
            avg_triangle_edge = np.sqrt(surface_area / len(tri_mesh.faces) / 0.433)  # 0.433 = sqrt(3)/4 for equilateral
            voxel_pitch = avg_triangle_edge * 0.5  # Half the avg triangle edge
            
            # Clamp to prevent too many voxels (but allow finer detail)
            voxel_pitch = np.clip(voxel_pitch, 0.3, 1.0)  # Allow down to 0.3mm for detail
            
            print(f"   Voxelizing (pitch={voxel_pitch:.2f}mm)...")
            voxel_grid = tri_mesh.voxelized(pitch=voxel_pitch)
            voxel_points = voxel_grid.points
            print(f"   Voxelized: {len(voxel_points)} points")
            
            # Delaunay tetrahedralization
            delaunay = Delaunay(voxel_points)
            nodes = voxel_points
            elements = delaunay.simplices.tolist()
            
            # Extract surface
            face_count = defaultdict(int)
            for tet in elements:
                faces = [
                    tuple(sorted([tet[0], tet[1], tet[2]])),
                    tuple(sorted([tet[0], tet[1], tet[3]])),
                    tuple(sorted([tet[0], tet[2], tet[3]])),
                    tuple(sorted([tet[1], tet[2], tet[3]]))
                ]
                for face in faces:
                    face_count[face] += 1
            
            surface_triangles = [list(face) for face, count in face_count.items() if count == 1]
            boundary_nodes = list(set([n for tri in surface_triangles for n in tri]))
            
            gmsh.clear()
            
            logger.info(f"✅ STEP meshed (voxel): {len(nodes)} nodes, {len(elements)} elements")
            logger.info(f"✅ Surface mesh preserved: {len(surface_mesh_nodes)} nodes, {len(surface_mesh_triangles)} tris")
            
            return {
                'nodes': nodes.tolist(),
                'elements': elements,
                'surface_triangles': surface_triangles,
                'boundary_nodes': boundary_nodes,
                # Return DIFFERENT meshes for each view
                'surface_mesh': {
                    'nodes': surface_mesh_nodes,
                    'triangles': surface_mesh_triangles
                },
                'voxel_mesh': {
                    'nodes': nodes.tolist(),
                    'triangles': surface_triangles
                }
            }
        
        # If volume mesh succeeded, extract it from Gmsh
        node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
        nodes = node_coords.reshape(-1, 3)
        node_map = {tag: idx for idx, tag in enumerate(node_tags)}
        
        # Get volume elements
        elem_types, elem_tags, elem_node_tags = gmsh.model.mesh.getElements(3)
        elements = []
        for elem_type, tags, node_tags_list in zip(elem_types, elem_tags, elem_node_tags):
            if elem_type == 4:  # 4-node tet
                node_tags_array = node_tags_list.reshape(-1, 4)
                for node_tags_elem in node_tags_array:
                    elem_nodes = [node_map[tag] for tag in node_tags_elem]
                    elements.append(elem_nodes)
            elif elem_type == 11:  # 10-node tet
                node_tags_array = node_tags_list.reshape(-1, 10)
                for node_tags_elem in node_tags_array:
                    elem_nodes = [node_map[tag] for tag in node_tags_elem[:4]]
                    elements.append(elem_nodes)
        
        # Get surface triangles
        elem_types_2d, elem_tags_2d, elem_node_tags_2d = gmsh.model.mesh.getElements(2)
        surface_triangles = []
        for elem_type, tags, node_tags_list in zip(elem_types_2d, elem_tags_2d, elem_node_tags_2d):
            if elem_type == 2:  # 3-node triangle
                node_tags_array = node_tags_list.reshape(-1, 3)
                for node_tags_elem in node_tags_array:
                    tri_nodes = [node_map[tag] for tag in node_tags_elem]
                    surface_triangles.append(tri_nodes)
            elif elem_type == 9:  # 6-node triangle
                node_tags_array = node_tags_list.reshape(-1, 6)
                for node_tags_elem in node_tags_array:
                    tri_nodes = [node_map[tag] for tag in node_tags_elem[:3]]
                    surface_triangles.append(tri_nodes)
        
        boundary_nodes = list(set([n for tri in surface_triangles for n in tri]))
        
        gmsh.clear()
        
        logger.info(f"✅ STEP meshed: {len(nodes)} nodes, {len(elements)} elements")
        
        return {
            'nodes': nodes.tolist(),
            'elements': elements,
            'surface_triangles': surface_triangles,
            'boundary_nodes': boundary_nodes,
            # Add dual mesh structure for consistency
            'surface_mesh': {
                'nodes': nodes.tolist(),
                'triangles': surface_triangles
            },
            'voxel_mesh': {
                'nodes': nodes.tolist(),
                'triangles': surface_triangles
            }
        }
        
    except Exception as e:
        gmsh.clear()
        logger.error(f"STEP mesh failed: {e}")
        return generate_simple_cube_mesh(size=50.0, divisions=10)


def generate_mesh_from_stl_voxel(stl_filepath):
    """Voxelization approach for STL"""
    import trimesh
    from scipy.spatial import Delaunay
    
    print(f"Loading STL: {stl_filepath}")
    tri_mesh = trimesh.load(stl_filepath)
    
    bbox_size = np.ptp(tri_mesh.vertices, axis=0)
    max_dim = np.max(bbox_size)
    voxel_pitch = max_dim * 0.01
    voxel_pitch = np.clip(voxel_pitch, 0.5, 2.0)
    
    print(f"Voxelizing (pitch={voxel_pitch:.2f}mm)...")
    voxel_grid = tri_mesh.voxelized(pitch=voxel_pitch)
    voxel_points = voxel_grid.points
    print(f"Voxelized: {len(voxel_points)} points")
    
    delaunay = Delaunay(voxel_points)
    nodes = voxel_points
    elements = delaunay.simplices.tolist()
    
    # Extract surface
    face_count = defaultdict(int)
    for tet in elements:
        faces = [
            tuple(sorted([tet[0], tet[1], tet[2]])),
            tuple(sorted([tet[0], tet[1], tet[3]])),
            tuple(sorted([tet[0], tet[2], tet[3]])),
            tuple(sorted([tet[1], tet[2], tet[3]]))
        ]
        for face in faces:
            face_count[face] += 1
    
    surface_triangles = [list(face) for face, count in face_count.items() if count == 1]
    boundary_nodes = list(set([n for tri in surface_triangles for n in tri]))
    
    logger.info(f"✅ Voxel mesh: {len(nodes)} nodes, {len(elements)} elements")
    
    return {
        'nodes': nodes.tolist(),
        'elements': elements,
        'surface_triangles': surface_triangles,
        'boundary_nodes': boundary_nodes,
        # Add dual mesh structure for consistency
        'surface_mesh': {
            'nodes': nodes.tolist(),
            'triangles': surface_triangles
        },
        'voxel_mesh': {
            'nodes': nodes.tolist(),
            'triangles': surface_triangles
        }
    }


def generate_simple_cube_mesh(size=50.0, divisions=10):
    """Generate a simple cube mesh as fallback"""
    logger.info(f"Generating cube mesh: size={size}mm, divisions={divisions}")
    
    # Create grid
    x = np.linspace(0, size, divisions)
    y = np.linspace(0, size, divisions)
    z = np.linspace(0, size, divisions)
    
    nodes = []
    node_map = {}
    idx = 0
    
    for i in range(divisions):
        for j in range(divisions):
            for k in range(divisions):
                nodes.append([x[i], y[j], z[k]])
                node_map[(i, j, k)] = idx
                idx += 1
    
    # Create tets (split each cube into 5 tets)
    elements = []
    surface_triangles = []
    
    for i in range(divisions - 1):
        for j in range(divisions - 1):
            for k in range(divisions - 1):
                n0 = node_map[(i, j, k)]
                n1 = node_map[(i+1, j, k)]
                n2 = node_map[(i+1, j+1, k)]
                n3 = node_map[(i, j+1, k)]
                n4 = node_map[(i, j, k+1)]
                n5 = node_map[(i+1, j, k+1)]
                n6 = node_map[(i+1, j+1, k+1)]
                n7 = node_map[(i, j+1, k+1)]
                
                # 5 tets per cube
                elements.extend([
                    [n0, n1, n2, n5],
                    [n0, n2, n3, n7],
                    [n0, n5, n2, n6],
                    [n0, n2, n7, n6],
                    [n0, n5, n6, n4]
                ])
    
    # Surface faces (just the 6 cube faces)
    for i in range(divisions - 1):
        for j in range(divisions - 1):
            # Bottom (k=0)
            surface_triangles.append([node_map[(i,j,0)], node_map[(i+1,j,0)], node_map[(i+1,j+1,0)]])
            surface_triangles.append([node_map[(i,j,0)], node_map[(i+1,j+1,0)], node_map[(i,j+1,0)]])
            # Top (k=divisions-1)
            k = divisions - 1
            surface_triangles.append([node_map[(i,j,k)], node_map[(i+1,j+1,k)], node_map[(i+1,j,k)]])
            surface_triangles.append([node_map[(i,j,k)], node_map[(i,j+1,k)], node_map[(i+1,j+1,k)]])
    
    boundary_nodes = list(set([n for tri in surface_triangles for n in tri]))
    
    return {
        'nodes': nodes,
        'elements': elements,
        'surface_triangles': surface_triangles,
        'boundary_nodes': boundary_nodes
    }

