"""Sphinx extension: ``.. variable-diagram:: <name>`` draws the inline SVG diagrams of user/speasy_variable.rst.

They are inline, not images, so they take their colours from the theme (see _static/diagrams.css) and follow
its light and dark modes."""
from docutils import nodes
from docutils.parsers.rst import Directive

ROW_H, COL_W, TIME_W = 26, 64, 150


def rect(x, y, w, h, cls):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" class="{cls}"/>'


def text(x, y, s, cls="d-text", anchor="start"):
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{s}</text>'


TIMES = ["2016-06-02T00:00:15", "2016-06-02T00:00:31", "2016-06-02T00:00:47", "⋮", "2016-06-04T23:59:59"]
VALUES = [["4.04", "0.93", "0.47"], ["4.07", "0.92", "0.42"], ["4.11", "0.95", "0.51"], ["⋮", "⋮", "⋮"],
          ["-0.15", "-5.14", "2.35"]]


def grid(x0, y0, rows, cols, row_cls=lambda r: "", cell_cls=lambda r, c: "", values=None, times=None):
    out = []
    if times:
        for r in range(rows):
            out.append(rect(x0, y0 + r * ROW_H, TIME_W, ROW_H, "d-time " + row_cls(r)))
            out.append(text(x0 + TIME_W / 2, y0 + r * ROW_H + 17, times[r], "d-mono", "middle"))
        x0 += TIME_W + 8
    for r in range(rows):
        for c in range(cols):
            out.append(rect(x0 + c * COL_W, y0 + r * ROW_H, COL_W, ROW_H, "d-val " + row_cls(r) + " " + cell_cls(r, c)))
            if values:
                out.append(text(x0 + c * COL_W + COL_W / 2, y0 + r * ROW_H + 17, values[r][c], "d-mono", "middle"))
    return out, x0


def svg(w, h, body, label):
    return (f'<svg class="spz-diagram" width="{w}" viewBox="0 0 {w} {h}" role="img" aria-label="{label}" '
            f'xmlns="http://www.w3.org/2000/svg">' + "".join(body) + "</svg>")


def anatomy():
    body = []
    y0 = 52
    cells, vx = grid(10, y0, 5, 3, values=VALUES, times=TIMES)
    body += cells
    for c, name in enumerate(["bx", "by", "bz"]):
        body.append(text(vx + c * COL_W + COL_W / 2, y0 - 10, name, "d-strong", "middle"))
    body.append(text(vx + 1.5 * COL_W, 22, "columns", "d-muted", "middle"))
    body.append(text(10 + TIME_W / 2, y0 - 10, "time", "d-strong", "middle"))
    bottom = y0 + 5 * ROW_H
    body.append(text(10 + TIME_W / 2, bottom + 24, "var.time", "d-code", "middle"))
    body.append(text(10 + TIME_W / 2, bottom + 42, "datetime64[ns], UTC", "d-muted", "middle"))
    body.append(text(vx + 1.5 * COL_W, bottom + 24, "var.values", "d-code", "middle"))
    body.append(text(vx + 1.5 * COL_W, bottom + 42, "numpy array, shape (N, 3)", "d-muted", "middle"))
    cx = vx + 3 * COL_W + 30
    body.append(rect(cx, y0 - 20, 250, 5 * ROW_H + 20, "d-card"))
    lines = [("var.name", "imf"), ("var.unit", "nT"), ("var.columns", "['bx', 'by', 'bz']"),
             ("var.fill_value", "nan"), ("var.meta", "CATDESC, FILLVAL, …")]
    for i, (k, v) in enumerate(lines):
        body.append(text(cx + 14, y0 + 4 + i * 26, k, "d-code"))
        body.append(text(cx + 236, y0 + 4 + i * 26, v, "d-muted", "end"))
    return svg(cx + 262, bottom + 54, body, "A SpeasyVariable: a time axis, a values array with named columns, and metadata")


def slicing():
    body = []
    panels = [
        ('var["2016-06-03":"2016-06-04"]', "rows inside a time range", lambda r: "d-hl" if r in (1, 2) else "",
         lambda r, c: ""),
        ('var["bx"]', "one or more columns", lambda r: "", lambda r, c: "d-hl" if c == 0 else ""),
        ("var[var.values[:, 2] > 0]", "rows where a test is true", lambda r: "d-hl" if r in (0, 3, 4) else "",
         lambda r, c: ""),
    ]
    pw = 3 * COL_W + 60
    for i, (code, caption, rows, cells) in enumerate(panels):
        x = 10 + i * (pw + 20)
        body.append(rect(x, 10, 40, 5 * ROW_H, "d-time-thin"))
        for r in range(5):
            body.append(rect(x, 10 + r * ROW_H, 40, ROW_H, "d-time " + rows(r)))
        g, _ = grid(x + 48, 10, 5, 3, row_cls=rows, cell_cls=cells)
        body += g
        body.append(text(x + pw / 2, 5 * ROW_H + 34, code, "d-code", "middle"))
        body.append(text(x + pw / 2, 5 * ROW_H + 52, caption, "d-muted", "middle"))
    return svg(3 * pw + 50, 5 * ROW_H + 62, body, "Three ways to select data: a time range, columns, or a boolean mask")


def spectrogram():
    body = []
    y0, n_e, cw = 40, 8, 34
    x_time = 10
    for r in range(5):
        body.append(rect(x_time, y0 + r * ROW_H, 40, ROW_H, "d-time"))
    body.append(text(x_time + 20, y0 - 10, "time", "d-strong", "middle"))
    xv = x_time + 48
    levels = [[1, 2, 4, 5, 4, 3, 2, 1], [1, 3, 5, 5, 4, 2, 1, 1], [2, 4, 5, 4, 3, 2, 1, 0],
              [1, 2, 3, 5, 5, 3, 2, 1], [0, 1, 3, 4, 5, 4, 2, 1]]
    for r in range(5):
        for c in range(n_e):
            body.append(rect(xv + c * cw, y0 + r * ROW_H, cw, ROW_H, f"d-heat{levels[r][c]}"))
    body.append(text(xv + n_e * cw / 2, y0 - 10, "energy channels", "d-strong", "middle"))
    xe = xv + n_e * cw + 30
    for r in range(5):
        for c in range(4):
            body.append(rect(xe + c * 44, y0 + r * ROW_H, 44, ROW_H, "d-axis"))
            body.append(text(xe + c * 44 + 22, y0 + r * ROW_H + 17, ["6.5", "8.5", "11.2", "…"][c] if r != 3 else "⋮",
                             "d-mono", "middle"))
    body.append(text(xe + 88, y0 - 10, "energy of each channel (eV)", "d-strong", "middle"))
    bottom = y0 + 5 * ROW_H
    body.append(text(xv + n_e * cw / 2, bottom + 24, "var.values", "d-code", "middle"))
    body.append(text(xv + n_e * cw / 2, bottom + 42, "shape (N, 32)", "d-muted", "middle"))
    body.append(text(xe + 88, bottom + 24, "var.axes[1].values", "d-code", "middle"))
    body.append(text(xe + 88, bottom + 42, "shape (N, 32): may change with time", "d-muted", "middle"))
    return svg(xe + 190, bottom + 52, body, "A spectrogram: values per time and energy channel, with an energy axis")


DIAGRAMS = {"anatomy": anatomy, "slicing": slicing, "spectrogram": spectrogram}


class VariableDiagram(Directive):
    required_arguments = 1

    def run(self):
        return [nodes.raw("", DIAGRAMS[self.arguments[0]](), format="html")]


def setup(app):
    app.add_directive("variable-diagram", VariableDiagram)
    app.add_css_file("diagrams.css")
    return {"parallel_read_safe": True}
