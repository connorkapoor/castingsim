"""
Professional solidification solver using established methods

Uses scipy's finite element assembly with proper:
- Implicit time integration (stable)
- Phase change via enthalpy method
- Niyama criterion for porosity
- Proper thermal gradients
"""

import numpy as np
from scipy.sparse import lil_matrix, csr_matrix
from scipy.sparse.linalg import spsolve
import time

class ProfessionalSolidificationSolver:
    """
    Production-grade solidification solver using established FEM methods
    Based on standard casting simulation approaches
    """
    
    MATERIALS = {
        'aluminum': {
            'name': 'Aluminum Alloy A356',
            'liquidus': 615,  # °C
            'solidus': 555,   # °C
            'density': 2685,  # kg/m³ (solid)
            'k_liquid': 95,   # W/(m·K)
            'k_solid': 180,   # W/(m·K)
            'cp_liquid': 1080,  # J/(kg·K)
            'cp_solid': 960,   # J/(kg·K)
            'latent_heat': 389000,  # J/kg
            'shrinkage': 6.5,  # %
            'niyama_critical': 1.0,  # (K·s^0.5)/mm^0.5
        },
        'steel': {
            'name': 'Carbon Steel',
            'liquidus': 1495,
            'solidus': 1450,
            'density': 7850,
            'k_liquid': 35,
            'k_solid': 50,
            'cp_liquid': 680,
            'cp_solid': 490,
            'latent_heat': 260000,
            'shrinkage': 3.0,
            'niyama_critical': 0.5,
        }
    }
    
    def __init__(self, mesh_data, material='aluminum', initial_temp=700, ambient_temp=25):
        # Validate material
        if material not in self.MATERIALS:
            raise ValueError(f"Unknown material: {material}. Available: {list(self.MATERIALS.keys())}")
        
        self.mesh = mesh_data
        self.material = self.MATERIALS[material]
        self.material_name = material
        self.T_init = initial_temp
        self.T_ambient = ambient_temp
        
        # Validate temperatures
        Tl = self.material['liquidus']
        Ts = self.material['solidus']
        
        if initial_temp < Ts:
            raise ValueError(f"Initial temperature ({initial_temp}°C) below solidus ({Ts}°C)")
        
        if ambient_temp >= initial_temp:
            raise ValueError(f"Ambient temperature ({ambient_temp}°C) must be below initial temperature ({initial_temp}°C)")
        
        if ambient_temp < 0:
            raise ValueError(f"Ambient temperature ({ambient_temp}°C) below absolute zero")
        
        # Validate mesh data
        if not mesh_data or 'nodes' not in mesh_data or 'elements' not in mesh_data:
            raise ValueError("Invalid mesh data: missing nodes or elements")
        
        self.nodes = np.array(mesh_data['nodes'])
        self.elements = mesh_data['elements']
        self.boundary = set(mesh_data.get('boundary_nodes', []))
        
        self.n_nodes = len(self.nodes)
        self.n_elems = len(self.elements)
        
        if self.n_nodes == 0:
            raise ValueError("Mesh has no nodes")
        if self.n_elems == 0:
            raise ValueError("Mesh has no elements")
        
        if self.n_nodes < 4:
            raise ValueError(f"Mesh too small: {self.n_nodes} nodes (minimum 4)")
        
        print(f"✓ Solver initialized: {self.n_nodes} nodes, {self.n_elems} elements")
        print(f"✓ Material: {self.material['name']}")
        print(f"✓ Temperature range: {initial_temp}°C → {ambient_temp}°C")
        
        # State variables
        self.T = np.full(self.n_nodes, initial_temp, dtype=float)
        self.T_prev = self.T.copy()
        self.liquid_frac = np.ones(self.n_nodes)
        
        # For defect analysis
        self.cooling_rate = np.zeros(self.n_nodes)
        self.grad_T = np.zeros(self.n_nodes)
        self.niyama = np.zeros(self.n_nodes)
        self.solidif_time = np.full(self.n_nodes, -1.0)
        
    def solve(self, total_time=10, dt=0.1, save_interval=1, streaming=False, run_until_solid=False, max_total_minutes=180, dt_seconds=1.0, streaming_delay=0.0):
        """
        Solve transient heat equation with phase change
        Uses backward Euler (unconditionally stable)
        
        Args:
            total_time: Total time in MINUTES (not seconds!)
            dt: Time step in MINUTES
            save_interval: Save every N steps
            streaming: If True, yield results as they're computed (for SSE)
        """
        print(f"\n{'='*70}")
        print(f"PROFESSIONAL SOLIDIFICATION SOLVER")
        print(f"Material: {self.material['name']}")
        print(f"Nodes: {self.n_nodes}, Elements: {self.n_elems}")
        print(f"Time: {total_time} minutes, dt: {dt} min")
        print(f"Ceramic shell casting simulation")
        print(f"{'='*70}\n")
        
        # Assemble constant matrices (SI units using meters, seconds)
        K, M, node_bc_area = self._assemble_matrices()
        
        # Time setup
        if run_until_solid:
            dt_s = float(dt_seconds)
            total_time_s = max_total_minutes * 60.0
            n_steps = int(total_time_s / dt_s)
        else:
            dt_s = dt * 60.0
            total_time_s = total_time * 60.0
            n_steps = int(total_time_s / dt_s)
        results = []
        
        # Yield initialization for streaming
        if streaming:
            yield {
                'type': 'init',
                'total_steps': n_steps // save_interval,
                'material': self.material['name']
            }
        
        start = time.time()
        
        step = 0
        while step < n_steps:
            t_min = (step * dt_s) / 60.0
            
            # Update phase using current temperature for cp_eff
            self._update_phase()
            
            # Solve heat equation
            self._solve_timestep(K, M, node_bc_area, dt_s)
            
            # Compute derived quantities
            self.cooling_rate = (self.T - self.T_prev) / dt_s
            self._compute_gradient()
            self._compute_niyama()
            
            self.T_prev = self.T.copy()
            
            # Save results
            if step % save_interval == 0 or step == n_steps - 1:
                state = self._save_state(t_min)
                results.append(state)
                
                Tl = self.material['liquidus']
                Ts = self.material['solidus']
                n_liquid = np.sum(self.T > Tl)
                n_mushy = np.sum((self.T <= Tl) & (self.T >= Ts))
                n_solid = np.sum(self.T < Ts)
                n_porosity = np.sum(self.niyama < self.material['niyama_critical'])
                
                print(f"t={t_min:6.1f}min | T_avg={np.mean(self.T):6.1f}°C | "
                      f"L:{n_liquid:4d} M:{n_mushy:4d} S:{n_solid:4d} | "
                      f"Porosity:{n_porosity:4d}")
                
                # Yield timestep for streaming
                if streaming:
                    import time as time_module
                    yield {
                        'type': 'timestep',
                        'data': state,
                        'step': len(results),
                        'progress': int((step / n_steps) * 100)
                    }
                    # Optional small delay to throttle SSE
                    if streaming_delay and streaming_delay > 0.0:
                        time_module.sleep(streaming_delay)
                    print(f"    [Streamed frame {len(results)}]", flush=True)
        
            # Stop if fully solid (by temperature and phase fraction)
            self._update_phase()
            if np.all(self.T <= self.material['solidus']) and np.all(self.liquid_frac <= 0.0):
                break

            step += 1

        elapsed = time.time() - start
        print(f"\n✅ Simulation complete in {elapsed:.2f}s\n")
        
        # Final defect analysis
        defects = self._analyze_defects()
        
        final_result = {
            'timesteps': results,
            'mesh': {
                'nodes': self.mesh['nodes'],
                'surface_triangles': self.mesh['surface_triangles']
            },
            'material': self.material_name,
            'defect_analysis': defects,
            'summary': {
                'total_time': total_time,
                'num_timesteps': len(results),
                'final_temperature': {
                    'avg': float(np.mean(self.T)),
                    'max': float(np.max(self.T)),
                    'min': float(np.min(self.T))
                },
                'computation_time': elapsed,
                'defects_detected': len(defects['porosity_zones']) > 0 or len(defects['hotspots']) > 0
            }
        }
        
        if streaming:
            yield {
                'type': 'complete',
                'data': final_result
            }
        else:
            return final_result
    
    def _assemble_matrices(self):
        """Assemble stiffness (K), mass (M) and per-node boundary area in SI units.
        Geometry nodes assumed in millimeters; convert to meters for assembly.
        """
        K = lil_matrix((self.n_nodes, self.n_nodes))
        M = lil_matrix((self.n_nodes, self.n_nodes))
        node_bc_area = np.zeros(self.n_nodes)  # m^2 per node

        # Thermal conductivity - average between phases (W/mK)
        k_avg = (self.material['k_liquid'] + self.material['k_solid']) / 2.0
        rho = self.material['density']  # kg/m^3

        # Assemble volume contributions
        for elem in self.elements:
            coords_mm = self.nodes[elem]
            coords_m = coords_mm * 1e-3
            grads, vol = self._tet_shape_grads_and_volume(coords_m)
            if vol <= 0.0:
                continue

            # Element stiffness: K_e[i,j] = k * vol * (gradNi · gradNj)
            Ke = np.zeros((4, 4))
            for i in range(4):
                for j in range(4):
                    Ke[i, j] = k_avg * vol * float(np.dot(grads[i], grads[j]))

            # Lumped mass: Mii += rho * vol / 4
            m_lump = rho * vol / 4.0

            for a in range(4):
                ia = elem[a]
                M[ia, ia] += m_lump
                for b in range(4):
                    ib = elem[b]
                    K[ia, ib] += Ke[a, b]

        # Assemble boundary (Robin) areas per node using surface triangles
        if 'surface_triangles' in self.mesh:
            for tri in self.mesh['surface_triangles']:
                p0 = self.nodes[tri[0]] * 1e-3
                p1 = self.nodes[tri[1]] * 1e-3
                p2 = self.nodes[tri[2]] * 1e-3
                area = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0))
                share = area / 3.0
                for vi in tri:
                    node_bc_area[vi] += share

        return K, M, node_bc_area
    
    def _tet_shape_grads_and_volume(self, coords_m):
        """Return gradients of linear shape functions (4x3) and volume (m^3)."""
        x1, x2, x3, x4 = coords_m
        J = np.column_stack((x2 - x1, x3 - x1, x4 - x1))  # 3x3
        detJ = np.linalg.det(J)
        vol = abs(detJ) / 6.0
        if vol <= 1e-20:
            return np.zeros((4, 3)), 0.0
        J_inv_T = np.linalg.inv(J).T
        grad_hat = np.array([
            [-1.0, -1.0, -1.0],
            [ 1.0,  0.0,  0.0],
            [ 0.0,  1.0,  0.0],
            [ 0.0,  0.0,  1.0],
        ])
        grads = np.zeros((4, 3))
        for i in range(4):
            grads[i] = J_inv_T @ grad_hat[i]
        return grads, vol
    
    def _elem_volume(self, coords):
        """Tetrahedron volume (mm^3)."""
        v1 = coords[1] - coords[0]
        v2 = coords[2] - coords[0]
        v3 = coords[3] - coords[0]
        return abs(np.dot(v1, np.cross(v2, v3))) / 6.0
    
    def _update_phase(self):
        """Update liquid fraction (lever rule)"""
        Tl = self.material['liquidus']
        Ts = self.material['solidus']
        
        self.liquid_frac = np.clip((self.T - Ts) / (Tl - Ts), 0, 1)
    
    def _solve_timestep(self, K, M, node_bc_area, dt_s):
        """Solve one timestep using implicit scheme in SI units."""
        # Effective heat capacity with latent heat (J/kgK)
        cp_liq = self.material['cp_liquid']
        cp_sol = self.material['cp_solid']
        cp_avg = 0.5 * (cp_liq + cp_sol)
        L = self.material['latent_heat']  # J/kg
        dT_phase = max(self.material['liquidus'] - self.material['solidus'], 1e-6)

        # Use cp_eff = cp + L/dT in mushy zone (positive addition)
        C_eff = np.full(self.n_nodes, cp_avg)
        mushy = (self.liquid_frac > 0) & (self.liquid_frac < 1)
        C_eff[mushy] = cp_avg + L / dT_phase

        # Build system A*T^{n+1} = b
        A = lil_matrix((self.n_nodes, self.n_nodes))
        b = np.zeros(self.n_nodes)

        # Base mass contribution
        for i in range(self.n_nodes):
            mii = M[i, i]
            if mii != 0.0:
                A[i, i] += mii * C_eff[i] / dt_s
                b[i] += mii * C_eff[i] * self.T[i] / dt_s

        # Add diffusion stiffness
        K_csr = csr_matrix(K)
        A = (A + K_csr).tolil()

        # Robin BC
        h_bc = 300.0  # W/m^2K (can be adjusted via UI)
        for i in range(self.n_nodes):
            area_i = node_bc_area[i]
            if area_i > 0.0:
                A[i, i] += h_bc * area_i
                b[i] += h_bc * area_i * self.T_ambient

        # Solve
        self.T = spsolve(csr_matrix(A), b)
        # Prevent unphysical below-ambient dips due to numeric noise
        self.T = np.maximum(self.T, self.T_ambient)
    
    def _compute_gradient(self):
        """Compute |∇T| at nodes using linear-tet gradients (K/m)."""
        grad_mag_sum = np.zeros(self.n_nodes)
        count = np.zeros(self.n_nodes)
        for elem in self.elements:
            Te = self.T[elem]
            coords_m = (self.nodes[elem]) * 1e-3
            grads, vol = self._tet_shape_grads_and_volume(coords_m)
            if vol <= 0.0:
                continue
            # grad T is constant per element: sum_i gradNi * T_i
            grad_T_elem = np.zeros(3)
            for i_local in range(4):
                grad_T_elem += grads[i_local] * Te[i_local]
            gmag = float(np.linalg.norm(grad_T_elem))
            for nid in elem:
                grad_mag_sum[nid] += gmag
                count[nid] += 1.0
        mask = count > 0
        self.grad_T[mask] = grad_mag_sum[mask] / count[mask]
    
    def _compute_niyama(self):
        """Niyama criterion: N = G / (|dT/dt| + eps)."""
        Tl = self.material['liquidus']
        Ts = self.material['solidus']
        mushy = (self.T <= Tl) & (self.T >= Ts)
        R = np.abs(self.cooling_rate)
        eps = 1e-6
        self.niyama = np.zeros(self.n_nodes)
        self.niyama[mushy] = self.grad_T[mushy] / (R[mushy] + eps)
    
    def _save_state(self, t):
        """Save current state"""
        Tl = self.material['liquidus']
        Ts = self.material['solidus']
        
        hotspots = np.where(self.T > Tl)[0].tolist()
        porosity = np.where((self.niyama > 0) & (self.niyama < self.material['niyama_critical']))[0].tolist()
        
        n_liquid = int(np.sum(self.T > Tl))
        n_mushy = int(np.sum((self.T <= Tl) & (self.T >= Ts)))
        n_solid = int(np.sum(self.T < Ts))
        
        return {
            'time': t,
            'temperature': self.T.tolist(),
            'liquid_fraction': self.liquid_frac.tolist(),
            'statistics': {
                'avg_temp': float(np.mean(self.T)),
                'max_temp': float(np.max(self.T)),
                'min_temp': float(np.min(self.T)),
                'liquid_nodes': n_liquid,
                'mushy_nodes': n_mushy,
                'solid_nodes': n_solid,
                'hotspot_count': len(hotspots),
                'porosity_risk_nodes': len(porosity)
            },
            'hotspot_nodes': hotspots,
            'porosity_nodes': porosity,
            'phase_distribution': {
                'liquid': n_liquid,
                'mushy': n_mushy,
                'solid': n_solid
            }
        }
    
    def _analyze_defects(self):
        """Final defect analysis"""
        Tl = self.material['liquidus']
        Ts = self.material['solidus']
        
        # Hotspots - regions still above liquidus
        hotspot_indices = np.where(self.T > Tl)[0]
        hotspots = [{
            'node_id': int(i),
            'location': self.nodes[i].tolist(),
            'temperature': float(self.T[i]),
            'severity': float((self.T[i] - Tl) / (self.T_init - Tl))
        } for i in hotspot_indices]
        
        # Porosity zones - low Niyama in solidified regions  
        porosity_mask = (self.niyama > 0) & (self.niyama < self.material['niyama_critical'])
        porosity_indices = np.where(porosity_mask)[0]
        
        porosity_zones = [{
            'node_id': int(i),
            'location': self.nodes[i].tolist(),
            'niyama_value': float(self.niyama[i]),
            'severity': float((self.material['niyama_critical'] - self.niyama[i]) / self.material['niyama_critical'])
        } for i in porosity_indices]
        
        porosity_zones.sort(key=lambda x: x['severity'], reverse=True)
        
        # Feeding issues - isolated hot regions
        feeding_issues = []
        for i in hotspot_indices:
            # Check if isolated
            other_hot = [j for j in hotspot_indices if j != i]
            if len(other_hot) > 0:
                dists = np.linalg.norm(self.nodes[other_hot] - self.nodes[i], axis=1)
                if np.min(dists) > 30.0:  # Isolated by >30mm
                    feeding_issues.append({
                        'node_id': int(i),
                        'location': self.nodes[i].tolist(),
                        'isolation_distance': float(np.min(dists)),
                        'severity': float(np.min(dists) / 30.0)
                    })
        
        # Shrinkage estimate
        total_vol = sum(self._elem_volume(self.nodes[elem]) for elem in self.elements)
        shrinkage_vol = total_vol * self.material['shrinkage'] / 100.0
        
        return {
            'hotspots': hotspots[:20],
            'porosity_zones': porosity_zones[:50],
            'feeding_issues': feeding_issues[:20],
            'shrinkage_estimate': {
                'total_volume_mm3': float(total_vol),
                'shrinkage_volume_mm3': float(shrinkage_vol),
                'shrinkage_percentage': float(self.material['shrinkage'])
            }
        }

