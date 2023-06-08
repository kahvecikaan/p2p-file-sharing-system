import socket
import json
import datetime


def stitch_chunks(content_name, extension):
    chunk_names = [content_name + "_" + str(i + 1) for i in range(5)]
    with open(content_name + extension, "wb") as outfile:
        for chunk in chunk_names:
            with open(chunk, "rb") as infile:
                outfile.write(infile.read())


def download_chunk(content_dict, content_name, chunk_index):
    filename = content_name + "_" + str(chunk_index)
    for ip in content_dict[filename]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ip, 5000))
                s.sendall(json.dumps({"requested_content": filename}).encode())
                with open(filename, "wb") as f:
                    data = s.recv(1024)
                    while data:  # keep receiving data from the socket and writing it to the file until there is no more
                        f.write(data)
                        data = s.recv(1024)
            return True
        except Exception as e:  # If an exception occurs we will try a different peer
            print("Exception occurred: ", e)
            continue
    return False  # If we cannot download the chunk from any of the peers


def main():
    content_name = input("Enter the content name that you want to download: ")
    extension = content_name[-4:]  # extension of the file
    content_name = content_name[0: -4]  # content_name without the extension
    with open("content_dict.json") as f:
        content_dict = json.load(f)
    for i in range(1, 6):
        if download_chunk(content_dict, content_name, i):
            print(f"{content_name}_{i} downloaded successfully.")
            with open("download_log.txt", "a") as log_file:
                log_file.write(f"{datetime.datetime.now()}: {content_name}_{i} downloaded\n")
        else:
            print(f"WARNING: CHUNK {content_name}_{i} CANNOT BE DOWNLOADED FROM ONLINE PEERS.")

    stitch_chunks(content_name, extension)
    print(f"{content_name}" + extension + " has been successfully downloaded.")


if __name__ == "__main__":
    main()
