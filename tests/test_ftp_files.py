import ftplib
import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import DTPHandler, FTPHandler, ThrottledDTPHandler
from pyftpdlib.servers import FTPServer

from speasy.core import ftp
from speasy.core.any_files import any_loc_open, list_files
from speasy.core.direct_archive_downloader import get_product

_RESOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')


class SlowDownloads(ThrottledDTPHandler):
    """Sends 1 KiB per second: gaps stay under ~2 s, the whole 32 KiB transfer takes ~30 s."""
    write_limit = 1024
    ac_out_buffer_size = 1024


class LocalFTPServer:
    """A real FTP server on 127.0.0.1, serving `root` anonymously and to user/secret."""

    def __init__(self, root: str, dtp_handler=DTPHandler):
        authorizer = DummyAuthorizer()
        authorizer.add_anonymous(root, perm='elr')
        authorizer.add_user('user', 'secret', root, perm='elr')

        class Handler(FTPHandler):
            pass

        Handler.authorizer = authorizer
        Handler.dtp_handler = dtp_handler
        self._server = FTPServer(('127.0.0.1', 0), Handler)
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

    def test_listing_drops_the_path_and_trailing_slash_of_entries(self):
        # servers differ: some return full paths, some mark folders with a trailing slash
        with patch.object(ftplib.FTP, 'nlst', return_value=['/data/sub/', '/data/x.cdf', 'y.cdf']):
            self.assertListEqual(ftp.list_dir(self.server.url + '/data', timeout=10), ['sub', 'x.cdf', 'y.cdf'])

    def test_random_split_relists_when_a_listed_file_is_gone(self):
        # a new release renames v01 to v02 while the folder listing is still cached:
        # reading v01 fails with FTP 550, which must trigger the same re-list as an HTTP 404
        os.makedirs(os.path.join(self.root, 'burst', '2018'))
        self._write('burst/2018/data_20180101_v01.cdf', b'v1', mtime=1_600_000_000)
        contents = []

        def read_file(url, variable, **kwargs):
            contents.append(any_loc_open(url, cache_remote_files=False).read())
            return None

        request = dict(url_pattern=self.server.url + r"/burst/{Y}/data_\d+_v\d+\.cdf",
                       split_rule='random', split_frequency='yearly', variable='B',
                       start_time='2018-01-01', stop_time='2018-01-02',
                       fname_regex=r"data_(?P<start>\d+)_v(?P<version>\d+)\.cdf",
                       date_format="%Y%m%d", file_reader=read_file)
        get_product(**request)
        os.remove(os.path.join(self.root, 'burst', '2018', 'data_20180101_v01.cdf'))
        self._write('burst/2018/data_20180101_v02.cdf', b'v2', mtime=1_700_000_000)
        get_product(**request)
        self.assertListEqual(contents, [b'v1', b'v2'])

    def test_direct_archive_reads_a_cdf_over_ftp(self):
        os.makedirs(os.path.join(self.root, 'ace', '2022'), exist_ok=True)
        shutil.copy(os.path.join(_RESOURCES, 'ac_k2_mfi_20220101_v03.cdf'),
                    os.path.join(self.root, 'ace', '2022'))
        v = get_product(url_pattern=self.server.url + r'/ace/{Y}/ac_k2_mfi_{Y}{M:02d}{D:02d}_v\d+\.cdf',
                        split_rule='regular', variable='Magnitude',
                        start_time='2022-01-01', stop_time='2022-01-01T12:00:00', use_file_list=True)
        self.assertIsNotNone(v)
        self.assertGreater(len(v), 0)


class FTPTimeout(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        with open(os.path.join(self.root, 'big.bin'), 'wb') as f:
            f.write(b'x' * 32 * 1024)
        self.server = LocalFTPServer(self.root, dtp_handler=SlowDownloads)

    def tearDown(self):
        self.server.close()
        shutil.rmtree(self.root)

    def test_timeout_bounds_the_whole_download(self):
        # a per-socket-operation timeout never fires on a server that keeps sending slowly,
        # so a download could run forever (the HTTP path uses a total timeout for the same reason)
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            ftp.get(self.server.url + '/big.bin', timeout=3)
        self.assertLess(time.monotonic() - start, 8)


if __name__ == '__main__':
    unittest.main()
