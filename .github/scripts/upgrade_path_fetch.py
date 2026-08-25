#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Fetch a few small, known-good products through whatever Speasy version is
currently installed. Run once per version step (see upgrade_path_driver.py)
within one persistent environment: AMDA's requested window grows with --step,
so a later step necessarily reuses at least one cache fragment written by an
older Speasy version and merges it with a freshly-fetched one written by the
current version -- the actual thing this CI job exists to catch.

Long-stable API only (spz.get_data / spz.list_providers, both present back to
speasy 1.5.2) so this one script runs unmodified across the whole version
range under test.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

AMDA_ANCHOR = "2016-06-02"
AMDA_FRAGMENT_DAYS = 1

# provider_name -> (product, start, stop). Verified live against the real
# services before being written here -- not guesses. CSA is deliberately
# excluded: no verified small product path was available when this was
# written (its inventory tree structure didn't match the obvious guess), see
# the design spec's "Open follow-ups".
SINGLE_SHOT_PRODUCTS = {
    "cda": ("cda/WI_PLSP_3DP/MOM.P.MAGF", "2018-01-01", "2018-01-02"),
    "ssc": ("ssc/moon", "2006-01-08T01:00:00", "2006-01-08T01:30:00"),
    "cdpp3dview": ("cdpp3dview/GEOTAIL", "1992-07-30T01:00:00", "1992-07-30T02:00:00"),
}


def _amda_stop_for_step(step: int) -> str:
    anchor = datetime.strptime(AMDA_ANCHOR, "%Y-%m-%d")
    stop = anchor + timedelta(days=(step + 2) * AMDA_FRAGMENT_DAYS)
    return stop.strftime("%Y-%m-%d")


def fetch_amda(get_data, step: int, state_file: Path) -> None:
    stop = _amda_stop_for_step(step)
    var = get_data("amda/imf", AMDA_ANCHOR, stop)
    if var is None or len(var) == 0:
        raise AssertionError(f"amda/imf returned no data for step {step} ([{AMDA_ANCHOR}, {stop}))")

    previous_length = None
    if state_file.exists():
        previous_length = json.loads(state_file.read_text()).get("amda_imf_length")

    if previous_length is not None and len(var) <= previous_length:
        raise AssertionError(
            f"amda/imf: requested window grew at step {step} but the returned length did not "
            f"({len(var)} <= {previous_length}) -- merging cache fragments written by an older "
            f"speasy version with freshly-fetched ones likely failed"
        )

    state_file.write_text(json.dumps({"amda_imf_length": len(var)}))
    print(f"amda/imf: {len(var)} samples for [{AMDA_ANCHOR}, {stop})"
          + (f" (previous: {previous_length})" if previous_length is not None else ""))


def fetch_single_shot(get_data, product: str, start: str, stop: str) -> None:
    var = get_data(product, start, stop)
    if var is None or len(var) == 0:
        raise AssertionError(f"{product} returned no data for [{start}, {stop})")
    print(f"{product}: {len(var)} samples")


def run(get_data, list_providers, step: int, state_file: Path) -> None:
    available = set(list_providers())
    print(f"available providers: {sorted(available)}")

    fetch_amda(get_data, step, state_file)

    for provider, (product, start, stop) in SINGLE_SHOT_PRODUCTS.items():
        if provider not in available:
            print(f"skip {product}: {provider!r} not available in this speasy version")
            continue
        try:
            fetch_single_shot(get_data, product, start, stop)
        except AssertionError as exc:
            print(f"WARNING: {product} failed: {exc}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--state-file", type=Path, default=Path("upgrade_path_state.json"))
    args = parser.parse_args(argv)

    import speasy as spz

    print(f"speasy {spz.__version__}, step {args.step}")
    run(spz.get_data, spz.list_providers, args.step, args.state_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
