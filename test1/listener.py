import socket
import threading
import os
import json
import logging
from config import P2PConfig
from peer_manager import PeerManager


class P2PListener:
    """
    Listens for and processes peer announcements in the P2P network.
    Handles incoming broadcasts and updates peer information.
    """

    def __init__(self, peer_id=None):
        # Initialize configuration and logging
        self.config = P2PConfig(peer_id)
        self.setup_logging()

        # Initialize peer manager
        self.peer_manager = PeerManager(peer_id)

        # Start stale peer removal thread
        threading.Thread(
            target=self.peer_manager.remove_stale_peers,
            daemon=True
        ).start()

        self.logger.info("P2PListener initialized")

    def setup_logging(self):
        """Configure logging for the listener component."""
        self.logger = logging.getLogger('P2PListener')
        self.logger.setLevel(logging.INFO)

        # Create handlers
        file_handler = logging.FileHandler(
            os.path.join(self.config.LOG_DIR, 'listener.log')
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

    def save_content_dict(self, content_dict):
        """Save content dictionary to file."""
        try:
            content_dict_path = self.config.get_content_dict_path()
            with open(content_dict_path, 'w') as f:
                json.dump(content_dict, f, indent=4)
            self.logger.debug("Content dictionary saved successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error saving content dictionary: {e}")
            return False

    def start(self):
        """Start listening for peer announcements"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("0.0.0.0", self.config.BROADCAST_PORT))
            self.logger.info(f"Listener started on port {self.config.BROADCAST_PORT}")

            while True:
                try:
                    # Receive and process announcements
                    data, addr = sock.recvfrom(65535)
                    self.logger.debug(f"Received data from {addr}")

                    message = json.loads(data.decode())
                    self.logger.debug(f"Message content: {message}")

                    if not message.get("chunks"):
                        self.logger.debug("Received empty chunks announcement, skipping")
                        continue

                    # Update peer information
                    self.peer_manager.update_peer(message["peer_ip"], message["chunks"])

                    # Save updated content dictionary
                    content_dict = self.peer_manager.get_content_dict()
                    if self.save_content_dict(content_dict):
                        self.logger.debug("Content dictionary updated successfully")
                except json.JSONDecodeError as e:
                    self.logger.error(f"Error decoding message: {e}")
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")

def main():
    """Start the P2P listener service."""
    try:
        listener = P2PListener()
        listener.start()
    except KeyboardInterrupt:
        print("\nShutting down listener...")
    except Exception as e:
        print(f"Error starting listener: {e}")


if __name__ == "__main__":
    main()