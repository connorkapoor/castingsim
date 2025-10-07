import numpy as np
from typing import Dict, Any


def estimate_thickness(mesh: Dict[str, Any]) -> np.ndarray:
	# Quick proxy: distance to surface via nearest surface vertex pair (very rough)
	nodes = np.array(mesh['nodes'])
	surf_nodes = np.unique(np.array(mesh.get('surface_triangles', [])).flatten()) if mesh.get('surface_triangles') else np.arange(len(nodes))
	if len(surf_nodes) == 0:
		return np.full(len(nodes), 10.0)
	from scipy.spatial import cKDTree
	tree = cKDTree(nodes[surf_nodes])
	dist, _ = tree.query(nodes, k=1)
	return 2.0 * dist  # approximate local thickness


def nearest_surface_point_along_gradient(x0: np.ndarray, grad_ts: np.ndarray, surface_tree):
	# Placeholder: just return the nearest surface point
	_, idx = surface_tree.query(x0)
	return surface_tree.data[idx]


