import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
script = root / "railway_start.sh"
os.execvp("sh", ["sh", str(script)])
