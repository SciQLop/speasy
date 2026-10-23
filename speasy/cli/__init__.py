"""The ``speasy`` command, e.g. ``uvx speasy archive validate my_datasets.yaml``."""
from typing import List, Optional

from cyclopts import App, CycloptsError

from . import archive, config, providers, data, quicklook, index
from ._common import error

app = App(name='speasy', help="Space Physics made EASY.", result_action='return_value')
app.command(archive.app)
app.command(config.app)
app.command(providers.app)
app.command(data.get)
app.command(data.cache_app)
app.command(index.app)
app.command(quicklook.quicklook)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        return app(argv, exit_on_error=False) or 0
    except CycloptsError:  # a usage error, cyclopts already printed what is wrong
        return 2
    except ValueError as e:  # bad names or values given on the command line
        return error(str(e))
