import ast
import re
from pathlib import Path

PATTERNS = {
    r":class:`~?([\w\.]+)`": lambda m: f"[`{m.group(1).split('.')[-1]}`][{m.group(1)}]",
    r":func:`~?([\w\.]+)`": lambda m: f"[`{m.group(1).split('.')[-1]}`][{m.group(1)}]",
    r":meth:`~?([\w\.]+)`": lambda m: f"[`{m.group(1).split('.')[-1]}`][{m.group(1)}]",
}
EXCLUDE = {".venv", ".git", "__pycache__", "site"}


def transform(text: str) -> str:
    for pattern, repl in PATTERNS.items():
        text = re.sub(pattern, repl, text)
    return text


def process_file(path: Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    new_source = source

    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            doc = ast.get_docstring(node, clean=False)
            if not doc:
                continue

            # Find docstring location
            if isinstance(node.body[0], ast.Expr) and isinstance(
                node.body[0].value, ast.Constant
            ):
                doc_node = node.body[0].value
                start = doc_node.lineno - 1
                end = doc_node.end_lineno

                lines = source.splitlines()
                original = "\n".join(lines[start:end])

                updated = transform(original)

                if original != updated:
                    lines[start:end] = updated.splitlines()
                    new_source = "\n".join(lines)

    if new_source != source:
        path.write_text(new_source, encoding="utf-8")
        print(f"updated {path}")


def should_skip(path: Path) -> bool:
    return any(part in EXCLUDE for part in path.parts)


for file in Path(".").rglob("*.py"):
    if should_skip(file):
        continue
    process_file(file)
