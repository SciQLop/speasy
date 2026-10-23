"""Packs a closed data index folder into a tar and unpacks one safely."""
import os
import tarfile
from pathlib import PurePosixPath

_ROOT = "speasy-data-index"
_SQLITE_SIDE_FILES = ("-wal", "-shm")


def pack(folder: str, tar_path: str):
    """The whole folder: pysciqlop-cache keeps large values as files next to its database."""
    with tarfile.open(tar_path, "w") as tar:
        tar.add(folder, arcname=_ROOT, filter=lambda info: None if info.name.endswith(_SQLITE_SIDE_FILES) else info)


def _check_member(member: tarfile.TarInfo):
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
        raise ValueError(f"Refusing a data index archive holding {member.name!r}: only plain files and folders inside "
                         f"the archive's own folder are allowed")


def unpack(tar_path: str, destination: str) -> str:
    """Extracts ``tar_path`` into ``destination`` and returns the folder holding the index.

    Every member is checked first: no absolute path, no '..', no link or device, so nothing lands outside
    ``destination``."""
    with tarfile.open(tar_path) as tar:
        members = tar.getmembers()
        for member in members:
            _check_member(member)
        # also the standard library's own guard, where it exists (3.12, and 3.10.12 / 3.11.4 backports)
        tar.extractall(destination, members=members,
                       **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return os.path.join(destination, _ROOT)
