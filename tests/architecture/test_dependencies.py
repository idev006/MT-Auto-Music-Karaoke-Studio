import ast
from pathlib import Path

import mt_engine

FORBIDDEN_PREFIXES = (
    "PySide6",
    "sqlalchemy",
    "alembic",
    "mt_engine.adapters",
)


def test_domain_and_contracts_do_not_import_infrastructure():
    source_root = Path(mt_engine.__file__).resolve().parent
    checked_roots = (source_root / "domain", source_root / "contracts")

    violations: list[str] = []
    for checked_root in checked_roots:
        for path in checked_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                for name in names:
                    if name.startswith(FORBIDDEN_PREFIXES):
                        violations.append(f"{path.relative_to(source_root)} imports {name}")

    assert violations == []


def test_importing_headless_package_does_not_import_pyside():
    import sys

    assert not any(name == "PySide6" or name.startswith("PySide6.") for name in sys.modules)
