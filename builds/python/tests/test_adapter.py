# Validates: REQ-F-CHAN-001
# Validates: REQ-F-CHAN-002
"""Tests for MessageAdapter ABC and EchoAdapter."""
from __future__ import annotations

import io
import sys
from unittest.mock import patch

import pytest

from genesis_chat.adapter.base import ChatMessage, ChannelResponse, MessageAdapter
from genesis_chat.adapter.echo import EchoAdapter


def test_chat_message_fields():
    msg = ChatMessage(id="MSG-0001", text="hello", sender_id="human",
                      channel_id="echo-main", platform="echo")
    assert msg.id == "MSG-0001"
    assert msg.text == "hello"
    assert msg.metadata == {}


def test_channel_response_fields():
    resp = ChannelResponse(text="hi", reply_to="MSG-0001", sender="genesis_chat")
    assert resp.text == "hi"
    assert resp.sender == "genesis_chat"


def test_message_adapter_is_abstract():
    with pytest.raises(TypeError):
        MessageAdapter()


def test_echo_adapter_receive():
    with patch("builtins.input", return_value="hello world"):
        adapter = EchoAdapter()
        msg = adapter.receive()
    assert msg.text == "hello world"
    assert msg.sender_id == "human"
    assert msg.platform == "echo"
    assert msg.id == "MSG-0001"


def test_echo_adapter_seq_increments():
    with patch("builtins.input", side_effect=["first", "second"]):
        adapter = EchoAdapter()
        m1 = adapter.receive()
        m2 = adapter.receive()
    assert m1.id == "MSG-0001"
    assert m2.id == "MSG-0002"


def test_echo_adapter_send(capsys):
    adapter = EchoAdapter()
    resp = ChannelResponse(text="response text", reply_to="MSG-0001", sender="claude")
    adapter.send(resp)
    captured = capsys.readouterr()
    assert "[claude] response text" in captured.out


def test_echo_adapter_eof_raises_system_exit():
    with patch("builtins.input", side_effect=EOFError):
        adapter = EchoAdapter()
        with pytest.raises(SystemExit):
            adapter.receive()


def test_echo_adapter_approval_yes():
    with patch("builtins.input", return_value="y"):
        adapter = EchoAdapter()
        msg = ChatMessage(id="MSG-0001", text="deploy?", sender_id="human",
                          channel_id="echo-main", platform="echo")
        op_id = adapter.request_approval(msg, "Deploy to staging?")
    assert adapter.get_approval_status(op_id) == "approved"


def test_echo_adapter_approval_no():
    with patch("builtins.input", return_value="n"):
        adapter = EchoAdapter()
        msg = ChatMessage(id="MSG-0001", text="deploy?", sender_id="human",
                          channel_id="echo-main", platform="echo")
        op_id = adapter.request_approval(msg, "Deploy to staging?")
    assert adapter.get_approval_status(op_id) == "rejected"


def test_echo_adapter_unknown_op_id():
    adapter = EchoAdapter()
    assert adapter.get_approval_status("nonexistent") is None
