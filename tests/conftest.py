import os
import sys

# Permite `import agent...` ao correr pytest da raiz do repositório.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
