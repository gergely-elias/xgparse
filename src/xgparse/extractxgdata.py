#
#   extractxgdata.py - Simple XG data extraction tool
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

import argparse
import pprint
from pathlib import Path

import xgimport
import xgstruct
import xgzarc


def _valid_directory(parser: argparse.ArgumentParser, path: str) -> Path:
    p = Path(path)
    if not p.is_dir():
        parser.error(f"Directory '{path}' does not exist")
    return p


def main() -> None:
    parser = argparse.ArgumentParser(
        description="XG data extraction utility",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-d",
        metavar="DIR",
        dest="outdir",
        help="Directory to write segments to (default: same directory as the import file)\n",
        type=lambda p: _valid_directory(parser, p),
        default=None,
    )
    parser.add_argument(
        "files",
        metavar="FILE",
        nargs="+",
        help="One or more .xg files to process",
    )
    args = parser.parse_args()

    for xg_path_str in args.files:
        xg_path = Path(xg_path_str)
        out_dir = args.outdir if args.outdir is not None else xg_path.parent
        stem = xg_path.stem

        try:
            importer = xgimport.Import(xg_path)
            print(f"Processing file: {xg_path}")
            file_version = -1

            for segment in importer.get_file_segments():
                if segment.extension is not None:
                    dest = (out_dir / stem).with_suffix("")
                    dest = out_dir / (stem + segment.extension)
                    segment.copy_to(dest)

                if segment.seg_type is xgimport.SegmentType.XG_GAMEFILE:
                    segment.fd.seek(0)
                    while True:
                        rec = xgstruct.read_game_record(
                            segment.fd, version=file_version
                        )
                        if rec is None:
                            break
                        if isinstance(rec, xgstruct.HeaderMatchEntry):
                            file_version = rec.version
                        if not isinstance(rec, xgstruct.UnimplementedEntry):
                            pprint.pprint(rec, width=160)

                elif segment.seg_type is xgimport.SegmentType.XG_ROLLOUTS:
                    segment.fd.seek(0)
                    while True:
                        rec = xgstruct.read_rollout_record(segment.fd)
                        if rec is None:
                            break
                        pprint.pprint(rec, width=160)

        except (xgimport.Error, xgzarc.Error) as exc:
            print(exc)


if __name__ == "__main__":
    main()
