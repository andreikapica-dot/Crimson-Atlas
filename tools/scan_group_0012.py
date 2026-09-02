import struct
from pathlib import Path

def read_trie_string(data, offset):
    if offset == -1:
        return ''
    next_offset = int.from_bytes(data[offset:offset+4], 'little', signed=True)
    string_length = data[offset+4]
    return data[offset+5:offset+5+string_length].decode('utf-8', errors='replace')

pamt_path = Path(r'G:\Steam\steamapps\common\Crimson Desert\0012\0.pamt')
with open(pamt_path, 'rb') as f:
    data = f.read()

print(f'Total PAMT size: {len(data)} bytes')

# Parse header
checksum = struct.unpack('<I', data[0:4])[0]
count = struct.unpack('<H', data[4:6])[0]
unknown0 = struct.unpack('<H', data[6:8])[0]
print(f'Header: checksum={checksum:#010x}, count={count}, unknown0={unknown0}')

# Parse chunks
offset = 12
chunks = []
for i in range(count):
    chunk_id, chunk_checksum, chunk_size = struct.unpack('<III', data[offset:offset+12])
    chunks.append((chunk_id, chunk_checksum, chunk_size))
    offset += 12

# Parse directory name buffer
dir_name_buf_len = struct.unpack('<I', data[offset:offset+4])[0]
offset += 4
dir_name_buf = data[offset:offset+dir_name_buf_len]
offset += dir_name_buf_len

# File name buffer
file_name_buf_len = struct.unpack('<I', data[offset:offset+4])[0]
offset += 4
file_name_buf = data[offset:offset+file_name_buf_len]
offset += file_name_buf_len

# Directories
dir_count = struct.unpack('<I', data[offset:offset+4])[0]
offset += 4
directories = []
for i in range(dir_count):
    name_checksum, name_offset, file_start, file_count = struct.unpack('<IIII', data[offset:offset+16])
    directories.append((name_checksum, name_offset, file_start, file_count))
    offset += 16

# Files
file_count = struct.unpack('<I', data[offset:offset+4])[0]
offset += 4
files = []
for i in range(file_count):
    name_offset, chunk_offset, comp_size, uncomp_size, chunk_id, flags, unknown0 = struct.unpack('<IIIIHBB', data[offset:offset+20])
    compression = flags & 0xF
    crypto = flags >> 4
    is_partial = (compression == 1)
    files.append({
        'name_offset': name_offset,
        'chunk_offset': chunk_offset,
        'compressed_size': comp_size,
        'uncompressed_size': uncomp_size,
        'chunk_id': chunk_id,
        'flags': flags,
        'compression': compression,
        'crypto': crypto,
        'is_partial': is_partial,
        'unknown0': unknown0,
    })
    offset += 20

# Reconstruct file paths
print(f'Total: {len(files)} files, {len(directories)} directories')
print()

# Map directories
dir_map = {}
for dc in directories:
    nc, no, fs, fc = dc
    name = read_trie_string(dir_name_buf, no)
    dir_map[no] = name

# Print all files with their paths
for i, f in enumerate(files):
    dir_name = ''
    for dc in directories:
        nc, no, fs, fc = dc
        if fs <= i < fs + fc:
            dir_name = read_trie_string(dir_name_buf, no)
            break
    name = read_trie_string(file_name_buf, f['name_offset'])
    full_path = (dir_name + '/' + name) if dir_name else name
    f['path'] = full_path
    f['directory'] = dir_name

# Search for map-related files
keywords = ['map', 'world', 'global', 'navigator', 'minimap', 'region', 'terrain', 'abyss', 'background', 'texture', 'tile']
map_files = []
for f in files:
    path_lower = f['path'].lower()
    if any(kw in path_lower for kw in keywords):
        map_files.append(f)

print(f'Found {len(map_files)} map-related files')
print()

# Sort by relevance
def relevance(f):
    path = f['path'].lower()
    score = 0
    if 'navigator' in path:
        score += 10
    if 'map' in path:
        score += 8
    if 'world' in path:
        score += 8
    if 'minimap' in path:
        score += 8
    if 'terrain' in path:
        score += 8
    if 'background' in path:
        score += 5
    if 'texture' in path:
        score += 3
    if 'tile' in path:
        score += 5
    if 'region' in path:
        score += 4
    if 'abyss' in path:
        score += 6
    if 'global' in path:
        score += 4
    if 'icon' in path:
        score -= 10
    if 'object' in path:
        score -= 10
    if 'character' in path:
        score -= 10
    if 'npc' in path:
        score -= 10
    if 'normal' in path:
        score -= 5
    if 'specular' in path:
        score -= 5
    return score

map_files.sort(key=relevance, reverse=True)

print('Top 50 likely map-base candidates:')
print('=' * 100)
for i, f in enumerate(map_files[:50]):
    comp = f['compression']
    crypto = f['crypto']
    comp_str = {0: 'NONE', 1: 'PARTIAL', 2: 'LZ4', 3: 'ZLIB', 4: 'QUICKLZ'}.get(comp, 'UNKNOWN')
    crypto_str = {0: 'NONE', 1: 'ICE', 2: 'AES', 3: 'CHACHA20'}.get(crypto, 'UNKNOWN')
    idx = i + 1
    path = f['path']
    chunk_id = f['chunk_id']
    chunk_offset = f['chunk_offset']
    comp_size = f['compressed_size']
    uncomp_size = f['uncompressed_size']
    flags = f['flags']
    print(f'{idx:3d}. [{chunk_id}] {path}')
    print(f'     chunk_offset={chunk_offset:#x}, comp={comp_size}->{uncomp_size}, flags={flags:#04x} ({comp_str}, {crypto_str})')
