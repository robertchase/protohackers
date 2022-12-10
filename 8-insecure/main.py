import asyncio


def reversebits(byte, _):
    # faster than individual bit manipulation
    return int(bin(byte)[2:].rjust(8, "0")[::-1], 2)


def xor(val):
    val = val & 255
    def inner(byte, _):
        return byte ^ val
    return inner


def xorpos(byte, pos):
    return (byte ^ pos) & 255


def add(val):
    def inner(byte, _):
        return (byte + val) & 255
    return inner


def addpos(byte, pos):
    return (byte + pos) & 255


def sub(val):
    def inner(byte, _):
        return (byte - val) & 255
    return inner


def subpos(byte, pos):
    return (byte - pos) & 255


def crypt(byte, cipher, pos):
    for fn in cipher:
        byte = fn(byte, pos)
    return byte


class Reader:

    def __init__(self, reader, cipher):
        self.reader = reader
        self.cipher = cipher
        self.read_length = 0

    async def readline(self):
        line = ""
        while True:
            byte = (await self.reader.readexactly(1))[0]
            char = crypt(byte, self.cipher, self.read_length)
            self.read_length += 1
            if char == 10:
                break
            line += chr(char)

        return line


class Writer:

    def __init__(self, writer, cipher):
        self.writer = writer
        self.cipher = cipher
        self.write_length = 0

    def writeline(self, line):
        line += "\n"
        data = []
        for c in line:
            data.append(crypt(ord(c), self.cipher, self.write_length))
            self.write_length += 1
        self.writer.write(bytes(data))

    def close(self):
        self.writer.close()


def test_cipher(cipher, decipher):
    test = bytes(i for i in range(256))
    enc = bytes([crypt(b, cipher, p)
                 for p, b in enumerate([c for c in test])])
    if enc == test:
        raise Exception("NOP cipher specified")

    dec = bytes([crypt(b, decipher, p)
                 for p, b in enumerate([c for c in enc])])
    if dec != test:
        raise Exception("cipher/decipher don't match")  # self-check


async def on_connect(reader, writer):
    host, port = writer.get_extra_info("peername")[:2]
    print(f"connection from {host}:{port}")

    cipher = []
    decipher = []

    try:
        while not reader.at_eof():
            spec = (await reader.readexactly(1))[0]

            if spec == 0x00:
                break

            elif spec == 0x01:
                cipher.append(reversebits)
                decipher.insert(0, reversebits)

            elif spec == 0x02:
                xor_with = (await reader.readexactly(1))[0]
                cipher.append(xor(xor_with))
                decipher.insert(0, xor(xor_with))

            elif spec == 0x03:
                cipher.append(xorpos)
                decipher.insert(0, xorpos)

            elif spec == 0x04:
                add_with = (await reader.readexactly(1))[0]
                cipher.append(add(add_with))
                decipher.insert(0, sub(add_with))

            elif spec == 0x05:
                cipher.append(addpos)
                decipher.insert(0, subpos)

        test_cipher(cipher, decipher)

        reader = Reader(reader, decipher)
        writer = Writer(writer, cipher)

        while True:
            line = await reader.readline()
            parts = sorted([(int(part[:part.index("x")]), part)
                            for part in line.split(",")])
            largest = parts[-1][-1]
            print(f"{host}:{port} {largest}")
            writer.writeline(largest)

    except asyncio.IncompleteReadError:
        pass
    finally:
        print(f"closed connection {host}:{port}")
        writer.close()


async def main():
    server = await asyncio.start_server(on_connect, port=12345)
    print(f"listening on port {server.sockets[0].getsockname()[1]}")
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
