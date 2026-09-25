"""Read-only FTP access for remote archives, the ``ftp://`` counterpart of :mod:`speasy.core.http`."""
import ftplib
import io
import posixpath
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Iterator, List, Tuple
from urllib.parse import unquote, urlparse


def is_ftp(url: str) -> bool:
    return urlparse(url).scheme == 'ftp'


@contextmanager
def _session(url: str, timeout: float) -> Iterator[Tuple[ftplib.FTP, str]]:
    parts = urlparse(url)
    try:
        with ftplib.FTP(timeout=timeout) as session:
            session.connect(parts.hostname, parts.port or ftplib.FTP_PORT)
            session.login(unquote(parts.username or 'anonymous'), unquote(parts.password or ''))
            yield session, unquote(parts.path) or '/'
    except ftplib.Error as e:
        # ftplib errors are not OSErrors; re-raise them as IOError like the HTTP path does
        error = FileNotFoundError if str(e).startswith('550') else IOError
        raise error(f"FTP request failed for {parts.hostname}{parts.path}: {e}") from e


def _mdtm(session: ftplib.FTP, path: str) -> str:
    # MDTM is an extension (RFC 3659). Without it, fall back like an HTTP server that sends no
    # Last-Modified header: the file always looks modified, so the cache refetches it.
    try:
        return session.voidcmd(f'MDTM {path}').split()[-1]
    except ftplib.error_perm:
        return str(datetime.now())


def _write_before(deadline: float, write: Callable[[bytes], Any]) -> Callable[[bytes], None]:
    def write_chunk(chunk: bytes):
        if time.monotonic() > deadline:
            raise TimeoutError("FTP download exceeded its total timeout")
        write(chunk)

    return write_chunk


def get(url: str, timeout: float) -> Tuple[bytes, str]:
    """Downloads a file, returns its content and its last-modified version.

    ``timeout`` bounds the whole call, like :func:`speasy.core.http.urlopen`: ftplib's own timeout only bounds each
    socket operation, so a server that keeps sending slowly would otherwise never time out.
    """
    deadline = time.monotonic() + timeout
    buffer = io.BytesIO()
    with _session(url, timeout) as (session, path):
        version = _mdtm(session, path)
        session.retrbinary(f'RETR {path}', _write_before(deadline, buffer.write))
    return buffer.getvalue(), version


def last_modified(url: str, timeout: float) -> str:
    with _session(url, timeout) as (session, path):
        return _mdtm(session, path)


def list_dir(url: str, timeout: float) -> List[str]:
    """Names of the entries in a folder, without their path (servers differ on NLST output)."""
    with _session(url, timeout) as (session, path):
        try:
            names = session.nlst(path)
        except ftplib.error_perm:
            # 550: a missing folder, or an empty one on some servers. Both mean "no files", like an HTTP 404.
            return []
        return [entry for entry in (posixpath.basename(name.rstrip('/')) for name in names) if entry]
