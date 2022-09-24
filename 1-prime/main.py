import asyncio
import json


def is_prime(num):
    if int(num) != float(num):
        return False
    if num <= 1:
        return False
    if num == 2:
        return True
    if num % 2 == 0:
        return False
    for i in range(3, int(num ** 0.5) + 1, 2):
        if num % i == 0:
            return False
    return True


async def on_connect(reader, writer):
    host, port = writer.get_extra_info("peername")[:2]
    print(f"connection from {host}:{port}")

    try:
        while (data := await reader.readline()):
            data = data.decode()
            print(f"[{host}:{port}] {data}")
            jdata = json.loads(data)
            method = jdata["method"]
            if method != "isPrime":
                raise Exception(f"invalid method: {method}")
            number = jdata["number"]
            if isinstance(number, bool):
                raise Exception(f"invalid number (boolean): {number}")
            if not isinstance(number, (int, float)):
                raise Exception(f"invalid number: {number}")
            result = {"method": "isPrime", "prime": is_prime(number)}
            writer.write(json.dumps(result).encode())
            writer.write(b"\n")
            await writer.drain()
    except Exception as exc:
        print(f"exception {host}:{port} {repr(exc)}")
    finally:
        print(f"closed connection {host}:{port}")
        writer.close()


async def main():
    server = await asyncio.start_server(on_connect, port=12345)
    print(f"listening on port {server.sockets[0].getsockname()[1]}")
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
