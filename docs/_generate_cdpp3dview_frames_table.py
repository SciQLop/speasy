"""Generates the CDPP 3DView coordinate-frames table from the live server at build time.

Queries https://3dview.irap.omp.eu/webresources/get_frames directly (the same endpoint
speasy.data_providers.cdpp3dview uses) so the table in the built docs always reflects
whatever the server currently offers, rather than a hand-maintained list that drifts.
Falls back to a committed snapshot if the server is unreachable at build time, so a
flaky network doesn't fail the whole docs build.
"""
import json
import os
from urllib.request import urlopen, Request

from _rst_gen_utils import escape_rst, render_list_table, utc_now_str

FRAMES_URL = "https://3dview.irap.omp.eu/webresources/get_frames"
FALLBACK_PATH = os.path.join(os.path.dirname(__file__), "_cdpp3dview_frames_fallback.json")
OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "user", "cdpp3dview", "_generated_frames_table.rst"
)


def _fetch_live_frames(timeout=10):
    request = Request(FRAMES_URL, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    return [
        {"name": f["name"], "center": f["center"], "desc": f["desc"]}
        for f in data["frames"]
    ]


def generate():
    now = utc_now_str()
    try:
        frames = _fetch_live_frames()
        source_note = f"Fetched live from the 3DView server when these docs were built, on {now}."
    except Exception as e:  # noqa: BLE001 - any failure falls back, build must not break
        fallback = json.load(open(FALLBACK_PATH))
        frames = fallback["frames"]
        source_note = (
            f"The live query to the 3DView server failed during this build ({e}); "
            f"showing a cached snapshot captured on {fallback['captured_on']} instead. "
            f"Build attempted on {now}."
        )

    table = render_list_table(
        headers=["Frame", "Centered on", "Description"],
        rows=[
            [f"``{escape_rst(f['name'])}``", escape_rst(f["center"]), escape_rst(f["desc"])]
            for f in frames
        ],
        widths=[15, 20, 65],
    )
    content = (
        f"{source_note} Run ``spz.cdpp3dview.get_frames()`` yourself for the current list.\n\n"
        f"{table}\n"
    )
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(content)


def setup(app):
    app.connect("builder-inited", lambda app: generate())
    return {"parallel_read_safe": True, "parallel_write_safe": True}
