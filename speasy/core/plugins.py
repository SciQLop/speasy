"""Plugin loading shared by every plugin kind Speasy defines (providers, codecs, virtual products):
PEP 621 entry points, and .py files dropped in user directories."""

import logging
import os
import runpy
from importlib.metadata import entry_points

from speasy.config import core as core_cfg

log = logging.getLogger(__name__)


def load_plugins(group: str) -> None:
    """Load and call every entry point declared in the group.

    Each entry point must resolve to a zero-argument callable that performs its own
    registration. A plugin that fails, to import or when called, is reported and skipped:
    third-party code must never break `import speasy`. Entry points named in the
    `core.disabled_plugins` config entry are not loaded at all, either by bare name
    (every group) or by group-qualified name (that group only).
    """
    disabled = core_cfg.disabled_plugins.get()
    for ep in entry_points(group=group):
        if ep.name in disabled or f"{group}.{ep.name}" in disabled:
            log.info(f"Skipping disabled {group} plugin {ep.name} ({ep.value})")
            continue
        try:
            ep.load()()
        except Exception:
            log.warning(f"Failed to load {group} plugin {ep.name} ({ep.value})", exc_info=True)


def _list_dir_abs(path: str):
    return [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.py')]


def load_plugin_files(kind: str, directories) -> None:
    """Run every .py file of each existing directory, each in its own module namespace.

    runpy gives the file one namespace for its globals, so its functions see its own imports
    and helpers. A file that fails is reported and skipped, like a failing entry point.
    """
    for directory in directories:
        if os.path.exists(directory):
            for path in _list_dir_abs(directory):
                try:
                    runpy.run_path(path)
                except Exception:
                    log.warning(f"Failed to load {kind} file {path}", exc_info=True)
