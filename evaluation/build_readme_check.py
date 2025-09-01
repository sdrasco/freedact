import tomllib
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject_path = root / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)

    readme = pyproject.get("project", {}).get("readme")
    if isinstance(readme, dict):
        readme_path = root / readme.get("file", "")
    elif isinstance(readme, str):
        readme_path = root / readme
    else:
        readme_path = None

    print(f"pyproject readme: {readme}")
    if readme_path is not None:
        print(f"resolved path: {readme_path}")
        print(f"exists: {readme_path.exists()}")
    else:
        print("resolved path: None")
        print("exists: False")


if __name__ == "__main__":
    main()
