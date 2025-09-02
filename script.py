import sys
import os
import logging
import time
import shutil
import hashlib
import argparse
from pathlib import Path

"""
Parameters:
- source: Path to the source directory
- replica: Path to the replica directory
- interval: Time interval between syncs (in seconds)
- amount: Number of sync iterations to perform
- log_path: Path to the log file
"""


class FileSync:
    def __init__(self, source: Path, replica: Path, interval: int, amount: int, log_path: Path) -> None:
        self.source_path = Path(source)
        self.replica_path = Path(replica)
        self.sync_interval = int(interval)
        self.sync_amount = int(amount)
        self.log_path = Path(log_path)

        self.validate_paths()

        self.logger = None
        self.init_logging()

    def init_logging(self) -> None:
        """
        Initialize logging configuration
        """
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            handlers=[logging.FileHandler(self.log_path), logging.StreamHandler()])
        self.logger = logging.getLogger(__name__)

    def validate_paths(self) -> None:
        """
        Validate source and replica paths, create replica folder and log file in case they do not exist
        """
        if not self.source_path.exists():
            raise FileNotFoundError(
                f"Source path '{self.source_path}' does not exist.")

        if not self.replica_path.exists():
            self.logger.info(
                f"Replica path '{self.replica_path}' does not exist. Creating...")
            os.makedirs(self.replica_path)

        if not self.log_path.exists():
            self.logger.info(
                f"Log path '{self.log_path}' does not exist. Creating...")
            open(self.log_path, 'w').close()

    def calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate the MD5 hash of a file for file comparison
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
        except Exception as e:
            self.logger.exception(
                f"Error calculating hash for {file_path}: {e}")
            return None
        return hash_md5.hexdigest()

    def are_files_different(self, source_file: Path, replica_file: Path) -> bool:
        """
        Check if the files are different
        """
        try:
            source_stat = os.stat(source_file)
            replica_stat = os.stat(replica_file)
        except FileNotFoundError:
            return True

        if source_stat.st_size != replica_stat.st_size:
            return True
        if int(source_stat.st_mtime) == replica_stat.st_mtime:
            return False

        if not replica_file.exists():
            return True

        return self.calculate_file_hash(source_file) != self.calculate_file_hash(replica_file)

    def copy_file(self, source_file: Path, replica_file: Path) -> bool:
        """
        Copy a file from one location to another using shutil library
        """
        try:
            tmp = replica_file.with_suffix('.tmp')
            replica_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, tmp)
            os.replace(tmp, replica_file)
            self.logger.info(f"Copied '{source_file}' to '{replica_file}'")
            return True
        except Exception as e:
            self.logger.exception(
                f"Error copying file from {source_file} to {replica_file}: {e}")
            return False

    def remove_file_or_directory(self, path: Path) -> None:
        """
        Remove file/directory from the location
        """
        try:
            if path.is_file():
                self.logger.info(f"Removed '{path}'")
                path.unlink()
            else:
                self.logger.info(f"Removed directory '{path}'")
                shutil.rmtree(path)
        except PermissionError as e:
            self.logger.exception(f"Permission error removing {path}: {e}")
        except Exception as e:
            self.logger.exception(f"Error removing file {path}: {e}")

    def sync(self) -> None:
        """
        Start the synchronization process
        """
        self.logger.info("Starting synchronization...")

        for i in range(self.sync_amount):
            self.logger.info(f"Sync iteration {i+1} started.")

            # Initialize counters for each sync iteration
            files_copied = files_removed = 0
            dirs_created = dirs_removed = 0
            errors = 0

            sync_start_time = time.time()

            source_root = Path(self.source_path)
            replica_root = Path(self.replica_path)

            files_copied, dirs_created, errors = self.sync_source_to_replica(
                source_root, replica_root)
            files_removed, dirs_removed = self.clean_replica(
                source_root, replica_root)

            self.log_sync_info(files_copied, files_removed,
                               dirs_created, dirs_removed, errors, time.time() - sync_start_time)

            if i < self.sync_amount - 1:
                self.logger.info(
                    f"Waiting for {self.sync_interval} seconds until next synchronization...")
                time.sleep(self.sync_interval)

    def sync_source_to_replica(self, source_root: Path, replica_root: Path) -> tuple[int, int, int]:
        """
        Synchronize files from the source directory to the replica directory
        """
        dirs_created = files_copied = errors = 0

        for root, dirs, files in os.walk(source_root):
            root_path = Path(root)
            replica_dir_path = replica_root / \
                root_path.relative_to(source_root)
            os.makedirs(replica_dir_path, exist_ok=True)

            for name in files:
                source_file = root_path / name
                replica_file = replica_dir_path / name

                if self.are_files_different(source_file, replica_file):
                    if self.copy_file(source_file, replica_file):
                        files_copied += 1
                    else:
                        errors += 1
                        self.logger.error(
                            f"Error copying file from {source_file} to {replica_file}")
            for name in dirs:
                replica_dir = replica_dir_path / name

                if not replica_dir.exists():
                    replica_dir.mkdir(parents=True, exist_ok=True)
                    self.logger.info(f"Created directory '{replica_dir}'")
                    dirs_created += 1

        return files_copied, dirs_created, errors

    def clean_replica(self, source_root: Path, replica_root: Path) -> tuple[int, int]:
        """
        Remove files/directories in the replica folder that no longer exist in the source
        """
        files_removed = dirs_removed = 0
        for root, dirs, files in os.walk(replica_root, topdown=False):
            root_path = Path(root)
            source_dir_path = source_root / \
                root_path.relative_to(replica_root)
            for name in files:
                replica_path = root_path / name
                source_path = source_dir_path / name

                if not source_path.exists():
                    self.remove_file_or_directory(replica_path)
                    files_removed += 1

            for name in dirs:
                replica_path = root_path / name
                source_path = source_dir_path / name

                if not source_path.exists():
                    self.remove_file_or_directory(replica_path)
                    dirs_removed += 1

        return files_removed, dirs_removed

    def log_sync_info(self, files_copied: int, files_removed: int, dirs_created: int, dirs_removed: int, errors: int, duration: float) -> None:
        self.logger.info(
            f"Files copied: {files_copied}, Files removed: {files_removed}, Directories created: {dirs_created}, Directories removed: {dirs_removed}, Errors: {errors}")
        self.logger.info(f"Synchronization completed in {duration} seconds")


def main() -> None:
    """
    Main function to start the synchronization process
    """
    parser = argparse.ArgumentParser(description="File Synchronization Script")
    parser.add_argument("source_path", help="Path to the source directory")
    parser.add_argument("replica_path", help="Path to the replica directory")
    parser.add_argument(
        "sync_interval", help="Synchronization interval", type=int)
    parser.add_argument(
        "sync_amount", help="Amount of data to synchronize", type=int)
    parser.add_argument("log_path", help="Path to the log file")

    args = parser.parse_args()

    if args is None or len(sys.argv) != 6:
        parser.print_help()
        sys.exit(1)

    source_path = args.source_path
    replica_path = args.replica_path
    sync_interval = args.sync_interval
    sync_amount = args.sync_amount
    log_path = args.log_path

    try:
        syncer = FileSync(source_path, replica_path,
                          sync_interval, sync_amount, log_path)
        syncer.sync()

    except Exception:
        logging.exception("Unhandled error during setup or sync")
        sys.exit(1)


if __name__ == "__main__":
    main()
