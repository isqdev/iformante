import ast
import unittest
from pathlib import Path


APP_DIR = Path(__file__).parents[1] / "app"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    return modules


def matches_prefix(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


class ArchitectureTests(unittest.TestCase):
    def test_rag_does_not_depend_on_http_or_application_layers(self) -> None:
        forbidden_prefixes = (
            "app.dtos",
            "app.routes",
            "app.use_cases",
            "app.repositories",
        )

        for path in (APP_DIR / "rag").rglob("*.py"):
            with self.subTest(path=path):
                imports = imported_modules(path)
                violations = {
                    module
                    for module in imports
                    if any(matches_prefix(module, prefix) for prefix in forbidden_prefixes)
                }
                self.assertEqual(violations, set())

    def test_use_cases_do_not_depend_on_fastapi(self) -> None:
        for path in (APP_DIR / "use_cases").rglob("*.py"):
            with self.subTest(path=path):
                imports = imported_modules(path)
                self.assertFalse(
                    any(module.startswith("fastapi") for module in imports),
                )

    def test_legacy_package_names_are_not_imported(self) -> None:
        forbidden_prefixes = (
            "app.schemas",
            "app.repository",
            "app.db.qdrant",
        )

        for path in APP_DIR.rglob("*.py"):
            with self.subTest(path=path):
                imports = imported_modules(path)
                violations = {
                    module
                    for module in imports
                    if any(matches_prefix(module, prefix) for prefix in forbidden_prefixes)
                }
                self.assertEqual(violations, set())
