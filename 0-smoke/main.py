import asyncio


async def on_connect(reader, writer):
    host, port = writer.get_extra_info("peername")[:2]
    print(f"connection from {host}:{port}")

    try:
        while (data := await reader.read(100)):
            print(f"[{host}:{port}] {data}")
            writer.write(data)
            await writer.drain()
    finally:
        print(f"closed connection {host}:{port}")
        writer.close()


async def main():
    server = await asyncio.start_server(on_connect, port=12345)
    print(f"listening on port {server.sockets[0].getsockname()[1]}")
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
