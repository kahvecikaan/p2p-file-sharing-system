import socket
import threading
import os
import json
import logging
from config import P2PConfig

class ChunkServer:
    """
    Server component that handles chunk distribution in the P2P network.
    """

    def __init__(self, peer_id=None):
        self.logger = None
        self.config = P2PConfig(peer_id)
        self.setup_logging()

        # Initialize server socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.host = self.get_local_ip()
        self.port = self.config.PEER_PORT
        self.sock.bind((self.host, self.port))

        if self.logger is not None:
            self.logger.info(f"ChunkServer initialized on {self.host}:{self.port}")

    def setup_logging(self):
        """Configure logging for the server."""
        self.logger = logging.getLogger('ChunkServer')
        self.logger.setLevel(logging.DEBUG)

        # Create handlers
        file_handler = logging.FileHandler(
            os.path.join(self.config.LOG_DIR, 'server.log')
        )
        console_handler = logging.StreamHandler()

        # Create formatters and add it to handlers
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to the logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    @staticmethod
    def get_local_ip():
        """Get local IP address."""
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            if s is not None:
                s.close()
        return ip

    def _receive_request(self, conn):
        """Receive and parse a JSON request from the connection"""
        message = b''
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    return None # Client closed connection
                message += data
                try:
                    return json.loads(message.decode())
                except json.JSONDecodeError:
                    continue # Incomplete data, keep reading
            except Exception as e:
                self.logger.error(f"Error receiving request: {e}")
                return None

    def _handle_chunk_request(self, conn, chunk_name):
        """Send the request chunk over the connection"""
        chunk_path = os.path.join(self.config.CHUNK_DIR, chunk_name)
        self.logger.info(f"Received request for chunk: {chunk_name}")
        if not os.path.exists(chunk_path):
            self.logger.error(f"Chunk not found: {chunk_path}")
            try:
                conn.sendall(b"ERROR: Chunk not found")
            except Exception:
                pass
            return
        try:
            file_size = os.path.getsize(chunk_path)
            # Send a header with file size followed by a new line
            size_header = (str(file_size) + "\n").encode()
            conn.sendall(size_header)
            with open(chunk_path, 'rb') as f:
                while True:
                    data = f.read(4096)
                    if not data:
                        break
                    conn.sendall(data)
            self.logger.info(f"Finished sending chunk {chunk_name} ({file_size} bytes)")
        except Exception as e:
            self.logger.error(f"Error sending chunk {chunk_name}: {e}")

    def handle_client(self, conn, addr):
        """Handle persistent client connection"""
        self.logger.info(f"New connection from {addr}")
        try:
            conn.settimeout(30)
            while True:
                request = self._receive_request(conn)
                if not request:
                    self.logger.info(f"Client {addr} closed connection or sent invalid data")
                    break
                if 'chunk' in request:
                    self._handle_chunk_request(conn, request['chunk'])
                else:
                    self.logger.error("Invalid request format – 'chunk' key missing")
        except Exception as e:
            self.logger.error(f"Error handling client {addr}: {e}")
        finally:
            conn.close()
            self.logger.info(f"Connection from {addr} closed")

    def _send_chunk(self, conn, chunk_name):
        """Send requested chunk to client."""
        chunk_path = os.path.join(self.config.CHUNK_DIR, chunk_name)

        if not os.path.exists(chunk_path):
            self.logger.warning(f"Chunk not found: {chunk_path}")
            return

        try:
            self.logger.info(f"Sending chunk: {chunk_name}")
            with open(chunk_path, 'rb') as f:
                while True:
                    bytes_read = f.read(4096)
                    if not bytes_read:
                        break
                    conn.sendall(bytes_read)
            self.logger.info(f"Finished sending: {chunk_name}")
        except Exception as e:
            self.logger.error(f"Error sending chunk {chunk_name}: {e}")

    def start(self):
        """Start the server and listen for connections."""
        self.sock.listen()
        self.logger.info(f"Server listening on {self.host}:{self.port}")

        while True:
            try:
                conn, addr = self.sock.accept()
                self.logger.info(f"New connection from {addr}")
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
            except Exception as e:
                self.logger.error(f"Error accepting connection: {e}")


if __name__ == "__main__":
    server = ChunkServer()
    server.start()