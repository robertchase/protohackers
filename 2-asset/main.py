import asyncio
from struct import pack, unpack


async def on_connect(reader, writer):
    host, port = writer.get_extra_info("peername")[:2]
    print(f"connection from {host}:{port}")

    data = []
    try:
        while (packet := await reader.readexactly(9)):
            packet = unpack("!cii", packet)
            if packet[0] == b"I":
                data.append(packet[1:])
            elif packet[0] == b"Q":
                beg, end = packet[1:]
                subset = [item[1] for item in data
                          if item[0] >= beg and item[0] <= end]
                result = int(sum(subset) / len(subset)) if subset else 0
                result = pack("!i", result)
                writer.write(result)
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
