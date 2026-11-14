"""OpenViking memory, with scheduler-injected turns relabelled before they are stored.

Hermes hands a turn a plugin injected (``ctx.inject_message``) to memory providers as if the person
had typed it (NousResearch/hermes-agent#130622), so OpenViking extracts "facts about the user"
from a wake's instructions. This provider is the installed OpenViking plugin with one change: such
a turn's user side is replaced by a short label first (see ``filtering.py``).

``name`` stays "openviking": OpenViking reads its settings from the literal ``memory.openviking``
section, and the provider is the same backend, only selected through ``memory.provider:
openviking_filtered``.
"""

from __future__ import annotations

from plugins.memory import import_provider_module

from .filtering import InjectedTurnFilterMixin

UPSTREAM_PROVIDER = "openviking"


def _upstream_provider_class() -> type:
    try:
        module = import_provider_module(UPSTREAM_PROVIDER)
    except ImportError as exc:
        raise ImportError(
            "openviking_filtered wraps the OpenViking memory plugin, which is not installed: "
            "run `hermes plugins install openviking` first"
        ) from exc
    return module.OpenVikingMemoryProvider


class FilteredOpenVikingMemoryProvider(InjectedTurnFilterMixin, _upstream_provider_class()):
    """OpenViking with injected turns relabelled in ``sync_turn``."""


def register(ctx) -> None:
    ctx.register_memory_provider(FilteredOpenVikingMemoryProvider())
