import os
import json

class P2PConfig:
    """
    Configuration manager for P2P file sharing application.
    Handles both peer-specific and general configurations.
    """
    def __init__(self, peer_id=None, config_file='peer_config.json'):
        self.peer_id = peer_id

        # Basic configuration with defaults
        self.base_config = {
            'CHUNK_SIZE': 100 * 1024,  # 100KB default chunk size
            'BROADCAST_IP': '0.0.0.0',  # Listen on all interfaces
            'BROADCAST_PORT': 5001,     # Base broadcast port
            'PEER_PORT': 5000,          # Base peer port
            'MAX_CONNECTIONS': 10,
            'CONNECTION_TIMEOUT': 300,
            'RETRY_ATTEMPTS': 3,
            'ANNOUNCE_INTERVAL': 10
        }

        # Directory structure - these are subdirectories
        self.directories = {
            'CHUNK_DIR': './chunks/',
            'LOG_DIR': './logs/',
            'DOWNLOADS_DIR': './downloads/'
        }

        # File paths - these are in the root directory
        self.files = {
            'CONTENT_DICT': './content_dict.json',  # Changed to be in root
            'CONFIG_FILE': './' + config_file       # Changed to be in root
        }

        # Initialize directories
        self._create_directories()

        # Load or create configuration
        self.config = self._load_config()

        # Adjust ports if peer_id is provided
        if peer_id is not None:
            self.config['BROADCAST_PORT'] += peer_id
            self.config['PEER_PORT'] += peer_id

    def _create_directories(self):
        """Create necessary directories for the application."""
        for directory in self.directories.values():
            os.makedirs(directory, exist_ok=True)

    def _load_config(self):
        """Load configuration from file or create default."""
        try:
            with open(self.files['CONFIG_FILE'], 'r') as f:  # Changed path
                saved_config = json.load(f)
                return {**self.base_config, **saved_config}
        except FileNotFoundError:
            return self.base_config.copy()

    def save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.files['CONFIG_FILE'], 'w') as f:  # Changed path
                json.dump(self.config, f, indent=4)
        except OSError as e:
            raise RuntimeError(f"Failed to save configuration: {e}")

    def get_content_dict_path(self):
        """Get the full path to content dictionary file."""
        return self.files['CONTENT_DICT']  # Now returns direct path

    def __getattr__(self, name):
        """Allow accessing configuration values as attributes."""
        if name in self.config:
            return self.config[name]
        if name in self.directories:
            return self.directories[name]
        if name in self.files:
            return self.files[name]
        raise AttributeError(f"Configuration has no attribute '{name}'")