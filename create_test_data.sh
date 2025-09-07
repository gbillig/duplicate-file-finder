#!/bin/bash
# Create various test files for testing duplicate finder

# Create some unique files of different sizes
echo "Small unique file" > test_data/small_unique.txt
echo "This is a medium sized unique file with more content than the small one" > test_data/medium_unique.txt
printf "Large unique file\n%.0s" {1..1000} > test_data/large_unique.txt

# Create duplicate files (same content, different names)
echo "This is duplicate content" > test_data/dup1.txt
echo "This is duplicate content" > test_data/dup2.txt
echo "This is duplicate content" > test_data/subdir/dup3.txt

# Create files with same size but different content (to test partial hashing)
echo "Content A - exactly 20b" > test_data/same_size_1.txt
echo "Content B - exactly 20b" > test_data/same_size_2.txt

# Create large duplicate files (to test that partial hash catches them early)
dd if=/dev/urandom bs=1M count=2 of=test_data/large_dup1.bin 2>/dev/null
cp test_data/large_dup1.bin test_data/subdir/large_dup2.bin

# Create files with same beginning but different endings (to test partial vs full hash)
echo "Same beginning but different ending A" > test_data/partial_match_1.txt
echo "Same beginning but different ending B" > test_data/partial_match_2.txt

# Create more varied content
for i in {1..5}; do
    echo "Unique content file $i with random data: $RANDOM" > test_data/unique_$i.txt
done

# Create nested duplicates
echo "Nested duplicate" > test_data/subdir/nested/nested_dup1.txt
echo "Nested duplicate" > test_data/subdir/nested/nested_dup2.txt

echo "Test data created successfully!"
echo "Summary:"
echo "  - $(find test_data -type f | wc -l) total files"
echo "  - Multiple duplicate groups"
echo "  - Files of various sizes"
echo "  - Files with same size but different content"
