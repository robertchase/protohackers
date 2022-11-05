import asyncio
from struct import pack, unpack


ERROR = 0x10
PLATE = 0x20
TICKET = 0x21
WANT_HEARTBEAT = 0x40
HEARTBEAT = 0x41
CAMERA = 0x80
DISPATCHER = 0x81


roads = {}  # asycio.Queue instances by road for tickets
days_by_plate = {}  # set(day numbers of tickets) by plate
observations = []  # [[timestamp, road, mile, plate], ...]


async def read_u8(reader):
    return unpack("!B", await reader.readexactly(1))[0]


async def read_u16(reader):
    return unpack("!H", await reader.readexactly(2))[0]


async def read_u32(reader):
    return unpack("!L", await reader.readexactly(4))[0]


async def read_string(reader):
    length = await read_u8(reader)
    value = await reader.readexactly(length)
    return value.decode()


async def heartbeat(writer, delay):
    delay = delay / 10
    while not writer.is_closing():
        await asyncio.sleep(delay)
        writer.write(pack("!B", HEARTBEAT))


def check_observations(plate, road, limit):
    obs = sorted([[ts, ml] for ts, rd, ml, pt in observations
                 if plate == pt and rd == road])
    ticket_days = days_by_plate.get(plate, set())
    t1, m1 = obs[0]
    for t2, m2 in obs[1:]:
        days = set((int(t1 / 86400), int(t2 / 86400)))
        if ticket_days.isdisjoint(days):
            duration = (t2 - t1) / 60 / 60
            distance = abs(m1 - m2)
            speed = distance / duration
            if speed > limit:
                print(f"ticket {plate=} {road=} {days=} {speed=}")
                ticket(plate, road, m1, t1, m2, t2, int(speed * 100))
                ticket_days.update(days)
        t1, m1 = t2, m2
    days_by_plate[plate] = ticket_days


def ticket(plate, road, m1, t1, m2, t2, speed):
    queue = roads.setdefault(road, asyncio.Queue())
    value = pack(f"!BB{len(plate)}sHHLHLH", TICKET, len(plate),
                 bytes(plate, "ascii"), road, m1, t1, m2, t2, speed)
    queue.put_nowait(value)


async def dispatch(road, writer):
    queue = roads.setdefault(road, asyncio.Queue())
    while not writer.is_closing():
        ticket = await queue.get()
        writer.write(ticket)
        queue.task_done()


async def on_connect(reader, writer):
    host, port = writer.get_extra_info("peername")[:2]
    print(f"connection from {host}:{port}")
    heartbeat_task = None
    client_type = None

    try:
        while not writer.is_closing():
            if not (packet_type := await reader.readexactly(1)):
                break
            packet_type = ord(packet_type)
            print(f"connection {port}: {hex(packet_type)}")

            if packet_type == CAMERA:
                if client_type:
                    raise Exception("client type already specified")
                client_type = CAMERA
                road = await read_u16(reader)
                mile = await read_u16(reader)
                limit = await read_u16(reader)
                print(f"camera {port}, {road=}, {mile=}, {limit=}")

            elif packet_type == PLATE:
                if client_type != CAMERA:
                    raise Exception("PLATE only valid for camera")
                plate = await read_string(reader)
                timestamp = await read_u32(reader)
                print(f"plate {port} {road=}, {mile=}, {plate=}")
                observations.append([timestamp, road, mile, plate])
                check_observations(plate, road, limit)

            elif packet_type == DISPATCHER:
                if client_type:
                    raise Exception("client type already specified")
                print(f"dispatcher {port}")
                client_type = DISPATCHER
                road_count = await read_u8(reader)
                for i in range(road_count):
                    road = await read_u16(reader)
                    print(f"dispatch {port}, {road=}")
                    asyncio.create_task(dispatch(road, writer))

            elif packet_type == WANT_HEARTBEAT:
                if heartbeat_task:
                    raise Exception("heartbeat specified twice")
                interval = await read_u32(reader)
                if interval:
                    heartbeat_task = asyncio.create_task(
                        heartbeat(writer, interval))

            else:
                raise Exception(
                    f"{port=} illegal packet: {hex(ord(packet_type))}")
    except Exception as exc:
        err_string = str(exc)
        writer.write(pack("!BB", ERROR, len(err_string)))
        writer.write(err_string.encode())
    finally:
        print(f"closed connection {host}:{port}")
        if heartbeat_task:
            heartbeat_task.cancel()
        writer.close()


async def main():
    server = await asyncio.start_server(on_connect, port=12345)
    print(f"listening on port {server.sockets[0].getsockname()[1]}")
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
