"""Recognise turns a scheduler plugin injected into a conversation and relabel them before memory.

No Hermes imports, so the tests run without a Hermes install.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Optional

# heartbeat2 opens every wake with this marker (heartbeat2/wake_text.py::render_wake); group and
# topic chats add an ` n:<16 hex>` tag. Hermes may put a sender prefix or an origin block before it,
# so it is searched for, not anchored. heartbeat2 rewrites `⟦pulse` in notes and payloads to
# `[pulse`, so text a person or a watched source wrote cannot carry it.
HEARTBEAT2_MARKER = re.compile(r"⟦pulse o:\S+ a:\d+(?: n:[0-9a-f]{16})?⟧")

HEARTBEAT2_LABEL = (
    "[自動ターン: HeartBeat 2.0 の予約によりエージェント自身が起動した。"
    "この行はユーザーの発言ではない]"
)
PLUGIN_LABEL = "[自動ターン: プラグイン {plugin} が会話に差し込んだ。この行はユーザーの発言ではない]"

# The author Hermes gives a plugin-injected turn once NousResearch/hermes-agent#130622 lands.
_PLUGIN_AUTHOR_PREFIX = "plugin:"


def message_text(content: Any) -> str:
    """Plain text of a message ``content``: a string, or a list of OpenAI-style parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, Mapping) and isinstance(part.get("text"), str):
                texts.append(part["text"])
        return "\n".join(texts)
    return ""


def injected_turn_label(user_content: Any, turn_author: Optional[Mapping[str, Any]]) -> Optional[str]:
    """The label that replaces this turn's user side, or None for a turn a person wrote."""
    if HEARTBEAT2_MARKER.search(message_text(user_content)):
        return HEARTBEAT2_LABEL
    if isinstance(turn_author, Mapping) and turn_author.get("is_bot"):
        author_id = str(turn_author.get("id") or "")
        # A `bot:` author is another agent speaking for itself; only plugin injections are relabelled.
        if author_id.startswith(_PLUGIN_AUTHOR_PREFIX):
            return PLUGIN_LABEL.format(plugin=author_id[len(_PLUGIN_AUTHOR_PREFIX):] or "unknown")
    return None


def relabel_injected_messages(messages: Optional[list], label: str) -> Optional[list]:
    """A copy of ``messages`` whose heartbeat2 wake rows carry ``label``; the input is not mutated.

    OpenViking slices the current turn out of ``messages`` by matching the user row against
    ``user_content``; relabelling the rows too keeps that match exact.
    """
    if messages is None:
        return None
    relabelled = []
    for message in messages:
        if (
            isinstance(message, Mapping)
            and message.get("role") == "user"
            and HEARTBEAT2_MARKER.search(message_text(message.get("content")))
        ):
            message = {**message, "content": label}
        relabelled.append(message)
    return relabelled


class InjectedTurnFilterMixin:
    """Put before a memory provider class: injected turns reach its ``sync_turn`` relabelled.

    Only the user side changes. The assistant reply and tool results are kept, so what the agent
    found or did during a wake is still remembered. The signature names ``messages`` and
    ``turn_author`` because Hermes passes each keyword only to a ``sync_turn`` that accepts it.
    """

    def sync_turn(
        self, user_content: str, assistant_content: str, *, session_id: str = "",
        messages: Optional[list] = None, turn_author: Optional[dict[str, Any]] = None,
    ) -> None:
        label = injected_turn_label(user_content, turn_author)
        if label is not None:
            user_content = label
            messages = relabel_injected_messages(messages, label)
        super().sync_turn(  # type: ignore[misc]
            user_content, assistant_content, session_id=session_id,
            messages=messages, turn_author=turn_author,
        )
