#
#   xgzarc.py - XG ZLib archive module
#   Copyright (C) 2013,2014  Michael Petch <mpetch@gnubg.org>
#                                          <mpetch@capp-sysware.com>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Lesser General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#   This library is an interpretation of ZLBArchive 1.52 data structures.
#   Please see: http://www.delphipages.com/comp/zlibarchive-2104.html
#

from __future__ import annotations

import os
import struct
import tempfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

import xgutils


class Error(Exception):
    """Raised for any error encountered while reading a Zlib archive."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Zlib archive: {message}")


# ---------------------------------------------------------------------------
# Low-level record structures
# ---------------------------------------------------------------------------


@dataclass
class ArchiveRecord:
    """Trailer record appended at the end of every ZLBArchive file."""

    SIZE = 36

    crc: int = 0
    filecount: int = 0
    version: int = 0
    registrysize: int = 0
    archivesize: int = 0
    compressedregistry: bool = False
    reserved: tuple[int, ...] = field(default_factory=tuple)

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> "ArchiveRecord":
        data = struct.unpack("<llllll12B", stream.read(cls.SIZE))
        return cls(
            crc=data[0] & 0xFFFFFFFF,
            filecount=data[1],
            version=data[2],
            registrysize=data[3],
            archivesize=data[4],
            compressedregistry=bool(data[5]),
            reserved=data[6:],
        )


@dataclass
class FileRecord:
    """Per-file entry stored in the ZLBArchive index."""

    SIZE = 532

    name: str = ""
    path: str = ""
    osize: int = 0
    csize: int = 0
    start: int = 0
    crc: int = 0
    compressed: bool = False
    compressionlevel: int = 0

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> "FileRecord":
        data = struct.unpack("<256B256BllllBBxx", stream.read(cls.SIZE))
        return cls(
            name=xgutils.delphishortstrtostr(data[0:256]),
            path=xgutils.delphishortstrtostr(data[256:512]),
            osize=data[512],
            csize=data[513],
            start=data[514],
            crc=data[515] & 0xFFFFFFFF,
            compressed=bool(data[516] == 0),
            compressionlevel=data[517],
        )


# ---------------------------------------------------------------------------
# Archive reader
# ---------------------------------------------------------------------------


class ZlibArchive:
    """Read-only accessor for a ZLBArchive 1.52 stream embedded inside an XG file."""

    _MAX_BUF = 32768
    _TMP_PREFIX = "tmpXGI"

    def __init__(
        self,
        stream: BinaryIO | None = None,
        filename: str | Path | None = None,
    ) -> None:
        if stream is None and filename is None:
            raise ValueError("Either stream or filename must be supplied.")

        self._owns_stream = stream is None
        self.stream: BinaryIO = stream if stream is not None else open(filename, "rb")  # type: ignore[arg-type]

        self.arcrec = ArchiveRecord()
        self.arcregistry: list[FileRecord] = []
        self.startofarcdata: int = -1
        self.endofarcdata: int = -1

        self._load_index()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_segment(
        self,
        *,
        compressed: bool = True,
        numbytes: int | None = None,
    ) -> Path:
        """Decompress or copy one archive segment into a fresh temp file.

        Returns the :class:`Path` of the temporary file.
        Raises :exc:`Error` on failure.
        """
        tmpfd, tmppath_str = tempfile.mkstemp(prefix=self._TMP_PREFIX)
        tmppath = Path(tmppath_str)
        try:
            with os.fdopen(tmpfd, "wb") as tmpfile:
                if compressed:
                    decomp = zlib.decompressobj()
                    buf = self.stream.read(self._MAX_BUF)
                    out = decomp.decompress(buf)
                    if not out:
                        raise Error("Empty decompressed output for segment")
                    tmpfile.write(out)
                    while not decomp.unused_data:
                        block = self.stream.read(self._MAX_BUF)
                        if not block:
                            break
                        try:
                            tmpfile.write(decomp.decompress(block))
                        except zlib.error:
                            break
                else:
                    if numbytes is None:
                        raise Error("numbytes required for uncompressed segment")
                    remaining = numbytes
                    while remaining > 0:
                        chunk = self.stream.read(min(self._MAX_BUF, remaining))
                        if not chunk:
                            break
                        tmpfile.write(chunk)
                        remaining -= len(chunk)
        except (zlib.error, OSError) as exc:
            tmppath.unlink(missing_ok=True)
            raise Error(str(exc)) from exc

        return tmppath

    def _load_index(self) -> None:
        saved_pos = self.stream.tell()
        try:
            # Read the trailer record from the end of the stream.
            self.stream.seek(-ArchiveRecord.SIZE, os.SEEK_END)
            self.endofarcdata = self.stream.tell()
            self.arcrec = ArchiveRecord.from_stream(self.stream)

            # Locate the start of the compressed data blob.
            self.stream.seek(
                -(ArchiveRecord.SIZE + self.arcrec.registrysize), os.SEEK_END
            )
            self.startofarcdata = self.stream.tell() - self.arcrec.archivesize

            # Verify archive integrity.
            crc = xgutils.streamcrc32(
                self.stream,
                startpos=self.startofarcdata,
                numbytes=self.endofarcdata - self.startofarcdata,
            )
            if crc != self.arcrec.crc:
                raise Error("Archive CRC check failed — file corrupt")

            # Extract and parse the (possibly compressed) file registry.
            idx_path = self._extract_segment(compressed=self.arcrec.compressedregistry)
            try:
                with idx_path.open("rb") as idx_file:
                    self.arcregistry = [
                        FileRecord.from_stream(idx_file)
                        for _ in range(self.arcrec.filecount)
                    ]
            finally:
                idx_path.unlink(missing_ok=True)
        finally:
            self.stream.seek(saved_pos)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def getarchivefile(self, filerec: FileRecord) -> tuple[BinaryIO, Path]:
        """Extract *filerec* into a temp file and return ``(file_object, path)``.

        The caller is responsible for closing the file object and deleting the
        temporary file when done.
        """
        self.stream.seek(filerec.start + self.startofarcdata)
        tmp_path = self._extract_segment(
            compressed=filerec.compressed,
            numbytes=filerec.csize,
        )
        tmp_file: BinaryIO = tmp_path.open("rb")

        crc = xgutils.streamcrc32(tmp_file)
        if crc != filerec.crc:
            tmp_file.close()
            tmp_path.unlink(missing_ok=True)
            raise Error("File CRC check failed — file corrupt")

        return tmp_file, tmp_path

    def set_block_size(self, size: int) -> None:
        """Override the internal read-buffer size (default: 32 768 bytes)."""
        self._MAX_BUF = size

    def __enter__(self) -> "ZlibArchive":
        return self

    def __exit__(self, *_: object) -> None:
        if self._owns_stream:
            self.stream.close()
