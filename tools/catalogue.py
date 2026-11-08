"""Validate untrusted metadata without downloading or executing a package."""
import argparse
import base64
import hashlib
import json
import re
import struct
from datetime import datetime
from pathlib import Path

MAX_BYTES = 8 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bdecode(data):
    position = 0
    info_bytes = None

    def parse(depth=0):
        nonlocal position, info_bytes
        require(depth < 40 and position < len(data), 'Invalid torrent nesting')
        marker = data[position:position + 1]
        if marker == b'i':
            end = data.index(b'e', position)
            number = data[position + 1:end]
            require(re.fullmatch(rb'(0|-?[1-9][0-9]*)', number), 'Invalid torrent integer')
            position = end + 1
            return int(number)
        if marker in (b'l', b'd'):
            position += 1
            result = [] if marker == b'l' else {}
            previous = None
            while position < len(data) and data[position:position + 1] != b'e':
                key = parse(depth + 1)
                if marker == b'l':
                    result.append(key)
                else:
                    require(isinstance(key, bytes) and (previous is None or key > previous), 'Invalid torrent dictionary')
                    previous = key
                    start = position
                    result[key] = parse(depth + 1)
                    if depth == 0 and key == b'info':
                        info_bytes = data[start:position]
            require(position < len(data), 'Incomplete torrent')
            position += 1
            return result
        colon = data.index(b':', position)
        length_text = data[position:colon]
        require(re.fullmatch(rb'(0|[1-9][0-9]*)', length_text), 'Invalid torrent string')
        length = int(length_text)
        start = colon + 1
        position = start + length
        require(position <= len(data), 'Incomplete torrent string')
        return data[start:position]

    result = parse()
    require(position == len(data) and isinstance(result, dict) and info_bytes, 'Invalid torrent metadata')
    return result, info_bytes


def segment(value):
    require(isinstance(value, str) and value and len(value) <= 200, 'Invalid folder name')
    require(not value.startswith('.') and not value.endswith((' ', '.')), 'Invalid folder name')
    require(not any(ord(c) < 32 or c in '<>:"/\\|?*' for c in value), 'Unsafe folder name')
    require(value.split('.')[0].upper() not in {'CON', 'PRN', 'AUX', 'NUL', *('COM' + str(i) for i in range(10)), *('LPT' + str(i) for i in range(10))}, 'Reserved folder name')


def validate(project):
    require(isinstance(project, dict), 'Invalid project')
    # Do not forward unknown fields that might expose machine-specific paths.
    allowed = {'PackageVersion', 'VersionDisplay', 'PackageKind', 'Id', 'Name', 'FolderName', 'PackageName', 'PackageBytes', 'UnpackedBytes', 'FileCount', 'Sha256', 'ContentSha256', 'InfoHash', 'TorrentBase64', 'IconBase64', 'CreatedUtc', 'SizeDisplay', 'SnapshotDisplay', 'CreatedDisplay'}
    require(set(project) <= allowed, 'Unknown project fields')
    version = project.get('PackageVersion', '')
    require(isinstance(version, str) and len(version) <= 128 and not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in version), 'Invalid package version')
    require(project.get('PackageKind') in ('Source', 'Game'), 'Invalid package type')
    require(re.fullmatch('[0-9a-fA-F]{32}', project.get('Id', '')), 'Invalid ID')
    name = project.get('Name')
    require(isinstance(name, str) and name.strip() and len(name) <= 200, 'Invalid name')
    if 'CreatedUtc' in project:
        require(isinstance(project['CreatedUtc'], str), 'Invalid creation timestamp')
        datetime.fromisoformat(project['CreatedUtc'].replace('Z', '+00:00'))
    segment(project.get('FolderName'))
    require(project.get('PackageName') == project['Id'] + '.zip', 'Invalid package name')
    for key, minimum, maximum in [('PackageBytes', 1, 101 * 1024**3), ('UnpackedBytes', 0, 100 * 1024**3), ('FileCount', 1, 100000)]:
        require(type(project.get(key)) is int and minimum <= project[key] <= maximum, 'Invalid ' + key)
    require(re.fullmatch('[0-9a-fA-F]{64}', project.get('Sha256', '')), 'Invalid SHA256')
    require(re.fullmatch('[0-9a-fA-F]{40}', project.get('InfoHash', '')), 'Invalid info hash')
    if project.get('ContentSha256'):
        require(re.fullmatch('[0-9a-fA-F]{64}', project['ContentSha256']), 'Invalid content hash')
    icon = project.get('IconBase64', '')
    require(isinstance(icon, str) and len(icon) <= 65536, 'Invalid artwork size')
    if icon:
        png = base64.b64decode(icon, validate=True)
        require(len(png) >= 33 and png[:8] == b'\x89PNG\r\n\x1a\n' and png[12:16] == b'IHDR', 'Invalid PNG')
        width, height = struct.unpack('>II', png[16:24])
        require(0 < width <= 128 and 0 < height <= 128, 'Artwork exceeds 128 pixels')
    encoded = project.get('TorrentBase64', '')
    require(isinstance(encoded, str) and 0 < len(encoded) <= 4 * 1024 * 1024, 'Invalid torrent size')
    torrent, raw_info = bdecode(base64.b64decode(encoded, validate=True))
    info = torrent.get(b'info', {})
    require(hashlib.sha1(raw_info).hexdigest() == project['InfoHash'].lower(), 'Torrent hash mismatch')
    require(info.get(b'name') == project['PackageName'].encode(), 'Torrent name mismatch')
    require(b'files' not in info and info.get(b'length') == project['PackageBytes'], 'Torrent is not the expected single ZIP')
    piece_length, pieces = info.get(b'piece length'), info.get(b'pieces')
    require(type(piece_length) is int and 0 < piece_length <= 64 * 1024 * 1024, 'Invalid piece length')
    require(isinstance(pieces, bytes) and len(pieces) == 20 * ((project['PackageBytes'] + piece_length - 1) // piece_length), 'Invalid piece hashes')
    return {key: value for key, value in project.items() if key not in {'VersionDisplay', 'SizeDisplay', 'SnapshotDisplay', 'CreatedDisplay'}}


def build(root):
    entries = root / 'entries'
    projects, hashes = [], set()
    if entries.exists():
        require(not entries.is_symlink(), 'Linked entries directory')
        for path in sorted(entries.iterdir()):
            require(not path.is_symlink() and path.is_file() and path.suffix == '.json', 'Unexpected entry file')
            require(path.stat().st_size <= MAX_BYTES, 'Entry too large')
            entry = json.loads(path.read_text(encoding='utf-8-sig'))
            require(entry.get('Version') == 1 and isinstance(entry.get('Projects'), list) and len(entry['Projects']) == 1, 'Each entry must contain one project')
            project = validate(entry['Projects'][0])
            require(path.name == project['InfoHash'].lower() + '.json', 'Entry filename mismatch')
            require(project['InfoHash'].lower() not in hashes, 'Duplicate torrent')
            hashes.add(project['InfoHash'].lower())
            projects.append(project)
            require(len(projects) <= 1000, 'Too many projects')
    data = json.dumps({'Version': 1, 'Projects': projects}, ensure_ascii=False, indent=2) + '\n'
    require(len(data.encode()) <= MAX_BYTES, 'Catalogue exceeds 8 MB')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build(args.root)
    if not args.check:
        (args.root / 'catalogue.json').write_text(result, encoding='utf-8')
    print('Catalogue metadata is valid.')
