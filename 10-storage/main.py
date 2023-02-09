import asyncio
from collections import defaultdict
import re


storage = defaultdict(dict)


def send(writer, message):
    message += "\n"
    writer.write(message.encode())


async def help_handler(reader, writer, _):
    send(writer, "OK usage: HELP|GET|PUT|LIST")


async def put_handler(reader, writer, params):

    def check_name(name):
        if name[0] != "/" \
                or (len(name) > 1 and name[-1] == "/") \
                or "//" in name \
                or not re.match(r"[a-zA-Z0-9-/\._]*$", name):
            name = None
        return name

    def check_length(length):
        try:
            length = int(length)
        except ValueError:
            length = None
        return length

    async def read_data(length):
        data = await reader.readexactly(length)
        for c in data:
            if c < 32 or c > 126:
                if c not in (9, 10, 13):  # HT LF CR
                    data = None
        if data:
            try:
                data = data.decode("ascii")
            except UnicodeDecodeError:
                data = None
        return data

    if len(params) != 2:
        send(writer, "ERR usage: PUT file length newline data")
    elif not (name := check_name(params[0])):
        send(writer, "ERR illegal file name")
    elif not (length := check_length(params[1])):
        send(writer, "OK")
    elif not (data := await read_data(length)):
        send(writer, "ERR invalid file data")
    else:
        s = storage[name]
        rid = f"r{len(s)+1}"
        if len(s):
            last_key, last_val = list(s.items())[-1]
        else:
            last_val = None
        if data == last_val:
            rid = last_key
        else:
            s[rid] = data
        send(writer, f"OK {rid}")


async def get_handler(reader, writer, params):
    if len(params) == 1:
        params.append("-")
    if len(params) != 2:
        send(writer, "ERR illegal file name")
    else:
        name, revision = params
        if name[0] != "/":
            send(writer, "ERR illegal file name")
        elif name not in storage:
            send(writer, "ERR no such file")
        else:
            s = storage[name]
            if revision == "-":
                revision = list(s.keys())[-1]
            if revision not in s:
                send(writer, "ERR no such revision")
            else:
                data = s[revision]
                send(writer, f"OK {len(data)}")
                writer.write(data.encode())


async def list_handler(reader, writer, params):
    if len(params) != 1:
        send(writer, "ERR usage: list dir")
    else:
        name, = params
        if name[-1] != "/":
            name += "/"
        listing = {}
        for key, val in storage.items():
            if key.startswith(name):
                key = key[len(name):]
                if "/" in key:
                    key = key.split("/")[0] + "/"
                    rev = "DIR"
                else:
                    rev = list(val.keys())[-1]
                listing[key] = rev
        if len(listing) == 0:
            send(writer, "ERR file not found")
        else:
            listing = [f"{key} {rev}" for key, rev in listing.items()]
            send(writer, f"OK {len(listing)}")
            for fn in sorted(listing):
                send(writer, fn)


async def on_connect(reader, writer):
    host, port = writer.get_extra_info("peername")[:2]
    print(f"connection from {host}:{port}")

    try:
        while True:
            send(writer, "READY")
            line = await reader.readline()
            print(f"{line=}")
            toks = line.decode().strip().split()
            if len(toks) == 0:
                send(writer, "ERR illegal method:")
                break
            else:
                cmd = toks[0].upper()
                handler = {
                    "HELP": help_handler,
                    "PUT": put_handler,
                    "GET": get_handler,
                    "LIST": list_handler,
                }.get(cmd)

            if handler:
                await handler(reader, writer, toks[1:])
            else:
                send(writer, f"ERR illegal method: {cmd}")

    finally:
        print(f"closed connection {host}:{port}")
        writer.close()


async def main():
    server = await asyncio.start_server(on_connect, port=12345)
    print(f"listening on port {server.sockets[0].getsockname()[1]}")
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
