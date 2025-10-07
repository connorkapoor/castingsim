"""
Configuration file for Casting Solidification Simulator
Modify these values to customize the simulation behavior
"""

# Server Configuration
HOST = '0.0.0.0'
PORT = 5000
DEBUG = True

# Simulation Parameters
DEFAULT_SIMULATION_TIME = 300  # seconds
DEFAULT_TIME_STEP = 1.0  # seconds
DEFAULT_SAVE_INTERVAL = 5  # save every N steps

# Mesh Generation
DEFAULT_MESH_SIZE = 5.0  # target element size in mm
MESH_SIZE_MIN_FACTOR = 0.5  # min size = mesh_size * this
MESH_SIZE_MAX_FACTOR = 2.0  # max size = mesh_size * this

# Boundary Conditions
HEAT_TRANSFER_COEFFICIENT = 50  # W/(m²·K) - convection to air
DEFAULT_AMBIENT_TEMP = 25  # °C

# Phase Change Model
SOLIDIFICATION_RANGE = 20  # °C - temperature range for mushy zone

# File Upload
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {'.step', '.stp'}

# Storage
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
MAX_STORED_RESULTS = 100  # automatically clean old results

# Performance
MAX_NODES = 50000  # maximum mesh nodes (prevents memory issues)
PARALLEL_ASSEMBLY = False  # enable for large meshes (experimental)

# Visualization
HOTSPOT_THRESHOLD = 0.5  # nodes that are hot in >50% of final timesteps
HOTSPOT_MARKER_SIZE = 1.5  # size of hotspot spheres in visualization

# Material Database
# You can add custom materials here
CUSTOM_MATERIALS = {
    # Example:
    # 'copper': {
    #     'name': 'Copper (Cu)',
    #     'melting_point': 1085,
    #     'density': 8960,
    #     'thermal_conductivity': 401,
    #     'specific_heat': 385,
    #     'latent_heat': 205000,
    #     'default_pour_temp': 1200
    # }
}

# Logging
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

