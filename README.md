# cmp2204project

A distributed Peer-to-Peer (P2P) file sharing system for the CMP2204 – Computer Networks course, implemented in Python. This system features dynamic peer discovery, persistent TCP connections with a connection pool, and concurrent, multithreaded file chunk transfer and reconstruction.

## Overview

The project has been refactored to use a modular design with the following main components:

- **Announcer:** Scans the local chunk directory, computes checksums, and broadcasts JSON-formatted announcements over UDP.
- **Listener & Peer Manager:** Listens for UDP announcements from other peers and maintains a content dictionary mapping available file chunks to peer IPs.
- **Peer Server:** Serves file chunk requests over persistent TCP connections, allowing multiple requests per connection.
- **Download Manager:** Downloads file chunks concurrently from available peers using a persistent connection pool, verifies them, and stitches the chunks together into the final file.
- **File Splitter:** Splits large files into smaller chunks to be shared across the network.
- **Supporting Modules:**  
  - **config.py:** Centralizes configuration settings (e.g., ports, directories, chunk size) and ensures required directories exist.  
  - **connection_pool.py:** Manages a thread-safe pool of persistent TCP connections to peers, reducing overhead and providing background cleanup.  
  - **peer_manager.py:** Updates and maintains a global content dictionary based on received announcements.

In addition, the project includes test directories (`test1/` and `test2/`) containing separate copies for experimental and integration testing purposes.

## Modules

### config.py
- **Purpose:** Provides centralized configuration for all modules.
- **Features:**  
  - Default values for chunk size, broadcast/peer ports, and maximum connections.  
  - Creation of necessary directories (e.g., `./chunks/`, `./logs/`, `./downloads/`).

### announcer.py
- **Purpose:** Broadcasts information about locally available file chunks.
- **Key Steps:**
  1. Scans the chunk directory and computes SHA-256 checksums.
  2. Formats chunk metadata into JSON messages.
  3. Broadcasts these messages over UDP so that other peers know which chunks are available.

### listener.py & peer_manager.py
- **Purpose:**  
  - `listener.py` listens on a UDP port for broadcast announcements from other peers.
  - `peer_manager.py` maintains a content dictionary that maps chunk names to peer IP addresses.
- **Key Steps:**
  1. Listen for UDP messages.
  2. Parse JSON data and update the content dictionary.
  3. Periodically remove stale peer entries.

### peer_server.py
- **Purpose:** Handles incoming TCP connections from peers requesting file chunks.
- **Key Steps:**
  1. Listens on a designated TCP port.
  2. For each client connection, spawns a new thread.
  3. Processes JSON requests for chunks and sends the requested file chunk (preceded by its file size) over the same connection.

### connection_pool.py
- **Purpose:** Provides a pool of persistent TCP connections for efficient, reusable communication.
- **Key Features:**  
  - Thread-safe checkout and return of connections.
  - A background cleanup thread that removes stale connections.

### download_manager.py
- **Purpose:** Coordinates the download of a file from multiple peers.
- **Key Steps:**
  1. Loads the content dictionary to identify which peers have the required chunks.
  2. Spawns multiple worker threads that use the connection pool to download chunks concurrently.
  3. Verifies each chunk using its SHA-256 checksum.
  4. Stitches the chunks together into the final file (saved in `./downloads/`).

### splitter.py
- **Purpose:** Splits a large file into smaller chunks.
- **Key Steps:**
  1. Reads the source file.
  2. Divides it into chunks of a specified size.
  3. Writes each chunk to the designated `./chunks/` directory.

## Usage

Assume:
- **Uploader Device:** Hosts the file (runs `announcer.py` and `peer_server.py`).
- **Downloader Device:** Downloads the file (runs `listener.py` and `download_manager.py`).

### To Share a File

1. **Prepare the File:**
   - Run the splitter to divide the file into chunks:
     ```bash
     python3 splitter.py
     ```
   - Chunks are saved in `./chunks/`.

2. **Announce Available Chunks:**
   - On the uploader device, run:
     ```bash
     python3 announcer.py
     ```
   - This broadcasts the available chunks to the network.

3. **Start the Peer Server:**
   - On the uploader device, run:
     ```bash
     python3 peer_server.py
     ```
   - This starts a TCP server to serve chunk requests.

4. **Discover Content:**
   - On the downloader device, run:
     ```bash
     python3 listener.py
     ```
   - This listens for announcements and builds a content dictionary.

5. **Download and Reconstruct:**
   - On the downloader device, run:
     ```bash
     python3 download_manager.py
     ```
   - Follow prompts to specify the file (base name) to download.
   - The download manager concurrently downloads all chunks and reconstructs the file into `./downloads/`.

### Test Directories

The repository also includes `test1/` and `test2/` directories for local testing and integration experiments. These directories mirror the project structure and can be used to test changes in an isolated environment.

## System Architecture

- **Multi-Threaded Components:**
  - **Peer Server:** Spawns a new thread for each incoming TCP connection, supporting multiple clients concurrently.
  - **Download Manager:** Uses multiple worker threads to download file chunks concurrently.
  - **Connection Pool:** Manages persistent connections with thread-safe access and background cleanup.

- **Persistent Connections:**
  - A connection pool (in `connection_pool.py`) reduces connection overhead by reusing TCP connections across multiple chunk transfers.

- **Dynamic Peer Discovery:**
  - The combination of UDP-based announcements (via `announcer.py`) and the content dictionary maintained by `listener.py` and `peer_manager.py` allows the system to dynamically discover available peers and file chunks.

## Note

- **Order of Execution:**  
  The order in which modules are started is flexible. For optimal performance, start the uploader modules (`announcer.py` and `peer_server.py`) before initiating the download process. It is recommended that the downloader first runs `listener.py` to ensure its content dictionary is populated before starting `download_manager.py`.

- **Logging:**  
  All modules log operations (file transfers, errors, and network events) to assist in debugging and monitoring the system.

---