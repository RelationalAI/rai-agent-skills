"""Compatibility exports for the shared rai-orm/tools/orm_usage.py scanner.

The shared ORM tools are a repository dependency of rai-orm-refactor. Load the
exact file without altering the import search path or importing another skill.
"""

import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[2] / "rai-orm" / "tools" / "orm_usage.py"
_spec = importlib.util.spec_from_file_location("orm_shared_usage", _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
referenced_symbols = _module.referenced_symbols
workload_support = _module.workload_support
