#
#   xgstruct.py - classes to read XG file structures
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
#   This code is based upon Delphi data structures provided by
#   Xavier Dufaure de Citres <contact@extremegammon.com> for purposes
#   of interacting with the ExtremeGammon XG file formats. Field
#   descriptions derived from xg_format.pas. The file formats are
#   published at http://www.extremegammon.com/xgformat.aspx
#

from __future__ import annotations

import binascii
import os
import struct
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import BinaryIO

from . import xgutils

# Convenience alias used throughout: a 26-element signed-byte board position.
Position = tuple[int, ...]


# ---------------------------------------------------------------------------
# Helper: read an exact number of bytes or raise EOFError
# ---------------------------------------------------------------------------


def _read(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) < size:
        raise EOFError(f"Expected {size} bytes, got {len(data)}")
    return data


# ===========================================================================
# Outer container — the RichGame / GDF header
# ===========================================================================


@dataclass
class GameDataFormatHdrRecord:
    """The 8 232-byte Rich Game Format header that wraps every .xg file.

    Fields correspond to ``TRichGameHeader`` in ``xg_format.pas``.
    """

    SIZE = 8232

    magic_number: str = ""  # Must be "HMGR"
    header_version: int = 0  # Must be 1
    header_size: int = 0  # Byte length of this header
    thumbnail_offset: int = 0  # Offset to thumbnail JPEG (from end of header)
    thumbnail_size: int = 0  # Byte length of thumbnail JPEG; 0 = absent
    game_guid: str = ""  # Game GUID
    game_name: str = ""  # Unicode game name
    save_name: str = ""  # Unicode save name
    level_name: str = ""  # Unicode level name
    comments: str = ""  # Unicode comments

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> "GameDataFormatHdrRecord | None":
        """Return a populated instance, or ``None`` if the magic/version is wrong."""
        try:
            data = struct.unpack(
                "<4BiiQiLHHBB6s1024H1024H1024H1024H",
                stream.read(cls.SIZE),
            )
        except struct.error:
            return None

        magic = bytearray(data[0:4][::-1]).decode("ascii")
        if magic != "HMGR" or data[4] != 1:
            return None

        guid_p1, guid_p2, guid_p3, guid_p4, guid_p5 = data[8:13]
        guid_p6 = int(binascii.b2a_hex(data[13]), 16)
        game_guid = str(
            uuid.UUID(fields=(guid_p1, guid_p2, guid_p3, guid_p4, guid_p5, guid_p6))
        )

        return cls(
            magic_number=magic,
            header_version=data[4],
            header_size=data[5],
            thumbnail_offset=data[6],
            thumbnail_size=data[7],
            game_guid=game_guid,
            game_name=xgutils.utf16intarraytostr(data[14:1038]),
            save_name=xgutils.utf16intarraytostr(data[1038:2062]),
            level_name=xgutils.utf16intarraytostr(data[2062:3086]),
            comments=xgutils.utf16intarraytostr(data[3086:4110]),
        )


# ===========================================================================
# Sub-records embedded inside game records
# ===========================================================================


@dataclass
class TimeSettingRecord:
    """Clock settings stored inside a :class:`HeaderMatchEntry` (v25+)."""

    SIZE = 32

    clock_type: int = 0  # 0=None, 1=Fischer, 2=Bronstein
    per_game: bool = False  # Reset clock after each game
    time1: int = 0  # Initial time in seconds
    time2: int = 0  # Time added (Fischer) / reserved (Bronstein) per move
    penalty: int = 0  # Point penalty when time expires
    time_left1: int = 0  # Current time left, player 1
    time_left2: int = 0  # Current time left, player 2
    penalty_money: int = 0  # Monetary penalty when time expires

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> "TimeSettingRecord":
        d = struct.unpack("<lBxxxllllll", _read(stream, cls.SIZE))
        return cls(
            clock_type=d[0],
            per_game=bool(d[1]),
            time1=d[2],
            time2=d[3],
            penalty=d[4],
            time_left1=d[5],
            time_left2=d[6],
            penalty_money=d[7],
        )


@dataclass
class EvalLevelRecord:
    """Analysis level attached to each candidate move."""

    SIZE = 4

    level: int = 0  # See PLAYERLEVEL table in xg_format.pas
    is_double: bool = False  # Analysis assumes double on the next move

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> "EvalLevelRecord":
        d = struct.unpack("<hBb", _read(stream, cls.SIZE))
        return cls(level=d[0], is_double=bool(d[1]))


@dataclass
class EngineStructBestMoveRecord:
    """Full checker-play analysis for one position (``EngineStructBestMove``)."""

    SIZE = 2184

    pos: Position = field(default_factory=tuple)  # Current position (26 bytes)
    dice: tuple[int, int] = (0, 0)  # Dice values
    level: int = 0  # Analysis level requested
    score: tuple[int, int] = (0, 0)  # Match score
    cube: int = 0  # Cube value
    cube_pos: int = 0  # 0=centre, +1=owns, -1=opponent
    crawford: int = 0
    jacoby: int = 0
    n_moves: int = 0  # Number of candidates (max 32)
    pos_played: tuple[Position, ...] = field(default_factory=tuple)
    moves: tuple[tuple[int, ...], ...] = field(default_factory=tuple)
    eval_level: tuple[EvalLevelRecord, ...] = field(default_factory=tuple)
    eval: tuple[tuple[float, ...], ...] = field(default_factory=tuple)
    unused: int = 0
    met: int = 0
    choice0: int = 0  # 1-ply computer choice (index into pos_played)
    choice3: int = 0  # 3-ply computer choice

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> "EngineStructBestMoveRecord":
        d = struct.unpack("<26bxx2ll2llllll", _read(stream, 68))
        pos_played = tuple(
            struct.unpack("<26b", _read(stream, 26))[0:26] for _ in range(32)
        )
        moves = tuple(struct.unpack("<8b", _read(stream, 8))[0:8] for _ in range(32))
        eval_level = tuple(EvalLevelRecord.from_stream(stream) for _ in range(32))
        evals = tuple(struct.unpack("<7f", _read(stream, 28)) for _ in range(32))
        tail = struct.unpack("<bbbb", _read(stream, 4))

        return cls(
            pos=d[0:26],
            dice=(d[26], d[27]),
            level=d[28],
            score=(d[29], d[30]),
            cube=d[31],
            cube_pos=d[32],
            crawford=d[33],
            jacoby=d[34],
            n_moves=d[35],
            pos_played=pos_played,
            moves=moves,
            eval_level=eval_level,
            eval=evals,
            unused=tail[0],
            met=tail[1],
            choice0=tail[2],
            choice3=tail[3],
        )


@dataclass
class EngineStructDoubleAction:
    """Cube-decision analysis for one position (``EngineStructDoubleAction``)."""

    SIZE = 132

    pos: Position = field(default_factory=tuple)
    level: int = 0
    score: tuple[int, int] = (0, 0)
    cube: int = 0
    cube_pos: int = 0
    jacoby: int = 0
    crawford: int = 0
    met: int = 0
    flag_double: int = 0  # 0=don't double, 1=double
    is_beaver: int = 0
    eval_nd: tuple[float, ...] = field(default_factory=tuple)  # No-double equities
    equ_b: float = 0.0  # Equity: No Double
    equ_double: float = 0.0  # Equity: Double/Take
    equ_drop: float = 0.0  # Equity: Double/Drop (should be -1)
    level_request: int = 0
    double_choice3: int = 0  # 3-ply choice (Double + 2*Take)
    eval_double: tuple[float, ...] = field(
        default_factory=tuple
    )  # Double/Take equities

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> "EngineStructDoubleAction":
        d = struct.unpack("<26bxxl2llllhhhh7ffffhh7f", _read(stream, 132))
        return cls(
            pos=d[0:26],
            level=d[26],
            score=(d[27], d[28]),
            cube=d[29],
            cube_pos=d[30],
            jacoby=d[31],
            crawford=d[32],
            met=d[33],
            flag_double=d[34],
            is_beaver=d[35],
            eval_nd=d[36:43],
            equ_b=d[43],
            equ_double=d[44],
            equ_drop=d[45],
            level_request=d[46],
            double_choice3=d[47],
            eval_double=d[48:55],
        )


# ===========================================================================
# Game-file record types  (EntryType values in TSaveRec)
# ===========================================================================


class EntryType(IntEnum):
    HEADER_MATCH = 0
    HEADER_GAME = 1
    CUBE = 2
    MOVE = 3
    FOOTER_GAME = 4
    FOOTER_MATCH = 5
    COMMENT = 6  # unused by XG, treated as UnimplementedEntry
    MISSING = 7


# All TSaveRec records are padded to exactly this size on disk.
_SAVE_REC_SIZE = 2560


@dataclass
class HeaderMatchEntry:
    """Match metadata — the first record in every ``temp.xg`` file."""

    entry_type: EntryType = EntryType.HEADER_MATCH
    version: int = 0  # File format version; forward to all other records

    # ANSI (XG1 compatibility) player/event/location/round names
    s_player1: str = ""
    s_player2: str = ""
    s_event: str = ""
    s_location: str = ""
    s_round: str = ""

    match_length: int = 0  # 99999 = unlimited (money game)
    variation: int = 0  # 0=backgammon 1=Nack 2=Hyper 3=Longgammon
    crawford: bool = False
    jacoby: bool = False
    beaver: bool = False
    auto_double: bool = False
    elo1: float = 0.0
    elo2: float = 0.0
    exp1: int = 0
    exp2: int = 0
    date: str = ""
    game_id: int = 0
    comp_level1: int = -1  # See PLAYERLEVEL table
    comp_level2: int = -1
    count_for_elo: bool = False
    add_to_profile1: bool = False
    add_to_profile2: bool = False
    game_mode: int = 0  # See GAMEMODE table
    imported: bool = False
    invert: int = 0
    magic: int = 0x494C4D44
    money_init_g: int = 0
    money_init_score: tuple[int, int] = (0, 0)
    entered: bool = False
    counted: bool = False
    unrated_imp: bool = False
    comment_header_match: int = -1
    comment_footer_match: int = -1
    is_money_match: bool = False
    win_money: float = 0.0
    lose_money: float = 0.0
    currency: int = 0
    fee_money: float = 0.0
    table_stake: float = 0.0
    site_id: int = -1
    # v8+
    cube_limit: int = 0
    auto_double_max: int = 0
    # v24+
    transcribed: bool = False
    event: str = ""
    player1: str = ""
    player2: str = ""
    location: str = ""
    round: str = ""
    # v25+
    time_setting: TimeSettingRecord | None = None
    # v26+
    tot_time_delay_move: int = 0
    tot_time_delay_cube: int = 0
    tot_time_delay_move_done: int = 0
    tot_time_delay_cube_done: int = 0
    # v30+
    transcriber: str = ""

    @classmethod
    def from_stream(cls, stream: BinaryIO, version: int = 0) -> "HeaderMatchEntry":
        d = struct.unpack(
            "<9x41B41BxllBBBBddlld129BxxxlllBBB129BlB129BxxllLl2lBBBxllBxxxfflfll",
            _read(stream, 612),
        )
        obj = cls(version=version)
        obj.s_player1 = xgutils.delphishortstrtostr(d[0:41])
        obj.s_player2 = xgutils.delphishortstrtostr(d[41:82])
        obj.match_length = d[82]
        obj.variation = d[83]
        obj.crawford = bool(d[84])
        obj.jacoby = bool(d[85])
        obj.beaver = bool(d[86])
        obj.auto_double = bool(d[87])
        obj.elo1 = d[88]
        obj.elo2 = d[89]
        obj.exp1 = d[90]
        obj.exp2 = d[91]
        obj.date = str(xgutils.delphidatetimeconv(d[92]))
        obj.s_event = xgutils.delphishortstrtostr(d[93:222])
        obj.game_id = d[222]
        obj.comp_level1 = d[223]
        obj.comp_level2 = d[224]
        obj.count_for_elo = bool(d[225])
        obj.add_to_profile1 = bool(d[226])
        obj.add_to_profile2 = bool(d[227])
        obj.s_location = xgutils.delphishortstrtostr(d[228:357])
        obj.game_mode = d[357]
        obj.imported = bool(d[358])
        obj.s_round = xgutils.delphishortstrtostr(d[359:487])
        obj.invert = d[488]
        obj.version = d[489]
        obj.magic = d[490]
        obj.money_init_g = d[491]
        obj.money_init_score = (d[492], d[493])
        obj.entered = bool(d[494])
        obj.counted = bool(d[495])
        obj.unrated_imp = bool(d[496])
        obj.comment_header_match = d[497]
        obj.comment_footer_match = d[498]
        obj.is_money_match = bool(d[499])
        obj.win_money = d[500]
        obj.lose_money = d[501]
        obj.currency = d[502]
        obj.fee_money = d[503]
        obj.table_stake = d[504]
        obj.site_id = d[505]

        if obj.version >= 8:
            d2 = struct.unpack("<ll", _read(stream, 8))
            obj.cube_limit = d2[0]
            obj.auto_double_max = d2[1]

        if obj.version >= 24:
            d2 = struct.unpack("<Bx129H129H129H129H129H", _read(stream, 1292))
            obj.transcribed = bool(d2[0])
            obj.event = xgutils.utf16intarraytostr(d2[1:130])
            obj.player1 = xgutils.utf16intarraytostr(d2[130:259])
            obj.player2 = xgutils.utf16intarraytostr(d2[259:388])
            obj.location = xgutils.utf16intarraytostr(d2[388:517])
            obj.round = xgutils.utf16intarraytostr(d2[517:646])

        if obj.version >= 25:
            obj.time_setting = TimeSettingRecord.from_stream(stream)

        if obj.version >= 26:
            d2 = struct.unpack("<llll", _read(stream, 16))
            obj.tot_time_delay_move = d2[0]
            obj.tot_time_delay_cube = d2[1]
            obj.tot_time_delay_move_done = d2[2]
            obj.tot_time_delay_cube_done = d2[3]

        if obj.version >= 30:
            d2 = struct.unpack("<129H", _read(stream, 258))
            obj.transcriber = xgutils.utf16intarraytostr(d2[0:129])

        return obj


@dataclass
class HeaderGameEntry:
    """Per-game header — one instance per game inside ``temp.xg``."""

    entry_type: EntryType = EntryType.HEADER_GAME
    version: int = 0

    score1: int = 0  # Player 1 score at game start
    score2: int = 0  # Player 2 score at game start
    crawford_apply: bool = False  # Crawford rule applies to this game
    pos_init: Position = field(default_factory=lambda: (0,) * 26)
    game_number: int = 0  # 1-based
    in_progress: bool = False
    comment_header_game: int = -1
    comment_footer_game: int = -1
    # v26+
    number_of_auto_doubles: int = 0

    @classmethod
    def from_stream(cls, stream: BinaryIO, version: int = 0) -> "HeaderGameEntry":
        d = struct.unpack("<9xxxxllB26bxlBxxxlll", _read(stream, 68))
        obj = cls(version=version)
        obj.score1 = d[0]
        obj.score2 = d[1]
        obj.crawford_apply = bool(d[2])
        obj.pos_init = d[3:29]
        obj.game_number = d[29]
        obj.in_progress = bool(d[30])
        obj.comment_header_game = d[31]
        obj.comment_footer_game = d[32]
        if version >= 26:
            obj.number_of_auto_doubles = d[33]
        return obj


@dataclass
class CubeEntry:
    """A cube-decision record (double / take / beaver / raccoon)."""

    entry_type: EntryType = EntryType.CUBE
    version: int = 0

    active_p: int = 0  # Active player (1 or 2)
    double: int = 0  # 0=no double, 1=doubled
    take: int = 0  # 0=no, 1=take, 2=beaver
    beaver_r: int = 0  # 0=no, 1=accept, 2=raccoon
    raccoon_r: int = 0
    cube_b: int = 0  # Cube level: 0=centre, +n=2^n own, -n=2^n opponent
    position: Position = field(default_factory=tuple)
    doubled: EngineStructDoubleAction | None = None
    err_cube: float = 0.0  # Error on doubling (-1000 = not analysed)
    dice_rolled: str = ""
    err_take: float = 0.0
    rollout_index_d: int = 0
    comp_choice_d: int = 0
    analyze_c: int = 0
    err_beaver: float = 0.0
    err_raccoon: float = 0.0
    analyze_cr: int = 0
    is_valid: int = 0
    tutor_cube: int = 0
    tutor_take: int = 0
    err_tutor_cube: float = 0.0
    err_tutor_take: float = 0.0
    flagged_double: bool = False
    comment_cube: int = -1
    # v24+
    edited_cube: bool = False
    # v26+
    time_delay_cube: bool = False
    time_delay_cube_done: bool = False
    # v27+
    number_of_auto_double_cube: int = 0
    # v28+
    time_bot: int = 0
    time_top: int = 0

    @classmethod
    def from_stream(cls, stream: BinaryIO, version: int = 0) -> "CubeEntry":
        d = struct.unpack("<9xxxxllllll26bxx", _read(stream, 64))
        obj = cls(version=version)
        obj.active_p = d[0]
        obj.double = d[1]
        obj.take = d[2]
        obj.beaver_r = d[3]
        obj.raccoon_r = d[4]
        obj.cube_b = d[5]
        obj.position = d[6:32]
        obj.doubled = EngineStructDoubleAction.from_stream(stream)

        d2 = struct.unpack(
            "<xxxxd3BxxxxxdlllxxxxddllbbxxxxxxddBxxxlBBBxlll",
            _read(stream, 116),
        )
        obj.err_cube = d2[0]
        obj.dice_rolled = xgutils.delphishortstrtostr(d2[1:4])
        obj.err_take = d2[4]
        obj.rollout_index_d = d2[5]
        obj.comp_choice_d = d2[6]
        obj.analyze_c = d2[7]
        obj.err_beaver = d2[8]
        obj.err_raccoon = d2[9]
        obj.analyze_cr = d2[10]
        obj.is_valid = d2[11]
        obj.tutor_cube = d2[12]
        obj.tutor_take = d2[13]
        obj.err_tutor_cube = d2[14]
        obj.err_tutor_take = d2[15]
        obj.flagged_double = bool(d2[16])
        obj.comment_cube = d2[17]

        if version >= 24:
            obj.edited_cube = bool(d2[18])
        if version >= 26:
            obj.time_delay_cube = bool(d2[19])
            obj.time_delay_cube_done = bool(d2[20])
        if version >= 27:
            obj.number_of_auto_double_cube = d2[21]
        if version >= 28:
            obj.time_bot = d2[22]
            obj.time_top = d2[23]

        return obj


@dataclass
class MoveEntry:
    """A checker-play record."""

    entry_type: EntryType = EntryType.MOVE
    version: int = 0

    position_i: Position = field(default_factory=tuple)  # Before the move
    position_end: Position = field(default_factory=tuple)  # After the move
    active_p: int = 0
    moves: tuple[int, ...] = field(default_factory=tuple)  # From1,die1,… –1=terminator
    dice: tuple[int, int] = (0, 0)
    cube_a: int = 0
    error_m: float = 0.0  # Unused
    n_move_eval: int = 0
    data_moves: EngineStructBestMoveRecord | None = None
    played: bool = False
    err_move: float = 0.0  # Checker-play error (-1000 = not analysed)
    err_luck: float = 0.0
    comp_choice: int = 0
    init_eq: float = 0.0
    rollout_index_m: tuple[int, ...] = field(default_factory=tuple)
    analyze_m: int = 0
    analyze_l: int = 0
    invalid_m: int = 0
    position_tutor: Position = field(default_factory=tuple)
    tutor: int = 0
    err_tutor_move: float = 0.0
    flagged: bool = False
    comment_move: int = -1
    # v24+
    edited_move: bool = False
    # v26+
    time_delay_move: int = 0
    time_delay_move_done: int = 0
    # v27+
    number_of_auto_double_move: int = 0

    @classmethod
    def from_stream(cls, stream: BinaryIO, version: int = 0) -> "MoveEntry":
        d = struct.unpack("<9x26b26bxxxl8l2lldl", _read(stream, 124))
        obj = cls(version=version)
        obj.position_i = d[0:26]
        obj.position_end = d[26:52]
        obj.active_p = d[52]
        obj.moves = d[53:61]
        obj.dice = (d[61], d[62])
        obj.cube_a = d[63]
        obj.error_m = d[64]
        obj.n_move_eval = d[65]
        obj.data_moves = EngineStructBestMoveRecord.from_stream(stream)

        d2 = struct.unpack("<Bxxxddlxxxxd32llll26bbxdBxxxl", _read(stream, 220))
        obj.played = bool(d2[0])
        obj.err_move = d2[1]
        obj.err_luck = d2[2]
        obj.comp_choice = d2[3]
        obj.init_eq = d2[4]
        obj.rollout_index_m = d2[5:37]
        obj.analyze_m = d2[37]
        obj.analyze_l = d2[38]
        obj.invalid_m = d2[39]
        obj.position_tutor = d2[40:66]
        obj.tutor = d2[66]
        obj.err_tutor_move = d2[67]
        obj.flagged = bool(d2[68])
        obj.comment_move = d2[69]

        if version >= 24:
            obj.edited_move = bool(struct.unpack("<B", _read(stream, 1))[0])
        if version >= 26:
            d3 = struct.unpack("<xxxLL", _read(stream, 11))
            obj.time_delay_move = d3[0]
            obj.time_delay_move_done = d3[1]
        if version >= 27:
            obj.number_of_auto_double_move = struct.unpack("<l", _read(stream, 4))[0]

        return obj


@dataclass
class FooterGameEntry:
    """End-of-game summary record."""

    entry_type: EntryType = EntryType.FOOTER_GAME
    version: int = 0

    score1g: int = 0
    score2g: int = 0
    crawford_applyg: bool = False
    winner: int = 0  # +1=player1, -1=player2
    points_won: int = 0
    termination: int = (
        0  # 0=drop 1=single 2=gammon 3=backgammon +100=resign +1000=settle
    )
    err_resign: float = 0.0
    err_take_resign: float = 0.0
    eval: tuple[float, ...] = field(default_factory=tuple)
    eval_level: int = 0

    @classmethod
    def from_stream(cls, stream: BinaryIO, version: int = 0) -> "FooterGameEntry":
        d = struct.unpack("<9xxxxllBxxxlllxxxxdd7dl", _read(stream, 116))
        return cls(
            version=version,
            score1g=d[0],
            score2g=d[1],
            crawford_applyg=bool(d[2]),
            winner=d[3],
            points_won=d[4],
            termination=d[5],
            err_resign=d[6],
            err_take_resign=d[7],
            eval=d[8:15],
            eval_level=d[15],
        )


@dataclass
class FooterMatchEntry:
    """End-of-match summary record."""

    entry_type: EntryType = EntryType.FOOTER_MATCH
    version: int = 0

    score1m: int = 0
    score2m: int = 0
    winner_m: int = 0
    elo1m: float = 0.0
    elo2m: float = 0.0
    exp1m: int = 0
    exp2m: int = 0
    datem: str = ""

    @classmethod
    def from_stream(cls, stream: BinaryIO, version: int = 0) -> "FooterMatchEntry":
        d = struct.unpack("<9xxxxlllddlld", _read(stream, 56))
        return cls(
            version=version,
            score1m=d[0],
            score2m=d[1],
            winner_m=d[2],
            elo1m=d[3],
            elo2m=d[4],
            exp1m=d[5],
            exp2m=d[6],
            datem=str(xgutils.delphidatetimeconv(d[7])),
        )


@dataclass
class MissingEntry:
    """Placeholder for a missing / unknown position."""

    entry_type: EntryType = EntryType.MISSING
    version: int = 0

    missing_err_luck: float = 0.0
    missing_winner: int = 0
    missing_points: int = 0

    @classmethod
    def from_stream(cls, stream: BinaryIO, version: int = 0) -> "MissingEntry":
        d = struct.unpack("<9xxxxxxxxdll", _read(stream, 32))
        return cls(
            version=version,
            missing_err_luck=d[0],
            missing_winner=d[1],
            missing_points=d[2],
        )


@dataclass
class UnimplementedEntry:
    """Catch-all for record types not yet parsed."""

    entry_type: EntryType = EntryType.COMMENT
    version: int = 0

    @classmethod
    def from_stream(cls, stream: BinaryIO, version: int = 0) -> "UnimplementedEntry":
        return cls(version=version)


# Union type for all possible game-file record payloads.
GameRecord = (
    HeaderMatchEntry
    | HeaderGameEntry
    | CubeEntry
    | MoveEntry
    | FooterGameEntry
    | FooterMatchEntry
    | MissingEntry
    | UnimplementedEntry
)

# Maps the raw EntryType byte to the appropriate dataclass.
_RECORD_CLASSES: dict[EntryType, type[GameRecord]] = {
    EntryType.HEADER_MATCH: HeaderMatchEntry,
    EntryType.HEADER_GAME: HeaderGameEntry,
    EntryType.CUBE: CubeEntry,
    EntryType.MOVE: MoveEntry,
    EntryType.FOOTER_GAME: FooterGameEntry,
    EntryType.FOOTER_MATCH: FooterMatchEntry,
    EntryType.COMMENT: UnimplementedEntry,
    EntryType.MISSING: MissingEntry,
}

_SAVE_REC_HDR_SIZE = 9  # 8 unused bytes + 1 EntryType byte


def read_game_record(stream: BinaryIO, version: int = -1) -> GameRecord | None:
    """Read one ``TSaveRec`` from *stream* and return the parsed record.

    Returns ``None`` at end-of-file.  The *version* must be the value read
    from the preceding :class:`HeaderMatchEntry`; pass ``-1`` before the
    first header is encountered.

    The function always advances the stream to the start of the next record
    (records are padded to exactly 2 560 bytes on disk).
    """
    start_pos = stream.tell()
    raw = stream.read(_SAVE_REC_HDR_SIZE)
    if len(raw) < _SAVE_REC_HDR_SIZE:
        return None

    entry_type = EntryType(struct.unpack("<8xB", raw)[0])
    stream.seek(-_SAVE_REC_HDR_SIZE, os.SEEK_CUR)

    cls = _RECORD_CLASSES[entry_type]
    record: GameRecord = cls.from_stream(stream, version=version)

    # Pad to the fixed record size.
    consumed = stream.tell() - start_pos
    stream.seek(_SAVE_REC_SIZE - consumed, os.SEEK_CUR)

    return record


# ===========================================================================
# Rollout file  (temp.xgr)
# ===========================================================================


@dataclass
class RolloutContextEntry:
    """One ``TRolloutContext`` record from ``temp.xgr``."""

    SIZE = 2184

    version: int = 0

    # Inputs
    truncated: bool = False
    error_limited: bool = False
    truncate: int = 0
    min_roll: int = 0
    error_limit: float = 0.0
    max_roll: int = 0
    level1: int = 0
    level2: int = 0
    level_cut: int = 0
    variance: bool = False
    cubeless: bool = False
    time: bool = False
    level1c: int = 0
    level2c: int = 0
    time_limit: int = 0
    truncate_bo: int = 0
    random_seed: int = 0
    random_seed_i: int = 0
    roll_both: bool = False
    search_interval: float = 0.0
    met: int = 0
    first_roll: bool = False
    do_double: bool = False
    extent: bool = False

    # Outputs
    rolled: int = 0
    double_first: bool = False
    sum1: tuple[float, ...] = field(default_factory=tuple)
    sum_square1: tuple[float, ...] = field(default_factory=tuple)
    sum2: tuple[float, ...] = field(default_factory=tuple)
    sum_square2: tuple[float, ...] = field(default_factory=tuple)
    stdev1: tuple[float, ...] = field(default_factory=tuple)
    stdev2: tuple[float, ...] = field(default_factory=tuple)
    rolled_d: tuple[int, ...] = field(default_factory=tuple)
    error1: float = 0.0
    error2: float = 0.0
    result1: tuple[float, ...] = field(default_factory=tuple)
    result2: tuple[float, ...] = field(default_factory=tuple)
    mwc1: float = 0.0
    mwc2: float = 0.0
    prev_level: int = 0
    prev_eval: tuple[float, ...] = field(default_factory=tuple)
    prev_nd: float = 0.0
    prev_d: float = 0.0
    duration: float = 0.0
    level_trunc: int = 0
    rolled2: int = 0
    multiple_min: int = 0
    multiple_stop_all: bool = False
    multiple_stop_one: bool = False
    multiple_stop_all_value: float = 0.0
    multiple_stop_one_value: float = 0.0
    as_take: bool = False
    rotation: int = 0
    user_interrupted: bool = False
    ver_maj: int = 0
    ver_min: int = 0

    @classmethod
    def from_stream(cls, stream: BinaryIO, version: int = 0) -> "RolloutContextEntry":
        d = struct.unpack(
            "<BBxxllxxxxdllllBBBxllLlllBxxx"
            "flBBBxlBxxxxxxx37d37d37d37d37d37d37l"
            "ff7f7fffl7fllllllBBxxffBxxxlBxHH",
            _read(stream, 2174),
        )
        return cls(
            version=version,
            truncated=bool(d[0]),
            error_limited=bool(d[1]),
            truncate=d[2],
            min_roll=d[3],
            error_limit=d[4],
            max_roll=d[5],
            level1=d[6],
            level2=d[7],
            level_cut=d[8],
            variance=bool(d[9]),
            cubeless=bool(d[10]),
            time=bool(d[11]),
            level1c=d[12],
            level2c=d[13],
            time_limit=d[14],
            truncate_bo=d[15],
            random_seed=d[16],
            random_seed_i=d[17],
            roll_both=bool(d[18]),
            search_interval=d[19],
            met=d[20],
            first_roll=bool(d[21]),
            do_double=bool(d[22]),
            extent=bool(d[23]),
            rolled=d[24],
            double_first=bool(d[25]),
            sum1=d[26:63],
            sum_square1=d[63:100],
            sum2=d[100:137],
            sum_square2=d[137:174],
            stdev1=d[174:211],
            stdev2=d[211:248],
            rolled_d=d[248:285],
            error1=d[285],
            error2=d[286],
            result1=d[287:294],
            result2=d[294:301],
            mwc1=d[301],
            mwc2=d[302],
            prev_level=d[303],
            prev_eval=d[304:311],
            prev_nd=d[311],
            prev_d=d[312],
            duration=d[313],
            level_trunc=d[314],
            rolled2=d[315],
            multiple_min=d[316],
            multiple_stop_all=bool(d[317]),
            multiple_stop_one=bool(d[318]),
            multiple_stop_all_value=d[319],
            multiple_stop_one_value=d[320],
            as_take=bool(d[321]),
            rotation=d[322],
            user_interrupted=bool(d[323]),
            ver_maj=d[324],
            ver_min=d[325],
        )


_ROLLOUT_REC_SIZE = 2184


def read_rollout_record(
    stream: BinaryIO, version: int = 0
) -> RolloutContextEntry | None:
    """Read one rollout record from *stream*.

    Returns ``None`` at end-of-file.  Records are padded to exactly 2 184 bytes.
    """
    start_pos = stream.tell()
    probe = stream.read(1)
    if not probe:
        return None
    stream.seek(-1, os.SEEK_CUR)

    record = RolloutContextEntry.from_stream(stream, version=version)
    consumed = stream.tell() - start_pos
    stream.seek(_ROLLOUT_REC_SIZE - consumed, os.SEEK_CUR)
    return record
