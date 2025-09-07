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

from duplicate_finder import cli, hasher, scanner, detector, formatter
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
        duplicates, unique_files = detector.find_duplicates(files)
        
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
        duplicates, unique_files = detector.find_duplicates(files)
        
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
        duplicates, unique_files = detector.find_duplicates(files)
        
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
        duplicates, unique_files = detector.find_duplicates(files)
        
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
        duplicates, unique_files = detector.find_duplicates(files)
        
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
        duplicates, unique_files = detector.find_duplicates(files)
        
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
        duplicates, unique_files = detector.find_duplicates(files)
        
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
            duplicates, unique_files = detector.find_duplicates(files)
        
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