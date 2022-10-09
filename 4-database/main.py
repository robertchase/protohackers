import socket


def main(host, port):
    store = {"version": "release-1.0"}
    server = socket.socket(
        family=socket.AF_INET, type=socket.SOCK_DGRAM)
    server.bind((host, port))
    print(f"listening on {port}")

    while True:
        message, address = server.recvfrom(1000)
        message = message.decode()
        print(address, message)

        if "=" in message:
            key, value = message.split("=", 1)
            if key != "version":
                store[key] = value
        else:
            value = store.get(message, "")
            response = f"{message}={value}"
            server.sendto(response.encode(), address)


if __name__ == "__main__":
    from os import getenv
    main(getenv("HOST", "127.0.0.1"), int(getenv("PORT", 12345)))
