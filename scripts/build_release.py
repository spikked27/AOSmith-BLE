"""Build the install archive from only the integration's distributable files."""

import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
component = root / "custom_components" / "aosmith_ble"
manifest = json.loads((component / "manifest.json").read_text())
version = manifest["version"]
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
    raise SystemExit("A stable semantic version is required for release")
output = root / "dist" / "aosmith_ble.zip"
output.parent.mkdir(exist_ok=True)
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for path in sorted(component.rglob("*")):
        if (
            path.is_file()
            and path.suffix in {".py", ".json", ".yaml", ".png"}
            and "__pycache__" not in path.parts
        ):
            archive.write(path, path.relative_to(root))
with ZipFile(output) as archive:
    assert archive.testzip() is None
    assert json.loads(archive.read("custom_components/aosmith_ble/manifest.json"))["version"] == version
print(f"Built {output.name} for v{version}")
