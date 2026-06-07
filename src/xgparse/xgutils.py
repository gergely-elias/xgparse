#
#   xgutils.py - XG related utility functions
#   Copyright (C) 2013  Michael Petch <mpetch@gnubg.org>
#                                     <mpetch@capp-sysware.com>
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

import datetime
import zlib
from collections.abc import Sequence
from typing import BinaryIO


def streamcrc32(
    stream: BinaryIO,
    numbytes: int | None = None,
    startpos: int | None = None,
    blksize: int = 32768,
) -> int:
    """Compute CRC32 over a binary stream.

    Restores the original stream position when done.  When *numbytes* is
    ``None`` the entire remaining stream is consumed; otherwise exactly
    *numbytes* bytes are read starting from *startpos* (or the current
    position if *startpos* is ``None``).
    """
    crc = 0
    saved_pos = stream.tell()

    if startpos is not None:
        stream.seek(startpos)

    if numbytes is None:
        while chunk := stream.read(blksize):
            crc = zlib.crc32(chunk, crc)
    else:
        remaining = numbytes
        while remaining > 0:
            chunk = stream.read(min(blksize, remaining))
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
            remaining -= len(chunk)

    stream.seek(saved_pos)
    return crc & 0xFFFFFFFF


def utf16intarraytostr(intarray: Sequence[int]) -> str:
    """Convert a null-terminated array of UTF-16 code-unit integers to a str."""
    chars: list[str] = []
    for value in intarray:
        if value == 0:
            break
        chars.append(chr(value))
    return "".join(chars)


def delphidatetimeconv(delphi_datetime: float) -> datetime.datetime:
    """Convert a Delphi TDateTime float to a Python datetime.

    Delphi stores dates as a double whose integer part is the number of
    days since 30 December 1899 and whose fractional part is the fraction of
    a day elapsed (multiply by 86400 to get seconds).
    """
    delta = datetime.timedelta(
        days=int(delphi_datetime),
        seconds=int(86400 * (delphi_datetime % 1)),
    )
    return datetime.datetime(1899, 12, 30) + delta


def delphishortstrtostr(shortstring_bytes: Sequence[int]) -> str:
    """Convert a Delphi ShortString to a Python str.

    A Delphi ShortString is a length-prefixed ANSI byte string: the first
    byte holds the string length and the following bytes are the characters.
    The string is not null-terminated.
    """
    length = shortstring_bytes[0]
    return "".join(chr(b) for b in shortstring_bytes[1 : length + 1])
