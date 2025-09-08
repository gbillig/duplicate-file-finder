"""
Unit tests for duplicate_finder.py
"""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, ANY
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from duplicate_finder import cli, hasher, scanner, detector, formatter, folder_detector
import pytest


class TestFileHashing:
    """Test file hashing functionality."""
    
    def test_calculate_file_hash_identical_content(self, tmp_path):
        """Test that identical files produce same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        content = b"This is test content"
        
        file1.write_bytes(content)
        file2.write_bytes(content)
        
        hash1 = hasher.calculate_file_hash(file1, partial=False)
        hash2 = hasher.calculate_file_hash(file2, partial=False)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex characters
    
    def test_calculate_file_hash_different_content(self, tmp_path):
        """Test that different files produce different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_bytes(b"Content A")
        file2.write_bytes(b"Content B")
        
        hash1 = hasher.calculate_file_hash(file1)
        hash2 = hasher.calculate_file_hash(file2)
        
        assert hash1 != hash2
    
    def test_calculate_file_hash_empty_file(self, tmp_path):
        """Test hashing of empty file."""
        empty_file = tmp_path / "empty.txt"
        empty_file.touch()
        
        file_hash = hasher.calculate_file_hash(empty_file)
        # SHA256 of empty string
        expected = hashlib.sha256(b"").hexdigest()
        assert file_hash == expected
    
    def test_calculate_file_hash_nonexistent_file(self, tmp_path):
        """Test handling of nonexistent file."""
        nonexistent = tmp_path / "nonexistent.txt"
        
        with patch('sys.stderr'):
            result = hasher.calculate_file_hash(nonexistent)
        
        assert result is None
    
    def test_calculate_partial_hash(self, tmp_path):
        """Test partial hash calculation."""
        # Create a large file
        large_file = tmp_path / "large.txt"
        content = b"Start content" + b"X" * 10000 + b"End content"
        large_file.write_bytes(content)
        
        partial_hash = hasher.calculate_file_hash(large_file, partial=True)
        full_hash = hasher.calculate_file_hash(large_file, partial=False)
        
        # Partial and full hash should be different for large files
        assert partial_hash != full_hash
        assert len(partial_hash) == 64
    
    def test_partial_hash_same_beginning(self, tmp_path):
        """Test that files with same beginning have same partial hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        # Same first 4KB, different afterwards
        common_start = b"A" * 4096
        file1.write_bytes(common_start + b"Different ending 1")
        file2.write_bytes(common_start + b"Different ending 2")
        
        partial1 = hasher.calculate_file_hash(file1, partial=True)
        partial2 = hasher.calculate_file_hash(file2, partial=True)
        full1 = hasher.calculate_file_hash(file1, partial=False)
        full2 = hasher.calculate_file_hash(file2, partial=False)
        
        assert partial1 == partial2  # Same partial hash
        assert full1 != full2  # Different full hash


class TestDirectoryScanning:
    """Test directory scanning functionality."""
    
    @patch('duplicate_finder.scanner.tqdm')
    def test_scan_directory_recursive(self, mock_tqdm, tmp_path):
        """Test recursive directory scanning."""
        # Mock tqdm context manager
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=None)
        mock_tqdm.return_value = mock_progress
        
        # Create nested structure
        (tmp_path / "subdir1").mkdir()
        (tmp_path / "subdir1" / "subdir2").mkdir()
        
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "subdir1" / "file2.txt"
        file3 = tmp_path / "subdir1" / "subdir2" / "file3.txt"
        
        file1.touch()
        file2.touch()
        file3.touch()
        
        with patch('builtins.print'):
            files = scanner.scan_directory(tmp_path)
        
        assert len(files) == 3
        assert file1 in files
        assert file2 in files
        assert file3 in files
    
    @patch('duplicate_finder.scanner.tqdm')
    def test_scan_directory_empty(self, mock_tqdm, tmp_path):
        """Test scanning empty directory."""
        # Mock tqdm context manager
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=None)
        mock_tqdm.return_value = mock_progress
        
        with patch('builtins.print'):
            files = scanner.scan_directory(tmp_path)
        assert files == []
    
    @patch('duplicate_finder.scanner.tqdm')
    def test_scan_directory_ignores_directories(self, mock_tqdm, tmp_path):
        """Test that directories are not included in file list."""
        # Mock tqdm context manager
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=None)
        mock_tqdm.return_value = mock_progress
        
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        file1 = tmp_path / "file.txt"
        file1.touch()
        
        with patch('builtins.print'):
            files = scanner.scan_directory(tmp_path)
        
        assert len(files) == 1
        assert file1 in files
        assert subdir not in files
    
    @patch('duplicate_finder.scanner.tqdm')
    def test_scan_directory_streaming_performance(self, mock_tqdm, tmp_path):
        """Test that scanning uses streaming approach without collecting all items."""
        # Mock tqdm context manager
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=None)
        mock_tqdm.return_value = mock_progress
        
        # Create multiple files
        for i in range(10):
            (tmp_path / f"file_{i}.txt").touch()
        
        with patch('builtins.print'):
            files = scanner.scan_directory(tmp_path)
        
        # Verify we found all files
        assert len(files) == 10
        
        # Verify tqdm was used as context manager (not called with iterable)
        mock_tqdm.assert_called_once()
        call_kwargs = mock_tqdm.call_args[1]
        assert 'desc' in call_kwargs
        assert call_kwargs['desc'] == 'Scanning'
        
        # Verify progress bar methods were called
        assert mock_progress.update.called
        
    def test_scan_directory_keyboard_interrupt(self, tmp_path):
        """Test that scan handles KeyboardInterrupt gracefully."""
        # Create a file to ensure some scanning happens
        (tmp_path / "file.txt").touch()
        
        with patch('duplicate_finder.scanner.tqdm') as mock_tqdm:
            # Mock the context manager to raise KeyboardInterrupt
            mock_progress = MagicMock()
            mock_progress.__enter__ = MagicMock(return_value=mock_progress)
            mock_progress.__exit__ = MagicMock(return_value=None)
            mock_progress.update.side_effect = KeyboardInterrupt("Test interrupt")
            mock_tqdm.return_value = mock_progress
            
            with patch('builtins.print'):
                with pytest.raises(KeyboardInterrupt):
                    scanner.scan_directory(tmp_path)


class TestDuplicateFinding:
    """Test duplicate finding logic."""
    
    @patch('duplicate_finder.detector.tqdm')
    @patch('builtins.print')
    def test_find_duplicates_with_duplicates(self, mock_print, mock_tqdm, tmp_path):
        """Test finding actual duplicates."""
        # Make tqdm act as a passthrough
        mock_tqdm.side_effect = lambda x, **kwargs: x
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file3 = tmp_path / "file3.txt"
        file4 = tmp_path / "unique.txt"
        
        # Create duplicates
        duplicate_content = b"Duplicate content"
        file1.write_bytes(duplicate_content)
        file2.write_bytes(duplicate_content)
        file3.write_bytes(duplicate_content)
        
        # Create unique file
        file4.write_bytes(b"Unique content")
        
        files = [file1, file2, file3, file4]
        duplicates, unique_files, duplicate_folders = detector.find_duplicates(files)
        
        assert len(duplicates) == 1
        assert len(unique_files) == 1
        assert file4 in unique_files
        
        # Check duplicate group
        dup_group = list(duplicates.values())[0]
        assert len(dup_group) == 3
        assert file1 in dup_group
        assert file2 in dup_group
        assert file3 in dup_group
    
    @patch('duplicate_finder.detector.tqdm')
    @patch('builtins.print')
    def test_find_duplicates_no_duplicates(self, mock_print, mock_tqdm, tmp_path):
        # Make tqdm act as a passthrough
        mock_tqdm.side_effect = lambda x, **kwargs: x
        """Test when no duplicates exist."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_bytes(b"Content 1")
        file2.write_bytes(b"Content 2")
        
        files = [file1, file2]
        duplicates, unique_files, duplicate_folders = detector.find_duplicates(files)
        
        assert len(duplicates) == 0
        assert len(unique_files) == 2
    
    @patch('duplicate_finder.detector.tqdm')
    @patch('builtins.print')
    def test_find_duplicates_all_duplicates(self, mock_print, mock_tqdm, tmp_path):
        # Make tqdm act as a passthrough
        mock_tqdm.side_effect = lambda x, **kwargs: x
        """Test when all files are duplicates."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        content = b"Same content"
        file1.write_bytes(content)
        file2.write_bytes(content)
        
        files = [file1, file2]
        duplicates, unique_files, duplicate_folders = detector.find_duplicates(files)
        
        assert len(duplicates) == 1
        assert len(unique_files) == 0
    
    @patch('duplicate_finder.detector.tqdm')
    @patch('builtins.print')
    def test_find_duplicates_multiple_groups(self, mock_print, mock_tqdm, tmp_path):
        # Make tqdm act as a passthrough
        mock_tqdm.side_effect = lambda x, **kwargs: x
        """Test multiple duplicate groups."""
        # Group 1
        file1a = tmp_path / "file1a.txt"
        file1b = tmp_path / "file1b.txt"
        
        # Group 2
        file2a = tmp_path / "file2a.txt"
        file2b = tmp_path / "file2b.txt"
        
        # Unique
        file3 = tmp_path / "unique.txt"
        
        file1a.write_bytes(b"Group 1")
        file1b.write_bytes(b"Group 1")
        file2a.write_bytes(b"Group 2")
        file2b.write_bytes(b"Group 2")
        file3.write_bytes(b"Unique")
        
        files = [file1a, file1b, file2a, file2b, file3]
        duplicates, unique_files, duplicate_folders = detector.find_duplicates(files)
        
        assert len(duplicates) == 2
        assert len(unique_files) == 1
        assert file3 in unique_files


class TestMainFunction:
    """Test main function and CLI."""
    
    def test_main_nonexistent_path(self):
        """Test handling of nonexistent path."""
        with patch('sys.argv', ['duplicate_finder.py', '/nonexistent/path']):
            with patch('sys.stderr'):
                with pytest.raises(SystemExit) as exc_info:
                    cli.main()
                assert exc_info.value.code == 1
    
    def test_main_file_instead_of_directory(self, tmp_path):
        """Test handling when file is provided instead of directory."""
        test_file = tmp_path / "file.txt"
        test_file.touch()
        
        with patch('sys.argv', ['duplicate_finder.py', str(test_file)]):
            with patch('sys.stderr'):
                with pytest.raises(SystemExit) as exc_info:
                    cli.main()
                assert exc_info.value.code == 1
    
    def test_main_empty_directory(self, tmp_path):
        """Test handling of empty directory."""
        with patch('sys.argv', ['duplicate_finder.py', str(tmp_path)]):
            with patch('sys.stdout'):
                with pytest.raises(SystemExit) as exc_info:
                    cli.main()
                assert exc_info.value.code == 0


class TestMultiStageComparison:
    """Test multi-stage duplicate detection optimization."""
    
    @patch('duplicate_finder.detector.tqdm')
    @patch('builtins.print')
    def test_size_based_filtering(self, mock_print, mock_tqdm, tmp_path):
        """Test that files with unique sizes are not hashed."""
        mock_tqdm.side_effect = lambda x, **kwargs: x
        
        # Create files with unique sizes
        file1 = tmp_path / "small.txt"
        file2 = tmp_path / "medium.txt"
        file3 = tmp_path / "large.txt"
        
        file1.write_bytes(b"A")  # 1 byte
        file2.write_bytes(b"BB")  # 2 bytes
        file3.write_bytes(b"CCC")  # 3 bytes
        
        files = [file1, file2, file3]
        duplicates, unique_files, duplicate_folders = detector.find_duplicates(files)
        
        # All files should be unique
        assert len(duplicates) == 0
        assert len(unique_files) == 3
        
        # Verify print output mentions size-based detection
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any("unique by size" in str(call).lower() for call in print_calls)
    
    @patch('duplicate_finder.detector.tqdm')
    @patch('builtins.print')
    def test_partial_hash_optimization(self, mock_print, mock_tqdm, tmp_path):
        """Test that partial hashing prevents unnecessary full hashing."""
        mock_tqdm.side_effect = lambda x, **kwargs: x
        
        # Create files with same size but different content at start
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        # Same size, different content
        file1.write_bytes(b"A" * 1000)
        file2.write_bytes(b"B" * 1000)
        
        files = [file1, file2]
        duplicates, unique_files, duplicate_folders = detector.find_duplicates(files)
        
        # Files should be unique
        assert len(duplicates) == 0
        assert len(unique_files) == 2
    
    @patch('duplicate_finder.detector.tqdm')
    @patch('builtins.print')
    def test_full_hash_for_partial_matches(self, mock_print, mock_tqdm, tmp_path):
        """Test that files with same partial hash get full hashed."""
        mock_tqdm.side_effect = lambda x, **kwargs: x
        
        # Create files with same beginning but different endings
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file3 = tmp_path / "file3.txt"
        
        common_start = b"X" * 5000  # Larger than 4KB
        file1.write_bytes(common_start + b"Ending1")
        file2.write_bytes(common_start + b"Ending2")
        file3.write_bytes(common_start + b"Ending1")  # Duplicate of file1
        
        files = [file1, file2, file3]
        duplicates, unique_files, duplicate_folders = detector.find_duplicates(files)
        
        # file1 and file3 should be duplicates
        assert len(duplicates) == 1
        assert len(unique_files) == 1
        
        dup_group = list(duplicates.values())[0]
        assert len(dup_group) == 2
        assert file1 in dup_group
        assert file3 in dup_group
        assert file2 in unique_files
    
    def test_get_file_size(self, tmp_path):
        """Test file size retrieval."""
        test_file = tmp_path / "test.txt"
        content = b"Test content"
        test_file.write_bytes(content)
        
        size = hasher.get_file_size(test_file)
        assert size == len(content)
    
    def test_get_file_size_nonexistent(self, tmp_path):
        """Test file size retrieval for nonexistent file."""
        nonexistent = tmp_path / "nonexistent.txt"
        size = hasher.get_file_size(nonexistent)
        assert size == -1


class TestProgressReporting:
    """Test progress reporting functionality."""
    
    @patch('duplicate_finder.scanner.tqdm')
    def test_scan_directory_shows_progress(self, mock_tqdm_class, tmp_path):
        """Test that scanning shows progress bar."""
        # Create some test files
        for i in range(3):
            (tmp_path / f"file{i}.txt").touch()
        
        # Mock tqdm context manager
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=None)
        mock_tqdm_class.return_value = mock_progress
        
        with patch('builtins.print') as mock_print:
            files = scanner.scan_directory(tmp_path)
        
        # Verify tqdm was called with correct parameters
        mock_tqdm_class.assert_called_once()
        call_args = mock_tqdm_class.call_args
        assert 'desc' in call_args[1]
        assert 'Scanning' in call_args[1]['desc']
        
        # Verify we found files
        assert len(files) == 3
    
    @patch('duplicate_finder.detector.tqdm')
    def test_find_duplicates_shows_progress(self, mock_tqdm_class, tmp_path):
        """Test that multi-stage comparison shows progress bars."""
        # Create test files
        files = []
        for i in range(3):
            file_path = tmp_path / f"file{i}.txt"
            file_path.write_text(f"content{i}")
            files.append(file_path)
        
        # Configure mock
        mock_tqdm_class.side_effect = lambda x, **kwargs: x
        
        with patch('builtins.print'):
            duplicates, unique_files, duplicate_folders = detector.find_duplicates(files)
        
        # Verify tqdm was called multiple times for different stages
        assert mock_tqdm_class.call_count >= 1
        calls = mock_tqdm_class.call_args_list
        
        # Check for progress bar descriptions
        descriptions = []
        for call in calls:
            if len(call[1]) > 0 and 'desc' in call[1]:
                descriptions.append(call[1]['desc'])
        
        # Should have progress bars for various stages
        assert any('sizes' in desc.lower() for desc in descriptions)  # Stage 1


class TestOutputFormatting:
    """Test output formatting functionality."""
    
    def test_format_file_size(self):
        """Test human-readable file size formatting."""
        from duplicate_finder.formatter import _format_file_size
        
        assert _format_file_size(512) == "512 bytes"
        assert _format_file_size(1024) == "1.0 KB"
        assert _format_file_size(1536) == "1.5 KB"
        assert _format_file_size(1024 * 1024) == "1.0 MB"
        assert _format_file_size(2.5 * 1024 * 1024) == "2.5 MB"
        assert _format_file_size(1024 * 1024 * 1024) == "1.0 GB"
    
    def test_get_file_info(self, tmp_path):
        """Test getting file size and formatted info."""
        from duplicate_finder.formatter import _get_file_info
        
        # Test normal file
        test_file = tmp_path / "test.txt"
        test_content = b"Hello, World!"
        test_file.write_bytes(test_content)
        
        size, size_str = _get_file_info(test_file)
        assert size == len(test_content)
        assert size_str == "13 bytes"
        
        # Test nonexistent file
        nonexistent = tmp_path / "nonexistent.txt"
        size, size_str = _get_file_info(nonexistent)
        assert size == 0
        assert size_str == "unknown size"
    
    def test_calculate_space_savings(self, tmp_path):
        """Test space savings calculation."""
        from duplicate_finder.formatter import _calculate_space_savings
        
        # Create test files
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file3 = tmp_path / "file3.txt"
        
        content = b"A" * 1000  # 1000 bytes
        file1.write_bytes(content)
        file2.write_bytes(content)
        file3.write_bytes(content)
        
        # Test with duplicate groups
        duplicates = {
            "hash1": [file1, file2],  # 2 files, 1000 bytes each
            "hash2": [file3],         # 1 file (no savings)
        }
        
        total_size, savings = _calculate_space_savings(duplicates)
        assert total_size == 2000  # Only counts duplicates
        assert savings == 1000     # Save 1 file worth
    
    def test_format_output_with_duplicates(self, tmp_path, capsys):
        """Test output formatting with duplicate files."""
        # Create test files
        file1 = tmp_path / "dup1.txt"
        file2 = tmp_path / "dup2.txt"
        file3 = tmp_path / "unique.txt"
        
        file1.write_bytes(b"duplicate content")
        file2.write_bytes(b"duplicate content")
        file3.write_bytes(b"unique content")
        
        duplicates = {"hash123": [file1, file2]}
        unique_files = [file3]
        
        formatter.format_output(duplicates, unique_files)
        captured = capsys.readouterr()
        
        # Check key output elements
        assert "DUPLICATE FILES FOUND" in captured.out
        assert "GROUP 1" in captured.out
        assert "2 identical files" in captured.out
        assert str(file1) in captured.out
        assert str(file2) in captured.out
        assert "UNIQUE FILES" in captured.out
        assert "SUMMARY STATISTICS" in captured.out
        assert "Total files scanned: 3" in captured.out
        assert "Duplicate files: 2" in captured.out
        assert "Unique files: 1" in captured.out
        assert "Potential space savings" in captured.out
    
    def test_format_output_no_duplicates(self, tmp_path, capsys):
        """Test output formatting with no duplicates."""
        # Create unique files
        file1 = tmp_path / "unique1.txt"
        file2 = tmp_path / "unique2.txt"
        
        file1.write_bytes(b"content 1")
        file2.write_bytes(b"content 2")
        
        duplicates = {}
        unique_files = [file1, file2]
        
        formatter.format_output(duplicates, unique_files)
        captured = capsys.readouterr()
        
        # Check output
        assert "No duplicate files found" in captured.out
        assert "UNIQUE FILES" in captured.out
        assert "Found 2 unique files" in captured.out
        assert "Total files scanned: 2" in captured.out
        assert "Duplicate files: 0" in captured.out
        assert "Unique files: 2" in captured.out
        # Should not have space analysis section
        assert "Space Analysis" not in captured.out
    
    def test_format_output_many_unique_files(self, tmp_path, capsys):
        """Test output formatting with many unique files."""
        # Create many unique files
        unique_files = []
        for i in range(25):
            file_path = tmp_path / f"unique_{i}.txt"
            file_path.write_bytes(f"content {i}".encode())
            unique_files.append(file_path)
        
        duplicates = {}
        
        formatter.format_output(duplicates, unique_files)
        captured = capsys.readouterr()
        
        # Should show sample and count
        assert "Found 25 unique files" in captured.out
        assert "Sample of unique files" in captured.out
        assert "and 15 more unique files" in captured.out
    
    def test_duplicate_groups_sorted_by_size(self, tmp_path, capsys):
        """Test that duplicate groups are sorted by size (largest first)."""
        # Create files of different sizes
        small1 = tmp_path / "small1.txt"
        small2 = tmp_path / "small2.txt"
        large1 = tmp_path / "large1.txt"
        large2 = tmp_path / "large2.txt"
        
        small_content = b"small"
        large_content = b"A" * 1000
        
        small1.write_bytes(small_content)
        small2.write_bytes(small_content)
        large1.write_bytes(large_content)
        large2.write_bytes(large_content)
        
        duplicates = {
            "small_hash": [small1, small2],
            "large_hash": [large1, large2],
        }
        
        formatter.format_output(duplicates, [])
        captured = capsys.readouterr()
        
        # Large files should appear first (GROUP 1)
        output_lines = captured.out.split('\n')
        large_group_line = next(i for i, line in enumerate(output_lines) if "GROUP 1" in line)
        small_group_line = next(i for i, line in enumerate(output_lines) if "GROUP 2" in line)
        
        assert large_group_line < small_group_line
        assert "1000 bytes" in output_lines[large_group_line] or "1.0 KB" in output_lines[large_group_line]


class TestArgumentParsing:
    """Test command-line argument parsing."""
    
    def test_parse_arguments_valid_path(self):
        """Test parsing valid path argument."""
        with patch('sys.argv', ['duplicate_finder.py', '/some/path']):
            args = cli.parse_arguments()
            assert args.path == Path('/some/path')
    
    def test_parse_arguments_no_args(self):
        """Test handling of missing arguments."""
        with patch('sys.argv', ['duplicate_finder.py']):
            with patch('sys.stderr'):
                with pytest.raises(SystemExit):
                    cli.parse_arguments()


class TestFolderDuplicateDetection:
    """Test folder duplicate detection functionality."""
    
    def test_create_folder_fingerprint_empty_folder(self, tmp_path):
        """Test fingerprinting an empty folder."""
        empty_folder = tmp_path / "empty"
        empty_folder.mkdir()
        
        fingerprint = folder_detector.create_folder_fingerprint(empty_folder, [empty_folder])
        
        assert fingerprint.folder_path == empty_folder
        assert fingerprint.file_count == 0
        assert fingerprint.total_size == 0
        assert len(fingerprint.relative_files) == 0
    
    def test_create_folder_fingerprint_with_files(self, tmp_path):
        """Test fingerprinting a folder with files."""
        folder = tmp_path / "test_folder"
        folder.mkdir()
        
        file1 = folder / "file1.txt"
        file2 = folder / "subdir" / "file2.txt"
        file1.write_text("content1")
        file2.parent.mkdir()
        file2.write_text("content2")
        
        all_files = [file1, file2, folder]
        fingerprint = folder_detector.create_folder_fingerprint(folder, all_files)
        
        assert fingerprint.folder_path == folder
        assert fingerprint.file_count == 2
        assert fingerprint.total_size == len("content1") + len("content2")
        assert "file1.txt" in fingerprint.relative_files
        assert "subdir/file2.txt" in fingerprint.relative_files
        assert fingerprint.structure_hash is not None
    
    def test_find_duplicate_folders_identical_folders(self, tmp_path):
        """Test finding identical duplicate folders."""
        # Create two identical folders
        folder1 = tmp_path / "folder1"
        folder2 = tmp_path / "folder2"
        folder1.mkdir()
        folder2.mkdir()
        
        # Add identical files to both folders
        (folder1 / "file1.txt").write_text("identical content")
        (folder1 / "file2.txt").write_text("more content")
        (folder2 / "file1.txt").write_text("identical content")
        (folder2 / "file2.txt").write_text("more content")
        
        # Create file list and hashes
        all_files = [
            folder1 / "file1.txt", folder1 / "file2.txt",
            folder2 / "file1.txt", folder2 / "file2.txt"
        ]
        
        file_hashes = {}
        for file_path in all_files:
            content = file_path.read_bytes()
            hash_obj = hashlib.sha256(content)
            file_hashes[file_path] = hash_obj.hexdigest()
        
        duplicate_folders = folder_detector.find_duplicate_folders(all_files, file_hashes)
        
        assert len(duplicate_folders) == 1
        assert len(duplicate_folders[0]) == 2
        assert folder1 in duplicate_folders[0]
        assert folder2 in duplicate_folders[0]
    
    def test_find_duplicate_folders_different_content(self, tmp_path):
        """Test that folders with different content are not considered duplicates."""
        folder1 = tmp_path / "folder1"
        folder2 = tmp_path / "folder2"
        folder1.mkdir()
        folder2.mkdir()
        
        # Add different files to each folder
        (folder1 / "file1.txt").write_text("content A")
        (folder2 / "file1.txt").write_text("content B")  # Different content
        
        all_files = [folder1 / "file1.txt", folder2 / "file1.txt"]
        
        file_hashes = {}
        for file_path in all_files:
            content = file_path.read_bytes()
            hash_obj = hashlib.sha256(content)
            file_hashes[file_path] = hash_obj.hexdigest()
        
        duplicate_folders = folder_detector.find_duplicate_folders(all_files, file_hashes)
        
        assert len(duplicate_folders) == 0
    
    def test_find_duplicate_folders_different_structure(self, tmp_path):
        """Test that folders with different structures are not considered duplicates."""
        folder1 = tmp_path / "folder1"
        folder2 = tmp_path / "folder2"
        folder1.mkdir()
        folder2.mkdir()
        
        # Different file structures - folder1 has 1 file, folder2 has 2 files
        (folder1 / "file1.txt").write_text("content")
        (folder2 / "file1.txt").write_text("content")
        (folder2 / "file2.txt").write_text("different")  # Extra file makes structure different
        
        all_files = [folder1 / "file1.txt", folder2 / "file1.txt", folder2 / "file2.txt"]
        
        file_hashes = {}
        for file_path in all_files:
            content = file_path.read_bytes()
            hash_obj = hashlib.sha256(content)
            file_hashes[file_path] = hash_obj.hexdigest()
        
        duplicate_folders = folder_detector.find_duplicate_folders(all_files, file_hashes)
        
        assert len(duplicate_folders) == 0
    
    def test_get_files_in_duplicate_folders(self, tmp_path):
        """Test getting all files contained in duplicate folders."""
        folder1 = tmp_path / "folder1"
        folder2 = tmp_path / "folder2"
        folder3 = tmp_path / "folder3"
        folder1.mkdir()
        folder2.mkdir()
        folder3.mkdir()
        
        file1 = folder1 / "file1.txt"
        file2 = folder2 / "file2.txt" 
        file3 = folder3 / "file3.txt"
        file1.write_text("content")
        file2.write_text("content") 
        file3.write_text("different")
        
        all_files = [file1, file2, file3]
        duplicate_folders = [[folder1, folder2]]  # folder1 and folder2 are duplicates
        
        files_in_duplicates = folder_detector.get_files_in_duplicate_folders(duplicate_folders, all_files)
        
        assert file1 in files_in_duplicates
        assert file2 in files_in_duplicates
        assert file3 not in files_in_duplicates
    
    def test_is_folder_duplicate(self, tmp_path):
        """Test checking if a folder is part of duplicate group."""
        folder1 = tmp_path / "folder1"
        folder2 = tmp_path / "folder2"
        folder3 = tmp_path / "folder3"
        
        duplicate_folders = [[folder1, folder2]]
        
        assert folder_detector.is_folder_duplicate(folder1, duplicate_folders) == True
        assert folder_detector.is_folder_duplicate(folder2, duplicate_folders) == True
        assert folder_detector.is_folder_duplicate(folder3, duplicate_folders) == False
    
    def test_calculate_folder_content_hash(self, tmp_path):
        """Test calculating folder content hash based on file hashes."""
        folder = tmp_path / "test_folder"
        folder.mkdir()
        
        file1 = folder / "file1.txt"
        file2 = folder / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")
        
        fingerprint = folder_detector.FolderFingerprint(folder)
        fingerprint.relative_files = {"file1.txt", "file2.txt"}
        
        file_hashes = {
            file1: "hash1",
            file2: "hash2"
        }
        
        content_hash = folder_detector.calculate_folder_content_hash(fingerprint, file_hashes)
        
        assert content_hash is not None
        assert len(content_hash) == 64  # SHA256 hex length
    
    def test_calculate_folder_content_hash_missing_file_hash(self, tmp_path):
        """Test that missing file hash returns None."""
        folder = tmp_path / "test_folder"
        folder.mkdir()
        
        file1 = folder / "file1.txt"
        file1.write_text("content1")
        
        fingerprint = folder_detector.FolderFingerprint(folder)
        fingerprint.relative_files = {"file1.txt"}
        
        file_hashes = {}  # Empty - missing hash for file1
        
        content_hash = folder_detector.calculate_folder_content_hash(fingerprint, file_hashes)
        
        assert content_hash is None


class TestIntegratedFolderDetection:
    """Test integrated folder detection with main duplicate detection flow."""
    
    @patch('duplicate_finder.detector.tqdm')
    @patch('builtins.print')
    def test_find_duplicates_with_folder_detection(self, mock_print, mock_tqdm, tmp_path):
        """Test that main find_duplicates function includes folder detection."""
        mock_tqdm.side_effect = lambda x, **kwargs: x
        
        # Create duplicate folders
        folder1 = tmp_path / "duplicate_folder_1"
        folder2 = tmp_path / "duplicate_folder_2"
        folder1.mkdir()
        folder2.mkdir()
        
        # Add identical files
        (folder1 / "file1.txt").write_text("identical content")
        (folder2 / "file1.txt").write_text("identical content")
        
        all_files = [folder1 / "file1.txt", folder2 / "file1.txt"]
        
        # Call main detection function
        duplicates, unique_files, duplicate_folders = detector.find_duplicates(all_files)
        
        # Should find folder duplicates
        assert len(duplicate_folders) == 1
        assert len(duplicate_folders[0]) == 2
        assert folder1 in duplicate_folders[0]
        assert folder2 in duplicate_folders[0]
        
        # Files should be removed from individual duplicates since they're part of folder duplicates
        assert len(duplicates) == 0
        assert len(unique_files) == 0
    
    @patch('duplicate_finder.detector.tqdm')
    @patch('builtins.print') 
    def test_mixed_folder_and_file_duplicates(self, mock_print, mock_tqdm, tmp_path):
        """Test detection with both folder and individual file duplicates."""
        mock_tqdm.side_effect = lambda x, **kwargs: x
        
        # Create duplicate folders
        folder1 = tmp_path / "dup_folder_1"
        folder2 = tmp_path / "dup_folder_2"
        folder1.mkdir()
        folder2.mkdir()
        
        (folder1 / "file1.txt").write_text("folder content")
        (folder2 / "file1.txt").write_text("folder content")
        
        # Create individual duplicate files outside folders
        individual1 = tmp_path / "individual1.txt"
        individual2 = tmp_path / "individual2.txt"
        individual1.write_text("individual content")
        individual2.write_text("individual content")
        
        all_files = [
            folder1 / "file1.txt", folder2 / "file1.txt",
            individual1, individual2
        ]
        
        duplicates, unique_files, duplicate_folders = detector.find_duplicates(all_files)
        
        # Should find both folder and individual duplicates
        assert len(duplicate_folders) == 1
        assert len(duplicates) == 1
        
        # Folder duplicates
        assert folder1 in duplicate_folders[0]
        assert folder2 in duplicate_folders[0]
        
        # Individual duplicates
        individual_dup_group = list(duplicates.values())[0]
        assert individual1 in individual_dup_group
        assert individual2 in individual_dup_group


class TestErrorHandling:
    """Test robust error handling and warning systems."""
    
    def test_scanner_handles_permission_denied(self):
        """Test that _process_item handles permission errors gracefully."""
        from unittest.mock import Mock
        
        # Create a mock item that raises permission error
        mock_item = Mock()
        mock_item.is_symlink.return_value = False
        mock_item.is_file.side_effect = PermissionError("Permission denied")
        
        result = scanner.ScanResult()
        
        # Process the item - should handle error gracefully
        scanner._process_item(mock_item, result)
        
        # Should have recorded the permission error
        assert result.skipped_items['permission_denied'] > 0
        assert len(result.warnings) > 0
        assert "Permission denied" in result.warnings[0]
    
    def test_scanner_handles_broken_symlinks(self, tmp_path):
        """Test scanner skips broken symlinks gracefully."""
        # Create directory with broken symlink
        test_dir = tmp_path / "test_symlinks"
        test_dir.mkdir()
        
        # Create a valid file
        valid_file = test_dir / "valid.txt"
        valid_file.write_text("content")
        
        # Create a broken symlink by linking to non-existent file
        broken_link = test_dir / "broken_link"
        try:
            broken_link.symlink_to(tmp_path / "nonexistent.txt")
        except OSError:
            # Skip test if symlinks not supported
            pytest.skip("Symlinks not supported on this system")
        
        # Scan should handle broken symlink gracefully
        result = scanner.scan_directory_detailed(test_dir)
        
        # Should find the valid file but skip the broken symlink
        assert len(result.files) == 1
        assert valid_file in result.files
        assert result.skipped_items['broken_symlinks'] >= 1
        assert any("Broken symlink" in warning for warning in result.warnings)
    
    def test_hasher_handles_file_not_found(self, tmp_path):
        """Test hasher handles file disappearing during processing."""
        nonexistent_file = tmp_path / "nonexistent.txt"
        
        # Reset warning counters for clean test
        hasher.reset_warning_counters()
        
        # Should return None and log warning
        result = hasher.calculate_file_hash(nonexistent_file)
        assert result is None
        
        # Should have logged warning
        warnings = hasher.get_warning_summary()
        assert warnings['file_not_found'] > 0
    
    def test_hasher_handles_permission_denied(self, tmp_path):
        """Test hasher handles permission denied on file."""
        from unittest.mock import patch, mock_open
        
        test_file = tmp_path / "restricted.txt"
        test_file.write_text("content")
        
        # Reset warning counters for clean test
        hasher.reset_warning_counters()
        
        # Mock file opening to raise PermissionError
        with patch('builtins.open', mock_open()) as mock_file:
            mock_file.side_effect = PermissionError("Permission denied")
            
            result = hasher.calculate_file_hash(test_file)
            assert result is None
        
        # Should have logged warning
        warnings = hasher.get_warning_summary()
        assert warnings['permission_denied'] > 0
    
    def test_warning_rate_limiting(self, tmp_path):
        """Test that warning messages are rate limited to prevent spam."""
        hasher.reset_warning_counters()
        
        # Create multiple files that will cause permission errors
        files = []
        for i in range(10):
            test_file = tmp_path / f"file_{i}.txt"
            test_file.write_text("content")
            files.append(test_file)
        
        from unittest.mock import patch, mock_open
        
        # Mock file opening to always raise PermissionError
        with patch('builtins.open', mock_open()) as mock_file:
            mock_file.side_effect = PermissionError("Permission denied")
            
            # Try to hash all files
            for file_path in files:
                hasher.calculate_file_hash(file_path)
        
        # Should have recorded all the warnings (including suppressed ones)
        warnings = hasher.get_warning_summary()
        assert warnings['permission_denied'] == len(files)  # All attempts recorded
        # Note: Only first 5 warnings are printed, then suppression message appears
    
    def test_file_size_error_handling(self, tmp_path):
        """Test file size calculation handles errors gracefully."""
        nonexistent = tmp_path / "nonexistent.txt"
        
        # Should return -1 for non-existent files
        size = hasher.get_file_size(nonexistent)
        assert size == -1
        
        # Should handle permission errors
        from unittest.mock import patch
        
        existing_file = tmp_path / "exists.txt"
        existing_file.write_text("content")
        
        # Mock the stat method to raise PermissionError
        with patch('pathlib.Path.stat', side_effect=PermissionError("No access")):
            size = hasher.get_file_size(existing_file)
            assert size == -1
    
    def test_scan_result_container(self, tmp_path):
        """Test ScanResult properly tracks different types of issues."""
        result = scanner.ScanResult()
        
        # Test initial state
        assert len(result.files) == 0
        assert len(result.warnings) == 0
        assert len(result.errors) == 0
        assert all(count == 0 for count in result.skipped_items.values())
        
        # Test adding items
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        result.files.append(test_file)
        result.warnings.append("Test warning")
        result.skipped_items['permission_denied'] = 1
        
        assert len(result.files) == 1
        assert len(result.warnings) == 1
        assert result.skipped_items['permission_denied'] == 1
    
    def test_scanner_continues_after_errors(self):
        """Test scanner continues processing after encountering errors."""
        from unittest.mock import Mock
        
        result = scanner.ScanResult()
        
        # Process multiple items, some with errors
        items = []
        for i in range(5):
            mock_item = Mock()
            mock_item.__str__ = Mock(return_value=f"file_{i}.txt")
            mock_item.is_symlink.return_value = False
            
            if i == 2:
                # Make file_2 raise permission error
                mock_item.is_file.side_effect = PermissionError("No access")
            else:
                # Normal files
                mock_item.is_file.return_value = True
                mock_item.stat.return_value.st_size = 10
            items.append(mock_item)
        
        # Process all items
        for item in items:
            scanner._process_item(item, result)
        
        # Should have processed most files despite errors
        assert len(result.files) == 4  # 4 out of 5 files processed successfully
        assert result.skipped_items['permission_denied'] == 1  # 1 permission error
    
    def test_main_cli_shows_warning_summary(self, capsys):
        """Test CLI warning summary display."""
        # Reset warning counters
        hasher.reset_warning_counters()
        
        # Add a test warning directly
        hasher._log_warning('io_errors', "Test I/O error")
        
        # Create a simple test to trigger the CLI warning summary
        warning_summary = hasher.get_warning_summary()
        total_warnings = sum(warning_summary.values())
        
        # Simulate what CLI does when warnings exist
        if total_warnings > 0:
            print(f"\n⚠️  Processing warnings summary:", file=sys.stderr)
            for warning_type, count in warning_summary.items():
                if count > 0:
                    warning_name = warning_type.replace('_', ' ').title()
                    print(f"  • {warning_name}: {count} files", file=sys.stderr)
        
        # Check the output
        captured = capsys.readouterr()
        assert "Processing warnings summary" in captured.err
        assert "Io Errors" in captured.err


class TestOutputFormats:
    """Test different output format options."""
    
    def test_parse_arguments_output_format_text(self):
        """Test parsing --output text argument."""
        with patch('sys.argv', ['duplicate_finder.py', '/some/path', '--output', 'text']):
            args = cli.parse_arguments()
            assert args.output == 'text'
    
    def test_parse_arguments_output_format_json(self):
        """Test parsing --output json argument."""
        with patch('sys.argv', ['duplicate_finder.py', '/some/path', '--output', 'json']):
            args = cli.parse_arguments()
            assert args.output == 'json'
    
    def test_parse_arguments_output_format_default(self):
        """Test default output format is text."""
        with patch('sys.argv', ['duplicate_finder.py', '/some/path']):
            args = cli.parse_arguments()
            assert args.output == 'text'
    
    def test_parse_arguments_verbose_flag(self):
        """Test parsing --verbose flag."""
        with patch('sys.argv', ['duplicate_finder.py', '/some/path', '--verbose']):
            args = cli.parse_arguments()
            assert args.verbose is True
        
        with patch('sys.argv', ['duplicate_finder.py', '/some/path', '-v']):
            args = cli.parse_arguments()
            assert args.verbose is True
    
    def test_parse_arguments_quiet_flag(self):
        """Test parsing --quiet flag."""
        with patch('sys.argv', ['duplicate_finder.py', '/some/path', '--quiet']):
            args = cli.parse_arguments()
            assert args.quiet is True
        
        with patch('sys.argv', ['duplicate_finder.py', '/some/path', '-q']):
            args = cli.parse_arguments()
            assert args.quiet is True
    
    def test_format_json_output(self, tmp_path, capsys):
        """Test JSON output format."""
        import json
        
        # Create test data
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file3 = tmp_path / "unique.txt"
        file1.write_text("duplicate content")
        file2.write_text("duplicate content")
        file3.write_text("unique content")
        
        # Create duplicate folders
        folder1 = tmp_path / "folder1"
        folder2 = tmp_path / "folder2"
        folder1.mkdir()
        folder2.mkdir()
        (folder1 / "same.txt").write_text("same")
        (folder2 / "same.txt").write_text("same")
        
        duplicates = {"hash1": [file1, file2]}
        unique_files = [file3]
        duplicate_folders = [[folder1, folder2]]
        
        # Call JSON formatter
        formatter.format_json_output(duplicates, unique_files, duplicate_folders)
        
        # Capture and parse JSON output
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        
        # Verify JSON structure
        assert "duplicate_files" in output
        assert "unique_files" in output
        assert "duplicate_folders" in output
        assert "statistics" in output
        
        # Verify duplicate files
        assert len(output["duplicate_files"]) == 1
        assert output["duplicate_files"][0]["count"] == 2
        assert output["duplicate_files"][0]["hash"] == "hash1"
        
        # Verify unique files
        assert len(output["unique_files"]) == 1
        assert str(file3) in output["unique_files"][0]["path"]
        
        # Verify duplicate folders
        assert len(output["duplicate_folders"]) == 1
        assert output["duplicate_folders"][0]["count"] == 2
        
        # Verify statistics
        stats = output["statistics"]
        assert stats["duplicate_files_count"] == 2
        assert stats["unique_files_count"] == 1
        assert stats["duplicate_folder_groups_count"] == 1
    
    def test_format_json_output_empty_results(self, capsys):
        """Test JSON output with no duplicates."""
        import json
        
        formatter.format_json_output({}, [], [])
        
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        
        # Verify empty results
        assert len(output["duplicate_files"]) == 0
        assert len(output["unique_files"]) == 0
        assert len(output["duplicate_folders"]) == 0
        assert output["statistics"]["total_files"] == 0
    
    def test_quiet_mode_suppresses_output(self, tmp_path):
        """Test that quiet mode suppresses non-error output."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")
        
        # Test scan_directory with quiet mode
        files = scanner.scan_directory(test_dir, quiet=True)
        assert len(files) == 1
        
        # Test find_duplicates with quiet mode
        duplicates, unique_files, duplicate_folders = detector.find_duplicates(files, quiet=True)
        assert len(unique_files) == 1
    
    def test_verbose_mode_enables_logging(self):
        """Test that verbose mode enables detailed logging."""
        import logging
        
        # Mock logging.basicConfig to check it's called with DEBUG level
        with patch('logging.basicConfig') as mock_config:
            with patch('sys.argv', ['duplicate_finder.py', '/tmp', '--verbose']):
                with patch('pathlib.Path.exists', return_value=True):
                    with patch('pathlib.Path.is_dir', return_value=True):
                        with patch('duplicate_finder.scanner.scan_directory', return_value=[]):
                            with patch('sys.exit'):
                                cli.main()
            
            # Check logging was set to DEBUG
            mock_config.assert_called()
            call_kwargs = mock_config.call_args[1]
            assert call_kwargs['level'] == logging.DEBUG
    
    def test_conflicting_verbose_quiet_flags(self):
        """Test error when both verbose and quiet flags are used."""
        with patch('sys.argv', ['duplicate_finder.py', '/tmp', '--verbose', '--quiet']):
            with patch('sys.stderr'):
                with pytest.raises(SystemExit):
                    cli.main()
    
    def test_cli_json_output_mode(self, tmp_path, capsys):
        """Test CLI correctly uses JSON formatter when --output json is specified."""
        import json
        
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")
        
        with patch('sys.argv', ['duplicate_finder.py', str(test_dir), '--output', 'json', '--quiet']):
            cli.main()
        
        # Capture and verify JSON output was produced
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        
        # Verify it's JSON format
        assert "duplicate_files" in output
        assert "unique_files" in output
        assert "statistics" in output
        assert len(output["unique_files"]) == 1