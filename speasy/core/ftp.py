"""Read-only FTP access for remote archives, the ``ftp://`` counterpart of :mod:`speasy.core.http`."""
import ftplib
import io
import posixpath
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, List, Tuple
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
        raise IOError(f"FTP request failed for {parts.hostname}{parts.path}: {e}") from e


def _mdtm(session: ftplib.FTP, path: str) -> str:
    # MDTM is an extension (RFC 3659). Without it, fall back like an HTTP server that sends no
    # Last-Modified header: the file always looks modified, so the cache refetches it.
    try:
        return session.voidcmd(f'MDTM {path}').split()[-1]
    except ftplib.error_perm:
        return str(datetime.now())


def get(url: str, timeout: float) -> Tuple[bytes, str]:
    """Downloads a file, returns its content and its last-modified version."""
    buffer = io.BytesIO()
    with _session(url, timeout) as (session, path):
        version = _mdtm(session, path)
        session.retrbinary(f'RETR {path}', buffer.write)
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
        return [posixpath.basename(name) for name in names]
