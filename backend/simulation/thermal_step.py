import numpy as np
from scipy.sparse import lil_matrix, csr_matrix
from scipy.sparse.linalg import spsolve
from .materials import effective_cp


def step_temperature(mesh, boundary_nodes, Tn, params):
	# Assemble implicit step with cp_eff(T)
	n_nodes = len(mesh['nodes'])
	A = lil_matrix((n_nodes, n_nodes))
	b = np.zeros(n_nodes)

	# Precompute per-node effective cp using Tn (Picard iteration single pass)
	cp_base = params.get('cp', 900.0)
	L = params.get('L', 3.5e5)
	Tsol = params.get('T_sol', 555.0)
	Tliq = params.get('T_liq', 615.0)
	rho = params.get('rho', 2700.0)
	k_val = params.get('k', 120.0)
	dt = params.get('dt', 0.5)
	T_inf = params.get('T_inf', 300.0)
	h = params.get('h', 300.0)

	C_eff = np.array([effective_cp(Ti, cp_base, L, Tsol, Tliq) for Ti in Tn])

	# Build crude mass and stiffness approximations using volumes per node
	vol_per_node = np.zeros(n_nodes)
	for elem in mesh['elements']:
		coords = np.array([mesh['nodes'][i] for i in elem])
		vol = _tetra_volume(coords)
		share = vol / 4.0
		for i in elem:
			vol_per_node[i] += share

	# Diagonal mass and simple laplacian surrogate (lumped)
	for i in range(n_nodes):
		mii = rho * C_eff[i] * vol_per_node[i]
		A[i, i] += mii / dt
		b[i] += mii * Tn[i] / dt

	# Very simple diffusion coupling: connect element nodes equally
	for elem in mesh['elements']:
		for i in range(4):
			for j in range(4):
				if i == j:
					continue
				ni = elem[i]
				nj = elem[j]
				A[ni, nj] += -k_val
				A[ni, ni] += k_val

	# Robin boundary
	if boundary_nodes:
		for i in boundary_nodes:
			A[i, i] += h
			b[i] += h * T_inf

	Tnp1 = spsolve(csr_matrix(A), b)

	return Tnp1


def _tetra_volume(coords):
	v1 = coords[1] - coords[0]
	v2 = coords[2] - coords[0]
	v3 = coords[3] - coords[0]
	return abs(np.dot(v1, np.cross(v2, v3))) / 6.0


