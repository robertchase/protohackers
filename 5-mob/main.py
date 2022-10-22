import asyncio
import re


up_url = "chat.protohackers.com"
up_port = 16963
hack = "7YWHMfk9JZe0LM0g1ZauHuiSxhI"


async def handle_connection(id, is_client, reader, writer):
    try:
        while not reader.at_eof():
            line = await reader.readline()
            if line:
                line = line.decode()
                print(f"->{'client' if is_client else 'server'}:{id}" + line)
                line = re.sub(r"(?<!\S)7[a-zA-Z0-9]{25,34}(?!\S)", hack, line)
                print(f"<--{'server' if is_client else 'client'}:{id}" + line)
                writer.write(line.encode())
    except Exception as exc:
        print(f"exception {'client' if is_client else 'server'}:{id} {exc}")
    finally:
        print(f"closed {'client' if is_client else 'server'}:{id}")
        writer.close()


async def on_connect(reader, writer):
    host, port = writer.get_extra_info("peername")[:2]
    print(f"connection from {host}:{port}")
    id = f"{port} "
    up_reader, up_writer = await asyncio.open_connection(up_url, up_port)
    asyncio.create_task(handle_connection(id, False, up_reader, writer))
    await handle_connection(id, True, reader, up_writer)


async def main(port=12345):
    server = await asyncio.start_server(on_connect, port=port)
    print(f"listening on port {port}")
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
