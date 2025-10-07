import numpy as np
from typing import Dict, Any, List


def detect_hotspots(t_solid: np.ndarray, niyama: np.ndarray, alpha: float = 0.85, beta: float = 0.15) -> List[Dict[str, Any]]:
	# Normalize fields
	ts = (t_solid - np.min(t_solid)) / max(np.ptp(t_solid), 1e-9)
	N = niyama
	N = (N - np.min(N)) / max(np.ptp(N), 1e-9)

	# Combined score: late freeze high, low Niyama high
	score = alpha * ts + (1.0 - alpha) * (1.0 - N)
	thr = np.quantile(score, 0.85)
	mask = score >= thr

	# Simple clustering via proximity on indices (placeholder)
	indices = np.where(mask)[0]
	clusters = []
	if indices.size == 0:
		return clusters

	visited = np.zeros_like(mask, dtype=bool)
	for idx in indices:
		if visited[idx]:
			continue
		# BFS over 1D neighbors as a placeholder; real impl should use mesh adjacency
		queue = [idx]
		comp = []
		visited[idx] = True
		while queue:
			u = queue.pop()
			comp.append(u)
			for v in (u - 1, u + 1):
				if 0 <= v < mask.size and mask[v] and not visited[v]:
					visited[v] = True
					queue.append(v)
		centroid_idx = int(np.mean(comp))
		clusters.append({
			'id': len(clusters),
			'indices': comp,
			'centroid_index': centroid_idx,
			'severity': float(np.mean(score[comp]))
		})

	# Sort by severity
	clusters.sort(key=lambda c: c['severity'], reverse=True)
	return clusters


