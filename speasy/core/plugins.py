"""PEP 621 entry-point plugin loading, shared by every plugin group Speasy defines
(codecs today, virtual products when they land)."""

import logging
from importlib.metadata import entry_points

from speasy.config import core as core_cfg

log = logging.getLogger(__name__)


def load_plugins(group: str) -> None:
    """Load and call every entry point declared in the group.

    Each entry point must resolve to a zero-argument callable that performs its own
    registration. A plugin that fails, to import or when called, is reported and skipped:
    third-party code must never break `import speasy`. Entry points named in the
    `core.disabled_plugins` config entry are not loaded at all.
    """
    disabled = core_cfg.disabled_plugins.get()
    for ep in entry_points(group=group):
        if ep.name in disabled:
            log.info(f"Skipping disabled plugin {ep.name} ({ep.value})")
            continue
        try:
            ep.load()()
        except Exception:
            log.warning(f"Failed to load plugin {ep.name} ({ep.value})", exc_info=True)
