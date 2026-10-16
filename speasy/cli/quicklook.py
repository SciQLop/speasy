import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated, Optional

from cyclopts import Parameter

from ._common import console, error


def _image_name(name: str, start, image_format: str) -> str:
    return f"{name.replace(os.sep, '_').replace(' ', '_')}_{start:%Y%m%dT%H%M%S}.{image_format}"


def quicklook(template: str, *, start: Optional[str] = None, stop: Optional[str] = None, split: str = 'daily',
              output_dir: str = '.', image_format: Annotated[str, Parameter(name='--format')] = 'png',
              workers: int = 1) -> int:
    """Render a SciQLop plot template as one image per time window.

    Only speasy products on time series plots are drawn, anything else is listed as skipped.

    Parameters
    ----------
    template: str
        SciQLop template file (.json or .yaml), e.g. from ~/.local/share/sciqlop/templates.
    start: Optional[str]
        Start time, defaults to the template's own time range.
    stop: Optional[str]
        Stop time, defaults to the template's own time range.
    split: str
        One image per day, month or year: 'daily', 'monthly', 'yearly', or 'none' for a single image.
    output_dir: str
        Where the images go.
    image_format: str
        Image format, anything matplotlib writes: png, pdf, svg...
    workers: int
        How many windows are downloaded at the same time.
    """
    from speasy.plotting.quicklook import fetch_window, render, windows
    from speasy.plotting.sciqlop_template import load_template
    loaded = load_template(template)
    for skipped in loaded.skipped:
        console().print(f"[yellow]skipped[/yellow] {skipped}", highlight=False)
    if not loaded.plots:
        return error(f"{template} has nothing Speasy can render")
    if (start is None) != (stop is None):
        return error("--start and --stop go together")
    start, stop = (start, stop) if start is not None else (loaded.time_range or (None, None))
    if start is None:
        return error(f"{template} stores no time range, give one with --start and --stop")
    if workers < 1:
        return error(f"--workers must be at least 1, got {workers}")
    os.makedirs(output_dir, exist_ok=True)
    failed = False
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_window, loaded, s, e): (s, e) for s, e in windows(start, stop, split)}
        for future in as_completed(futures):  # matplotlib is not thread safe: render on this thread only
            (s, e), (data, failures) = futures[future], future.result()
            path = os.path.join(output_dir, _image_name(loaded.name, s, image_format))
            render(loaded, data, s, e, path)
            mark = "[red]✗[/red]" if failures else "[green]✓[/green]"
            console().print(f"{mark} {path}", highlight=False)
            for failure in failures:
                console().print(f"    {failure}", highlight=False)
            failed = failed or bool(failures)
    return 1 if failed else 0
