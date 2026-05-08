"""One-shot script to add pytest markers to existing test files.

Run from repo root:
    uv run python devtools/apply_test_markers.py

Idempotent: if a `pytestmark = pytest.mark.<tier>` line already exists, the
script leaves the file untouched.
"""

from __future__ import annotations

from pathlib import Path

CLASSIFICATION: dict[str, str] = {
    "test_dataset.py": "unit",
    "test_datetimerange.py": "unit",
    "test_file_access.py": "unit",
    "test_filtering.py": "unit",
    "test_proxy.py": "unit",
    "test_resampling.py": "unit",
    "test_speasy_catalog.py": "unit",
    "test_speasy_timetable.py": "unit",
    "test_speasy_variable.py": "unit",
    "test_url_utils.py": "unit",
    "test_zzz_disable_ws.py": "unit",
    "test_amda.py": "contract",
    "test_amda_catalog.py": "contract",
    "test_amda_parameter.py": "contract",
    "test_amda_timetable.py": "contract",
    "test_cache.py": "contract",
    "test_cdaweb.py": "contract",
    "test_cdpp3dview.py": "contract",
    "test_codecs.py": "contract",
    "test_common.py": "contract",
    "test_config_module.py": "contract",
    "test_csa.py": "contract",
    "test_direct_archive_downloader.py": "contract",
    "test_hapi.py": "contract",
    "test_hapi_codecs.py": "contract",
    "test_http_module.py": "contract",
    "test_inventories.py": "contract",
    "test_speasy.py": "contract",
    "test_sscweb.py": "contract",
    "test_uiowa_eph_tool.py": "contract",
    "test_wasm.py": "contract",
}

MARKER_LINE_PREFIX = "pytestmark = pytest.mark."


def apply(path: Path, tier: str) -> bool:
    text = path.read_text()
    if MARKER_LINE_PREFIX in text:
        return False
    lines = text.splitlines(keepends=True)
    insert_at = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith(("import ", "from "))),
        0,
    )
    while insert_at < len(lines) and lines[insert_at].strip().startswith(("import ", "from ", "#")):
        insert_at += 1
    block = [
        "\n",
        "import pytest\n",
        f"\n{MARKER_LINE_PREFIX}{tier}\n",
        "\n",
    ]
    if any("import pytest" in ln for ln in lines):
        block = [f"\n{MARKER_LINE_PREFIX}{tier}\n", "\n"]
    lines[insert_at:insert_at] = block
    path.write_text("".join(lines))
    return True


def main() -> None:
    tests_dir = Path(__file__).resolve().parent.parent / "tests"
    changed = 0
    for name, tier in CLASSIFICATION.items():
        path = tests_dir / name
        if not path.exists():
            print(f"  SKIP (missing): {name}")
            continue
        if apply(path, tier):
            print(f"  marked  {tier:8} {name}")
            changed += 1
        else:
            print(f"  already {tier:8} {name}")
    print(f"\n{changed} files modified.")


if __name__ == "__main__":
    main()
