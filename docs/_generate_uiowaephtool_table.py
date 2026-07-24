"""Generates the UiowaEphTool body/coordinate-systems table at build time.

Unlike CDPP 3DView, UiowaEphTool has no server endpoint listing its bodies or coordinate
systems -- that structure is entirely hardcoded in speasy.data_providers.uiowa_eph_tool's
dictionaries. Introspecting the built inventory here (rather than hand-typing a table)
means the docs can never drift from what the current code actually offers, and there's
no network call involved so no fallback is needed either.
"""
import os

import speasy as spz

from _rst_gen_utils import render_list_table, utc_now_str

OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "user", "Uiowa_eph_tool", "_generated_bodies_table.rst"
)


def _coordinate_systems(body_node):
    return sorted(
        k for k in body_node.__dict__
        if k not in ("Id", "Radius") and not k.startswith(("_", "spz"))
    )


def generate():
    trajectories = spz.inventories.tree.uiowaephtool.Trajectories
    body_attrs = sorted(k for k in trajectories.__dict__ if not k.startswith(("_", "spz")))
    rows = []
    for attr in body_attrs:
        node = getattr(trajectories, attr)
        systems = _coordinate_systems(node)
        rows.append([node.spz_name(), ", ".join(f"``{s}``" for s in systems)])

    table = render_list_table(
        headers=["Body", "Coordinate systems"],
        rows=rows,
        widths=[25, 75],
    )
    content = (
        f"Generated from the current Speasy inventory when these docs were built, on "
        f"{utc_now_str()}. Run the same introspection yourself "
        f"(``sorted(k for k in trajectories.<Body>.__dict__ if not k.startswith(('_', 'spz')))``, "
        f"minus ``Id``/``Radius``) to check any single body.\n\n"
        f"{table}\n"
    )
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(content)


def setup(app):
    app.connect("builder-inited", lambda app: generate())
    return {"parallel_read_safe": True, "parallel_write_safe": True}
