import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.storage_check import StorageCheckError, parse_mount_info, validate_storage


def completed(stdout: str, returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["findmnt"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class StorageCheckTests(unittest.TestCase):
    def test_parse_mount_info(self):
        mount = parse_mount_info("/dev/sda1 rw,relatime\n")
        self.assertEqual(mount.source, "/dev/sda1")
        self.assertEqual(mount.options, frozenset({"rw", "relatime"}))

    def test_rejects_incomplete_mount_metadata(self):
        with self.assertRaisesRegex(StorageCheckError, "incomplete"):
            parse_mount_info("/dev/sda1\n")

    def test_accepts_writable_sda_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            mount = validate_storage(
                Path(directory),
                runner=lambda _: completed("/dev/sda1 rw,relatime\n"),
            )
        self.assertEqual(mount.source, "/dev/sda1")

    def test_rejects_non_sda_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(StorageCheckError, "expected"):
                validate_storage(
                    Path(directory),
                    runner=lambda _: completed("/dev/nvme0n1p1 rw,relatime\n"),
                )

    def test_rejects_read_only_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(StorageCheckError, "read-only"):
                validate_storage(
                    Path(directory),
                    runner=lambda _: completed("/dev/sda1 ro,relatime\n"),
                )

    def test_rejects_findmnt_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(StorageCheckError, "cannot resolve"):
                validate_storage(
                    Path(directory),
                    runner=lambda _: completed(
                        "", returncode=1, stderr="not a mountpoint"
                    ),
                )

    def test_rejects_sdb_as_expected_device(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(StorageCheckError, "/dev/sdb"):
                validate_storage(
                    Path(directory),
                    expected_device_prefix="/dev/sdb",
                    runner=lambda _: completed("/dev/sdb1 rw,relatime\n"),
                )
