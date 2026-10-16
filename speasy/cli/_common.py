from rich.console import Console
from rich.table import Table

from speasy.config import ConfigEntry, entry_source


def console() -> Console:
    # built per call: Console() binds to sys.stdout when created, and tests redirect it
    return Console()


def error(message: str) -> int:
    Console(stderr=True).print(f"[red]Error:[/red] {message}", highlight=False)
    return 1


def table(*columns: str, rows) -> Table:
    t = Table(*columns, show_header=any(columns))
    for row in rows:
        t.add_row(*row)
    return t


def warn_if_env_overrides(entry: ConfigEntry):
    if entry_source(entry) == 'env':
        console().print(f"[yellow]Note:[/yellow] the {entry.env_var_name} environment variable is set, "
                        f"it overrides the config file until you unset it.", highlight=False)
