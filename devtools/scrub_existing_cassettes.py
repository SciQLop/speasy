"""One-off cassette scrubber for the response-side leaks introduced by
recording sessions that pre-date the `before_record_response` callback
in `tests/conftest.py` vcr_config.

Walks `tests/cassettes/`, in-place edits each YAML to:
- Drop any `Set-Cookie:` response headers (server session IDs).
- Replace any response body that is a bare 32-char hex string (AMDA's
  `auth.php` returns one) with `<SCRUBBED>`.

Idempotent: re-running on already-scrubbed cassettes is a no-op.

Use:
    uv run python devtools/scrub_existing_cassettes.py

Then re-run `devtools/publish_cassettes.py` to regenerate the manifest
with the new content-addressed hashes for the affected cassettes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CASSETTE_DIR = ROOT / "tests" / "cassettes"

AUTH_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")


def _scrub_response(response: dict) -> bool:
    """Mutate response in-place. Returns True if anything changed."""
    changed = False

    headers = response.get("headers") or {}
    for name in list(headers):
        if name.lower() in {"set-cookie", "cookie"}:
            headers.pop(name)
            changed = True

    body = response.get("body") or {}
    raw = body.get("string")
    if isinstance(raw, str) and AUTH_TOKEN_RE.match(raw):
        body["string"] = "<SCRUBBED>"
        changed = True
    elif isinstance(raw, (bytes, bytearray)) and AUTH_TOKEN_RE.match(
        raw.decode("ascii", errors="ignore")
    ):
        body["string"] = b"<SCRUBBED>"
        changed = True

    return changed


def scrub_file(path: Path) -> bool:
    """Returns True if file was modified."""
    with open(path) as f:
        data = yaml.safe_load(f)
    if not data or "interactions" not in data:
        return False

    file_changed = False
    for interaction in data["interactions"]:
        response = interaction.get("response")
        if response and _scrub_response(response):
            file_changed = True

    if file_changed:
        with open(path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    return file_changed


def main() -> None:
    if not CASSETTE_DIR.exists():
        print(f"No cassette dir at {CASSETTE_DIR}")
        sys.exit(0)

    yaml_files = sorted(CASSETTE_DIR.rglob("*.yaml"))
    if not yaml_files:
        print(f"No cassettes under {CASSETTE_DIR}")
        sys.exit(0)

    changed = 0
    for path in yaml_files:
        rel = path.relative_to(ROOT)
        try:
            if scrub_file(path):
                changed += 1
                print(f"  scrubbed  {rel}")
            else:
                print(f"  clean     {rel}")
        except Exception as exc:
            print(f"  ERROR     {rel}: {exc}", file=sys.stderr)

    print(f"\n{changed}/{len(yaml_files)} cassettes modified.")


if __name__ == "__main__":
    main()
