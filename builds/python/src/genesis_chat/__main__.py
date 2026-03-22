# Implements: REQ-F-CHAN-003
# Implements: REQ-F-AREG-001
# Implements: REQ-F-SSE-001
"""Entry point: python -m genesis_chat [options]

  --adapter echo              Local stdin/stdout (default)
  --adapter irc               IRC channel
  --sse-port 8086             Enable SSE event stream on given port
  --presence-only             Join channel but do not dispatch (observer/second slot)
  --agent-nicks nick1,nick2   Nicks to treat as agents — ignore their messages (prevents loops)
"""
import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="genesis_chat — multi-agent construction channel")
    parser.add_argument("--workspace", default=".", help="Root workspace directory")
    parser.add_argument("--config", default=None, help="Config directory (default: auto)")
    parser.add_argument("--adapter", default="echo", help="Adapter name (echo, irc, or any registered adapter)")
    parser.add_argument("--sse-port", type=int, default=None,
                        help="Enable SSE event stream on this port (e.g., 8086)")
    parser.add_argument("--sse-host", default="0.0.0.0",
                        help="SSE server bind address (default: 0.0.0.0)")
    parser.add_argument("--presence-only", action="store_true",
                        help="Connect to channel but do not dispatch messages (presence slot)")
    parser.add_argument("--agent-nicks", default="",
                        help="Comma-separated nicks to ignore (prevents agent→agent loops)")
    # IRC options (passthrough to IRCConfig via adapter registry)
    parser.add_argument("--irc-host", default="localhost")
    parser.add_argument("--irc-port", type=int, default=6667)
    parser.add_argument("--irc-nick", default="genesis_chat")
    parser.add_argument("--irc-channel", default="#genesis")
    args = parser.parse_args()

    ws = Path(args.workspace).resolve()
    if not ws.exists():
        print(f"Error: workspace not found: {ws}", file=sys.stderr)
        sys.exit(1)

    if args.config:
        config_dir = Path(args.config).resolve()
    elif Path("/app/agents.yml").exists():
        config_dir = Path("/app")
    else:
        config_dir = ws

    agent_nicks = {n.strip() for n in args.agent_nicks.split(",") if n.strip()}
    adapter_name = args.adapter

    # Try adapter registry first, fallback to hardcoded for backwards compat
    adapters_yml = config_dir / "adapters.yml"
    if not adapters_yml.exists():
        adapters_yml = ws / "adapters.yml"

    if adapters_yml.exists():
        from genesis_chat.adapter.registry import AdapterRegistry
        registry = AdapterRegistry(adapters_yml)

        # Validate at startup
        validation = registry.validate_all()
        for name, err in validation.items():
            if err:
                print(f"Warning: adapter '{name}' unavailable: {err}", file=sys.stderr)

        # Build adapter kwargs from CLI args
        adapter_kwargs = {}
        if adapter_name == "irc":
            adapter_kwargs = {
                "host": args.irc_host,
                "port": args.irc_port,
                "nick": args.irc_nick,
                "channel": args.irc_channel,
            }
            if agent_nicks:
                adapter_kwargs["agent_nicks"] = agent_nicks

        try:
            adapter = registry.resolve(adapter_name, **adapter_kwargs)
        except (ValueError, ImportError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Fallback: hardcoded adapter resolution (V1 compat)
        if adapter_name == "irc":
            from genesis_chat.adapter.irc import IRCAdapter, IRCConfig
            cfg = IRCConfig(
                host=args.irc_host,
                port=args.irc_port,
                nick=args.irc_nick,
                channel=args.irc_channel,
            )
            adapter = IRCAdapter(cfg, agent_nicks=agent_nicks)
        else:
            from genesis_chat.adapter.echo import EchoAdapter
            adapter = EchoAdapter()

    # IRC-specific: connect and optionally run in presence-only mode
    if adapter_name == "irc":
        print(f"Connecting to IRC {args.irc_host}:{args.irc_port} as {args.irc_nick} ...")
        adapter.connect()
        print(f"Joined {args.irc_channel}. Workspace: {ws}")

        if args.presence_only:
            print(f"Presence-only mode — {args.irc_nick} is in channel but will not dispatch.")
            try:
                while True:
                    adapter.receive()
            except (KeyboardInterrupt, SystemExit):
                adapter.disconnect()
            return

    # Run main channel loop
    from genesis_chat.channel import run
    run(
        workspace_root=str(ws),
        config_dir=str(config_dir),
        adapter=adapter,
        platform=adapter_name,
        sse_port=args.sse_port,
        sse_host=args.sse_host,
        irc_host=args.irc_host,
        irc_port=args.irc_port,
        irc_channel=args.irc_channel,
        nick=args.irc_nick,
    )

    # Cleanup IRC if needed
    if adapter_name == "irc" and hasattr(adapter, "disconnect"):
        adapter.disconnect()


if __name__ == "__main__":
    main()
