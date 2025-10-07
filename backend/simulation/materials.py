from dataclasses import dataclass
import numpy as np


@dataclass
class Alloy:
	T_liq: float
	T_sol: float
	L: float
	k: float
	rho: float
	cp: float


def fs(T: np.ndarray, Tsol: float, Tliq: float) -> np.ndarray:
	return np.clip((Tliq - T) / max(Tliq - Tsol, 1e-9), 0.0, 1.0)


def effective_cp(T_val: float, cp: float, L: float, Tsol: float, Tliq: float) -> float:
	if Tsol < T_val < Tliq:
		dfdT = -1.0 / max(Tliq - Tsol, 1e-9)
		return cp + L * dfdT
	return cp


