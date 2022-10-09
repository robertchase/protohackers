import asyncio


class Protocol(asyncio.DatagramProtocol):

    def __init__(self):
        self.store = {"version": "release=2.0"}

    @classmethod
    def create(cls):
        return cls()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, message, address):
        message = message.decode()
        print(address, message)

        if "=" in message:
            key, value = message.split("=", 1)
            if key != "version":
                self.store[key] = value
        else:
            value = self.store.get(message, "")
            response = f"{message}={value}"
            self.transport.sendto(response.encode(), address)


async def main(host, port):
    """this is non-blocking, just because.

       this would be useful if other blocking things had to share the loop
       but, since nothing else is happening, this is overkill.
    """
    loop = asyncio.get_running_loop()
    print(f"listening on {port}")

    # note: one Protocol instance gets created for this port
    transport, protocol = await loop.create_datagram_endpoint(
        Protocol.create, local_addr=(host, port))

    # run_forever kludge
    while loop.is_running:
        await asyncio.sleep(10)


if __name__ == "__main__":
    from os import getenv
    asyncio.run(main(getenv("HOST", "127.0.0.1"), int(getenv("PORT", 12345))))
