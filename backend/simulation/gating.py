import numpy as np
from typing import Dict, Any, List


def surface_candidates(mesh: Dict[str, Any], t_solid: np.ndarray, clusters: List[Dict[str, Any]], min_thickness: float = 5.0):
	nodes = np.array(mesh['nodes'])
	surf_tris = mesh.get('surface_triangles', [])

	# Estimate naive normals per triangle and per-vertex
	tri_normals = []
	for tri in surf_tris:
		p0, p1, p2 = nodes[tri[0]], nodes[tri[1]], nodes[tri[2]]
		n = np.cross(p1 - p0, p2 - p0)
		n_norm = np.linalg.norm(n) or 1.0
		tri_normals.append(n / n_norm)

	vertex_normal = np.zeros_like(nodes)
	for tri, n in zip(surf_tris, tri_normals):
		for vid in tri:
			vertex_normal[vid] += n
	vn_norm = np.linalg.norm(vertex_normal, axis=1)
	mask = vn_norm > 0
	vertex_normal[mask] = (vertex_normal[mask].T / vn_norm[mask]).T

	gates = []
	for cl in clusters:
		indices = cl['indices']
		# pick node with maximal t_solid in cluster
		idx = indices[int(np.argmax(t_solid[indices]))]
		# march towards surface by following gradient ascent of t_solid (1D placeholder)
		cand = idx
		for _ in range(10):
			next_idx = min(max(cand + 1, 0), len(t_solid) - 1)
			if t_solid[next_idx] >= t_solid[cand]:
				cand = next_idx
			else:
				break
		point = nodes[cand].tolist() if 0 <= cand < len(nodes) else nodes[idx].tolist()
		normal = vertex_normal[cand].tolist() if 0 <= cand < len(nodes) else [0.0, 0.0, 1.0]

		gates.append({
			'point': point,
			'normal': normal,
			'pad_diam': float(max(min_thickness * 1.2, 5.0)),
			'feeds_cluster_id': cl['id']
		})

	return gates


