{
********************************* XG FILE FORMAT *********************************
(c) 2009-2014 GameSite 2000 Ltd;

This information can be freely redistributed

Last modification: 12/31/2013

A .XG file is a RichGameFormatfile using DirectX format (unfortunately abandoned by Microsoft after Vista).

Steps to read XG file:
1. Strip RichGameFormatfile.
  - Read the first Sizeof(RichGameHeader)
  - The 4 first byte should be RGMH (RM_MAGICNUMBER) if not, the file is invalid.
  - The content of the file is starting at SizeOf(TRichGameHeader) + RichGameHeader.dwThumbnailSize
  - Copy the remain data into "temp.xg"
  - Close the file.
  - Note: The thumbnail is a JPG that show the position selected at the time of saving
  
2. uncompress the file temp.xg
temp.xg can be uncompressed using ZLIB (see ZlibArchive unit)  4 files are generated
      temp.xg   // full game                            fixed size (2560 bytes) using TSaveRec 
      temp.xgi  // header (for fast information access) 1st record and Last record (TSaveRec) of temp.xg
      temp.xgr  // rollouts indexed in temp.xg          fixed size (2184 bytes) using TRolloutContext 
      temp.xgc  // comments indexed in temp.xg          text file using RTF format with CRLF to separate the
                                                        comments, after reading each line replace
                                                        #1#2 by #13#10 (CRLF)

3. Load the individual files

}

{ -------------- NOTES on PASCAL TYPES ------------------------
All data is stored using little-endian format
Pascal Syntax is not Case Senstive

**** INTEGERS *****
            SIZE  SIGNED  RANGE       
ShortInt    1     Yes     -128..127
byte        1     No       0..255

SmallInt    2     Yes     -32768..32767
Word        2     No       0..65535

Integer     4     Yes     -2147483648..2147483647
Dword       4     No       0..4294967295
Longword    4     No       0..4294967295

Int64       8     Yes     -2^63..2^63-1
UInt64      8     No       0..2^64-1


**** FLOATS *****
            SIZE  SIGNED  RANGE       
single      4     Yes     Single precision
double      8     Yes     Double Precision

**** STRINGS *****
                          SIZE      NOTES
char                      2         in recent version of Delphi, this is the Unicode double byte value of
                                    the character
WideChar                  2         same as char
AnsiChar                  1         ANSI char : #0 to #255

array [a..b] of widechar  (b-a+1)*2 #0 terminated string, typically a=0
array [a..b] of char      (b-a+1)*2 same as above
string[b]                 (b+1)     ANSI string, the 1st byte is the string length. it is NOT #0 terminated

**** MISC ****
          SIZE  NOTES
Boolean   1     0=false or 1=true stored in a byte.
TdateTime 8     Double precision Float, The integral part of a TDateTime value is the number of days that have
                passed since December 30, 1899. The fractional part of a TDateTime value is the time of day.
                Example 35065.541667 January 1, 1996; 1:00 P.M
Pointer   4     memory address, in 32 bits it is 4 bytes long, equivalent to Dword

**** RECORD ALIGNEMENT ****
array [a..b] of char    aligns on a 2 byte boundary
Smallint and word       aligns on a 2 byte boundary

integers and Single     aligns on a 4 byte boundary

Doubles and DateTime    aligns on a 8 byte boundary

Boolean                 does not align
byte and shortint       does not align
String[x]               does not align

example TsaveRec               Size Pad Start End
    Previous: Pointer;            4         0   3
    Next: Pointer;                4         4   7
    case EntryType: Typesave....  1         8   8
        SPlayer1,                41         9  49
        SPlayer2: string[40];    41        50  90
        MatchLength: integer;     4   1    92  95   //needs one byte padding to start on a multiple of 4
        Variation: integer;       4        96  99
        Crawford: Boolean;        1       100 100
        Jacoby: Boolean;          1       101 101
        Beaver: Boolean;          1       102 102
        AutoDouble: Boolean;      1       103 103
        Elo1: Double;             8       104 111   //no alignment needed as 104 is multiple of 8
        Elo2: Double;             8       112 119
        exp1: integer;            4       120 123
        exp2: integer;            4       124 127
        Date: TdateTime;          8       128 135
        SEvent: string[128];    129       136 264
        GameId: integer;          4   3   268 271   //needs 3 bytes padding to start on a multiple of 4
        ......................

}

const
  RM_MAXLENGTH = 1024;
  RM_MAGICNUMBER: Dword = $484D4752;                          // RGMH 
  
  MagicNumber = $494C4D44;                                    // DMLI (should have been reversed...)

type
  (* defined in windows unit
  TGUID = packed record
    D1: LongWord;
    D2: Word;
    D3: Word;
    D4: array[0..7] of Byte;
  end;
  *)

  TRichGameHeader = packed record                             // 8232 Bytes
    dwMagicNumber: Dword;                                     // $484D4752, RM_MAGICNUMBER
    dwHeaderVersion: Dword;                                   // version
    dwHeaderSize: Dword;                                      // size of the header
    liThumbnailOffset: int64;                                 // location of the thumbnail (jpg)
    dwThumbnailSize: Dword;                                   // size in bye of the thumbnail
    guidGameId: TGUID;                                        // game id
    szGameName: array [0 .. RM_MAXLENGTH - 1] of widechar;    // Unicode game name
    szSaveName: array [0 .. RM_MAXLENGTH - 1] of widechar;    // Unicode save name
    szLevelName: array [0 .. RM_MAXLENGTH - 1] of widechar;   // Unicode level name
    szComments: array [0 .. RM_MAXLENGTH - 1] of widechar;    // Unicode comments
  end;


Const
  SaveFileVersion    = 30;                                    // 28 is XG 2.00, 30 for 2.10
  MaxSaveFileVersion = 40;                                    // XG2 will refuse any version higher than this:
                                                              // i.e. compatibility is broken.

const
  tsNone = 0;
  tsFischer = 1;
  tsBronstein = 2;

type
  PositionEngine = array [0 .. 25] of ShortInt;
  //from the player on roll perspective: 0 is the opponent bar, 1 is the 1 point ... 25 if the player bar
  //0 means empty, negative #: mean opponent player, positive # means player's checkers.

  TResult = array [0 .. 6] of single; //lose bg, lose G, lose S, win S, win G, Win BG, normalized equity
  //28 Bytes

  TEvalLevel = record      // 4 Bytes
    Level: SmallInt;       // Level used see PLAYERLEVEL table
    isDouble: Boolean;     // The analyze assume double for the very next move
    Fill1: byte;           // filler
  end;

  TTimeSetting = record    // 32 bytes
    ClockType : integer;   // tsNone,tsFischer,tsBronstein
    PerGame   : Boolean;   // time is for session reset after each game
    Time1     : integer;   // initial time in sec
    Time2     : integer;   // time added (fisher) or reserved (Bronstein) per move in sec
    Penalty   : integer;   // point penalty when running out of time (in point)
    TimeLeft1 : integer;   // current time left
    TimeLeft2 : integer;   // current time left
    PenaltyMoney: integer; // point penalty when running out of time (in point)
  end;

  EngineStructBestMove = record                       // 2184 Bytes
    Pos: PositionEngine;                              // Current position
    Dice: array [1 .. 2] of integer;                  // Dice
    Level: integer;                                   // analyze level requested
    Score: array [1 .. 2] of integer;                 // current score
    Cube: integer;                                    // cube value 1,2,4, etc.
    CubePos: integer;                                 // 0: Center 1: Player owns cube -1 Opponent owns cube
    Crawford: integer;                                // 1 = Crawford   0 = No Crawford
    Jacoby: integer;                                  // 1 = Jacoby   0 = No Jacoby
    // Result:
    Nmoves: integer;                                  // number of move (max 32)
    PosPlayed: array [1 .. 32] of PositionEngine;     // position played
    Moves: array [1 .. 32, 1 .. 8] of ShortInt;       // move list as From1,dice1, from2,dice2 etc.. -1 show
                                                      // termination of list
    EvalLevel: array [1 .. 32] of TEvalLevel;         // evaluation level of each move
    Eval: array [1 .. 32, 0 .. 6] of single;          // evaluation values of each move
    Irrevalent: Boolean;                              // if 1 does not count as a decision
    met: ShortInt;                                    // unused
    Choice0: ShortInt;                                // 1-ply choice (index to PosPlayed)
    Choice3: ShortInt;                                // 3-ply choice (index to PosPlayed) 
  end;

  EngineStructDoubleAction = record                   // 132 Bytes
    Pos: PositionEngine;                              // Current position
    Level: integer;                                   // analyze level performed
    Score: array [1 .. 2] of integer;                 // current score
    Cube: integer;                                    // cube value 1,2,4, etc.
    CubePos: integer;                                 // 0: Center 1: Player owns cube -1 Opponent owns cube
    Jacoby: integer;                                  // 1 = Jacoby   0 = No Jacoby
    Crawford: SmallInt;                               // 1 = Crawford   0 = No Crawford
    met: SmallInt;                                    // unused
    // Result:
    FlagDouble: SmallInt;                             // 0: Don’t double 1: Double
    isBeaver: SmallInt;                               // is it a beaver if doubled
    Eval: array [0 .. 6] of single;                   // evaluation value for No double
    equB,                                             // equity No Double    
    equDouble,                                        // equity Double/take    
    equDrop: single;                                  // equity double/drop (-1)    
    LevelRequest: SmallInt;                           // analyze level requested
    DoubleChoice3: SmallInt;                          // 3-ply choice as double + take*2
    EvalDouble: array [0 .. 6] of single;             // evaluation value for Double/Take
  end;

  TShortUnicodeString = record                        //128 character long max, #0 termindate (size 258 Bytes)
  private
    Data: array [0 .. 128] of char;                   //char is the double byte Unicode
  public
    class operator Implicit(const sus: TShortUnicodeString): string; inline;
    class operator Implicit(const ws: string): TShortUnicodeString;  inline;
  end;


const
  inValid = 0;
  inError = 1;
  inInvalid = 2;

type
  Typesave = (                                             // Type of record     
      tsHeaderMatch                                        // Match header (only 1)
    , tsHeaderGame                                         // Game header    
    , tsCube                                               // Cube action
    , tsMove                                               // Checker play 
    , tsFooterGame                                         // Game footer 
    , tsFooterMatch                                        // Match footer
    , tsComment                                            // unused
    , tsMissing                                            // unused
  );

  TSaveRec = record                                        // 2560 Bytes
    Previous: Pointer;                                     // ignored for loading/saving
    Next: Pointer;                                         // ignored for loading/saving
    case EntryType: Typesave of                            // byte showing the type of record 0=tsHeaderMatch,
                                                           // 1=tsHeaderGame etc..
      tsHeaderMatch: (
        SPlayer1, SPlayer2: string[40];                    // player name in ANSI string for XG1 compatibility
                                                           // see "Player1" and "Player2" below for Unicode
        MatchLength: integer;                              // Match length, 99999 for unlimited
        Variation: integer;                                // 0: backgammon, 1: Nack, 2: Hyper, 3: Longgammon
        Crawford: Boolean;                                 // Crawford in use
        Jacoby: Boolean;                                   // Jacoby in use
        Beaver: Boolean;                                   // Beaver in use
        AutoDouble: Boolean;                               // Automatic double in use
        Elo1: Double;                                      // player1 Elo 
        Elo2: Double;                                      // player2 experience 
        exp1: integer;                                     // player1 Elo 
        exp2: integer;                                     // player2 experience 
        Date: TdateTime;                                   // game date 
        SEvent: string[128];                               // event name, in ANSI string for XG1 compatibility
                                                           // see "event" below for Unicode
        GameId: integer;                                   // game ID, if player are swapped GameID:=-GameID
        CompLevel1, CompLevel2: integer;                   // Player level: see PLAYERLEVEL table at the end
        CountForElo: Boolean;                              // outcome of the session will affect Elo
        AddtoProfile1: Boolean;                            // outcome of the session will affect player 1 profile
        AddtoProfile2: Boolean;                            // outcome of the session will affect player 2 profile
        SLocation: string[128];                            // location name, in ANSI string for XG1 compatibility
                                                           // see "location" below for Unicode
        GameMode: integer;                                 // game mode : see table at the end (GAMEMODE TABLE) 
        Imported: Boolean;                                 // game was imported from a site (MAT, CBG etc.)
        SRound: string[128];                               // round name, in ANSI string for XG1 compatibility
                                                           // see "round" below for Unicode
        Invert: integer;                                   // If the board is swap then invert=-invert
                                                           // and GameID:=-GameID
        version: integer;                                  // file version, currently SaveFileVersion    
        Magic: integer;                                    // must be MagicNumber = $494C4D44;       
        MoneyInitG: integer;                               // initial game played from the profile against that
                                                           // Opponent in money
        MoneyInitScore: array [1 .. 2] of integer;         // initial score from the profile against that
                                                           // opponent in money
        Entered: Boolean;                                  // entered in profile
        Counted: Boolean;                                  // already accounted in the profile Elo
        UnratedImp: Boolean;                               // game was unrated on the site it was imported from
        CommentHeaderMatch: integer;                       // index of the match comment header in temp.xgc              
        CommentFooterMatch: integer;                       // index of the match comment footer in temp.xgc   
        IsMoneyMatch: Boolean;                             // was player for real money
        WinMoney: single;                                  // amount of money for the winner
        LoseMoney: single;                                 // amount of money for the looser
        Currency: integer;                                 // currency code from Currency.ini (see table)
        FeeMoney: single;                                  // amount of rake 
        TableStake: single;                                // max amount that can be lost -- NOT IMPLEMENTED 
        SiteId: integer;                                   // site id from siteinfo.ini (see table at the end)
        CubeLimit: integer;                                // v8: maximum cube value    
        AutoDoubleMax: integer;                            // v8: maximum # of time the auto double can be used 
        Transcribed: Boolean;                              // v24: game was transcribed
        Event: TShortUnicodeString;                        // v24: Event name (Unicode)
        Player1: TShortUnicodeString;                      // v24: Player1 name (Unicode)            
        Player2: TShortUnicodeString;                      // v24: Player2 name (Unicode)
        Location: TShortUnicodeString;                     // v24: Location (Unicode)
        Round: TShortUnicodeString;                        // v24: Round (Unicode)
        TimeSetting: TTimeSetting;                         // v25: Time setting for the session
        TotTimeDelayMove: integer;                         // v26: # of checker play marked for delayed RO
        TotTimeDelayCube: integer;                         // v26: # of Cube marked for delayed RO
        TotTimeDelayMoveDone: integer;                     // v26: # of checker play marked for delayed RO Done
        TotTimeDelayCubeDone: integer;                     // v26: # of Cube action marked for delayed RO Done
        Transcriber: TShortUnicodeString;                  // v30: Name of the Transcriber (Unicode)
      );
      tsHeaderGame: (
        score1: integer;                                   // initial score player1 
        score2: integer;                                   // initial score player1 
        CrawfordApply: Boolean;                            // Does Crawford apply on that game
        PosInit: PositionEngine;                           // initial position 
        GameNumber: integer;                               // Game number (start at 1) 
        InProgress: Boolean;                               // Game is still in progress
        CommentHeaderGame: integer;                        // index of the game comment header in temp.xgc   
        CommentFooterGame: integer;                        // index of the game comment footer in temp.xgc   
        NumberOfAutoDouble: integer;                       // v26: Number of Auto double that happen in that game
                                                           // note that in the rest of the game the cube still
                                                           // start at 1. For display purpose or point
                                                           // calculation add 2^NumberOfAutoDouble
      );
      tsCube: (
        Actif: integer;                                    // Active player (1:player1, -1:player2)
        double: integer;                                   // player double (0= no, 1=yes)
        Take: integer;                                     // Opponent take (0= no, 1=yes, 2=beaver )
        BeaverR: integer;                                  // player accept beaver (0= no, 1=yes, 2=raccoon)
        RaccoonR: integer;                                 // player accept raccoon (0= no, 1=yes)
        CubeB: integer;                                    // Cube value 0=center, +1=2 own, +2=4 own ...
                                                           // -1=2 opp, -2=4 opp
        Position: PositionEngine;                          // initial position
        DoubleD: EngineStructDoubleAction;                 // Analyze result
        ErrCube: Double;                                   // error made on doubling (-1000 if not analyze)
        DiceRolled: string[2];                             // dice rolled
        ErrTake: Double;                                   // error made on taking (-1000 if not analyze)
        RolloutindexD: integer;                            // index of the Rollout in temp.xgr
        CompChoiceD: integer;                              // 3-ply choice as Double+2*take   
        AnalyzeC: integer;                                 // Level of the analyze           
        ErrBeaver: Double;                                 // error made on beavering (-1000 if not analyze)
        ErrRaccoon: Double;                                // error made on raccoonning (-1000 if not analyze)
        AnalyzeCR: integer;                                // requested Level of the analyze (sometime a XGR+
                                                           // request will stop at 4-ply when obvious)
        inValid: integer;                                  // invalid decision 0=Ok, 1=error, 2=invalid
        TutorCube: ShortInt;                               // player initial double in tutor mode (0= no, 1=yes)
        TutorTake: ShortInt;                               // player initial take in tutor mode (0= no, 1=yes)
        ErrTutorCube: Double;                              // error made on doubling (-1000 if not analyze)
        ErrTutorTake: Double;                              // error made on taking (-1000 if not analyze)
        FlaggedDouble: Boolean;                            // cube has been flagged
        CommentCube: integer;                              // index of the cube comment in temp.xgc
        EditedCube: Boolean;                               // v24: Position was edited at this point
        TimeDelayCube: Boolean;                            // v26: position is marked for later RO
        TimeDelayCubeDone: Boolean;                        // v26: position later RO has been done
        NumberOfAutoDoubleCube: integer;                   // v27: Number of Auto double that happen in that game
        TimeBot,TimeTop : integer;                         // v28: time left for both players
      );
      tsMove: (
        PositionI: PositionEngine;                         // Initial position
        PositionEnd: PositionEngine;                       // Final Position
        ActifP: integer;                                   // active player (1:player1, -1:player2)
        Moves: array [1 .. 8] of integer;                  // list of move as From1,dice1, from2,dice2 etc..
                                                           // -1 show termination of list
        Dice: array [1 .. 2] of integer;                   // dice rolled
        CubeA: integer;                                    // Cube value 0=center, +1=2 own, +2=4 own ...
                                                           // -1=2 opp, -2=4 opp
        ErrorM: Double;                                    // Not used anymore 
        NMoveEval: integer;                                // Number of candidate (max 32)
        DataMoves: EngineStructBestMove;                   // analyze
        Played: Boolean;                                   // move was played 
        ErrMove: Double;                                   // error made (-1000 if not analyze)
        ErrLuck: Double;                                   // luck of the roll
        CompChoice: integer;                               // computer choice (index to DataMoves.moveplayed)
        InitEq: Double;                                    // Equity before the roll (for luck purposes)
        RolloutindexM: array [1 .. 32] of integer;         // index of the Rollout in temp.xgr
        AnalyzeM: integer;                                 // level of analyze of the move
        AnalyzeL: integer;                                 // level of analyze for the luck
        InvalidM: integer;                                 // invalid decision 0=Ok, 1=error, 2=invalid
        PositionTutor: PositionEngine;                     // Position resulting of the initial move
        Tutor: ShortInt;                                   // index of the move played dataMoves.moveplayed
        ErrTutorMove: Double;                              // error initially made (-1000 if not analyze)
        Flagged: Boolean;                                  // move has been flagged
        CommentMove: integer;                              // index of the move comment in temp.xgc
        Editedmove: Boolean;                               // v24: Position was edited at this point
        TimeDelayMove: Dword;                              // v26: Bit list: position is marked for later RO
        TimeDelayMoveDone: Dword;                          // v26: Bit list: position later RO has been done
        NumberOfAutoDoubleMove: integer;                   // v27: Number of Auto double that happen in that game
        Filler: array [1 .. 4] of integer;                 // filler, ignore, should be set to 0
      );
      tsFooterGame: (
        Score1g: integer;                                  // Final score
        Score2g: integer;                                  // Final score
        CrawfordApplyg: Boolean;                           // will Crawford apply next game
        Winner: integer;                                   // who win +1=player1, -1 player 2
        Pointswon: integer;                                // point scored
        Termination: integer;                              // 0=Drop 1=single 2=gammon 3=Backgammon +100=Resign
                                                           // +1000 settle. For instance 102=Resign Gammon
        ErrResign: Double;                                 // error made by resigning (-1000 if not analyze)             
        ErrTakeResign: Double;                             // error made by accepting the resign
                                                           // (-1000 if not analyze)
        Eval: array [0 .. 6] of Double;                    // evaluation of the final position
        EvalLevel: integer;                                // level of analyze 
      );
      tsFooterMatch: (
        Score1m: integer;                                  // Final score of the match
        Score2m: integer;                                  // Final score of the match
        WinnerM: integer;                                  // who win +1=player1, -1 player 2
        Elo1m: Double;                                     // resulting Elo, player1
        Elo2m: Double;                                     // resulting Elo, player2
        exp1m: integer;                                    // resulting Exp, player1
        exp2m: integer;                                    // resulting Exp, player2
        Datem: TdateTime;                                  // Date time of the match end
      );
  end;

  TRolloutContext = record
    // inputs                                              // 2184 Bytes
    Truncated: Boolean;                                    // is truncated
    ErrorLimited: Boolean;                                 // stop when CI under "ErrorLimit"
    Truncate: integer;                                     // truncation level 
    MinRoll: integer;                                      // minimum games to roll
    ErrorLimit: Double;                                    // CI to stop the RO
    MaxRoll: integer;                                      // maximum games to roll
    Level1: integer;                                       // checker play Level used before "LevelCut"
    Level2: integer;                                       // checker play Level used on and after "LevelCut"
    LevelCut: integer;                                     // Cutoff for level1 and level2
    Variance: Boolean;                                     // use variance reduction
    Cubeless: Boolean;                                     // is a cubeless RO
    Time: Boolean;                                         // is time limited
    Level1C: integer;                                      // cube Level used before "LevelCut"
    Level2C: integer;                                      // cube Level used on and after "LevelCut"
    TimeLimit: Dword;                                      // limit in time (min)
    TruncateBO: integer;                                   // what to do when reaching BO db: 0=if dead cube,
                                                           // 1=Always, 2=Never
    RandomSeed: integer;                                   // calculated seed=RandomSeedI + hashpos
    RandomSeedI: integer;                                  // user entered seed
    RollBoth: Boolean;                                     // roll both line (ND and D/T)
    searchinterval: single;                                // Search interval used (1=normal, 1.5=large,
                                                           // 2=huge, 4=gigantic)
    met: integer;                                          // unused
    FirstRoll: Boolean;                                    // is it a first roll rollout
    DoDouble: Boolean;                                     // roll both line (ND and D/T) in multiple rollout
    Extent: Boolean;                                       // if the RO is extended

    // outputs
    Rolled: integer;                                       // games rolled
    DoubleFirst: Boolean;                                  // a double happens immediately.

    Sum1: array [0 .. 36] of double;                       // sum of equities for all 36 1st roll
    SumSquare1: array [0 .. 36] of double;                 // sum of square equities for all 36 1st roll
    Sum2: array [0 .. 36] of double;                       // D/T sum of equities for all 36 1st roll
    SumSquare2: array [0 .. 36] of double;                 // D/T sum of square equities for all 36 1st roll
    Stdev1: array [0 .. 36] of double;                     // Standard deviation for all 36 1st roll
    Stdev2: array [0 .. 36] of double;                     // D/T Stand deviation for all 36 1st roll
    RolledD: array [0 .. 36] of integer;                   // number of game rolled for all 36 1st roll
    Error1: single;                                        // 95% CI
    Error2: single;                                        // D/T 95% CI

    Result1: array [0 .. 6] of single;                     // evaluation of the position
    Result2: array [0 .. 6] of single;                     // D/T evaluation of the position
    Mwc1: single;                                          // ND  mwc equivalent of result1[1,6] 
    Mwc2: single;                                          // D/T mwc equivalent of result2[1,6] 

    PrevLevel: integer;                                    // store the prev. analyze level (for removing RO)
    PrevEval: array [0 .. 6] of single;                    // store the prev. analyze result (for removing RO)
    PrevND, PrevD: single;                                 // store the prev. analyze equities (for removing RO)

    Duration: single;                                      // duration in seconds

    // inputs
    LevelTrunc: integer;                                   // level used at truncation
    // outputs
    Rolled2: integer;                                      // D/T number of game rolled

    MultipleMin: integer;                                  // Multiple RO minimum # games
    MultipleStopAll: Boolean;                              // Multiple RO stop all if one move reach
                                                           // MultipleStopAllValue
    MultipleStopOne: Boolean;                              // Multiple RO stop one move is reach under
                                                           // MultipleStopOneValue
    MultipleStopAllValue: single;                          // value to stop all RO (for instance 99.9%)
    MultipleStopOneValue: single;                          // value to stop one move(for instance 0.01%)

    AsTake: Boolean;                                       // when running ND and D/T if AsTake is true, checker
                                                           // decisions are made using the cube position in the
                                                           // D/T line
    Rotation: integer;                                     // 0=36 dice, 1=21 dice (XG1), 2=30 dice (for 1st pos)
    UserInterrupted: Boolean;                              // RO was interrupted by user
    VerMaj: Word;                                          // Major version use for the RO, currently (2.10): 2
    VerMin: Word;                                          // Minor version use for the RO, currently (2.10): 10
                                                           // (no change in RO or engine between 2.10 and 2.20)
    Fixed: integer;                                        // unused=0
    Filler: array [1 .. 1] of integer;                     // unused=0
  end;

(*
PLAYERLEVEL TABLE
   0: 1-ply
   1: 2-ply
   2: 3-ply
  12: 3-ply red
   3: 4-ply
   4: 5-ply
   5: 6-ply
   6: 7-ply
 100: Rollout
1000: XGRoller
1001: XGRoller+
1002: XGRoller++

 999: Opening Book V1
 998: Opening Book V2

GAMEMODE TABLE
  0: Free
  1: Tutor
  2: Teaching
  3: Coaching
  4: Competition
  5: IronMan
  6: Custom
  
  
SITE ID
   0: GammonSite
   1: FIBS
   2: TrueMoney Games
   3: GridGammon
   4: DailyGammon
   5: NetGammon
   6: VOG
   7: Gammon Empire/Play65
   8: Club Games
   9: PartyGammon
  10: XcitingGames
  11: BGRoom
  12: DiceArena
  13: Safe Harbor Games
  14: GameAccount
  15: XG Mobile

CURRENCY ID
  0: Dollar
  1: Euro
  2: Sterling Pounds
  3: Japanese Yen
  4: Swiss Franc
  5: Canadian Dollar
  
*)


