import asyncio
import re


users = {}


async def send(stream, message):
    stream.write(message.encode())
    await stream.drain()


async def notify(message, exclude=None):
    work = [send(writer, message) for name, writer in users.items()
            if name != exclude]
    await asyncio.gather(*work)


async def on_connect(reader, writer):
    host, port = writer.get_extra_info("peername")[:2]
    print(f"connection from {host}:{port}")

    try:
        await send(writer, "what's your name?\n")
        if not (name := await reader.readline()):
            raise Exception("remote close")
        name = name.decode().strip()
        if not name:
            raise Exception("name is null")
        if not re.match("[a-zA-Z0-9]+$", name):
            raise Exception("invalid characters in name")
        if name in users:
            raise Exception("duplicate user")
        await notify(f"* {name} has entered the room\n")
        await send(writer, "* the room contains: "
                   f"{', '.join(name for name in users.keys())}\n")
        users[name] = writer

        while (line := await reader.readline()):
            line = line.decode()
            await notify(f"[{name}] {line}", exclude=name)

        del users[name]
        await notify(f"* {name} has left the room\n")
    except Exception as exc:
        print(f"exception {host}:{port} {exc}")
    finally:
        print(f"closed connection {host}:{port}")
        writer.close()


async def main():
    server = await asyncio.start_server(on_connect, port=12345)
    print(f"listening on port {server.sockets[0].getsockname()[1]}")
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
