# Folder Synchronization Script

This script synchronizes the contents of a source directory with a replica directory at specified intervals, logging all actions and changes.

## Features

- Recursively copies new and updated files from the source to the replica directory
- Removes files and directories from the replica that no longer exist in the source
- Logs all operations and errors to a specified log file
- Supports repeated synchronization at a user-defined interval and number of iterations

## Requirements

- Python 3.7 or higher

## Usage

Run the script from the command line:

```bash
python script.py <source_path> <replica_path> <sync_interval> <sync_amount> <log_path>
```

- `<source_path>`: Path to the source directory
- `<replica_path>`: Path to the replica directory
- `<sync_interval>`: Time interval between synchronizations (in seconds)
- `<sync_amount>`: Number of synchronization iterations to perform
- `<log_path>`: Path to the log file

### Example

```bash
python script.py ./source ./replica 60 10 ./log.txt
```

This will synchronize folder `./replica` with `./source` every 60 seconds, for 10 iterations, logging to `./log.txt`.

## Logging

Such actions as file copies, deletions, errors, and sync statistics, are logged to the specified log file and printed to the console.

## License

MIT License
