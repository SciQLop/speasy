from cyclopts import App

from speasy.config import core as core_cfg, add_values, remove_values
from speasy.core.dataprovider import registered_providers, provider_names, main_provider_name
from ._common import console, table, warn_if_env_overrides

app = App(name='providers', help="List, enable and disable data providers.")


def _main_name(name: str) -> str:
    main_name = main_provider_name(name)
    if main_name is None:
        raise ValueError(f"unknown provider '{name}', known ones are: {', '.join(registered_providers())}")
    return main_name


@app.command(name='list')
def list_providers() -> int:
    """List every provider, whether it is enabled, and its other names."""
    disabled = core_cfg.disabled_providers.get()
    rows = [(name, 'no' if disabled.intersection(provider_names(name)) else 'yes', ', '.join(provider_names(name)[1:]))
            for name in registered_providers()]
    console().print(table('Provider', 'Enabled', 'Aliases', rows=rows))
    return 0


@app.command
def enable(*names: str) -> int:
    """Enable providers, under any of their names."""
    main_names = [_main_name(name) for name in names]
    remove_values(core_cfg.disabled_providers, [n for main in main_names for n in provider_names(main)])
    warn_if_env_overrides(core_cfg.disabled_providers)
    return 0


@app.command
def disable(*names: str) -> int:
    """Disable providers: a disabled provider never starts, even when you use it."""
    add_values(core_cfg.disabled_providers, [_main_name(name) for name in names])
    warn_if_env_overrides(core_cfg.disabled_providers)
    return 0
