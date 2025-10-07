import numpy as np
from typing import Dict, Any
from .materials import Alloy, fs
from .thermal_step import step_temperature


def run_sim(mesh: Dict[str, Any], facets: Dict[str, Any], alloy: Alloy, bc: Dict[str, Any], time_cfg: Dict[str, Any]):
	# Initialize temperature field
	n_nodes = len(mesh['nodes'])
	T0 = float(bc.get('T0', alloy.T_liq + 30.0))
	T_inf = float(bc.get('T_inf', 300.0))
	h = float(bc.get('h', 300.0))
	dt = float(time_cfg.get('dt', 0.5))
	t_end = float(time_cfg.get('t_end', 60.0))

	T = np.full(n_nodes, T0, dtype=float)
	T_prev = T.copy()

	# Outputs
	t_solid = np.full(n_nodes, np.inf)
	min_niyama = np.full(n_nodes, np.inf)

	n_steps = int(np.ceil(t_end / max(dt, 1e-9)))
	for step in range(n_steps):
		params = {
			'cp': alloy.cp,
			'L': alloy.L,
			'T_sol': alloy.T_sol,
			'T_liq': alloy.T_liq,
			'rho': alloy.rho,
			'k': alloy.k,
			'dt': dt,
			'T_inf': T_inf,
			'h': h,
		}
		T_new = step_temperature(mesh, facets.get('boundary_nodes', []), T, params)

		# Derived fields
		cooling_rate = (T_new - T) / max(dt, 1e-9)
		# gradient magnitude (simple per-element estimate averaged to nodes)
		G = _estimate_gradient_magnitude(mesh, T_new)
		niyama = G / (np.abs(cooling_rate) + 1e-9)

		# Solid fraction and time-to-solid
		fsol = fs(T_new, alloy.T_sol, alloy.T_liq)
		solid_mask = (fsol >= 1.0) & np.isinf(t_solid)
		t_solid[solid_mask] = (step + 1) * dt

		# Track min Niyama late in solidification
		in_mushy = (T_new <= alloy.T_liq) & (T_new >= alloy.T_sol)
		min_niyama[in_mushy] = np.minimum(min_niyama[in_mushy], niyama[in_mushy])

		T_prev = T
		T = T_new

	# Replace infs
	t_solid[np.isinf(t_solid)] = t_end
	min_niyama[np.isinf(min_niyama)] = np.max(min_niyama[~np.isinf(min_niyama)]) if np.any(~np.isinf(min_niyama)) else 0.0

	return {
		'T_final': T,
		't_solid': t_solid,
		'min_niyama': min_niyama,
		'last_to_freeze_idx': int(np.argmax(t_solid)),
	}


def _estimate_gradient_magnitude(mesh, T_vec):
	n_nodes = len(mesh['nodes'])
	acc = np.zeros(n_nodes)
	cnt = np.zeros(n_nodes)
	for elem in mesh['elements']:
		Te = T_vec[elem]
		coords = np.array([mesh['nodes'][i] for i in elem])
		dT = float(np.max(Te) - np.min(Te))
		size = float(np.max(np.linalg.norm(coords[:, None] - coords, axis=2)))
		g = dT / max(size, 1e-9)
		for i in elem:
			acc[i] += g
			cnt[i] += 1.0
	mask = cnt > 0
	G = np.zeros(n_nodes)
	G[mask] = acc[mask] / cnt[mask]
	return G


