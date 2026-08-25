#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Drive the upgrade-path CI job for one scenario: install each version in
the given order (from PyPI, or from the checked-out working tree for
"main"), running upgrade_path_fetch.py after each install. All steps share
the same interpreter/site-packages and the same current directory across the
whole run, so the cache/index/config Speasy writes at one step is exactly
what the next step's (newer) Speasy sees -- that persistence, entirely via
the OS filesystem, is what makes this an upgrade-path test rather than N
independent single-version smoke tests.
"""
import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FETCH_SCRIPT = SCRIPT_DIR / "upgrade_path_fetch.py"
REPO_ROOT = SCRIPT_DIR.parent.parent


def install_target(version: str, repo_root: Path) -> str:
    if version == "main":
        return str(repo_root)
    return f"speasy=={version}"


def install(version: str, repo_root: Path, runner) -> None:
    runner([sys.executable, "-m", "pip", "install", "--upgrade", "--quiet",
            install_target(version, repo_root)], check=True)


def run_steps(versions, repo_root: Path, fetch_script: Path, state_file: str,
              installer=install, runner=subprocess.run) -> None:
    Path(state_file).unlink(missing_ok=True)
    for step, version in enumerate(versions):
        print(f"::group::step {step}: speasy {version}", flush=True)
        installer(version, repo_root, runner)
        runner([sys.executable, str(fetch_script), "--step", str(step),
                "--state-file", state_file], check=True)
        print("::endgroup::", flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", required=True,
                        help="comma-separated version list, e.g. 1.5.2,1.7.1,main")
    parser.add_argument("--state-file", default="upgrade_path_state.json")
    args = parser.parse_args(argv)

    run_steps(args.versions.split(","), REPO_ROOT, FETCH_SCRIPT, args.state_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
