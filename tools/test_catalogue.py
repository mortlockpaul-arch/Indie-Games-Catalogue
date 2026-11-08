import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from catalogue import build, validate


def example():
    name = 'a' * 32 + '.zip'
    info = b'd6:lengthi4e4:name36:' + name.encode() + b'12:piece lengthi16384e6:pieces20:' + b'x' * 20 + b'e'
    return dict(PackageKind='Source', Id='a' * 32, Name='Synthetic test', FolderName='Example',
                PackageName=name, PackageBytes=4, UnpackedBytes=4, FileCount=1, Sha256='b' * 64,
                InfoHash=hashlib.sha1(info).hexdigest(), TorrentBase64=base64.b64encode(b'd4:info' + info + b'e').decode(),
                CreatedUtc='2026-11-04T12:00:00Z')


class CatalogueTests(unittest.TestCase):
    def test_valid_metadata(self):
        self.assertEqual(validate(example())['Name'], 'Synthetic test')

    def test_versions_and_legacy_entries(self):
        self.assertNotIn('PackageVersion', validate(example()))
        for version in ('', '1.0.1', '2.0.0-beta.1'):
            project = example(); project.update(PackageVersion=version, VersionDisplay=version)
            result = validate(project)
            self.assertEqual(result['PackageVersion'], version)
            self.assertNotIn('VersionDisplay', result)
        for version in (None, 42, 'v' * 129, '1.0\nforged', '1.0\x7f'):
            project = example(); project['PackageVersion'] = version
            with self.assertRaises(ValueError): validate(project)

    def test_infohash(self):
        project = example(); project['InfoHash'] = '0' * 40
        with self.assertRaises(ValueError): validate(project)

    def test_unsafe_path(self):
        for folder in ('../bad', 'COM0', 'bad/name', 'bad\\name', '.hidden', 'name.'):
            project = example(); project['FolderName'] = folder
            with self.assertRaises(ValueError): validate(project)

    def test_bad_fields(self):
        for key, value in [('PackageBytes', -1), ('FileCount', True), ('CreatedUtc', 'yesterday'), ('IconBase64', 'not base64'), ('UnpackedBytes', 101 * 1024**3), ('PackageName', 'wrong.zip')]:
            project = example(); project[key] = value
            with self.assertRaises((ValueError, TypeError)): validate(project)

    def test_unknown_paths_not_forwarded(self):
        project = example(); project['SourcePath'] = 'C:/private/project'
        with self.assertRaises(ValueError): validate(project)

    def test_build_and_entry_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'entries').mkdir()
            project = example(); project['PackageVersion'] = '1.0.1'; path = root / 'entries' / (project['InfoHash'] + '.json')
            path.write_text(json.dumps(dict(Version=1, Projects=[project])), encoding='utf-8')
            self.assertEqual(json.loads(build(root))['Projects'][0]['PackageVersion'], '1.0.1')
            path.rename(root / 'entries' / 'wrong.json')
            with self.assertRaises(ValueError): build(root)

    def test_reject_multiple_entries_in_one_submission_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'entries').mkdir()
            (root / 'entries' / 'wrong.json').write_text(json.dumps(dict(Version=1, Projects=[example(), example()])), encoding='utf-8')
            with self.assertRaises(ValueError): build(root)


if __name__ == '__main__':
    unittest.main()
