#
#   convertxg.py - XG data to text conversion tool
#   Copyright (C) 2026  Gergely Elias <gergely.elias@gmail.com>
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

import pprint
from collections.abc import Generator

from . import xgimport
from . import xgstruct


def convert_xg_to_py_dataclasses(
    path: str,
) -> Generator[xgstruct.GameRecord | xgstruct.RolloutContextEntry, None, None]:
    """Yield parsed records from an XG file as dataclass objects.

    Produces the same sequence as :func:`convert_xg_to_text` but returns
    live dataclass instances instead of a text dump.  :class:`~xgstruct.UnimplementedEntry`
    records are skipped (matching the text-dump behaviour).  Rollout records
    are yielded after all game records.
    """
    importer = xgimport.Import(path)
    file_version = -1

    for segment in importer.get_file_segments():
        if segment.seg_type is xgimport.SegmentType.XG_GAMEFILE:
            segment.fd.seek(0)
            while True:
                rec = xgstruct.read_game_record(segment.fd, version=file_version)
                if rec is None:
                    break
                if isinstance(rec, xgstruct.HeaderMatchEntry):
                    file_version = rec.version
                if not isinstance(rec, xgstruct.UnimplementedEntry):
                    yield rec

        elif segment.seg_type is xgimport.SegmentType.XG_ROLLOUTS:
            segment.fd.seek(0)
            while True:
                rec = xgstruct.read_rollout_record(segment.fd)
                if rec is None:
                    break
                yield rec


def convert_xg_to_text(path: str) -> bytes:
    """Convert XG data to text format, returning the text as bytes."""
    output = [pprint.pformat(rec, width=160) for rec in convert_xg_to_py_dataclasses(path)]
    return "\n".join(output).encode("utf-8")
