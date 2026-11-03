
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader('health_tool', "/usr/local/bin/kvorix-health-check")
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

def entry(name, size=1024, mode=0o600, uid=0, gid=0, link=False, mtime=None, dir=False):
    return dict(name=name, size=size, mtime=time.time() if mtime is None else mtime,
                mode=mode, uid=uid, gid=gid, link=link, dir=dir)

class VaultAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.rows = [entry('config-a.tar.gz', size=10 * 1024**2),
                     entry('config-a.tar.gz.json', size=508),
                     entry('.lock', size=0)]

    def states(self, rows):
        return {name: state for name, state, _ in module.vault_assessment(rows)}

    def test_healthy_vault(self):
        states = self.states(self.rows)
        self.assertEqual(list(states.values()), ['PASS'] * 4)
        self.assertEqual(len(states), 4)

    def test_world_readable_archive(self):
        self.rows[0]['mode'] = 0o644
        self.assertEqual(self.states(self.rows)['snapshot archive permissions'], 'FAIL')

    def test_wrong_owner(self):
        self.rows[1]['uid'] = 1001
        self.assertEqual(self.states(self.rows)['snapshot archive permissions'], 'FAIL')

    def test_symlink_archive(self):
        self.rows[0]['link'] = True
        self.assertEqual(self.states(self.rows)['snapshot archive permissions'], 'FAIL')

    def test_world_readable_temp_file(self):
        self.rows.append(entry('.snapshot-leftover.tar.gz', mode=0o644))
        self.assertEqual(self.states(self.rows)['snapshot archive permissions'], 'FAIL')

    def test_subdirectory_not_treated_as_file(self):
        self.rows.append(entry('subdir', mode=0o755, dir=True))
        self.assertEqual(self.states(self.rows)['snapshot archive permissions'], 'PASS')

    def test_missing_manifest(self):
        self.rows.pop(1)
        self.assertEqual(self.states(self.rows)['snapshot manifest pairs'], 'FAIL')

    def test_orphan_manifest(self):
        self.rows.pop(0)
        self.assertEqual(self.states(self.rows)['snapshot manifest pairs'], 'FAIL')

    def test_stale_warn_and_fail(self):
        self.rows[0]['mtime'] = time.time() - 12 * 86400
        self.assertEqual(self.states(self.rows)['snapshot freshness'], 'WARN')
        self.rows[0]['mtime'] = time.time() - 30 * 86400
        self.assertEqual(self.states(self.rows)['snapshot freshness'], 'FAIL')

    def test_no_archives_yet(self):
        self.assertEqual(self.states([entry('.lock', size=0)])['snapshot freshness'], 'WARN')

    def test_capacity_warn_and_fail(self):
        self.rows[0]['size'] = int(module.VAULT_LIMIT * 0.9)
        self.assertEqual(self.states(self.rows)['snapshot storage usage'], 'WARN')
        self.rows[0]['size'] = module.VAULT_LIMIT + 1
        self.assertEqual(self.states(self.rows)['snapshot storage usage'], 'FAIL')

    def test_future_mtime_never_negative_age(self):
        self.rows[0]['mtime'] = time.time() + 86400
        self.assertEqual(self.states(self.rows)['snapshot freshness'], 'PASS')

class VaultDirectoryTests(unittest.TestCase):
    def test_private_directory(self):
        fake = os.stat_result((0o40700, 1, 2, 1, 0, 0, 4096, 0, 0, 0))
        with patch.object(module.os, 'lstat', return_value=fake):
            self.assertEqual(module.vault_directory_check(Path('/x'))[1], 'PASS')

    def test_open_directory(self):
        fake = os.stat_result((0o40755, 1, 2, 1, 0, 0, 4096, 0, 0, 0))
        with patch.object(module.os, 'lstat', return_value=fake):
            self.assertEqual(module.vault_directory_check(Path('/x'))[1], 'FAIL')

    def test_missing_directory(self):
        with patch.object(module.os, 'lstat', side_effect=FileNotFoundError('absent')):
            self.assertEqual(module.vault_directory_check(Path('/x'))[1], 'WARN')

class VaultScanTests(unittest.TestCase):
    def setUp(self):
        self.rows = [entry('config-a.tar.gz'), entry('config-a.tar.gz.json', size=508)]

    def done(self, args, code=0, out='', err=''):
        return subprocess.CompletedProcess(args, code, stdout=out, stderr=err)

    def test_uses_sudo_when_not_root(self):
        with patch.object(module.os, 'geteuid', return_value=1001), \
             patch.object(module.subprocess, 'run', return_value=self.done([], out=json.dumps(self.rows))) as run:
            rows = module.vault_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(run.call_args[0][0][:3], ['sudo', '-n', 'python3'])

    def test_no_sudo_when_root(self):
        with patch.object(module.os, 'geteuid', return_value=0), \
             patch.object(module.subprocess, 'run', return_value=self.done([], out=json.dumps(self.rows))) as run:
            module.vault_rows()
        self.assertEqual(run.call_args[0][0][:2], ['python3', '-c'])

    def test_scan_failure(self):
        with patch.object(module.os, 'geteuid', return_value=1001), \
             patch.object(module.subprocess, 'run', return_value=self.done([], code=1, err='no permission')):
            with self.assertRaisesRegex(RuntimeError, 'no permission'):
                module.vault_rows()

    def test_bad_json(self):
        with patch.object(module.os, 'geteuid', return_value=1001), \
             patch.object(module.subprocess, 'run', return_value=self.done([], out='not-json')):
            with self.assertRaises(ValueError):
                module.vault_rows()

class ReportTests(unittest.TestCase):
    def test_json_report_contains_vault_checks(self):
        rows = [entry('config-a.tar.gz', size=10 * 1024**2), entry('config-a.tar.gz.json', size=508)]
        def fake_run(args, **kwargs):
            head = args[0]
            if head == 'sudo':
                return subprocess.CompletedProcess(args, 0, stdout=json.dumps(rows), stderr='')
            if head == 'timedatectl':
                return subprocess.CompletedProcess(args, 0, stdout='yes\n', stderr='')
            if head == 'findmnt':
                return subprocess.CompletedProcess(args, 0, stdout='rw,noatime\n', stderr='')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        out = io.StringIO()
        with patch.object(module.os, 'geteuid', return_value=1001), \
             patch.object(module, 'vault_directory_check', return_value=('snapshot vault private', 'PASS', 'stub')), \
             patch.object(module.subprocess, 'run', side_effect=fake_run), redirect_stdout(out):
            with self.assertRaises(SystemExit) as caught:
                module.main(['--json'])
        self.assertEqual(caught.exception.code, 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report['summary']['FAIL'], 0)
        names = [c['check'] for c in report['checks']]
        for expected in ('snapshot vault private', 'snapshot inventory readable',
                         'snapshot archive permissions', 'snapshot manifest pairs',
                         'snapshot freshness', 'snapshot storage usage',
                         'syntax /usr/local/bin/kvorix-health-check',
                         'syntax /usr/local/sbin/kvorix-config-verify'):
            self.assertIn(expected, names)
        self.assertEqual(len(names), len(set(names)))

if __name__ == '__main__':
    unittest.main(verbosity=2)
