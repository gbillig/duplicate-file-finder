# Duplicate File Finder

## Program Description
A Python command-line tool that efficiently detects duplicate files within a specified folder. The program uses a multi-stage comparison approach to identify duplicates based on file content, with smart detection of entire duplicate folders to avoid redundant reporting.

## Requirements

### Functional Requirements
- **Input**: Single folder path from command line
- **Output**: 
  - List of files that have duplicates (grouped by identical content)
  - List of unique files (no duplicates found)
- **Smart Folder Detection**: If an entire folder's contents are duplicated elsewhere, report the folder as a unit rather than individual files

### Performance Requirements
- Multi-stage comparison for efficiency:
  1. Metadata filtering (file size)
  2. Partial content hashing (first 4KB)
  3. Full content hashing (only when necessary)
- Handle large directory structures efficiently
- Provide progress feedback for long operations

## Implementation Plan

See @PLAN.md for the detailed commit-by-commit implementation plan.

The implementation follows these principles:
- Each commit produces a working program
- Tests are included with each feature
- Progressive enhancement from MVP to full solution
- Core requirements prioritized (especially smart folder detection)

## Python Best Practices for CLI Applications

### Project Structure
```
duplicate-file-finder/
├── duplicate_finder.py   # Main script
├── requirements.txt       # Dependencies
├── README.md             # User documentation
├── CLAUDE.md            # Development documentation
└── tests/               # Unit tests
    └── test_duplicate_finder.py
```

### Code Style and Standards
- **PEP 8 Compliance**: Use `black` for formatting, `flake8` for linting
- **Type Hints**: Use type annotations for better code clarity
- **Docstrings**: Google-style docstrings for all functions and classes

### Command-Line Interface
```python
import argparse
from pathlib import Path

def create_parser():
    parser = argparse.ArgumentParser(
        description='Find duplicate files in a directory',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('path', type=Path, help='Directory to scan')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress non-error output')
    parser.add_argument('-o', '--output', type=str, choices=['text', 'json'], default='text', help='Output format')
    parser.add_argument('--no-progress', action='store_true', help='Disable progress bar')
    return parser
```

### Error Handling
```python
import sys
import logging

def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def handle_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except PermissionError as e:
            logging.error(f"Permission denied: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            logging.info("Operation cancelled by user")
            sys.exit(130)
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            sys.exit(1)
    return wrapper
```

### Progress Feedback
```python
from tqdm import tqdm

def scan_files_with_progress(directory: Path, show_progress=True):
    files = list(directory.rglob('*'))
    iterator = tqdm(files, desc="Scanning files") if show_progress else files
    for file_path in iterator:
        if file_path.is_file():
            yield file_path
```

### Testing Approach
- Use `pytest` for unit testing
- Mock file system operations with `pytest` fixtures
- Test edge cases: empty directories, permission errors, symbolic links
- Performance tests for large file sets

### Dependencies
```
# requirements.txt
tqdm>=4.65.0       # Progress bars
colorama>=0.4.6    # Cross-platform colored output
```

### Development Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Format code
black duplicate_finder.py

# Lint code
flake8 duplicate_finder.py

# Run the program
python duplicate_finder.py /path/to/scan
```

## Git Commit Message Guidelines

### Conventional Commit Format
```
<type>: <subject>

<body>

<footer>
```

### Types
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, etc.)
- **refactor**: Code refactoring
- **perf**: Performance improvements
- **test**: Test additions or corrections
- **chore**: Build process or auxiliary tool changes

### Rules
1. **Subject line**: Max 50 chars, imperative mood, no period
2. **Body**: Wrap at 72 chars, explain why not how
3. **Separate** subject from body with blank line

### Examples
```
feat: Add multi-stage file comparison

Implement three-stage approach to optimize performance:
- Stage 1: Compare file sizes
- Stage 2: Compare partial hashes (first 4KB)
- Stage 3: Full content hash when necessary

Reduces full file reads by ~70% in typical use cases.
```

### Auto-generated Footer
When using Claude Code to generate commits, add:
```
🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Performance Considerations

### Memory Efficiency
- Process files in chunks for hashing
- Don't load entire file contents into memory
- Use generators where possible

### I/O Optimization
- Buffer size: 64KB chunks for reading files
- Parallel processing for independent file operations (use `concurrent.futures`)
- Cache partial hashes to avoid re-computation

### Example Hashing Implementation
```python
import hashlib
from pathlib import Path

def get_file_hash(file_path: Path, partial=False, chunk_size=65536) -> str:
    """Calculate SHA256 hash of a file."""
    hash_obj = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        if partial:
            # Read only first 4KB for partial hash
            data = f.read(4096)
            if data:
                hash_obj.update(data)
        else:
            # Read entire file in chunks
            while chunk := f.read(chunk_size):
                hash_obj.update(chunk)
    
    return hash_obj.hexdigest()
```

## Next Steps
1. Implement core file scanning and hashing logic
2. Add multi-stage comparison optimization
3. Implement smart folder detection
4. Create comprehensive test suite
5. Add performance benchmarks