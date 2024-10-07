### Sunflow Cryptobot ###
#
# Load configuration

# Load external libraries
from pathlib import Path
import importlib, sys, argparse

# Load configuration file
def load_config():
    
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', default='config.py')
    parser.add_argument('-d', '--days', type=int, default=30,)
    args = parser.parse_args()

    # Resolve config file path
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"Config file not found at {config_path}, aborting...\n")
        sys.exit()

    # Dynamically load the config module
    sys.path.append(str(config_path.parent))
    config_module_name = config_path.stem
    config = importlib.import_module(config_module_name)
    
    # Return config
    return config