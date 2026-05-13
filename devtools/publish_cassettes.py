"""Maintainer tool: stage cassettes for upload, update the manifest.

Walks tests/cassettes/, hashes each .yaml file (sha256 of uncompressed
content), gzips it deterministically (mtime=0), writes the .yaml.gz to
.publish_staging/<sha>.yaml.gz, and updates tests/cassettes_manifest.json.

This script does NOT upload — it stages files and prints the rsync
command for the maintainer to execute. Run from repo root:

    uv run python devtools/publish_cassettes.py

Then upload the staged files manually:

    rsync -av .publish_staging/ <user>@sciqlop.lpp.polytechnique.fr:/var/www/data/speasy_cassettes/
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASSETTE_DIR = ROOT / "tests" / "cassettes"
MANIFEST = ROOT / "tests" / "cassettes_manifest.json"
STAGING = ROOT / ".publish_staging"


def _gzip_deterministic(data: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as f:
        f.write(data)
    return buf.getvalue()


def main() -> None:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir()

    manifest: dict[str, str] = {}
    cassettes = sorted(CASSETTE_DIR.rglob("*.yaml"))
    if not cassettes:
        print(f"No cassettes found under {CASSETTE_DIR}.")
        MANIFEST.write_text("{}\n")
        return

    total_uncompressed = 0
    total_compressed = 0
    for cassette_path in cassettes:
        rel = cassette_path.relative_to(CASSETTE_DIR)
        content = cassette_path.read_bytes()
        sha = hashlib.sha256(content).hexdigest()
        compressed = _gzip_deterministic(content)
        (STAGING / f"{sha}.yaml.gz").write_bytes(compressed)
        manifest[str(rel)] = sha
        total_uncompressed += len(content)
        total_compressed += len(compressed)

    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(f"Staged {len(manifest)} cassettes in {STAGING.relative_to(ROOT)}/")
    print(
        f"Uncompressed: {total_uncompressed / (1024 * 1024):.1f} MB; "
        f"compressed: {total_compressed / (1024 * 1024):.1f} MB"
    )
    print(f"Manifest: {MANIFEST.relative_to(ROOT)} ({len(manifest)} entries)")
    print()
    print("To upload (run yourself; this script has no SSH access):")
    print(
        f"  rsync -av {STAGING.relative_to(ROOT)}/ "
        "<user>@sciqlop.lpp.polytechnique.fr:/var/www/data/speasy_cassettes/"
    )


if __name__ == "__main__":
    main()
