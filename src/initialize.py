# initialize.py
import os
import importlib.util
import sys

def init_obs_planner():
    # Set up OBS_PLANNER_ROOT environment variable (must be absolute)
    obs_planner_root = os.getenv("OBS_PLANNER_ROOT")
    if not obs_planner_root or not os.path.isabs(obs_planner_root):
        raise ValueError("OBS_PLANNER_ROOT must be set to an absolute path")

    # Import the obs_planner module dynamically
    spec = importlib.util.spec_from_file_location("obs_planner", 
                                                os.path.join(obs_planner_root, "__init__.py"))
    obs_planner = importlib.util.module_from_spec(spec)
    # Add obs_planner directory to Python path before executing
    sys.path.insert(0, obs_planner_root)
    spec.loader.exec_module(obs_planner)
    return obs_planner

obs_planner = init_obs_planner()