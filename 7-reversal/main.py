import asyncio
import re
import socket


sessions = {}
SESSION_TIMEOUT = 60
RETRANSMISSION_TIMEOUT = 3


class ReadBuffer:

    def __init__(self):
        self.buffer = ""
        self.length = 0

    def add(self, pos, data):
        append = data[self.length - pos:]
        self.buffer += append
        self.length += len(append)
        return len(append) > 0

    def readline(self):
        line = None
        if 0 <= (end := self.buffer.find("\n")):
            line, self.buffer = self.buffer[:end], self.buffer[end + 1:]
        return line


class WriteBuffer:

    def __init__(self, writer, session_id):
        self.writer = writer
        self.session_id = session_id
        self.buffer = ""
        self.length = 0
        self.acked = 0
        self.sending = None

    def add(self, line):
        self.buffer += line + "\n"
        self.length += len(line) + 1

    def send_all(self):
        if self.sending:
            self.sending.cancel()
        self.sending = asyncio.create_task(self.send_chunked(self.buffer))

    async def send_chunked(self, data):

        def send_in_parts(parts):
            sent = self.acked
            while parts:
                part, parts = parts[:500], parts[500:]  # max msg size 1000
                part = part.replace("/", r"\/").replace("\\", r"\\")
                message = f"/data/{self.session_id}/{sent}/{part}/"
                self.writer(message)
                sent += len(part)

        while self.session_id in sessions and self.length > self.acked:
            send_in_parts(data)
            await asyncio.sleep(RETRANSMISSION_TIMEOUT)

    def ack(self, pos):
        if pos <= self.acked:  # duplicate or overlapping
            pass
        elif pos == self.length:  # ack all
            self.acked = pos
            self.buffer = ""
        elif pos > self.length:  # not reasonable
            self.writer(f"/close/{self.session_id}/")
            del sessions[self.session_id]
        elif pos < self.length:  # partial (between acked and length)
            self.buffer = self.buffer[pos - self.acked:]
            self.acked = pos
            self.send_all()


class Session:

    def __init__(self, id, server, address):
        self.reader = ReadBuffer()
        self.writer = WriteBuffer(self.send, id)
        self.id = id
        self.server = server
        self.address = address
        self.expiry = None

    def send(self, message):
        print(f"sending: {message}")
        self.server.sendto(message.encode(), self.address)

    def handle(self, message):
        if match := re.match(r"(\d+?)/(.*)", message,
                             flags=re.MULTILINE | re.DOTALL):
            pos, message = match.groups()
            pos = int(pos)
            if pos < 0:
                return
            if pos > self.reader.length:
                self.send(f"/ack/{self.id}/{self.reader.length}/")
                return

            if re.search(r"(?<!\\)/", message):
                print(f"message for {self.id} has too many parts")
                return
            message = message.replace(r"\\", "\\").replace(r"\/", "/")

            if self.reader.add(pos, message):
                self.send(f"/ack/{self.id}/{self.reader.length}/")
                original_length = self.writer.length
                while line := self.reader.readline():
                    self.writer.add(line[::-1])
                if self.writer.length > original_length:
                    self.writer.send_all()

    def ack(self, pos):
        try:
            pos = int(pos)
            if pos < 0:
                return
        except ValueError:
            return
        self.writer.ack(pos)

    async def inactivity_timer(self):
        await asyncio.sleep(SESSION_TIMEOUT)
        print(f"session {self.id} expired")
        del sessions[self.id]

    def reset_expiry(self):
        if self.expiry:
            self.expiry.cancel()
        self.expiry = asyncio.create_task(self.inactivity_timer())


async def main(host, port):
    server = socket.socket(
        family=socket.AF_INET, type=socket.SOCK_DGRAM)
    server.setblocking(False)
    server.bind((host, port))
    print(f"listening on {port}")

    loop = asyncio.get_running_loop()
    while True:
        message, address = await loop.sock_recvfrom(server, 1000)
        message = message.decode()
        print(address, message)

        if match := re.match(
                r"/([^/]+?)/(\d+?)/(?:(.*)/)?", message,
                flags=re.MULTILINE | re.DOTALL):
            type, session_id, remainder = match.groups()
            session_id = int(session_id)
            print(type, session_id, remainder)
            if session_id > 0:

                if type == "connect" and remainder is None:
                    if not (session := sessions.get(session_id)):
                        session = Session(session_id, server, address)
                        sessions[session_id] = session
                    session.send(f"/ack/{session_id}/0/")
                    session.reset_expiry()

                elif type == "close" and remainder is None:
                    print(f"closing session {session_id}")
                    server.sendto(
                        f"/close/{session_id}/".encode(), address)
                    if session_id in sessions:
                        del sessions[session_id]

                else:
                    if not (session := sessions.get(session_id)):
                        server.sendto(
                            f"/close{session_id}/".encode(), address)

                    elif type == "data" and remainder is not None:
                        session.handle(remainder)
                        session.reset_expiry()

                    elif type == "ack" and remainder is not None:
                        session.ack(remainder)
                        session.reset_expiry()


if __name__ == "__main__":
    from os import getenv
    asyncio.run(main(getenv("HOST", "0.0.0.0"), int(getenv("PORT", 12345))))
