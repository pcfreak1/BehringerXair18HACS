"""Build a manual-install ZIP containing only the integration and documentation."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "behringer_xair.zip"


def main() -> None:
    OUTPUT.parent.mkdir(exist_ok=True)
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "custom_components" / "behringer_xair").rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.write(path, path.relative_to(ROOT))
        for name in ("README.md", "LICENSE", "CHANGELOG.md"):
            archive.write(ROOT / name, name)
    print(OUTPUT)


if __name__ == "__main__":
    main()
