import numpy as np
from typing import Tuple, Dict, Any


def mesh_from_stl(stl_path: str, h_min: float = 5.0, h_max: float = 15.0) -> Tuple[Dict[str, Any], Dict[str, Any]]:

	try:
		from .mesher import generate_mesh_from_stl
		mesh = generate_mesh_from_stl(stl_path, mesh_size=max(h_min, (h_min + h_max) * 0.5))
		facets = {
			"boundary_nodes": mesh.get("boundary_nodes", []),
			"surface_triangles": mesh.get("surface_triangles", []),
		}
		return mesh, facets
	except Exception:
		# Fallback to simple cube
		from .mesher import generate_simple_cube_mesh
		mesh = generate_simple_cube_mesh(size=50.0, divisions=10)
		facets = {
			"boundary_nodes": mesh.get("boundary_nodes", []),
			"surface_triangles": mesh.get("surface_triangles", []),
		}
		return mesh, facets


def mesh_from_path(path: str, h_min: float = 5.0, h_max: float = 15.0) -> Tuple[Dict[str, Any], Dict[str, Any]]:
	# Route to STL or STEP meshing using existing mesher
	from .mesher import generate_mesh
	mesh = generate_mesh(path, mesh_size=max(h_min, (h_min + h_max) * 0.5))
	facets = {
		"boundary_nodes": mesh.get("boundary_nodes", []),
		"surface_triangles": mesh.get("surface_triangles", []),
	}
	return mesh, facets


