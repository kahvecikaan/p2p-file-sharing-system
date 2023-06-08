# cmp2204project

Implementation of the project of the course CMP2204.

## Explanation

### Chunk_Announcer.py

1) Divides given file into 5 chunks and writes them to `announce_path` with `divide_file()`
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
