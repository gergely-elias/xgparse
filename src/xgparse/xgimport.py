#
#   xgimport.py - XG import module
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

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Generator
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import BinaryIO

import xgstruct
import xgzarc


# ---------------------------------------------------------------------------
# Public exceptions
# ---------------------------------------------------------------------------


class Error(Exception):
    """Raised when a file cannot be parsed as a valid XG game data file."""

    def __init__(self, message: str, filename: str | Path) -> None:
        self.message = message
        self.filename = Path(filename)
        super().__init__(f"XG import error processing '{filename}': {message}")


# ---------------------------------------------------------------------------
# Segment types and metadata
# ---------------------------------------------------------------------------


class SegmentType(IntEnum):
    GDF_HDR = 0
    GDF_IMAGE = 1
    XG_GAMEHDR = 2
    XG_GAMEFILE = 3
    XG_ROLLOUTS = 4
    XG_COMMENT = 5
    ZLIBARC_IDX = 6
    XG_UNKNOWN = 7


_EXTENSIONS: dict[SegmentType, str | None] = {
    SegmentType.GDF_HDR: "_gdh.bin",
    SegmentType.GDF_IMAGE: ".jpg",
    SegmentType.XG_GAMEHDR: "_gamehdr.bin",
    SegmentType.XG_GAMEFILE: "_gamefile.bin",
    SegmentType.XG_ROLLOUTS: "_rollouts.bin",
    SegmentType.XG_COMMENT: "_comments.bin",
    SegmentType.ZLIBARC_IDX: "_idx.bin",
    SegmentType.XG_UNKNOWN: None,
}

_FILEMAP: dict[str, SegmentType] = {
    "temp.xgi": SegmentType.XG_GAMEHDR,
    "temp.xgr": SegmentType.XG_ROLLOUTS,
    "temp.xgc": SegmentType.XG_COMMENT,
    "temp.xg": SegmentType.XG_GAMEFILE,
}

# Byte offset of the magic string "DMLI" inside temp.xg.
_XG_GAMEHDR_LEN = 556


# ---------------------------------------------------------------------------
# Segment object
# ---------------------------------------------------------------------------


@dataclass
class Segment:
    """One logical chunk extracted from an XG file.

    Attributes:
        seg_type:   Which part of the XG file this segment represents.
        filename:   Path to the backing temp file on disk (may be ``None``
                    before :meth:`create_temp_file` is called).
        fd:         Open file object for the backing temp file.
        extension:  File extension used when saving this segment to disk.
    """

    seg_type: SegmentType
    filename: Path | None = field(default=None, repr=False)
    fd: BinaryIO | None = field(default=None, repr=False)
    _autodelete: bool = field(default=True, repr=False)
    _prefix: str = field(default="tmpXGI", repr=False)

    @property
    def extension(self) -> str | None:
        return _EXTENSIONS.get(self.seg_type)

    # Context-manager support for auto-creating/deleting temp files.
    def __enter__(self) -> "Segment":
        self._create_temp_file()
        return self

    def __exit__(self, *_: object) -> None:
        self._close()

    def _create_temp_file(self, mode: str = "w+b") -> None:
        raw_fd, path_str = tempfile.mkstemp(prefix=self._prefix)
        self.filename = Path(path_str)
        self.fd = os.fdopen(raw_fd, mode)

    def _close(self) -> None:
        if self.fd is not None:
            try:
                self.fd.close()
            finally:
                self.fd = None
        if self._autodelete and self.filename is not None:
            self.filename.unlink(missing_ok=True)
            self.filename = None

    def copy_to(self, dest: str | Path) -> None:
        """Copy the backing temp file to *dest*."""
        if self.filename is None:
            raise RuntimeError("Segment has no backing file to copy.")
        shutil.copy(self.filename, dest)


# ---------------------------------------------------------------------------
# Top-level importer
# ---------------------------------------------------------------------------


class Import:
    """Parse an eXtreme Gammon ``.xg`` file and iterate over its segments."""

    def __init__(self, filename: str | Path) -> None:
        self.filename = Path(filename)

    def get_file_segments(self) -> Generator[Segment, None, None]:
        """Yield each :class:`Segment` found in the XG file in order.

        Segments are:

        1. The GDF header binary blob (always present).
        2. The thumbnail JPEG (present only when a thumbnail was saved).
        3. The game header (``temp.xgi``).
        4. The full game file (``temp.xg``).
        5. The rollout data (``temp.xgr``).
        6. The comments (``temp.xgc``).

        Each segment's backing temp file is valid for the duration of a single
        loop iteration.  Do **not** hold on to segment references across
        iterations — the file will be deleted.
        """
        with self.filename.open("rb") as xginfile:
            # --- GDF / RichGame outer header ---
            gdf_header = xgstruct.GameDataFormatHdrRecord.from_stream(xginfile)
            if gdf_header is None:
                raise Error("Not a game data format file", self.filename)

            with Segment(SegmentType.GDF_HDR) as seg:
                xginfile.seek(0)
                seg.fd.write(xginfile.read(gdf_header.header_size))  # type: ignore[union-attr]
                seg.fd.flush()
                yield seg

            # --- Embedded thumbnail JPEG (optional) ---
            if gdf_header.thumbnail_size > 0:
                with Segment(SegmentType.GDF_IMAGE) as seg:
                    xginfile.seek(gdf_header.thumbnail_offset, os.SEEK_CUR)
                    seg.fd.write(xginfile.read(gdf_header.thumbnail_size))  # type: ignore[union-attr]
                    seg.fd.flush()
                    yield seg

            # --- Zlib archive containing the four inner XG files ---
            archive = xgzarc.ZlibArchive(stream=xginfile)
            for file_rec in archive.arcregistry:
                seg_file, seg_path = archive.getarchivefile(file_rec)
                seg_type = _FILEMAP[file_rec.name]
                seg = Segment(
                    seg_type=seg_type,
                    filename=seg_path,
                    fd=seg_file,
                    _autodelete=False,
                )

                if seg_type is SegmentType.XG_GAMEFILE:
                    seg_file.seek(_XG_GAMEHDR_LEN)
                    magic = seg_file.read(4).decode("ascii", errors="replace")
                    if magic != "DMLI":
                        seg_file.close()
                        seg_path.unlink(missing_ok=True)
                        raise Error("Not a valid XG gamefile", self.filename)

                yield seg

                seg_file.close()
                seg_path.unlink(missing_ok=True)
