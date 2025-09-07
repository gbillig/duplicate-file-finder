"""
Duplicate file detection logic with multi-stage optimization.
"""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from tqdm import tqdm

from .hasher import calculate_file_hash, get_file_size


def find_duplicates(files: List[Path]) -> Tuple[Dict[str, List[Path]], List[Path]]:
    """
    Find duplicate files using multi-stage comparison.
    
    Stage 1: Group by file size
    Stage 2: Partial hash (first 4KB) for same-size files
    Stage 3: Full hash only when partial hashes match
    
    Args:
        files: List of file paths to check
        
    Returns:
        Tuple of (duplicates_dict, unique_files)
        duplicates_dict: hash -> list of duplicate file paths
        unique_files: list of files with no duplicates
    """
    print("\n=== Stage 1: Grouping files by size ===")
    
    # Stage 1: Group files by size
    size_to_files = defaultdict(list)
    for file_path in tqdm(files, desc="Analyzing sizes", unit=" files", leave=False):
        size = get_file_size(file_path)
        if size >= 0:
            size_to_files[size].append(file_path)
    
    # Count files that need further checking
    files_needing_hash = sum(len(group) for group in size_to_files.values() if len(group) > 1)
    unique_by_size = sum(1 for group in size_to_files.values() if len(group) == 1)
    
    print(f"  Found {len(size_to_files)} unique file sizes")
    print(f"  {unique_by_size} files are unique by size alone")
    print(f"  {files_needing_hash} files need content comparison")
    
    # Early exit if no potential duplicates
    if files_needing_hash == 0:
        unique_files = [f for group in size_to_files.values() for f in group]
        return {}, unique_files
    
    print("\n=== Stage 2: Partial hash comparison ===")
    
    # Stage 2: Partial hash for files with same size
    candidates_for_full_hash = []
    
    for size, file_group in tqdm(size_to_files.items(), desc="Partial hashing", unit=" groups", leave=False):
        if len(file_group) == 1:
            # Unique by size
            continue
        
        # Calculate partial hashes for this size group
        size_partial_hashes = defaultdict(list)
        for file_path in file_group:
            partial_hash = calculate_file_hash(file_path, partial=True)
            if partial_hash:
                # Combine size and partial hash for unique key
                key = f"{size}:{partial_hash}"
                size_partial_hashes[key].append(file_path)
        
        # Check which need full hashing
        for partial_key, partial_group in size_partial_hashes.items():
            if len(partial_group) > 1:
                candidates_for_full_hash.extend(partial_group)
    
    print(f"  {len(candidates_for_full_hash)} files need full content comparison")
    
    print("\n=== Stage 3: Full hash comparison ===")
    
    # Stage 3: Full hash only for files with matching partial hashes
    full_hash_to_files = defaultdict(list)
    
    # Group candidates by size and partial hash for efficient full hashing
    candidate_groups = defaultdict(list)
    for file_path in candidates_for_full_hash:
        size = get_file_size(file_path)
        partial = calculate_file_hash(file_path, partial=True)
        if size >= 0 and partial:
            candidate_groups[f"{size}:{partial}"].append(file_path)
    
    for group_key, group_files in tqdm(candidate_groups.items(), desc="Full hashing", unit=" groups", leave=True):
        for file_path in group_files:
            full_hash = calculate_file_hash(file_path, partial=False)
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
    
    print(f"  Optimization complete!")
    
    return duplicates, unique_files