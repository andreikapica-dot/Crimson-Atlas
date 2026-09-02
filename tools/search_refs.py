from pathlib import Path

output_dir = Path('output')

# Search all extracted files for map references
keywords = ['.dds', 'textureid', 'world', 'map', 'minimap', 'navigator', 'abyss', 'pywel', 'terrain', 'tile', 'region', 'background']
references = []

for file_path in output_dir.rglob('*'):
    if file_path.is_file():
        try:
            text = file_path.read_text('utf-8', errors='replace')
        except:
            continue
        
        lines = text.split('\n')
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            if any(kw in line_lower for kw in keywords):
                references.append({
                    'file': str(file_path.relative_to(output_dir)),
                    'line': line_num,
                    'content': line.strip(),
                    'keywords': [kw for kw in keywords if kw in line_lower]
                })

print(f'Found {len(references)} references')
print()
print('Top 50 references:')
for i, ref in enumerate(references[:50]):
    idx = i + 1
    file = ref['file']
    line = ref['line']
    content = ref['content'][:100]
    kws = ref['keywords']
    print(f'{idx:3d}. {file}:{line}')
    print(f'     {content}')
    print(f'     Keywords: {kws}')
