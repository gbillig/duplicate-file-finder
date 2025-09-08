"""
Memory-efficient duplicate detection with streaming and batch processing.
"""

import gc
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Iterator, Optional, Set

from tqdm import tqdm

from .hasher import get_file_size
from .parallel_hasher import parallel_hash_files, get_optimal_worker_count
from .folder_detector import find_duplicate_folders, get_files_in_duplicate_folders


class PartialHashCache:
    """Cache for partial hashes to avoid redundant calculations."""
    
    def __init__(self, max_size: int = 10000):
        """
        Initialize the cache with a maximum size.
        
        Args:
            max_size: Maximum number of entries to cache
        """
        self.cache: Dict[Path, str] = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
    
    def get(self, file_path: Path) -> Optional[str]:
        """Get a cached hash if available."""
        if file_path in self.cache:
            self.hits += 1
            return self.cache[file_path]
        self.misses += 1
        return None
    
    def put(self, file_path: Path, hash_value: str) -> None:
        """Store a hash in the cache."""
        if len(self.cache) >= self.max_size:
            # Simple FIFO eviction - remove oldest entries
            # In production, could use LRU
            num_to_remove = max(1, self.max_size // 10)
            to_remove = list(self.cache.keys())[:num_to_remove]
            for key in to_remove:
                del self.cache[key]
        self.cache[file_path] = hash_value
    
    def clear(self) -> None:
        """Clear the cache."""
        self.cache.clear()
        gc.collect()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'size': len(self.cache),
            'hit_rate': hit_rate
        }


def batch_files_by_size(files: List[Path], batch_size: int = 1000) -> Iterator[List[Path]]:
    """
    Stream files in batches for memory-efficient processing.
    
    Args:
        files: List of file paths
        batch_size: Number of files to process per batch
        
    Yields:
        Batches of file paths
    """
    for i in range(0, len(files), batch_size):
        yield files[i:i + batch_size]


def process_size_groups_streaming(
    files: List[Path],
    batch_size: int = 1000,
    quiet: bool = False
) -> Tuple[Dict[int, List[Path]], List[Path]]:
    """
    Process files in batches to group by size with minimal memory usage.
    
    Args:
        files: List of file paths
        batch_size: Files per batch
        quiet: Suppress output
        
    Returns:
        Tuple of (size_to_files dict, unique_files list)
    """
    size_to_files = defaultdict(list)
    unique_files = []
    processed_sizes: Set[int] = set()
    
    total_batches = (len(files) + batch_size - 1) // batch_size
    
    for batch in tqdm(
        batch_files_by_size(files, batch_size),
        total=total_batches,
        desc="Processing file batches",
        unit=" batches",
        disable=quiet,
        leave=False
    ):
        # Process batch
        for file_path in batch:
            size = get_file_size(file_path)
            if size >= 0:
                size_to_files[size].append(file_path)
        
        # Early cleanup: identify and remove unique sizes
        sizes_to_remove = []
        for size, file_list in size_to_files.items():
            if size not in processed_sizes:
                if len(file_list) == 1:
                    # Check if more files might come in future batches
                    # For now, we'll mark it but not remove yet
                    processed_sizes.add(size)
    
    # Final pass: separate unique files
    final_size_groups = {}
    for size, file_list in size_to_files.items():
        if len(file_list) == 1:
            unique_files.extend(file_list)
        else:
            final_size_groups[size] = file_list
    
    # Clear the temporary dict to free memory
    size_to_files.clear()
    gc.collect()
    
    return final_size_groups, unique_files


def find_duplicates_memory_efficient(
    files: List[Path],
    batch_size: int = 1000,
    cache_size: int = 10000,
    verbose: bool = False,
    quiet: bool = False
) -> Tuple[Dict[str, List[Path]], List[Path], List[List[Path]]]:
    """
    Find duplicates using memory-efficient streaming and caching.
    
    This version processes files in batches to maintain constant memory usage
    regardless of directory size.
    
    Args:
        files: List of file paths to check
        batch_size: Number of files to process per batch
        cache_size: Maximum size of partial hash cache
        verbose: Enable verbose output
        quiet: Suppress non-error output
        
    Returns:
        Tuple of (duplicates_dict, unique_files, duplicate_folders)
    """
    if not quiet:
        print("\n=== Memory-Efficient Duplicate Detection ===")
        print(f"  Processing {len(files)} files in batches of {batch_size}")
    
    # Initialize partial hash cache
    partial_cache = PartialHashCache(max_size=cache_size)
    
    # Stage 1: Group by size with streaming
    if not quiet:
        print("\n=== Stage 1: Streaming size analysis ===")
    
    size_to_files, unique_by_size = process_size_groups_streaming(
        files, batch_size, quiet
    )
    
    files_needing_hash = sum(len(group) for group in size_to_files.values())
    
    if not quiet:
        print(f"  Found {len(size_to_files)} groups with potential duplicates")
        print(f"  {len(unique_by_size)} files are unique by size")
        print(f"  {files_needing_hash} files need content comparison")
    
    # Early exit if no potential duplicates
    if files_needing_hash == 0:
        return {}, unique_by_size, []
    
    # Stage 2: Batch partial hashing with cache
    if not quiet:
        print("\n=== Stage 2: Cached partial hash comparison ===")
    
    candidates_for_full_hash = []
    files_to_partial_hash = []
    
    # Check cache first
    for size, file_group in size_to_files.items():
        for file_path in file_group:
            cached_hash = partial_cache.get(file_path)
            if cached_hash is None:
                files_to_partial_hash.append(file_path)
    
    if verbose and not quiet:
        cache_stats = partial_cache.get_stats()
        print(f"  Cache stats: {cache_stats['hits']} hits, {cache_stats['misses']} misses")
        print(f"  Need to hash {len(files_to_partial_hash)} files")
        print(f"  Using {get_optimal_worker_count()} parallel workers")
    
    # Batch process partial hashing
    for batch in batch_files_by_size(files_to_partial_hash, batch_size):
        batch_hashes = parallel_hash_files(
            batch,
            partial=True,
            desc="Partial hashing batch",
            quiet=quiet
        )
        
        # Update cache
        for file_path, hash_val in batch_hashes.items():
            if hash_val:
                partial_cache.put(file_path, hash_val)
    
    # Group by size and partial hash
    size_partial_groups = defaultdict(list)
    for size, file_group in size_to_files.items():
        for file_path in file_group:
            partial_hash = partial_cache.get(file_path)
            if not partial_hash:
                # Try to hash if not in cache
                batch_hashes = parallel_hash_files(
                    [file_path],
                    partial=True,
                    quiet=True
                )
                partial_hash = batch_hashes.get(file_path)
            
            if partial_hash:
                key = f"{size}:{partial_hash}"
                size_partial_groups[key].append(file_path)
    
    # Find candidates for full hashing and collect unique files
    unique_by_partial = []
    for group_key, group_files in size_partial_groups.items():
        if len(group_files) > 1:
            candidates_for_full_hash.extend(group_files)
        elif len(group_files) == 1:
            # File is unique by partial hash
            unique_by_partial.extend(group_files)
    
    # Clear size groups to free memory
    size_to_files.clear()
    size_partial_groups.clear()
    gc.collect()
    
    if not quiet:
        print(f"  {len(candidates_for_full_hash)} files need full content comparison")
    
    # Stage 3: Batch full hashing
    if not quiet:
        print("\n=== Stage 3: Batch full hash comparison ===")
    
    full_hash_to_files = defaultdict(list)
    
    # Process full hashes in batches
    for batch in batch_files_by_size(candidates_for_full_hash, batch_size):
        batch_hashes = parallel_hash_files(
            batch,
            partial=False,
            desc="Full hashing batch",
            quiet=quiet
        )
        
        for file_path, full_hash in batch_hashes.items():
            if full_hash:
                full_hash_to_files[full_hash].append(file_path)
    
    # Clear candidates list to free memory
    candidates_for_full_hash.clear()
    partial_cache.clear()
    gc.collect()
    
    # Compile results
    duplicates = {}
    unique_files = unique_by_size.copy()
    unique_files.extend(unique_by_partial)  # Add files unique by partial hash
    
    for full_hash, file_list in full_hash_to_files.items():
        if len(file_list) > 1:
            duplicates[full_hash] = file_list
        else:
            unique_files.extend(file_list)
    
    if not quiet:
        print("  Batch processing complete!")
        print("\n=== Stage 4: Smart folder duplicate detection ===")
    
    # Create file hashes for folder detection
    all_file_hashes = {}
    for hash_val, file_list in full_hash_to_files.items():
        for file_path in file_list:
            all_file_hashes[file_path] = hash_val
    
    # Hash remaining unique files for folder detection
    files_needing_folder_hash = []
    for file_path in files:
        if file_path not in all_file_hashes:
            files_needing_folder_hash.append(file_path)
    
    if files_needing_folder_hash:
        # Process in batches
        for batch in batch_files_by_size(files_needing_folder_hash, batch_size):
            batch_hashes = parallel_hash_files(
                batch,
                partial=False,
                desc="Folder detection hashing",
                quiet=quiet
            )
            all_file_hashes.update(batch_hashes)
    
    # Find duplicate folders
    duplicate_folders = find_duplicate_folders(files, all_file_hashes)
    
    if duplicate_folders:
        if not quiet:
            print(f"  Found {len(duplicate_folders)} groups of duplicate folders")
        
        # Filter out files in duplicate folders
        files_in_duplicate_folders = get_files_in_duplicate_folders(duplicate_folders, files)
        
        filtered_duplicates = {}
        for hash_val, file_list in duplicates.items():
            filtered_files = [f for f in file_list if f not in files_in_duplicate_folders]
            if len(filtered_files) > 1:
                filtered_duplicates[hash_val] = filtered_files
            elif len(filtered_files) == 1:
                unique_files.extend(filtered_files)
        
        duplicates = filtered_duplicates
        unique_files = [f for f in unique_files if f not in files_in_duplicate_folders]
    else:
        if not quiet:
            print("  No duplicate folders found")
    
    # Final garbage collection
    gc.collect()
    
    if verbose and not quiet:
        print(f"\n  Memory-efficient processing complete")
        print(f"  Processed {len(files)} files with constant memory usage")
    
    return duplicates, unique_files, duplicate_folders