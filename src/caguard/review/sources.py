"""The uploaded files themselves, kept exactly as they arrived.

A reviewer has to be able to answer "where did this finding come from?" with
the client's own file, not with something CA-Guard regenerated. So the original
upload is stored byte-for-byte and never rewritten: what is downloaded later is
what was uploaded, and the stored SHA-256 proves it.

**Content-addressed.** A file is stored under its own hash, so uploading the
same ledger twice keeps one copy, and a name chosen by the user never becomes
part of a path.

**Only after a successful analysis.** A file CA-Guard could not read is not
kept, so "Nothing was saved" on an error message stays true.

**Retention is the firm's decision** (D-054). Files are kept until a reviewer
deletes them; nothing here expires on its own.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from caguard.intake.readers import SUPPORTED_SUFFIXES

_HASH_CHUNK = 1024 * 1024


class SourceIntegrityError(RuntimeError):
    """A stored file no longer matches the hash it was stored under."""


@dataclass(frozen=True)
class StoredFile:
    sha256: str
    suffix: str
    size_bytes: int


class SourceVault:
    """A directory of original uploads, named by content hash."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        # Owner-only: these are client ledgers.
        self.directory.chmod(0o700)

    def keep(self, upload: Path, suffix: str) -> StoredFile:
        """Move a finished upload into the vault. The temporary file is consumed.

        A rename within one filesystem is atomic, so a crash leaves either the
        whole file or none of it — never a truncated "original".
        """
        _check_suffix(suffix)
        digest = sha256_of(upload)
        size = upload.stat().st_size
        target = self.path_for(digest, suffix)
        if target.exists():
            upload.unlink(missing_ok=True)
        else:
            upload.replace(target)
            target.chmod(0o600)
        return StoredFile(digest, suffix, size)

    def path_for(self, sha256: str, suffix: str) -> Path:
        _check_suffix(suffix)
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise ValueError("not a SHA-256 digest")
        return self.directory / f"{sha256}{suffix}"

    def exists(self, sha256: str, suffix: str) -> bool:
        return self.path_for(sha256, suffix).is_file()

    def verified_path(self, sha256: str, suffix: str) -> Path:
        """The stored file, after proving it is still the bytes that were uploaded."""
        path = self.path_for(sha256, suffix)
        if not path.is_file():
            raise FileNotFoundError(sha256)
        if sha256_of(path) != sha256:
            raise SourceIntegrityError(
                "The stored original no longer matches the file that was uploaded."
            )
        return path

    def remove(self, sha256: str, suffix: str) -> bool:
        """Delete a stored file. Returns whether there was anything to delete."""
        path = self.path_for(sha256, suffix)
        if not path.exists():
            return False
        path.unlink()
        return True


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _check_suffix(suffix: str) -> None:
    # The suffix is part of a path, so it is matched against the allow-list
    # rather than trusted, exactly as at upload time.
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported suffix {suffix!r}")
