# cmp2204project

Implementation of the project of the course CMP2204.

## Explanation

### Chunk_Announcer.py

1) Divides given file into 5 chunks and writes them to `announce_path` with `divide_file()`, `announce_path` is `./announce` by default
2) Gets names of chunks that is new or already existing in `announce_path`
3) Formats them into appropiate JSON format as per Functional Specification with `format_json_messages()`
4) Broadcasts formatted JSON messages into the network with `send_broadcast()`

### Content_Discovery.py

1) Binds socket `sock` to the appropiate port `5001` with `listen()`
2) If recieved data from `sock`, decode that data to `content`
3) If recieved broadcast from IP `addr[0]` for the chunk `chunk` does not exist in our content dictionary `content_dict[chunk][]`, add `addr[0]` to `content_dict[chunk][]`
4) Write modifications to content dictionary file `content_dict.json`

### Chunk_Uploader.py

1) Binds socket `s` to own IP, using `get_local_ip()`, and port `5000`
2) If a download request is recieved from a pair, write that request to `data` and decode it into `request`
3) Send requested chunk to the pair with `send_chunk()`
4) Write completed upload job log to `upload_log.txt`

### Chunk_Downloader.py

1) Loads available pair IPs for requested file into `content_dict` from `content_dict.json`
2) Calls `download_chunk()` with `content_dict`, which then tries downloading chunk `i` from available pairs in `content_dict`
3) If successful, chunk `i` is written, and download job is logged into `download_log.txt`, otherwise a warning is printed to `stdout`
4) Merges downloaded chunks into one file with `stitch_chunks()`

## Usage

Assume the device that will receive the file is `downloader_device`, and the device that will send the file is `uploader_device`.

1) Change current directory to the directory that contains python files
2) Run `Content_Discovery.py` on the `downloader_device`
```
python3 Content_Discovery.py
```
3) Run `Chunk_Announcer.py` on the `uploader_device`
```
python3 Chunk_Announcer.py
```
Enter file name that is to be hosted.

4) Run `Chunk_Uploader.py` on the `uploader_device`
```
python3 Chunk_Uploader.py
```
5) Run `Chunk_Downloader.py` on the `downloader_device`
```
python3 Chunk_Downloder.py
```
Enter file name that is to be downloaded.
If successful, the file should appear in the current directory of `downloader_device`


### Note
File running order is not important as long as `Chunk_Uploader.py` was started before `Chunk_Downloader.py`. Also running `Content_Discovery.py` before `Chunk_Announcer.py` is recommended for saving time as announcements are made once a minute as per the specification.
