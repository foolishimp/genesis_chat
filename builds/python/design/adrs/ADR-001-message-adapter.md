# ADR-001: MessageAdapter Interface and EchoAdapter

**Status**: Accepted
**Implements**: REQ-F-CHAN-001, REQ-F-CHAN-002, REQ-F-CHAN-003
**Date**: 2026-03-17

## Decision

Define `MessageAdapter` as a platform-agnostic ABC with three methods. Implement
`EchoAdapter` as the V1 spike substrate using stdin/stdout. The channel loop is a
`while True` receive → dispatch → send cycle.

## Interface

```
MessageAdapter (ABC)
  receive() → ChatMessage
  send(response: ChannelResponse) → None
  request_approval(msg: ChatMessage, prompt: str) → str  # returns pending_op_id

ChatMessage
  id: str          # platform message ID
  text: str        # raw message text
  sender_id: str   # agent identity or "human"
  channel_id: str
  platform: str    # "echo" | "slack" | "discord"  (V2+)

ChannelResponse
  text: str
  reply_to: str    # ChatMessage.id
  sender: str      # agent identity that produced this response
```

`EchoAdapter` reads one line per message from stdin, writes responses to stdout
prefixed with `[{sender}]`. `request_approval` posts the prompt to stdout and
blocks on the next stdin line (y/n).

## Channel loop

```
channel = EchoAdapter()
dispatcher = Dispatcher(registry, bindings)
while True:
    msg = channel.receive()
    response = dispatcher.dispatch(msg)
    channel.send(response)
```

## Consequences

- EchoAdapter has no networking, no credentials, no async — spike runs anywhere
- Swapping to SlackAdapter in V2 requires no change to dispatcher or agent code
- `request_approval` blocking model is acceptable for CLI; V2 platform adapters
  will use async approval flows (reactions, buttons)
