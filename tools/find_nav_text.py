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

offset = 12
count = struct.unpack('<H', data[4:6])[0]
offset += count * 12

dir_name_buf_len = struct.unpack('<I', data[offset:offset+4])[0]
offset += 4
dir_name_buf = data[offset:offset+dir_name_buf_len]
offset += dir_name_buf_len

file_name_buf_len = struct.unpack('<I', data[offset:offset+4])[0]
offset += 4
file_name_buf = data[offset:offset+file_name_buf_len]
offset += file_name_buf_len

dir_count = struct.unpack('<I', data[offset:offset+4])[0]
offset += 4
directories = []
for i in range(dir_count):
    name_checksum, name_offset, file_start, file_count = struct.unpack('<IIII', data[offset:offset+16])
    directories.append((name_checksum, name_offset, file_start, file_count))
    offset += 16

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

# Look for navigator/ui text files
text_extensions = ['.xml', '.css', '.html', '.js', '.json']
nav_files = []
for f in files:
    path_lower = f['path'].lower()
    if any(path_lower.endswith(ext) for ext in text_extensions):
        if any(kw in path_lower for kw in ['navigator', 'map', 'world', 'minimap', 'ui', 'guide', 'playguide', 'commonimage']):
            nav_files.append(f)

print(f'Found {len(nav_files)} navigator/ui text files')
for f in nav_files[:30]:
    chunk_id = f['chunk_id']
    path = f['path']
    flags = f['flags']
    comp = f['compressed_size']
    uncomp = f['uncompressed_size']
    print(f'  [{chunk_id}] {path} (flags={flags:#04x}, comp={comp}->{uncomp})')
