import os
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from speasy.core import ftp
from speasy.core.any_files import any_loc_open, list_files
from speasy.core.direct_archive_downloader import get_product

_RESOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')


class LocalFTPServer:
    """A real FTP server on 127.0.0.1, serving `root` anonymously and to user/secret."""

    def __init__(self, root: str):
        authorizer = DummyAuthorizer()
        authorizer.add_anonymous(root, perm='elr')
        authorizer.add_user('user', 'secret', root, perm='elr')
        handler = type('Handler', (FTPHandler,), {'authorizer': authorizer})
        self._server = FTPServer(('127.0.0.1', 0), handler)
        self.url = f'ftp://127.0.0.1:{self._server.address[1]}'
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={'timeout': 0.05}, daemon=True)
        self._thread.start()

    def close(self):
        self._server.close_all()
        self._thread.join()


class FTPFileAccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(cls.root, 'data'))
        for name, content in (('a.txt', 'hello ftp'), ('b.txt', 'other'), ('readme.md', 'skip me')):
            with open(os.path.join(cls.root, 'data', name), 'w') as f:
                f.write(content)
        cls.server = LocalFTPServer(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.server.close()
        shutil.rmtree(cls.root)

    def _write(self, relative_path: str, content: bytes, mtime: float):
        path = os.path.join(self.root, relative_path)
        with open(path, 'wb') as f:
            f.write(content)
        os.utime(path, (mtime, mtime))

    def test_ftp_urls_are_remote(self):
        self.assertTrue(ftp.is_ftp(self.server.url + '/data/a.txt'))
        self.assertFalse(ftp.is_ftp('https://example.org/data/a.txt'))

    def test_reads_a_binary_file(self):
        f = any_loc_open(self.server.url + '/data/a.txt', mode='rb', cache_remote_files=False)
        self.assertEqual(f.read(), b'hello ftp')

    def test_reads_a_text_file(self):
        f = any_loc_open(self.server.url + '/data/a.txt', mode='r', cache_remote_files=False)
        self.assertEqual(f.read(), 'hello ftp')

    def test_reads_with_credentials_from_the_url(self):
        url = self.server.url.replace('ftp://', 'ftp://user:secret@') + '/data/a.txt'
        f = any_loc_open(url, mode='rb', cache_remote_files=False)
        self.assertEqual(f.read(), b'hello ftp')

    def test_missing_file_raises_ioerror(self):
        with self.assertRaises(IOError):
            any_loc_open(self.server.url + '/data/missing.txt', cache_remote_files=False)

    def test_cached_read_skips_the_download_when_unchanged(self):
        self._write('data/cached.bin', b'v1', mtime=1_600_000_000)
        url = self.server.url + '/data/cached.bin'
        self.assertEqual(any_loc_open(url, cache_remote_files=True).read(), b'v1')
        with patch.object(ftp, 'get', side_effect=AssertionError('should come from the cache')):
            self.assertEqual(any_loc_open(url, cache_remote_files=True).read(), b'v1')

    def test_cached_read_refetches_a_modified_file(self):
        self._write('data/changing.bin', b'v1', mtime=1_600_000_000)
        url = self.server.url + '/data/changing.bin'
        self.assertEqual(any_loc_open(url, cache_remote_files=True).read(), b'v1')
        self._write('data/changing.bin', b'v2', mtime=1_700_000_000)
        self.assertEqual(any_loc_open(url, cache_remote_files=True).read(), b'v2')

    def test_lists_files_matching_a_regex(self):
        files = list_files(self.server.url + '/data', r'.*\.txt', disable_cache=True)
        self.assertListEqual(sorted(files), ['a.txt', 'b.txt'])

    def test_listing_a_missing_folder_is_empty(self):
        # like an HTTP 404: a date range with no folder in the archive has no files, it is not an error
        self.assertListEqual(list_files(self.server.url + '/no_such_folder', r'.*', disable_cache=True), [])

    def test_direct_archive_reads_a_cdf_over_ftp(self):
        os.makedirs(os.path.join(self.root, 'ace', '2022'), exist_ok=True)
        shutil.copy(os.path.join(_RESOURCES, 'ac_k2_mfi_20220101_v03.cdf'),
                    os.path.join(self.root, 'ace', '2022'))
        v = get_product(url_pattern=self.server.url + r'/ace/{Y}/ac_k2_mfi_{Y}{M:02d}{D:02d}_v\d+\.cdf',
                        split_rule='regular', variable='Magnitude',
                        start_time='2022-01-01', stop_time='2022-01-01T12:00:00', use_file_list=True)
        self.assertIsNotNone(v)
        self.assertGreater(len(v), 0)


if __name__ == '__main__':
    unittest.main()
