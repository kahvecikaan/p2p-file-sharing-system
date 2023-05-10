import os
import json
import socket
import time
import math


broadcast_ip = "192.168.154.255"  # TBD
broadcast_port = 5001

announce_path = "./announce/"


def divide_file(file_path, chunk_size):
    content_name = os.path.splitext(os.path.basename(file_path))[0]
    index = 1
    with open(file_path, "rb") as infile:
        chunk = infile.read(chunk_size)
        while chunk:
            chunk_name = content_name + "_" + str(index)
            with open(announce_path + chunk_name, "wb+") as chunk_file:
                chunk_file.write(chunk)
            index += 1
            chunk = infile.read(chunk_size)


file_path = input("Enter the file path to be hosted: ")
chunk_size = math.ceil(os.path.getsize(file_path) / 5)
divide_file(file_path, chunk_size)


def send_broadcast(messages, broadcast_ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # allows socket to send broadcast messages
    while True:
        for message in messages:
            sock.sendto(message.encode(), (broadcast_ip, port))
            time.sleep(60)


def get_file_names(directory):
    return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
# note that this func returns the file names with extensions (ask Ece Hoca about this!)
# without extensions: return [os.path.splitext(f)[0] for f in os.listdir(directory) if os.path.isfile(os.path.join...


def format_json_messages(file_names):
    return json.dumps({"chunks": file_names})  # passing a dictionary to json.dumps() will return a string


directory = None  # specify the directory containing chunk files
file_names = get_file_names(directory)
json_message = format_json_messages(file_names)

# run the broadcast function:
send_broadcast([json_message], broadcast_ip, broadcast_port)

