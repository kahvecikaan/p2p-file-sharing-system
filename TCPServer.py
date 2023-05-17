import socket
import json
import datetime


def send_chunk(conn, addr, chunk_name):
    with open("./announce/" + chunk_name, "rb") as f:
        data = f.read(1024)
        while data:  # keep sending until the entire file is sent
            conn.send(data)
            data = f.read(1024)


def main():
    host = "192.168.154.204"
    port = 5000

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        while True:
            s.listen()
            conn, addr = s.accept()  # conn: new socket for communicating with the client
            with conn:  # ensures that the connection socket is properly closed
                print("Connected by", addr)
                data = conn.recv(1024)
                if data:
                    request = json.loads(data.decode())
                    requested_chunk = request.get("requested_content")
                    send_chunk(conn, addr, requested_chunk)
                    with open("upload_log.txt", "a") as log_file:
                        log_file.write(f"{datetime.datetime.now()}: {requested_chunk} sent to {addr[0]}\n")


if __name__ == "__main__":
    main()
