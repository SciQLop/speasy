"""Shared helpers for the build-time generated-table Sphinx extensions."""
from datetime import datetime, timezone


def utc_now_str():
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def escape_rst(text):
    return str(text).replace("`", "'").replace("*", "").strip()


def render_list_table(headers, rows, widths):
    """Render a list-table from already RST-safe cell strings.

    Callers are responsible for escaping any untrusted text themselves (with
    :func:`escape_rst`) before building a cell -- this function does not escape,
    so cells may contain their own inline markup (e.g. ` ``literal`` `).
    """
    assert len(headers) == len(widths)
    lines = [
        ".. list-table::",
        f"   :widths: {' '.join(str(w) for w in widths)}",
        "   :header-rows: 1",
        "",
        "   * - " + "\n     - ".join(headers),
    ]
    for row in rows:
        assert len(row) == len(headers)
        lines.append("   * - " + "\n     - ".join(str(cell) for cell in row))
    return "\n".join(lines)
