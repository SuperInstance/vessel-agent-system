"""Repo-root conftest.py — ensures aelma/ subdirectories are importable.

The aelma/ package uses `from twin.xxx import ...` style imports,
which requires aelma/ to be on sys.path. This conftest adds it
automatically when pytest runs from the repo root.
"""
import os, sys

aelma_path = os.path.join(os.path.dirname(__file__), "aelma")
if os.path.isdir(aelma_path) and aelma_path not in sys.path:
    sys.path.insert(0, aelma_path)

# Also ensure the aelma/ pytest config is respected
aelma_pytest_ini = os.path.join(aelma_path, "pytest.ini")
if os.path.exists(aelma_pytest_ini):
    # Add importlib mode if running from root
    if "--import-mode=importlib" not in sys.argv:
        sys.argv.extend(["--import-mode=importlib"])
