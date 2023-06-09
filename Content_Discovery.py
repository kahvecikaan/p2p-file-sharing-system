import json
import socket


def listen(port):
     sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
     sock.bind(("", port))
     return sock


def save_content_dict(content_dict, file_path):
    with open(file_path, "w") as f:
        json.dump(content_dict, f)


PORT = 5001
sock = listen(PORT)

content_dict = {}
file_path = "./content_dict.json"  # specify the path to store the content dictionary

content_modified = False  # to change the dict only when there is a change


while True:
    data, addr = sock.recvfrom(1024)
    content = json.loads(data.decode())
    for chunk in content["chunks"]:
        if chunk not in content_dict:
            content_dict[chunk] = []
            content_modified = True

        if addr[0] not in content_dict[chunk]:
            content_dict[chunk].append(addr[0])
            content_modified = True
            print(f"{addr[0]} : {', '.join(content_dict)}")
    if content_modified:
        save_content_dict(content_dict, file_path)
        content_modified = False

    save_content_dict(content_dict, file_path)
