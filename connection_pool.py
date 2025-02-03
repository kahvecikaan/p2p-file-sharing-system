import socket
import threading
import time
import logging
import os
from config import P2PConfig

class P2PConnection:
    """
    Wraps a socket connection with its own lock so that it can be safely reused.
    """
    def __init__(self, sock):
        self.sock = sock
        self.lock = threading.Lock()

    def __enter__(self):
        self.lock.acquire()
        return self.sock

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()


class ConnectionPool:
    """
    A thread-safe connection pool for managing peer connections.
    Handles connection creation, reuse, and cleanup for both seeder and leecher peers.
    """

    def __init__(self, peer_id=None):
        # Initialize configuration and logging
        self.config = P2PConfig(peer_id)
        self.setup_logging()

        # Pool configuration
        self.pool = {}  # Dictionary to store active connections: {peer_ip: (P2PConnection, last_used_time)}
        self.max_connections = self.config.config.get('MAX_CONNECTIONS', 10)
        self.connection_timeout = self.config.config.get('CONNECTION_TIMEOUT', 300)
        self.lock = threading.Lock()

        # Start background cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_stale_connections,
            daemon=True  # Thread will exit when main program exits
        )
        self.cleanup_thread.start()

        self.logger.info(
            f"Connection pool initialized with max_connections={self.max_connections}, "
            f"timeout={self.connection_timeout}s"
        )

    def setup_logging(self):
        """Configure logging for the connection pool component."""
        self.logger = logging.getLogger('ConnectionPool')
        self.logger.setLevel(logging.INFO)

        # Create handlers for both file and console output
        file_handler = logging.FileHandler(
            os.path.join(self.config.LOG_DIR, 'connection_pool.log')
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

    def _create_connection(self, peer_ip):
        try:
            self.logger.debug(f"Creating new connection to {peer_ip}:{self.config.PEER_PORT}")
            sock = socket.create_connection((peer_ip, self.config.PEER_PORT), timeout=10)
            sock.settimeout(10)
            return P2PConnection(sock)
        except socket.error as e:
            self.logger.error(f"Failed to connect to {peer_ip}: {e}")
            raise ConnectionError(f"Failed to connect to {peer_ip}: {e}")

    def get_connection(self, peer_ip):
        """Get a connection to a peer with proper settings."""
        with self.lock:
            if peer_ip in self.pool:
                conn, _ = self.pool[peer_ip]
                try:
                    conn.sock.getpeername()  # verify connection is live
                    self.pool[peer_ip] = (conn, time.time())
                    self.logger.debug(f"Reusing connection to {peer_ip}")
                    return conn
                except socket.error:
                    self.logger.debug(f"Dead connection to {peer_ip}, removing")
                    self._remove_connection(peer_ip)
            if len(self.pool) >= self.max_connections:
                self._remove_oldest_connection()
            conn = self._create_connection(peer_ip)
            self.pool[peer_ip] = (conn, time.time())
            return conn

    def _remove_connection(self, peer_ip):
        """
        Safely close and remove a connection from the pool.
        """
        if peer_ip in self.pool:
            conn, _ = self.pool[peer_ip]
            try:
                conn.sock.close()
                self.logger.debug(f"Closed connection to {peer_ip}")
            except socket.error as e:
                self.logger.warning(f"Error closing connection to {peer_ip}: {e}")
            finally:
                del self.pool[peer_ip]

    def _remove_oldest_connection(self):
        """
        Remove the least recently used connection from the pool.
        Called when pool is at capacity and a new connection is needed.
        """
        if self.pool:
            oldest_peer = min(self.pool.items(), key=lambda x: x[1][1])[0]
            self.logger.debug(f"Removing oldest connection to {oldest_peer}")
            self._remove_connection(oldest_peer)

    def _cleanup_stale_connections(self):
        """
        Background task to remove inactive connections.
        Runs continuously in a separate thread.
        """
        while True:
            try:
                time.sleep(60)  # Check every minute
                with self.lock:
                    current_time = time.time()
                    # Find connections that haven't been used recently
                    stale_peers = [
                        peer for peer, (_, last_used) in self.pool.items()
                        if current_time - last_used > self.connection_timeout
                    ]

                    # Remove stale connections
                    for peer in stale_peers:
                        self.logger.info(f"Removing stale connection to {peer}")
                        self._remove_connection(peer)

            except Exception as e:
                self.logger.error(f"Error in cleanup thread: {e}")

    def close_all(self):
        """
        Close all connections in the pool.
        Called during shutdown to clean up resources.
        """
        self.logger.info("Closing all connections")
        with self.lock:
            for peer_ip in list(self.pool.keys()):
                self._remove_connection(peer_ip)
        self.logger.info("All connections closed")

    def __del__(self):
        """
        Ensure all connections are closed when the pool is destroyed.
        """
        try:
            self.close_all()
        except Exception as e:
            self.logger.error(f"Error during connection pool cleanup: {e}")