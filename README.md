# Duplicate File Finder

A high-performance Python command-line tool for finding duplicate files and folders with intelligent optimization and memory-efficient processing.

## Features

### 🚀 Core Functionality
- **Smart Duplicate Detection**: Finds duplicate files based on content, not just names
- **Folder Duplicate Detection**: Identifies entire duplicate folders to avoid redundant file reports
- **Multi-Stage Optimization**: Uses size, partial hash, and full hash comparison for efficiency
- **Progress Tracking**: Real-time progress bars with tqdm
- **Error Resilience**: Handles permission errors, broken symlinks, and missing files gracefully

### ⚡ Performance Optimizations
- **Parallel Processing**: Utilizes multiple CPU cores for faster hashing
- **Adaptive Optimization**: Automatically adjusts worker counts based on system resources
- **Memory-Efficient Mode**: Process massive directories with constant memory usage
- **Disk-Aware Strategy**: Optimizes differently for SSDs vs HDDs
- **Smart Caching**: Reduces redundant hash calculations

### 📊 Output Options
- **Text Output**: Human-readable grouped display with statistics
- **JSON Output**: Machine-readable format for scripting
- **Quiet Mode**: Suppress non-essential output
- **Verbose Mode**: Detailed debugging information

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Install from Source

```bash
# Clone the repository
git clone https://github.com/gbillig/duplicate-file-finder.git
cd duplicate-file-finder

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

### Dependencies
- `tqdm` - Progress bars
- `colorama` - Cross-platform colored output
- `psutil` - System resource monitoring

## Usage

### Basic Usage

Find duplicates in a directory:
```bash
python -m duplicate_finder /path/to/directory
```

### Output Formats

#### Text Output (Default)
```bash
python -m duplicate_finder /path/to/scan
```

#### JSON Output
```bash
python -m duplicate_finder /path/to/scan --output json
```

#### Quiet JSON (for scripting)
```bash
python -m duplicate_finder /path/to/scan --output json --quiet
```

### Performance Modes

#### Standard Mode
Best for directories with < 10,000 files:
```bash
python -m duplicate_finder /path/to/scan
```

#### Adaptive Mode
Automatically optimizes based on system resources:
```bash
python -m duplicate_finder /path/to/scan --adaptive
```

#### Memory-Efficient Mode
For very large directories (100k+ files):
```bash
python -m duplicate_finder /path/to/scan --memory-efficient
```

#### Custom Settings
```bash
# Manual worker count
python -m duplicate_finder /path/to/scan --workers 8

# Custom batch size for memory-efficient mode
python -m duplicate_finder /path/to/scan --memory-efficient --batch-size 2000
```

### Output Control

#### Verbose Output
```bash
python -m duplicate_finder /path/to/scan --verbose
# or
python -m duplicate_finder /path/to/scan -v
```

#### Quiet Mode
```bash
python -m duplicate_finder /path/to/scan --quiet
# or
python -m duplicate_finder /path/to/scan -q
```

## Command-Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `path` | | Directory path to scan for duplicates (required) |
| `--output {text,json}` | `-o` | Output format (default: text) |
| `--verbose` | `-v` | Enable verbose output with detailed information |
| `--quiet` | `-q` | Suppress non-error output |
| `--adaptive` | | Use adaptive optimization based on system resources |
| `--memory-efficient` | | Use memory-efficient mode for very large directories |
| `--workers N` | | Manual override for worker count |
| `--batch-size N` | | Batch size for memory-efficient mode (default: 1000) |

## Performance Characteristics

### Multi-Stage Comparison Algorithm

1. **Stage 1: Size Filtering**
   - Groups files by size
   - O(n) time complexity
   - Files with unique sizes are immediately marked as unique

2. **Stage 2: Partial Hash (4KB)**
   - Hashes first 4KB of same-size files
   - Eliminates files with different beginnings
   - Reduces full file reads by ~70% in typical cases

3. **Stage 3: Full Content Hash**
   - SHA-256 hash of entire file content
   - Only for files with matching size and partial hash
   - Guarantees content-based duplicate detection

4. **Stage 4: Folder Detection**
   - Identifies duplicate folders
   - Filters out individual file reports for folder duplicates
   - Reduces output clutter significantly

### Performance Benchmarks

| Directory Size | Files | Standard Mode | Adaptive Mode | Memory-Efficient |
|---------------|-------|---------------|---------------|------------------|
| Small | 1,000 | 2-3s | 2-3s | 3-4s |
| Medium | 10,000 | 15-20s | 12-18s | 20-25s |
| Large | 100,000 | 3-5 min | 2-4 min | 4-6 min |
| Very Large | 1,000,000 | 30-45 min | 20-35 min | 35-50 min |

*Note: Times vary based on file sizes, disk speed, and system resources*

### Memory Usage

- **Standard Mode**: ~200MB for 100k files
- **Adaptive Mode**: Adjusts based on available RAM
- **Memory-Efficient Mode**: Constant ~100MB regardless of directory size

## Examples

### Find Duplicates in Downloads Folder
```bash
python -m duplicate_finder ~/Downloads
```

### Scan Large Photo Library with Adaptive Optimization
```bash
python -m duplicate_finder ~/Pictures --adaptive --verbose
```

### Generate JSON Report for Automation
```bash
python -m duplicate_finder /data/backups --output json > duplicates.json
```

### Process Massive Directory on Limited Memory System
```bash
python -m duplicate_finder /mnt/archive --memory-efficient --batch-size 500
```

### Quick Scan with Minimal Output
```bash
python -m duplicate_finder /path/to/scan --quiet
```

## Output Format Examples

### Text Output
```
🔍 DUPLICATE FOLDERS
====================
📁 Duplicate folder group (2 folders):
   • /path/to/folder1
   • /path/to/backup/folder1

🔍 DUPLICATE FILES
==================
📄 GROUP 1 (2 files, 10.5 MB each):
   • /path/to/file1.pdf
   • /path/to/backup/file1.pdf

📊 SUMMARY STATISTICS
====================
📁 Total files scanned: 5,234
👥 Duplicate files: 89
📄 Unique files: 5,145
🔗 Duplicate file groups: 23
📂 Duplicate folders: 4
💾 Space Analysis:
   Total potential savings: 1.2 GB
```

### JSON Output Structure
```json
{
  "duplicate_files": [
    {
      "hash": "abc123...",
      "files": [
        {
          "path": "/path/to/file1.pdf",
          "size": 10485760,
          "size_formatted": "10.0 MB"
        }
      ],
      "count": 2
    }
  ],
  "duplicate_folders": [
    {
      "folders": [
        {
          "path": "/path/to/folder1",
          "size": 52428800,
          "size_formatted": "50.0 MB",
          "file_count": 10
        }
      ],
      "count": 2
    }
  ],
  "unique_files": [...],
  "statistics": {
    "total_files": 5234,
    "duplicate_files_count": 89,
    "unique_files_count": 5145,
    "total_potential_savings": 1288490188
  }
}
```

## Architecture

### Module Structure
```
duplicate_finder/
├── __init__.py          # Package initialization
├── cli.py               # Command-line interface
├── scanner.py           # Directory scanning with error handling
├── hasher.py            # File hashing utilities
├── detector.py          # Duplicate detection logic
├── parallel_hasher.py   # Parallel processing
├── adaptive_optimizer.py # System resource optimization
├── memory_efficient_detector.py # Memory-efficient processing
├── folder_detector.py   # Folder duplicate detection
└── formatter.py         # Output formatting
```

### Key Design Decisions

1. **Streaming Processing**: Files are processed as discovered, not collected in memory
2. **Parallel I/O**: Multiple workers for disk operations on SSDs
3. **Adaptive Concurrency**: Worker count adjusts to system load
4. **Smart Caching**: Partial hashes cached to avoid re-computation
5. **Progressive Enhancement**: Each stage filters candidates for the next

## Troubleshooting

### Permission Errors
The tool handles permission errors gracefully and reports them at the end:
```bash
⚠️  Processing warnings summary:
  • Permission Denied: 5 files
```

### Broken Symlinks
Broken symbolic links are automatically skipped and reported.

### Large Directories Taking Too Long
Try adaptive or memory-efficient mode:
```bash
python -m duplicate_finder /large/directory --adaptive
# or
python -m duplicate_finder /large/directory --memory-efficient
```

### High Memory Usage
Use memory-efficient mode with smaller batch size:
```bash
python -m duplicate_finder /path --memory-efficient --batch-size 500
```

## Development

### Running Tests
```bash
pytest tests/ -v
```

### Code Formatting
```bash
black duplicate_finder/
```

### Linting
```bash
flake8 duplicate_finder/
```

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with Python 3
- Progress bars by [tqdm](https://github.com/tqdm/tqdm)
- System monitoring by [psutil](https://github.com/giampaolo/psutil)
- Colored output by [colorama](https://github.com/tartley/colorama)

## Author

Gleb Billig

## Project Status

✅ **Production Ready** - All planned features implemented and tested

### Completed Features
- [x] Basic duplicate detection
- [x] Progress bars
- [x] Multi-stage optimization
- [x] Directory streaming
- [x] Output formatting
- [x] Folder duplicate detection
- [x] Error handling
- [x] Output format options
- [x] Parallel processing
- [x] Memory-efficient mode
- [x] Adaptive optimization
- [x] Complete documentation