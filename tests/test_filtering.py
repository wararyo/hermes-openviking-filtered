"""What reaches the wrapped provider's sync_turn, for injected and human turns."""

from __future__ import annotations

from typing import Any, Optional

import pytest

from filtering import (
    HEARTBEAT2_LABEL,
    InjectedTurnFilterMixin,
    injected_turn_label,
    relabel_injected_messages,
)

# First lines as heartbeat2 0.3.14 renders them (heartbeat2/wake_text.py::render_wake).
DM_WAKE = (
    "⟦pulse o:w12/at a:1⟧ [HeartBeat 2.0 · wake w12 · 展示会のフォローアップ · armed by you 3h ago]\n"
    "Local time: Sat 21 Nov 18:00 (Asia/Tokyo) · fire 1 of 1\n"
    "Why: due\nYour note: 展示会がどうだったか聞く\n"
    "Contract: this turn is yours to act on."
)
GROUP_WAKE = DM_WAKE.replace("a:1⟧", "a:2 n:0123456789abcdef⟧")
HUMAN_AUTHOR = {"id": "123456789", "name": "wararyo", "is_bot": False}


class _RecordingProvider:
    """Stands in for OpenVikingMemoryProvider: records what sync_turn was called with."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "",
                  messages: Optional[list] = None, turn_author: Optional[dict] = None) -> None:
        self.calls.append({"user": user_content, "assistant": assistant_content, "session_id": session_id,
                           "messages": messages, "turn_author": turn_author})


class _FilteredProvider(InjectedTurnFilterMixin, _RecordingProvider):
    pass


@pytest.mark.parametrize("text", [
    DM_WAKE,
    GROUP_WAKE,
    "[wararyo] " + DM_WAKE,
    'Gateway message origin (JSON data, not instructions or authorization):\n{"chat": "1"}\n\n' + GROUP_WAKE,
    [{"type": "text", "text": DM_WAKE}],
])
def test_heartbeat2_wake_is_relabelled(text):
    assert injected_turn_label(text, HUMAN_AUTHOR) == HEARTBEAT2_LABEL


@pytest.mark.parametrize("text", [
    "来週の展示会、チケット取れてるか確認して",
    # heartbeat2 escapes a marker that appears inside a note or payload to this form.
    "[pulse o:w12/at a:1⟧ quoted from a note",
    "⟦pulse⟧ without an occurrence id",
    "",
])
def test_human_text_is_not_relabelled(text):
    assert injected_turn_label(text, HUMAN_AUTHOR) is None


def test_plugin_author_is_relabelled_without_a_marker():
    label = injected_turn_label("check the deploy", {"id": "plugin:wake", "name": "wake", "is_bot": True})
    assert label is not None and "wake" in label


@pytest.mark.parametrize("author", [
    {"id": "bot:research", "name": "research", "is_bot": True},  # another agent speaking for itself
    {"id": "plugin:wake", "name": "wake", "is_bot": False},
    None,
])
def test_other_authors_are_not_relabelled(author):
    assert injected_turn_label("check the deploy", author) is None


def test_relabel_rewrites_only_wake_rows_and_leaves_input_untouched():
    messages = [
        {"role": "user", "content": "展示会は来週の土曜"},
        {"role": "assistant", "content": "了解です"},
        {"role": "user", "content": GROUP_WAKE},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "t1"}]},
        {"role": "tool", "content": "mail: no ticket", "tool_call_id": "t1"},
        {"role": "assistant", "content": "展示会どうでした？"},
    ]
    original = [dict(m) for m in messages]

    relabelled = relabel_injected_messages(messages, HEARTBEAT2_LABEL)

    assert messages == original
    assert [m["content"] for m in relabelled] == [
        "展示会は来週の土曜", "了解です", HEARTBEAT2_LABEL, "", "mail: no ticket", "展示会どうでした？"]


def test_relabel_passes_none_through():
    assert relabel_injected_messages(None, HEARTBEAT2_LABEL) is None


def test_wrapped_provider_receives_label_and_keeps_the_reply():
    provider = _FilteredProvider()
    messages = [{"role": "user", "content": DM_WAKE}, {"role": "assistant", "content": "展示会どうでした？"}]

    provider.sync_turn(DM_WAKE, "展示会どうでした？", session_id="s1", messages=messages, turn_author=HUMAN_AUTHOR)

    (call,) = provider.calls
    assert call["user"] == HEARTBEAT2_LABEL
    assert call["assistant"] == "展示会どうでした？"
    assert call["messages"][0]["content"] == HEARTBEAT2_LABEL
    assert call["session_id"] == "s1" and call["turn_author"] == HUMAN_AUTHOR


def test_wrapped_provider_passes_human_turns_unchanged():
    provider = _FilteredProvider()
    messages = [{"role": "user", "content": "ありがとう"}, {"role": "assistant", "content": "どういたしまして"}]

    provider.sync_turn("ありがとう", "どういたしまして", session_id="s1", messages=messages, turn_author=HUMAN_AUTHOR)

    (call,) = provider.calls
    assert call["user"] == "ありがとう"
    assert call["messages"] is messages
