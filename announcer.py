import datetime
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
        self.logger = None
        self.config = P2PConfig(peer_id)
        self.setup_logging()

        # Initialize socket for broadcasting
        self.sock = self._create_socket()

        # Get target ports from configuration or use defaults
        self.target_ports = self.config.config.get('TARGET_PORTS', [5001, 5002])

        if self.logger is not None:
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

    @staticmethod
    def _create_socket():
        """Create and configure UDP socket for broadcasting."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Enable broadcasting

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
                    sha.update(data)  # Update hash with each chunk
            return sha.hexdigest()  # Returns the final hash in hexadecimal format
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
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
            return chunks
        except Exception as e:
            self.logger.error(f"Error scanning chunks: {e}")
            return {}

    def get_local_ip(self):
        """Get a local IP address by connecting to DNS server."""
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
                all_chunks = self.get_available_chunks()

                # Check if there are chunks to announce
                if all_chunks:
                    # Break chunks into batches and announce them
                    self._announce_chunks_in_batches(all_chunks)
                else:
                    self.logger.info("No chunks available to announce")

            except Exception as e:
                self.logger.error(f"Error in announcement cycle: {e}")

            # Wait before the next announcement
            time.sleep(self.config.config.get('ANNOUNCE_INTERVAL', 10))

    def _announce_chunks_in_batches(self, all_chunks, max_batch_size=8):
        """Split chunks into manageable batches to avoid UDP size limits."""
        # Split chunks into manageable batches
        chunk_items = list(all_chunks.items())

        # Calculate the number of batches
        num_batches = (len(chunk_items) + max_batch_size - 1) // max_batch_size

        # Process each batch
        for batch_num in range(num_batches):
            start_idx = batch_num * max_batch_size
            end_idx = min(start_idx + max_batch_size, len(chunk_items))
            batch_chunks = dict(chunk_items[start_idx:end_idx])

            # Prepare the announcement for this batch
            message = {
                "peer_ip": self.get_local_ip(),
                "chunks": batch_chunks,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "batch_info": {
                    "current": batch_num + 1,
                    "total": num_batches
                }
            }

            # Convert to bytes
            data = json.dumps(message).encode()

            # Check size before sending
            message_size = len(data)
            if message_size > 60000:  # Leave some margin below the ~65507 limit
                self.logger.warning(f"Batch {batch_num + 1} too large ({message_size} bytes), reducing batch size")
                # Retry with smaller batch size
                new_batch_size = max(1, max_batch_size // 2)
                return self._announce_chunks_in_batches(all_chunks, new_batch_size)  # Pass the new batch size

            # Send the batch
            self._send_announcement_data(data, f"Batch {batch_num + 1}/{num_batches}")

        self.logger.info(f"Announced {len(all_chunks)} chunks in {num_batches} batches")
        return None

    def _send_announcement_data(self, data, batch_desc=""):
        """Send announcement data using multiple strategies."""
        for port in self.target_ports:
            broadcast_success = False

            # Try subnet-specific broadcast
            try:
                subnet_addr = self.get_broadcast_address()
                self.sock.sendto(data, (subnet_addr, port))
                self.logger.info(f"Subnet broadcast to {subnet_addr}:{port} successful {batch_desc}")
                broadcast_success = True
            except Exception as e:
                self.logger.warning(f"Subnet broadcast failed: {e} (message size: {len(data)} bytes)")

            # Try global broadcast if subnet failed
            if not broadcast_success:
                try:
                    self.sock.sendto(data, ('255.255.255.255', port))
                    self.logger.info(f"Global broadcast to 255.255.255.255:{port} successful {batch_desc}")
                    broadcast_success = True
                except Exception as e:
                    self.logger.warning(f"Global broadcast failed: {e}")

            # Last resort - direct localhost communication
            if not broadcast_success:
                try:
                    self.sock.sendto(data, ('127.0.0.1', port))
                    self.logger.info(f"Using localhost fallback to 127.0.0.1:{port} {batch_desc}")
                except Exception as e:
                    self.logger.error(f"All broadcast methods failed for port {port}: {e}")

    def get_broadcast_address(self):
        """Calculate the broadcast address for the current subnet"""
        local_ip = self.get_local_ip()
        if local_ip == '127.0.0.1':
            return '255.255.255.255'  # Fallback for localhost

        # For a typical /24 network (like 192.168.1.x)
        ip_parts = local_ip.split('.')
        return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"


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