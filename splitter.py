import os
import math
import logging
from config import P2PConfig


class FileSplitter:
    """
    Handles splitting files into chunks for P2P distribution.
    """

    def __init__(self, peer_id=None):
        self.logger = None
        self.config = P2PConfig(peer_id)
        self.setup_logging()

    def setup_logging(self):
        """Configure logging for the file splitter."""
        self.logger = logging.getLogger('FileSplitter')
        self.logger.setLevel(logging.INFO)

        # Create handlers and formatters
        file_handler = logging.FileHandler(
            os.path.join(self.config.LOG_DIR, 'splitter.log')
        )
        console_handler = logging.StreamHandler()

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def split_file(self, file_path):
        """Split a file into chunks."""
        try:
            # Get file information
            content_name = os.path.splitext(os.path.basename(file_path))[0]
            extension = os.path.splitext(file_path)[1]
            file_size = os.path.getsize(file_path)

            # Calculate chunks
            chunk_size = self.config.CHUNK_SIZE
            num_chunks = math.ceil(file_size / chunk_size)

            self.logger.info(f"Processing file: {file_path}")
            self.logger.info(f"File size: {file_size} bytes")
            self.logger.info(f"Chunk size: {chunk_size} bytes")
            self.logger.info(f"Number of chunks: {num_chunks}")

            # Split file into chunks
            with open(file_path, "rb") as infile:
                index = 1
                while True:
                    chunk = infile.read(chunk_size)
                    if not chunk:
                        break

                    # Naming convention: {original_name}_{index}{extension}
                    chunk_name = f"{content_name}_{index}{extension}"
                    chunk_path = os.path.join(self.config.CHUNK_DIR, chunk_name)

                    self.logger.info(f"Creating chunk: {chunk_name}")
                    with open(chunk_path, "wb") as chunk_file:
                        chunk_file.write(chunk)

                    index += 1

            return num_chunks

        except Exception as e:
            self.logger.error(f"Error splitting file: {e}", exc_info=True)
            return 0


def main():
    splitter = FileSplitter()
    file_path = input("Enter file path to split: ")
    num_chunks = splitter.split_file(file_path)
    if num_chunks > 0:
        print(f"File successfully split into {num_chunks} chunks")
    else:
        print("Failed to split file")


if __name__ == "__main__":
    main()