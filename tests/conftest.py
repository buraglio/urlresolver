import sys
from pathlib import Path

# urlresolver.py is a standalone script, not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
