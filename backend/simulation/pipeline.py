import os
import json
import numpy as np
from typing import Dict, Any
from .mesh_io import mesh_from_stl, mesh_from_path
from .materials import Alloy
from .simulate import run_sim
from .hotspots import detect_hotspots
from .gating import surface_candidates


def analyze_cast(stl_path: str, alloy_json: Dict[str, Any], bc_json: Dict[str, Any], time_json: Dict[str, Any], outdir: str):
	# Accept both STL and STEP via unified loader
	mesh, facets = mesh_from_path(stl_path, h_min=bc_json.get('h_min', 5.0), h_max=bc_json.get('h_max', 15.0))
	alloy = Alloy(
		T_liq=float(alloy_json['T_liq']),
		T_sol=float(alloy_json['T_sol']),
		L=float(alloy_json['L']),
		k=float(alloy_json['k']),
		rho=float(alloy_json['rho']),
		cp=float(alloy_json['cp']),
	)
	fields = run_sim(mesh, facets, alloy, bc_json, time_json)
	clusters = detect_hotspots(fields['t_solid'], fields['min_niyama'])
	gates = surface_candidates(mesh, fields['t_solid'], clusters, min_thickness=bc_json.get('min_gate_diam', 8.0))

	# Export minimal JSON outputs
	os.makedirs(outdir, exist_ok=True)
	with open(os.path.join(outdir, 'fields.json'), 'w') as f:
		json.dump({
			'T_final': fields['T_final'].tolist(),
			't_solid': fields['t_solid'].tolist(),
			'min_niyama': fields['min_niyama'].tolist(),
			'last_to_freeze_idx': fields['last_to_freeze_idx'],
		}, f)
	with open(os.path.join(outdir, 'clusters.json'), 'w') as f:
		json.dump(clusters, f)
	with open(os.path.join(outdir, 'gates.json'), 'w') as f:
		json.dump(gates, f)

	# Write VTU for ParaView
	_write_vtu(os.path.join(outdir, 'fields.vtu'), mesh, fields)

	return {
		'clusters': clusters,
		'gates': gates
	}


def _write_vtu(filepath: str, mesh: Dict[str, Any], fields: Dict[str, Any]):
	try:
		import meshio
		points = np.array(mesh['nodes'], dtype=float)
		# mesh elements are tets with 4 nodes
		cells = [("tetra", np.array(mesh['elements'], dtype=int))]
		point_data = {
			"T_final": np.array(fields['T_final'], dtype=float),
			"t_solid": np.array(fields['t_solid'], dtype=float),
			"min_niyama": np.array(fields['min_niyama'], dtype=float),
		}
		meshio.write_points_cells(
			filepath,
			points,
			cells,
			point_data=point_data,
		)
	except Exception:
		# Silently skip VTU export if meshio or writing fails
		return


