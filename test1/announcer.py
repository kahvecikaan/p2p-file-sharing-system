import hashlib
import json
import os
import socket
import time
import logging
from config import P2PConfig


class ChunkAnnouncer:
    """
    Handles chunk announcements for P2P file sharing.
    Announces available chunks to other peers in the network.
    """

    def __init__(self, peer_id=None):
        # Initialize configuration
        self.config = P2PConfig(peer_id)
        self.setup_logging()

        # Initialize socket for broadcasting
        self.sock = self._create_socket()

        # Get target ports from configuration or use defaults
        self.target_ports = self.config.config.get('TARGET_PORTS', [5001, 5002])

        self.logger.info(f"ChunkAnnouncer initialized with target ports: {self.target_ports}")

    def setup_logging(self):
        """Configure logging for the announcer component."""
        self.logger = logging.getLogger('ChunkAnnouncer')
        self.logger.setLevel(logging.INFO)

        # Create handlers for both file and console output
        file_handler = logging.FileHandler(
            os.path.join(self.config.LOG_DIR, 'announcer.log')
        )
        console_handler = logging.StreamHandler()

        # Create and set formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _create_socket(self):
        """Create and configure UDP socket for broadcasting."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', 0))  # Bind to any available port
        return sock

    def get_file_checksum(self, file_path):
        """Calculate SHA-256 checksum of a file in chunks."""
        sha = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while True:
                    data = f.read(65536)  # Read in 64KB chunks
                    if not data:
                        break
                    sha.update(data)
            return sha.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating checksum for {file_path}: {e}")
            return None

    def get_available_chunks(self):
        """Scan chunk directory and collect metadata about available chunks."""
        chunks = {}
        try:
            for filename in os.listdir(self.config.CHUNK_DIR):
                file_path = os.path.join(self.config.CHUNK_DIR, filename)
                checksum = self.get_file_checksum(file_path)
                if checksum:
                    chunks[filename] = {
                        "size": os.path.getsize(file_path),
                        "checksum": checksum,
                        "timestamp": time.time()
                    }
            return chunks
        except Exception as e:
            self.logger.error(f"Error scanning chunks: {e}")
            return {}

    def get_local_ip(self):
        """Get local IP address by connecting to DNS server."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            return ip
        except Exception as e:
            self.logger.warning(f"Could not get local IP: {e}, using localhost")
            return '127.0.0.1'

    def announce_chunks(self):
        """Main loop for announcing chunks to the network."""
        self.logger.info("Starting chunk announcements")

        while True:
            try:
                # Get available chunks
                chunks = self.get_available_chunks()

                # Prepare announcement message
                message = {
                    "peer_ip": self.get_local_ip(),
                    "chunks": chunks,
                    "timestamp": time.time()
                }
                data = json.dumps(message).encode()

                # Send to all target ports
                local_ip = self.get_local_ip()
                for port in self.target_ports:
                    try:
                        # Send to both localhost and network interface
                        self.sock.sendto(data, ('127.0.0.1', port))
                        if local_ip != '127.0.0.1':
                            self.sock.sendto(data, (local_ip, port))
                        self.logger.debug(f"Sent announcement to port {port}")
                    except Exception as e:
                        self.logger.error(f"Failed to send to port {port}: {e}")

                if chunks:
                    self.logger.info(f"Announced {len(chunks)} chunks")

            except Exception as e:
                self.logger.error(f"Error in announcement cycle: {e}")

            # Wait before next announcement
            time.sleep(self.config.config.get('ANNOUNCE_INTERVAL', 10))


def main():
    announcer = ChunkAnnouncer()
    try:
        announcer.announce_chunks()
    except KeyboardInterrupt:
        announcer.logger.info("Announcer shutting down")
    except Exception as e:
        announcer.logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()