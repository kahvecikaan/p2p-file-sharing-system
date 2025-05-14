import os
import json
import threading
import hashlib
import socket
import logging
from queue import Queue, Empty
from config import P2PConfig
from connection_pool import ConnectionPool


class DownloadManager:
    """
    Manages parallel downloading and reconstruction of files in the P2P network.
    Handles chunk downloading, verification, and file reconstruction.
    """

    def __init__(self, content_name, peer_id=None):
        # Initialize configuration and logging
        self.logger = None
        self.config = P2PConfig(peer_id)
        self.setup_logging()

        # File information
        self.content_name = content_name
        self.base_name = os.path.splitext(content_name)[0]
        self.extension = os.path.splitext(content_name)[1]

        # Download management
        self.chunk_queue = Queue()
        self.successful_chunks = set()
        self.lock = threading.Lock()
        self.download_complete = threading.Event()

        # Initialize connection pool
        self.connection_pool = ConnectionPool(peer_id)

        # Load and process content dictionary
        self._initialize_chunks()

        if self.logger is not None:
            self.logger.info(
                f"DownloadManager initialized for {content_name} "
                f"with {len(self.chunks)} chunks"
        )

    def setup_logging(self):
        """Configure logging for the download manager."""
        self.logger = logging.getLogger('DownloadManager')
        self.logger.setLevel(logging.DEBUG)

        # Create handlers
        file_handler = logging.FileHandler(
            os.path.join(self.config.LOG_DIR, 'download_manager.log')
        )
        console_handler = logging.StreamHandler()

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _initialize_chunks(self):
        """Load content dictionary and initialize chunk queue."""
        try:
            with open(self.config.get_content_dict_path()) as f:
                self.content_dict = json.load(f)

            # Find chunks for this file
            self.chunks = [
                chunk for chunk in self.content_dict
                if chunk.startswith(self.base_name + "_")
            ]

            # Initialize download queue
            for chunk in self.chunks:
                self.chunk_queue.put((
                    chunk,
                    self.content_dict[chunk]['checksum'],
                    self.content_dict[chunk]['peers']
                ))

        except FileNotFoundError:
            self.logger.error("Content dictionary not found")
            self.chunks = []
        except Exception as e:
            self.logger.error(f"Error initializing chunks: {e}")
            self.chunks = []

    def download_chunk(self):
        """Worker thread function for downloading chunks."""
        while True:
            try:
                # Get next chunk from queue with timeout
                item = self.chunk_queue.get(timeout=5)
                if item is None:  # Shutdown signal
                    break

                chunk_name, checksum, peers = item
                success = False

                # Try downloading from each available peer
                for peer in peers:
                    self.logger.info(f"Attempting to download {chunk_name} from {peer}")
                    if self.try_download(peer, chunk_name, checksum):
                        with self.lock:
                            self.successful_chunks.add(chunk_name)
                        success = True
                        self.logger.info(f"Successfully downloaded {chunk_name}")
                        break

                self.chunk_queue.task_done()

                # Check if download is complete
                if len(self.successful_chunks) == len(self.chunks):
                    self.download_complete.set()

            except Empty:
                if len(self.successful_chunks) < len(self.chunks):
                    continue  # Keep trying if chunks are missing
                break  # Exit if all chunks are downloaded
            except Exception as e:
                self.logger.error(f"Error in download thread: {e}")

    def try_download(self, peer_ip, chunk_name, checksum):
        temp_path = os.path.join(self.config.CHUNK_DIR, f"temp_{chunk_name}")
        try:
            conn = self.connection_pool.get_connection(peer_ip)
            # Use the persistent connection via context manager:
            with conn as sock:
                request = {"chunk": chunk_name}
                sock.sendall(json.dumps(request).encode())
                success = self.receive_and_verify(sock, temp_path, checksum)
            return success
        except socket.error as e:
            self.logger.error(f"Socket error downloading {chunk_name}: {e}")
            with self.lock:
                self.connection_pool._remove_connection(peer_ip)
            return False
        except Exception as e:
            self.logger.error(f"Error downloading {chunk_name}: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

    def receive_and_verify(self, sock, temp_path, checksum):
        """Receive chunk data and verify its checksum."""
        sha = hashlib.sha256()
        total_bytes = 0

        try:
            # First receive the file size
            size_data = b''
            while b'\n' not in size_data:
                data = sock.recv(1024)
                if not data:
                    self.logger.error("Connection closed while reading size")
                    return False
                size_data += data

            # Parse the size
            file_size = int(size_data.split(b'\n')[0])
            self.logger.debug(f"Expected file size: {file_size} bytes")

            # Now receive the file data
            with open(temp_path, "wb") as f:
                while total_bytes < file_size:
                    # Calculate remaining bytes
                    remaining = file_size - total_bytes
                    chunk_size = min(4096, remaining)

                    # Receive data
                    data = sock.recv(chunk_size)
                    if not data:
                        self.logger.error("Connection closed prematurely")
                        return False

                    total_bytes += len(data)
                    f.write(data)
                    sha.update(data)

                    # Update progress
                    progress = (total_bytes / file_size) * 100
                    self.logger.debug(f"Download progress: {progress:.1f}%")

            # Verify the download
            if total_bytes != file_size:
                self.logger.error(f"Size mismatch: got {total_bytes}, expected {file_size}")
                return False

            # Verify checksum
            calculated_checksum = sha.hexdigest()
            if calculated_checksum == checksum:
                self.logger.info(f"Successfully received and verified {os.path.basename(temp_path)}")
                os.rename(
                    temp_path,
                    os.path.join(self.config.CHUNK_DIR, os.path.basename(temp_path)[5:])
                )
                return True

            self.logger.error(f"Checksum mismatch: expected {checksum}, got {calculated_checksum}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

        except Exception as e:
            self.logger.error(f"Error receiving chunk: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

    def download_and_stitch(self):
        """Coordinate parallel downloads and file reconstruction."""
        if not self.chunks:
            self.logger.warning("No chunks available to download")
            return False

        try:
            # Start download threads
            num_workers = min(5, len(self.chunks))
            threads = [
                threading.Thread(target=self.download_chunk)
                for _ in range(num_workers)
            ]

            for t in threads:
                t.start()

            # Wait for downloads to complete with timeout
            if self.download_complete.wait(timeout=300):  # 5-minute timeout
                self.logger.info("All chunks downloaded successfully")
                self.stitch_file()
                return True
            else:
                self.logger.error("Download timed out")
                return False

        except Exception as e:
            self.logger.error(f"Error in download process: {e}")
            return False

    def stitch_file(self):
        """Reconstruct the complete file from downloaded chunks."""
        output_path = os.path.join(self.config.DOWNLOADS_DIR, self.content_name)
        self.logger.info(f"Starting file reconstruction: {output_path}")

        try:
            # Get and sort chunks
            chunks = sorted(
                [f for f in os.listdir(self.config.CHUNK_DIR)
                 if f.startswith(self.base_name + "_")],
                key=lambda x: int(x.split("_")[-1].split(".")[0])
            )

            # Combine chunks into final file
            with open(output_path, "wb") as outfile:
                for chunk in chunks:
                    chunk_path = os.path.join(self.config.CHUNK_DIR, chunk)
                    with open(chunk_path, "rb") as infile:
                        outfile.write(infile.read())
                    os.remove(chunk_path)

            self.logger.info(f"File reconstruction complete: {output_path}")

        except Exception as e:
            self.logger.error(f"Error stitching file: {e}")
            raise

    def __del__(self):
        """Cleanup resources on object destruction."""
        try:
            if hasattr(self, 'connection_pool'):
                self.connection_pool.close_all()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point for the download manager."""
    try:
        content_name = input("Enter content name to download: ")
        dm = DownloadManager(content_name)

        if dm.download_and_stitch():
            print(f"Successfully downloaded and reconstructed: {content_name}")
        else:
            print("Download failed")

    except KeyboardInterrupt:
        print("\nDownload cancelled by user")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()