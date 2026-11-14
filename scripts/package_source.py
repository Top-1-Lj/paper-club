"""Build a source-only ZIP next to the project; local data is excluded."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT.parent / "paper-club-source.zip"
EXCLUDED_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", "staticfiles", "media", "artifacts", ".idea", ".vscode"}


def include(path):
    relative = path.relative_to(ROOT)
    if not path.is_file() or any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    name = path.name
    if ".sqlite3" in name or path.suffix.casefold() in {".pyc", ".pyo", ".log", ".zip", ".pdf"}:
        return False
    if name.startswith(".env") and name != ".env.example":
        return False
    return name not in {".coverage", ".DS_Store", "Thumbs.db"}


if __name__ == "__main__":
    paths = sorted(path for path in ROOT.rglob("*") if include(path))
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, Path(ROOT.name) / path.relative_to(ROOT))
    print(f"Created {OUTPUT.name}: {len(paths)} files, {OUTPUT.stat().st_size:,} bytes")
