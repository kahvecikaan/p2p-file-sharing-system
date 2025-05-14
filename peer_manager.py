import json
import logging
import os
import threading
import time
from collections import defaultdict

from config import P2PConfig


class PeerManager:
    """
    Manages peer information and chunk availability in the P2P network.
    Handles peer tracking, content updates, and stale peer removal.
    """

    def __init__(self, peer_id=None):
        # Initialize configuration and logging
        self.logger = None
        self.config = P2PConfig(peer_id)
        self.setup_logging()

        # Initialize peer tracking
        self.peers = defaultdict(dict)
        self.lock = threading.Lock()
        self.content_modified = False

        # Load existing content dictionary if available
        self._load_content_dict()

        if self.logger is not None:
            self.logger.info("PeerManager initialized")

    def setup_logging(self):
        """Configure logging for the peer manager component."""
        self.logger = logging.getLogger('PeerManager')
        self.logger.setLevel(logging.DEBUG)

        # Create handlers for both file and console output
        file_handler = logging.FileHandler(
            os.path.join(self.config.LOG_DIR, 'peer_manager.log')
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

    def _load_content_dict(self):
        """Load existing content dictionary from file."""
        try:
            content_dict_path = self.config.get_content_dict_path()
            if os.path.exists(content_dict_path):
                with open(content_dict_path) as f:
                    content_dict = json.load(f)

                    # Initialize peer data from content dictionary
                    for chunk_name, chunk_data in content_dict.items():
                        for peer in chunk_data['peers']:
                            self.peers[peer]['chunks'] = {
                                chunk_name: {'checksum': chunk_data['checksum']}
                            }
                    self.logger.info("Loaded existing content dictionary")
            else:
                self.logger.info("No existing content dictionary found")
        except Exception as e:
            self.logger.error(f"Error loading content dictionary: {e}")

    def update_peer(self, peer_ip, chunks):
        """Update peer information with new chunk data."""
        with self.lock:
            try:
                # Skip empty updates for existing peers
                if not chunks and peer_ip in self.peers:
                    return

                current_chunks = self.peers.get(peer_ip, {}).get('chunks', {})
                if current_chunks != chunks:
                    self.content_modified = True
                    self.logger.debug(f"Updating chunks for peer {peer_ip}")

                self.peers[peer_ip] = {
                    "last_seen": time.time(),
                    "chunks": chunks
                }
            except Exception as e:
                self.logger.error(f"Error updating peer {peer_ip}: {e}")

    def remove_stale_peers(self, timeout=300):
        """Remove peers that haven't been seen recently."""
        while True:
            try:
                time.sleep(60)  # Check every minute
                now = time.time()

                with self.lock:
                    stale = []
                    for ip, data in self.peers.items():
                        # Use .get() with a default to handle missing 'last_seen' key
                        if now - data.get("last_seen", 0) > timeout:
                            stale.append(ip)

                    if stale:
                        self.content_modified = True
                        for ip in stale:
                            self.logger.info(f"Removing stale peer: {ip}")
                            del self.peers[ip]

            except Exception as e:
                self.logger.error(f"Error removing stale peers: {e}", exc_info=True)

    def get_content_dict(self):
        """Generate content dictionary from current peer information."""
        content_dict = {}
        with self.lock:
            try:
                for peer_ip, data in self.peers.items():
                    for chunk_name, chunk_meta in data['chunks'].items():
                        if chunk_name not in content_dict:
                            content_dict[chunk_name] = {
                                "checksum": chunk_meta['checksum'],
                                "peers": [peer_ip]
                            }
                        else:
                            # Verify checksum matches
                            if content_dict[chunk_name]['checksum'] != chunk_meta['checksum']:
                                self.logger.warning(
                                    f"Checksum mismatch for {chunk_name} from {peer_ip}"
                                )
                                continue

                            # Add peer if not already listed
                            if peer_ip not in content_dict[chunk_name]['peers']:
                                content_dict[chunk_name]['peers'].append(peer_ip)

                return content_dict
            except Exception as e:
                self.logger.error(f"Error generating content dictionary: {e}")
                return {}
