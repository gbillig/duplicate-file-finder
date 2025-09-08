"""
Duplicate file detection logic with multi-stage optimization.
"""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from tqdm import tqdm

from .hasher import get_file_size
from .folder_detector import find_duplicate_folders, get_files_in_duplicate_folders
from .parallel_hasher import parallel_hash_files, get_optimal_worker_count, parallel_hash_files_adaptive
from .adaptive_optimizer import get_adaptive_config


def find_duplicates(files: List[Path], verbose: bool = False, quiet: bool = False, adaptive: bool = False, manual_workers: int = None) -> Tuple[Dict[str, List[Path]], List[Path], List[List[Path]]]:
    """
    Find duplicate files and folders using multi-stage comparison.
    
    Stage 1: Group by file size
    Stage 2: Partial hash (first 4KB) for same-size files
    Stage 3: Full hash only when partial hashes match
    Stage 4: Smart folder duplicate detection
    
    Args:
        files: List of file paths to check
        verbose: Enable verbose output
        quiet: Suppress non-error output
        adaptive: Use adaptive optimization
        manual_workers: Manual override for worker count
        
    Returns:
        Tuple of (duplicates_dict, unique_files, duplicate_folders)
        duplicates_dict: hash -> list of duplicate file paths
        unique_files: list of files with no duplicates
        duplicate_folders: list of duplicate folder groups
    """
    if not quiet:
        print("\n=== Stage 1: Grouping files by size ===")
    
    # Stage 1: Group files by size
    size_to_files = defaultdict(list)
    for file_path in tqdm(files, desc="Analyzing sizes", unit=" files", leave=False, disable=quiet):
        size = get_file_size(file_path)
        if size >= 0:
            size_to_files[size].append(file_path)
    
    # Count files that need further checking
    files_needing_hash = sum(len(group) for group in size_to_files.values() if len(group) > 1)
    unique_by_size = sum(1 for group in size_to_files.values() if len(group) == 1)
    
    if not quiet:
        print(f"  Found {len(size_to_files)} unique file sizes")
        print(f"  {unique_by_size} files are unique by size alone")
        print(f"  {files_needing_hash} files need content comparison")
    
    # Early exit if no potential duplicates
    if files_needing_hash == 0:
        unique_files = [f for group in size_to_files.values() for f in group]
        return {}, unique_files, []
    
    if not quiet:
        print("\n=== Stage 2: Partial hash comparison ===")
    
    # Stage 2: Partial hash for files with same size
    candidates_for_full_hash = []
    
    # Collect all files that need partial hashing (groups with > 1 file)
    files_to_partial_hash = []
    for size, file_group in size_to_files.items():
        if len(file_group) > 1:
            files_to_partial_hash.extend(file_group)
    
    if verbose and not quiet:
        if adaptive:
            config = get_adaptive_config(files[0].parent if files else None, len(files), manual_workers)
            print(f"  Using adaptive optimization: {config['io_workers']} I/O workers")
        else:
            print(f"  Using {get_optimal_worker_count()} parallel workers for hashing")
    
    # Parallel partial hashing
    if adaptive:
        partial_hashes = parallel_hash_files_adaptive(
            files_to_partial_hash,
            partial=True,
            desc="Partial hashing",
            quiet=quiet,
            path=files[0].parent if files else None
        )
    else:
        partial_hashes = parallel_hash_files(
            files_to_partial_hash,
            partial=True,
            desc="Partial hashing",
            quiet=quiet,
            max_workers=manual_workers
        )
    
    # Group files by size and partial hash
    size_partial_groups = defaultdict(list)
    for file_path, partial_hash in partial_hashes.items():
        if partial_hash:
            size = get_file_size(file_path)
            key = f"{size}:{partial_hash}"
            size_partial_groups[key].append(file_path)
    
    # Find candidates for full hashing
    for group_key, group_files in size_partial_groups.items():
        if len(group_files) > 1:
            candidates_for_full_hash.extend(group_files)
    
    if not quiet:
        print(f"  {len(candidates_for_full_hash)} files need full content comparison")
        print("\n=== Stage 3: Full hash comparison ===")
    
    # Stage 3: Full hash only for files with matching partial hashes
    full_hash_to_files = defaultdict(list)
    
    # Parallel full hashing
    if candidates_for_full_hash:
        if adaptive:
            full_hashes = parallel_hash_files_adaptive(
                candidates_for_full_hash,
                partial=False,
                desc="Full hashing",
                quiet=quiet,
                path=files[0].parent if files else None
            )
        else:
            full_hashes = parallel_hash_files(
                candidates_for_full_hash,
                partial=False,
                desc="Full hashing",
                quiet=quiet,
                max_workers=manual_workers
            )
        
        # Group by full hash
        for file_path, full_hash in full_hashes.items():
            if full_hash:
                full_hash_to_files[full_hash].append(file_path)
    
    # Compile final results
    duplicates = {}
    unique_files = []
    
    # Add unique-by-size files
    for size, file_group in size_to_files.items():
        if len(file_group) == 1:
            unique_files.extend(file_group)
    
    # Add files that were unique after partial/full hashing
    processed_files = set(candidates_for_full_hash)
    for size, file_group in size_to_files.items():
        if len(file_group) > 1:
            for file_path in file_group:
                if file_path not in processed_files:
                    unique_files.append(file_path)
    
    # Add duplicates and remaining unique files from full hash
    for full_hash, file_list in full_hash_to_files.items():
        if len(file_list) > 1:
            duplicates[full_hash] = file_list
        else:
            unique_files.extend(file_list)
    
    if not quiet:
        print(f"  Optimization complete!")
        print("\n=== Stage 4: Smart folder duplicate detection ===")
    
    # Create a dictionary of file hashes for folder detection
    all_file_hashes = {}
    for hash_val, file_list in full_hash_to_files.items():
        for file_path in file_list:
            all_file_hashes[file_path] = hash_val
    
    # Add files that were unique by size or partial hash
    # Collect files that need hashing for folder detection
    files_needing_folder_hash = []
    for size, file_group in size_to_files.items():
        for file_path in file_group:
            if file_path not in all_file_hashes:
                files_needing_folder_hash.append(file_path)
    
    # Parallel hash remaining files for folder detection
    if files_needing_folder_hash:
        if adaptive:
            remaining_hashes = parallel_hash_files_adaptive(
                files_needing_folder_hash,
                partial=False,
                desc="Hashing for folder detection",
                quiet=quiet,
                path=files[0].parent if files else None
            )
        else:
            remaining_hashes = parallel_hash_files(
                files_needing_folder_hash,
                partial=False,
                desc="Hashing for folder detection",
                quiet=quiet,
                max_workers=manual_workers
            )
        all_file_hashes.update(remaining_hashes)
    
    # Find duplicate folders
    duplicate_folders = find_duplicate_folders(files, all_file_hashes)
    
    if duplicate_folders:
        if not quiet:
            print(f"  Found {len(duplicate_folders)} groups of duplicate folders")
        
        # Remove files that are in duplicate folders from individual file duplicates
        files_in_duplicate_folders = get_files_in_duplicate_folders(duplicate_folders, files)
        
        # Filter out individual file duplicates that are part of folder duplicates
        filtered_duplicates = {}
        for hash_val, file_list in duplicates.items():
            filtered_files = [f for f in file_list if f not in files_in_duplicate_folders]
            if len(filtered_files) > 1:
                filtered_duplicates[hash_val] = filtered_files
            elif len(filtered_files) == 1:
                # Single file remaining after folder filtering becomes unique
                unique_files.extend(filtered_files)
        
        duplicates = filtered_duplicates
        
        # Also remove folder-duplicate files from unique files list
        unique_files = [f for f in unique_files if f not in files_in_duplicate_folders]
    else:
        if not quiet:
            print("  No duplicate folders found")
    
    return duplicates, unique_files, duplicate_folders