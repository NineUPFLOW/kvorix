import hashlib
import importlib.machinery
import importlib.util
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader('verify_tool', "/usr/local/sbin/kvorix-config-verify")
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.archive = self.base / 'config-test.tar.gz'
        self.manifest = Path(str(self.archive) + '.json')

    def build(self, extra=None, omit=False):
        names = list(module.TARGETS)
        if omit:
            names.pop()
        if extra:
            names.append(extra)
        with tarfile.open(self.archive, 'w:gz') as tar:
            for name in names:
                content = b'configuration\n'
                info = tarfile.TarInfo(name)
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
        self.manifest.write_text(json.dumps(dict(archive=self.archive.name,
            sha256=hashlib.sha256(self.archive.read_bytes()).hexdigest(), members=len(names))))
        self.base.chmod(0o700)
        self.archive.chmod(0o600)
        self.manifest.chmod(0o600)

    def test_recovery(self):
        self.build()
        result = module.verify(self.archive, self.manifest)
        self.assertTrue(result['verified'])
        self.assertEqual(len(result['recovered_files']), 3)

    def test_corruption(self):
        self.build()
        with self.archive.open('ab') as f:
            f.write(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            module.verify(self.archive, self.manifest)

    def test_traversal(self):
        self.build('../escape')
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            module.verify(self.archive, self.manifest)
        self.assertFalse((self.base.parent / 'escape').exists())

    def test_absolute_path(self):
        self.build('/etc/should-not-be-written')
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            module.verify(self.archive, self.manifest)

    def test_duplicate(self):
        self.build(module.TARGETS[0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            module.verify(self.archive, self.manifest)

    def test_missing_target(self):
        self.build(omit=True)
        with self.assertRaisesRegex(ValueError, 'missing'):
            module.verify(self.archive, self.manifest)

    def test_manifest_count(self):
        self.build()
        data = json.loads(self.manifest.read_text())
        data['members'] = 100
        self.manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'count'):
            module.verify(self.archive, self.manifest)

    def audit(self):
        real_path = Path
        def mapped_path(value):
            return self.base if str(value) == '/var/backups/kvorix-config-private' else real_path(value)
        output = io.StringIO()
        code = 0
        with patch.object(module, 'Path', side_effect=mapped_path), patch.object(module.os, 'geteuid', return_value=0), patch.object(module.os, 'umask', return_value=0o22), patch('sys.argv', ['verify', '--all']), redirect_stdout(output):
            try:
                module.main()
            except SystemExit as e:
                code = e.code
        return code, json.loads(output.getvalue())

    def test_audit_success(self):
        self.build()
        code, report = self.audit()
        self.assertEqual(code, 0)
        self.assertTrue(report['verified'])
        self.assertEqual(report['checked'], 1)
        self.assertEqual(report['missing_manifests'], [])
        self.assertEqual(report['permission_issues'], [])
        self.assertEqual(report['orphan_manifests'], [])

    def test_audit_corruption(self):
        self.build()
        with self.archive.open('ab') as f:
            f.write(b'damaged')
        code, report = self.audit()
        self.assertEqual(code, 1)
        self.assertEqual(len(report['failures']), 1)
        self.assertTrue(self.archive.exists())

    def test_audit_orphan_manifest(self):
        self.build()
        orphan = self.base / 'config-orphan.tar.gz.json'
        orphan.write_text('{}')
        orphan.chmod(0o600)
        code, report = self.audit()
        self.assertEqual(code, 1)
        self.assertIn(str(orphan), report['orphan_manifests'])
        self.assertTrue(orphan.exists())

    def test_missing_manifest_file(self):
        self.build()
        self.manifest.unlink()
        with self.assertRaisesRegex(ValueError, 'Manifest missing'):
            module.verify(self.archive, self.manifest)

    def test_audit_missing_manifest(self):
        self.build()
        self.manifest.unlink()
        code, report = self.audit()
        self.assertEqual(code, 1)
        self.assertFalse(report['verified'])
        self.assertIn(str(self.archive), report['missing_manifests'])
        self.assertEqual(report['failures'][0]['error'], 'Manifest missing')
        self.assertTrue(self.archive.exists())

    def test_audit_no_snapshots(self):
        real_path = Path
        def mapped_path(value):
            return self.base if str(value) == '/var/backups/kvorix-config-private' else real_path(value)
        err = io.StringIO()
        with patch.object(module, 'Path', side_effect=mapped_path), \
             patch.object(module.os, 'geteuid', return_value=0), \
             patch.object(module.os, 'umask', return_value=0o22), \
             patch('sys.argv', ['verify', '--all']), redirect_stderr(err):
            with self.assertRaises(SystemExit) as caught:
                module.main()
        self.assertEqual(caught.exception.code, 1)
        self.assertIn('No snapshots found', err.getvalue())

    def test_vault_permission_helper(self):
        self.build()
        self.assertEqual(module.vault_issues(self.base), [])
        self.archive.chmod(0o644)
        self.assertTrue(module.vault_issues(self.base))

    def test_audit_world_readable_temp_file(self):
        self.build()
        leftover = self.base / '.snapshot-leftover.tar.gz'
        leftover.write_bytes(b'partial configuration')
        leftover.chmod(0o644)
        code, report = self.audit()
        self.assertEqual(code, 1)
        self.assertFalse(report['verified'])
        self.assertTrue(any('.snapshot-leftover' in issue for issue in report['permission_issues']))
        self.assertTrue(leftover.exists())

    def test_audit_world_readable_archive(self):
        self.build()
        self.archive.chmod(0o644)
        code, report = self.audit()
        self.assertEqual(code, 1)
        self.assertFalse(report['verified'])
        self.assertTrue(any(self.archive.name in issue for issue in report['permission_issues']))
        self.assertTrue(self.archive.exists())

    def test_audit_symlink_archive(self):
        self.build()
        link = self.base / 'config-link.tar.gz'
        link.symlink_to(self.archive)
        (self.base / 'config-link.tar.gz.json').write_text('{}')
        code, report = self.audit()
        self.assertEqual(code, 1)
        self.assertTrue(any('config-link.tar.gz' in issue for issue in report['permission_issues']))
        self.assertTrue(link.exists())

    def test_symlink_input(self):
        self.build()
        link = self.base / 'link.tar.gz'
        link.symlink_to(self.archive)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            module.verify(link, self.manifest)

if __name__ == '__main__':
    unittest.main(verbosity=2)
