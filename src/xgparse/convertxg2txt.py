#
#   convertxg2txt.py - XG data to text conversion tool
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

from . import xgimport
from . import xgstruct


def convert_xg_to_text(path: str) -> bytes:
    """Convert XG data to text format, returning the text as bytes."""
    importer = xgimport.Import(path)
    output = []
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
                    output.append(pprint.pformat(rec, width=160))

        elif segment.seg_type is xgimport.SegmentType.XG_ROLLOUTS:
            segment.fd.seek(0)
            while True:
                rec = xgstruct.read_rollout_record(segment.fd)
                if rec is None:
                    break
                output.append(pprint.pformat(rec, width=160))

    return "\n".join(output).encode("utf-8")
