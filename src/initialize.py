# initialize.py
import os
import sys

def init_obs_planner():
    # Set up OBS_PLANNER_ROOT environment variable (must be absolute)
    obs_planner_root = os.getenv("OBS_PLANNER_ROOT")
    if not obs_planner_root or not os.path.isabs(obs_planner_root):
        raise ValueError("OBS_PLANNER_ROOT must be set to an absolute path")
    
    # Add the parent directory of obs_planner to sys.path
    parent_dir = os.path.dirname(obs_planner_root)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    # Import obs_planner normally
    try:
        import obs_planner
        return obs_planner
    except ImportError as e:
        raise ImportError(f"Failed to import obs_planner: {e}")
    
obs_planner = init_obs_planner()


def init_obs_tasker():
    # Set up OBS_TASKER_ROOT environment variable (must be absolute)
    obs_tasker_root = os.getenv("OBS_TASKER_ROOT")
    if not obs_tasker_root or not os.path.isabs(obs_tasker_root):
        raise ValueError("OBS_TASKER_ROOT must be set to an absolute path")
    
    # The actual python code is within the src directory
    #obs_tasker_src = os.path.join(obs_tasker_root, "src")

    # Add the parent directory of obs_tasker to sys.path
    #parent_dir = os.path.dirname(obs_tasker_root)
    if obs_tasker_root not in sys.path:
        sys.path.insert(0, obs_tasker_root)
    
    # Import obs_tasker normally
    try:
        import obs_tasker
        return obs_tasker
    except ImportError as e:
        raise ImportError(f"Failed to import obs_tasker: {e}")

# Initialize the observation tasker
obs_tasker = init_obs_tasker()