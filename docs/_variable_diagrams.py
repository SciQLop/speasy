"""Sphinx extension: ``.. variable-diagram:: <name>`` draws the inline SVG diagrams of user/speasy_variable.rst.

Arrays are drawn as extruded blocks, in the spirit of Scipp's ``sc.show`` (https://scipp.github.io): the shape
and the alignment of the blocks tell which axis labels which dimension. They are inline, not images, so they
take their colours from the theme (see _static/diagrams.css) and follow its light and dark modes."""
from docutils import nodes
from docutils.parsers.rst import Directive


def _pts(*xy):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)


def poly(cls, *xy):
    return f'<polygon points="{_pts(*xy)}" class="{cls}"/>'


def rect(x, y, w, h, cls):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" class="{cls}"/>'


def text(x, y, s, cls, anchor="middle", rotate=None):
    turn = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate is not None else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}"{turn}>{s}</text>'


def block(x, y, rows, cols, cw, ch, cls, layers=1, depth=7):
    """A rows x cols x layers block whose front face has its top-left corner at (x, y).
    ``cls(r, c)`` gives the class of each cell; the top and side faces repeat the edge cells."""
    ox, oy = depth, -depth * 0.75
    w, h = cols * cw, rows * ch
    out = []
    for l in range(layers):
        for c in range(cols):
            x0, y0 = x + c * cw + l * ox, y + l * oy
            out.append(poly(cls(0, c), (x0, y0), (x0 + cw, y0), (x0 + cw + ox, y0 + oy), (x0 + ox, y0 + oy)))
        for r in range(rows):
            x0, y0 = x + w + l * ox, y + r * ch + l * oy
            out.append(poly(cls(r, cols - 1), (x0, y0), (x0 + ox, y0 + oy), (x0 + ox, y0 + ch + oy), (x0, y0 + ch)))
    dx, dy = layers * ox, layers * oy
    out.append(poly("d-lit", (x, y), (x + w, y), (x + w + dx, y + dy), (x + dx, y + dy)))
    out.append(poly("d-shade", (x + w, y), (x + w + dx, y + dy), (x + w + dx, y + h + dy), (x + w, y + h)))
    out += [rect(x + c * cw, y + r * ch, cw, ch, cls(r, c)) for r in range(rows) for c in range(cols)]
    return out


def labelled(x, y, code, note):
    return [text(x, y, code, "d-code"), text(x, y + 18, note, "d-muted")]


def arrow(x, y0, y1):
    return [f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1 - 6}" class="d-arrow"/>',
            poly("d-arrowhead", (x - 5, y1 - 7), (x + 5, y1 - 7), (x, y1))]


def svg(w, h, body, label):
    return (f'<svg class="spz-diagram" width="{w}" viewBox="0 0 {w} {h}" role="img" aria-label="{label}" '
            f'xmlns="http://www.w3.org/2000/svg">' + "".join(body) + "</svg>")


def anatomy():
    rows, ch, y0 = 8, 18, 56
    tx, vx, cw = 70, 170, 36
    bottom = y0 + rows * ch
    row = lambda base: (lambda r, c: f"{base} d-row" if r == 2 else base)
    body = block(tx, y0, rows, 1, 22, ch, row("d-time"))
    body += block(vx, y0, rows, 3, cw, ch, row("d-val"))
    body += [text(vx + c * cw + cw / 2 + 4, y0 - 12, name, "d-strong") for c, name in enumerate(["bx", "by", "bz"])]
    body.append(text(tx - 10, y0 + rows * ch / 2, "time", "d-strong", rotate=-90))
    body.append(text(vx + 3 * cw + 20, y0 + 2 * ch + 13, "← one row per time", "d-muted", "start"))
    body += labelled(tx + 11, bottom + 26, "var.time", "datetime64[ns], UTC")
    body += labelled(vx + 1.5 * cw, bottom + 26, "var.values", "numpy array, shape (N, 3)")
    cx = 440
    body.append(rect(cx, y0 - 10, 240, rows * ch + 10, "d-card"))
    lines = [("var.name", "imf"), ("var.unit", "nT"), ("var.columns", "['bx', 'by', 'bz']"),
             ("var.fill_value", "nan"), ("var.meta", "CATDESC, FILLVAL, …")]
    for i, (k, v) in enumerate(lines):
        body.append(text(cx + 14, y0 + 16 + i * 27, k, "d-code", "start"))
        body.append(text(cx + 226, y0 + 16 + i * 27, v, "d-muted", "end"))
    return svg(cx + 250, bottom + 54, body, "A SpeasyVariable: a time axis, a values array with named columns, and metadata")


HEAT = [[1, 2, 3, 4, 5, 5, 4, 3, 2, 1, 1, 0], [1, 2, 4, 5, 5, 4, 3, 2, 1, 1, 0, 0], [2, 3, 4, 5, 4, 3, 2, 2, 1, 0, 0, 0],
        [1, 3, 5, 5, 4, 3, 2, 1, 1, 1, 0, 0], [1, 2, 3, 4, 5, 4, 3, 2, 1, 0, 0, 0], [0, 1, 2, 4, 5, 5, 4, 2, 1, 1, 0, 0],
        [0, 1, 3, 4, 5, 4, 3, 2, 1, 0, 0, 0], [1, 2, 3, 5, 5, 4, 2, 1, 1, 0, 0, 0]]


def spectrogram():
    rows, ch, cw, cols, y0 = 8, 18, 16, 12, 40
    tx, vx, ex = 50, 110, 370
    bottom = y0 + rows * ch
    body = block(tx, y0, rows, 1, 22, ch, lambda r, c: "d-time")
    body += block(vx, y0, rows, cols, cw, ch, lambda r, c: f"d-heat{HEAT[r][c]}")
    body += block(ex, y0, rows, cols, cw, ch, lambda r, c: "d-axis")
    body.append(text(tx - 10, y0 + rows * ch / 2, "time", "d-strong", rotate=-90))
    body.append(text(vx + cols * cw / 2, y0 - 14, "energy channel →", "d-strong"))
    body.append(text(ex + cols * cw / 2, y0 - 14, "energy of each channel", "d-strong"))
    body += labelled(tx + 11, bottom + 26, "var.time", "(N,)")
    body += labelled(vx + cols * cw / 2, bottom + 26, "var.values", "shape (N, 32)")
    body += labelled(ex + cols * cw / 2, bottom + 26, "var.axes[1].values", "(N, 32), or (32,) when fixed")
    return svg(ex + cols * cw + 40, bottom + 54, body,
               "A spectrogram: values per time and energy channel, next to the energy axis with the same shape")


def distribution():
    rows, ch, cw, cols, layers, y0 = 8, 16, 16, 8, 6, 64
    tx, vx = 50, 110
    bottom = y0 + rows * ch
    body = block(tx, y0, rows, 1, 22, ch, lambda r, c: "d-time")
    body += block(vx, y0, rows, cols, cw, ch, lambda r, c: "d-val", layers=layers, depth=10)
    body.append(text(tx - 10, y0 + rows * ch / 2, "time", "d-strong", rotate=-90))
    body.append(text(vx + cols * cw / 2, bottom + 18, "energy", "d-strong"))
    side_x, side_y = vx + cols * cw + layers * 5 + 12, y0 + rows * ch + layers * -3.75 + 4
    body.append(text(side_x, side_y, "angle", "d-strong", "start", rotate=-37))
    lx = 360
    for i, (code, note) in enumerate([("var.values", "shape (N, 32, 16)"), ("var.axes[0]", "time"),
                                      ("var.axes[1]", "energy of each channel"), ("var.axes[2]", "angle of each sector")]):
        body.append(text(lx, y0 + 6 + i * 30, code, "d-code", "start"))
        body.append(text(lx + 100, y0 + 6 + i * 30, note, "d-muted", "start"))
    return svg(640, bottom + 34, body, "A 3D variable: one axis per dimension of the values")


def slicing():
    rows, ch, tw, cw = 8, 14, 16, 26
    top, gap = 20, 44
    src_bottom = top + rows * ch
    res_top = src_bottom + gap
    panels = [
        ('var["2016-06-03":"2016-06-04"]', "rows inside a time range", {2, 3, 4, 5}, {0, 1, 2}),
        ('var["bx"]', "one or more columns", set(range(rows)), {0}),
        ("var[var.values[:, 2] > 0]", "rows where a test is true", {0, 3, 4, 6}, {0, 1, 2}),
    ]
    body = []
    for i, (code, caption, kept_rows, kept_cols) in enumerate(panels):
        px = 66 + i * 240
        centre = px + (tw + 8 + 3 * cw) / 2
        body += block(px, top, rows, 1, tw, ch, lambda r, c: "d-time" if r in kept_rows else "d-dim", depth=5)
        body += block(px + tw + 8, top, rows, 3, cw, ch,
                      lambda r, c: "d-hl" if r in kept_rows and c in kept_cols else "d-dim", depth=5)
        body += arrow(centre, src_bottom + 8, res_top - 6)
        body += block(px, res_top, len(kept_rows), 1, tw, ch, lambda r, c: "d-time", depth=5)
        body += block(px + tw + 8, res_top, len(kept_rows), len(kept_cols), cw, ch, lambda r, c: "d-hl", depth=5)
        body += labelled(centre, res_top + rows * ch + 26, code, caption)
    return svg(720, res_top + rows * ch + 54, body, "Three ways to select data: a time range, columns, or a boolean mask")


DIAGRAMS = {"anatomy": anatomy, "slicing": slicing, "spectrogram": spectrogram, "distribution": distribution}


class VariableDiagram(Directive):
    required_arguments = 1

    def run(self):
        return [nodes.raw("", DIAGRAMS[self.arguments[0]](), format="html")]


def setup(app):
    app.add_directive("variable-diagram", VariableDiagram)
    app.add_css_file("diagrams.css")
    return {"parallel_read_safe": True}
