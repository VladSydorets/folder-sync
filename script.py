import sys
import os
import logging
import time
import shutil
import hashlib

"""
Parameters:
- source: Path to the source directory
- replica: Path to the replica directory
- interval: Time interval between syncs (in seconds)
- amount: Number of sync iterations to perform
- log_path: Path to the log file
"""


class FileSync:
    def __init__(self, source, replica, interval, amount, log_path):
        self.source_path = source
        self.replica_path = replica
        self.sync_interval = int(interval)
        self.sync_amount = int(amount)
        self.log_path = log_path

        self.validate_paths()

        self.logger = None
        self.init_logging()

    def init_logging(self):
        """
        Initialize logging configuration
        """
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            handlers=[logging.FileHandler(self.log_path), logging.StreamHandler()])
        self.logger = logging.getLogger(__name__)

    def validate_paths(self):
        """
        Validate source and replica paths, create replica folder and log file in case they do not exist
        """
        if not os.path.exists(self.source_path):
            raise FileNotFoundError(
                f"Source path '{self.source_path}' does not exist.")

        if not os.path.exists(self.replica_path):
            self.logger.info(
                f"Replica path '{self.replica_path}' does not exist. Creating...")
            os.makedirs(self.replica_path)

        if not os.path.exists(self.log_path):
            self.logger.info(
                f"Log path '{self.log_path}' does not exist. Creating...")
            open(self.log_path, 'w').close()

    def calculate_file_hash(self, file_path):
        """
        Calculate the MD5 hash of a file for file comparison
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
        except Exception as e:
            self.logger.error(f"Error calculating hash for {file_path}: {e}")
            return None
        return hash_md5.hexdigest()

    def are_files_different(self, source_file, replica_file):
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

        if not os.path.exists(replica_file):
            return True

        return self.calculate_file_hash(source_file) != self.calculate_file_hash(replica_file)

    def copy_file(self, source_file, replica_file):
        """
        Copy a file from one location to another using shutil library
        """
        try:
            tmp = replica_file + '.tmp'
            shutil.copy2(source_file, tmp)
            os.replace(tmp, replica_file)
            self.logger.info(f"Copied '{source_file}' to '{replica_file}'")
            return True
        except Exception as e:
            self.logger.error(
                f"Error copying file from {source_file} to {replica_file}: {e}")
            return False

    def remove_file_or_directory(self, path):
        """
        Remove file/directory from the location
        """
        try:
            if os.path.isfile(path):
                self.logger.info(f"Removed '{path}'")
                os.remove(path)
                return True
            else:
                self.logger.info(f"Removed directory '{path}'")
                shutil.rmtree(path)
                return True
        except Exception as e:
            self.logger.error(f"Error removing file {path}: {e}")
            return False

    def sync(self):
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

            files_copied, dirs_created, errors = self.sync_source_to_replica()
            files_removed, dirs_removed = self.clean_replica()

            self.log_sync_info(files_copied, files_removed,
                               dirs_created, dirs_removed, errors, time.time() - sync_start_time)

            if i < self.sync_amount - 1:
                self.logger.info(
                    f"Waiting for {self.sync_interval} seconds until next synchronization...")
                time.sleep(self.sync_interval)

    def sync_source_to_replica(self):
        """
        Synchronize files from the source directory to the replica directory
        """
        dirs_created = files_copied = errors = 0
        for root, dirs, files in os.walk(self.source_path):
            replica_dir_path = os.path.relpath(
                self.source_path, self.replica_path)
            os.makedirs(replica_dir_path, exist_ok=True)

            for name in files:
                source_file = os.path.join(root, name)
                replica_file = os.path.join(replica_dir_path, name)

                if self.are_files_different(source_file, replica_file):
                    if self.copy_file(source_file, replica_file):
                        files_copied += 1
                    else:
                        errors += 1
                        self.logger.error(
                            f"Error copying file from {source_file} to {replica_file}")
            for name in dirs:
                replica_dir = os.path.join(replica_dir_path, name)

                if not os.path.exists(replica_dir):
                    os.makedirs(replica_dir, exist_ok=True)
                    self.logger.info(f"Created directory '{replica_dir}'")
                    dirs_created += 1

        return files_copied, dirs_created, errors

    def clean_replica(self):
        """
        Remove files/directories in the replica folder that no longer exist in the source
        """
        files_removed = dirs_removed = 0
        for root, dirs, files in os.walk(self.replica_path):
            source_dir_path = os.path.relpath(
                self.replica_path, self.source_path)

            for name in files:
                replica_path = os.path.join(root, name)
                source_path = os.path.join(source_dir_path, name)

                if not os.path.exists(source_path):
                    self.remove_file_or_directory(replica_path)
                    files_removed += 1

            for name in dirs:
                replica_path = os.path.join(root, name)
                source_path = os.path.join(source_dir_path, name)

                if not os.path.exists(source_path):
                    self.remove_file_or_directory(replica_path)
                    dirs_removed += 1

        return files_removed, dirs_removed

    def log_sync_info(self, files_copied, files_removed, dirs_created, dirs_removed, errors, duration):
        self.logger.info(
            f"Files copied: {files_copied}, Files removed: {files_removed}, Directories created: {dirs_created}, Directories removed: {dirs_removed}, Errors: {errors}")
        self.logger.info(f"Synchronization completed in {duration} seconds")


def main():
    """
    Main function to start the synchronization process
    """
    if len(sys.argv) != 6:
        print("Usage: python python.py <source_path> <replica_path> <sync_interval> <sync_amount> <log_path>")
        return

    source_path = sys.argv[1]
    replica_path = sys.argv[2]
    sync_interval = sys.argv[3]
    sync_amount = sys.argv[4]
    log_path = sys.argv[5]

    try:
        syncer = FileSync(source_path, replica_path,
                          sync_interval, sync_amount, log_path)
        syncer.sync()

    except Exception as e:
        syncer.logger.error(f"Error occurred: {e}")


if __name__ == "__main__":
    main()
