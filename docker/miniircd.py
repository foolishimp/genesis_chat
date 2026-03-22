#!/usr/bin/env python3
"""
miniircd — minimal IRC server for genesis_chat demo.
Supports: NICK, USER, JOIN, PRIVMSG, PING/PONG, QUIT.
Single channel #genesis, no auth, no TLS.
"""
import select
import socket
import sys
import time

HOST = "0.0.0.0"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 6667
SERVER_NAME = "irc.genesis.local"
CHANNEL = "#genesis"


class Client:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.nick = None
        self.user = None
        self.buf = ""
        self.registered = False
        self.in_channel = False

    def send(self, line):
        try:
            self.sock.sendall(f"{line}\r\n".encode())
        except Exception:
            pass

    def fileno(self):
        return self.sock.fileno()


clients: dict[socket.socket, Client] = {}
nicks: dict[str, Client] = {}  # nick → client


def broadcast(sender: Client, msg: str):
    for c in list(clients.values()):
        if c.in_channel and c is not sender:
            c.send(msg)


def handle_line(client: Client, line: str):
    parts = line.split(" ", 3)
    cmd = parts[0].upper()

    if cmd == "PING":
        token = parts[1] if len(parts) > 1 else SERVER_NAME
        client.send(f":{SERVER_NAME} PONG {SERVER_NAME} :{token}")

    elif cmd == "NICK":
        if len(parts) < 2:
            return
        new_nick = parts[1].lstrip(":")
        if new_nick in nicks and nicks[new_nick] is not client:
            client.send(f":{SERVER_NAME} 433 * {new_nick} :Nickname is already in use")
            return
        if client.nick and client.nick in nicks:
            del nicks[client.nick]
        client.nick = new_nick
        nicks[new_nick] = client
        maybe_register(client)

    elif cmd == "USER":
        if len(parts) >= 2:
            client.user = parts[1]
        maybe_register(client)

    elif cmd == "JOIN":
        if not client.registered:
            return
        chan = parts[1].lstrip(":") if len(parts) > 1 else CHANNEL
        if chan.lower() == CHANNEL:
            client.in_channel = True
            client.send(f":{client.nick}!{client.nick}@host JOIN {CHANNEL}")
            client.send(f":{SERVER_NAME} 332 {client.nick} {CHANNEL} :genesis_chat construction channel")
            # Send names list
            nicks_in = " ".join(c.nick for c in clients.values() if c.in_channel and c.nick)
            client.send(f":{SERVER_NAME} 353 {client.nick} = {CHANNEL} :{nicks_in}")
            client.send(f":{SERVER_NAME} 366 {client.nick} {CHANNEL} :End of /NAMES list")
            # Announce join to others
            broadcast(client, f":{client.nick}!{client.nick}@host JOIN {CHANNEL}")

    elif cmd == "PRIVMSG":
        if not client.registered or len(parts) < 3:
            return
        target = parts[1]
        text = parts[2].lstrip(":") if len(parts) == 3 else parts[2].lstrip(":")
        if len(parts) > 3:
            text = parts[2].lstrip(":") + " " + parts[3]
        msg = f":{client.nick}!{client.nick}@host PRIVMSG {target} :{text}"
        if target.lower() == CHANNEL:
            broadcast(client, msg)

    elif cmd == "QUIT":
        remove_client(client)

    elif cmd == "CAP":
        # Ignore capability negotiation
        pass


def maybe_register(client: Client):
    if client.nick and client.user and not client.registered:
        client.registered = True
        client.send(f":{SERVER_NAME} 001 {client.nick} :Welcome to GenesisNet {client.nick}")
        client.send(f":{SERVER_NAME} 376 {client.nick} :End of /MOTD command")


def remove_client(client: Client):
    if client.nick and client.nick in nicks:
        del nicks[client.nick]
    if client.sock in clients:
        del clients[client.sock]
    if client.in_channel:
        broadcast(client, f":{client.nick}!{client.nick}@host QUIT :Disconnected")
    try:
        client.sock.close()
    except Exception:
        pass


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(50)
    print(f"miniircd listening on {HOST}:{PORT}", flush=True)

    while True:
        readable, _, _ = select.select([server, *clients.keys()], [], [], 1.0)
        for s in readable:
            if s is server:
                conn, addr = server.accept()
                c = Client(conn, addr)
                clients[conn] = c
            else:
                client = clients.get(s)
                if not client:
                    continue
                try:
                    data = s.recv(4096).decode("utf-8", errors="replace")
                    if not data:
                        remove_client(client)
                        continue
                    client.buf += data
                    while "\r\n" in client.buf:
                        line, client.buf = client.buf.split("\r\n", 1)
                        if line.strip():
                            handle_line(client, line.strip())
                except Exception:
                    remove_client(client)


if __name__ == "__main__":
    main()
