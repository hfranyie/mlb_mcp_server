# main.py
from __future__ import annotations

from typing import Optional, Any, Union, Dict, List, Iterable
from datetime import datetime
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
import statsapi
import logging
import re
import asyncio


# Load environment variables from .env file
load_dotenv()

# Initialize logging for the server
logging.basicConfig(level=logging.INFO)

# Initialize FastMCP server
mcp = FastMCP("mlb-mcp-server")

_VALID_PLAYER_POOLS = {"all", "qualified", "rookies"}
_ALLOWED_GROUPS = {"hitting", "pitching", "fielding"}
_FORMATTABLE_TYPES = {"career", "season"}  # statsapi.player_stats supports these
_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")

# HELPERS
def _to_league_str(leagueID: Optional[Union[List[int], str]]) -> Optional[str]:
    if leagueID is None:
        return None
    if isinstance(leagueID, str):
        return leagueID  # assume already like "103,104" or "104"
    return ",".join(str(x) for x in leagueID)


def _to_multi_str(val: Optional[Iterable[str] | str]) -> Optional[str]:
    """Accept list like ['hitting','pitching'] or 'hitting,pitching' → '[hitting,pitching]'."""
    if val is None:
        return None
    if isinstance(val, str):
        items = [x.strip() for x in val.strip("[] ").split(",") if x.strip()]
    else:
        items = [str(x).strip() for x in val if str(x).strip()]
    if not items:
        return None
    return f"[{','.join(items)}]"


def _parse_multi(val: Optional[str]) -> List[str]:
    if not val:
        return []
    return [x.strip() for x in val.strip("[] ").split(",") if x.strip()]


def _ensure_season(season: Optional[int]) -> int:
    return season if season is not None else datetime.now().year


def _to_list(cats: Union[str, List[str], None]) -> List[str]:
    if cats is None:
        raise ValueError("leaderCategories is required (e.g., 'walks').")
    return [cats] if isinstance(cats, str) else list(cats)


##Tools
@mcp.tool(name="date")
async def date():
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

@mcp.tool(name="boxscore")
async def boxscore_data(
    gamePk: Optional[int] = None,
    battingBox: Optional[bool] = False,
    fieldingInfo: Optional[bool] = False,
    pichitingBox: Optional[bool] = False,
    gameInfo: Optional[bool] = False,
    timeCode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Description:
        Get a formatted boxscore for a given game.
        Use this tool to get boxscore information for a specific game.
        You can specify the game ID, time code, and whether to include batting and fielding information.

    Args:
        gamePk: MLB game ID
        timeCode: Time code for the boxscore (e.g., 'h' for hitting, 'p' for pitching)
        battingBox: Whether to include batting box information
        fieldingInfo: Whether to include fielding information
        pichitingBox: Whether to include pitching box information

    Returns:
        Dictionary with "boxscore" key containing boxscore information.
        Each boxscore contains:
        - Basic info: game_id, game_date, game_datetime, status
        - Teams: away_name, home_name, away_id, home_id
        - Scores: away_score, home_score, winning/losing teams
        - Pitchers: probable starters, winning/losing/save pitchers with notes
        - Venue: venue_id, venue_name
        - Broadcast: national_broadcasts list
        - Game context: doubleheader status, game_num, series_status
        - Live game info: current_inning, inning_state
        - Summary: formatted game summary string

    Examples:
        - Print the full box score for Phillies @ Mets game on 4/24/2019 (gamePk=565997):
            - print( statsapi.boxscore(565997) )
    Output:
        ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------
        Phillies Batters                         AB   R   H  RBI BB   K  LOB AVG   OPS  | Mets Batters                             AB   R   H  RBI BB   K  LOB AVG   OPS
        ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------
        1 McCutchen  LF                           5   0   1   0   0   1   3  .250 .830  | 1 McNeil  LF                              4   0   1   0   0   0   1  .363 .928
        2 Realmuto  C                             3   1   1   0   1   1   2  .282 .786  | 2 Conforto  RF                            3   0   0   0   1   1   1  .292 .986
        3 Harper  RF                              4   1   1   1   1   3   4  .261 .909  | 3 Canó  2B                                3   0   3   0   1   0   0  .272 .758
        4 Hoskins  1B                             4   2   2   2   1   1   3  .273 .982  | 4 Ramos, W  C                             4   0   0   0   0   3   6  .278 .687
        5 Franco  3B                              5   1   1   1   0   0   3  .271 .905  | 5 Smith, Do  1B                           2   0   0   0   1   1   2  .400 .996
        6 Hernández, C  2B                        5   1   1   0   0   1   2  .267 .730  |     c-Alonso, P  1B                       1   0   0   0   0   1   1  .306 1.086
        7 Rodríguez, S  SS                        4   0   1   0   0   1   1  .250 .750  | 6 Frazier, T  3B                          3   0   0   0   0   0   4  .182 .705
        8 Velasquez  P                            1   0   0   0   0   0   0  .167 .453  | 7 Rosario, A  SS                          4   0   1   0   0   0   1  .261 .676
            a-Williams, N  PH                     1   0   0   0   0   0   1  .150 .427  | 8 Lagares  CF                             2   0   0   0   0   1   1  .244 .653
            Neshek  P                             0   0   0   0   0   0   0  .000 .000  |     a-Nimmo  CF                           2   0   0   0   0   0   1  .203 .714
            Domínguez  P                          0   0   0   0   0   0   0  .000 .000  | 9 Vargas  P                               2   0   0   0   0   1   1  .000 .000
            b-Gosselin  PH                        1   0   1   1   0   0   0  .211 .474  |     Lugo, S  P                            0   0   0   0   0   0   0  .000 .000
            Morgan  P                             0   0   0   0   0   0   0  .000 .000  |     Zamora  P                             0   0   0   0   0   0   0  .000 .000
            c-Knapp  PH                           1   0   0   0   0   1   1  .222 .750  |     b-Guillorme  PH                       1   0   1   0   0   0   0  .167 .378
            Nicasio  P                            0   0   0   0   0   0   0  .000 .000  |     Gsellman  P                           0   0   0   0   0   0   0  .000 .000
        9 Quinn  CF                               4   0   1   1   0   1   1  .120 .305  |     Rhame  P                              0   0   0   0   0   0   0  .000 .000
            1-Altherr  CF                         0   0   0   0   0   0   0  .042 .163  |     d-Davis, J  PH                        1   0   0   0   0   1   0  .276 .865
        ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------
        Totals                                   38   6  10   6   3  10  21             | Totals                                   32   0   6   0   3   9  19
        ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------
        a-Popped out for Velasquez in the 6th.                                          | a-Flied out for Lagares in the 6th.
        b-Singled for Domínguez in the 8th.                                             | b-Singled for Zamora in the 7th.
        c-Struck out for Morgan in the 9th.                                             | c-Struck out for Smith, Do in the 8th.
        1-Ran for Quinn in the 8th.                                                     | d-Struck out for Rhame in the 9th.
                                                                                        |
        BATTING                                                                         | BATTING
        2B: Harper (7, Vargas); Rodríguez, S (1, Rhame); Realmuto (4, Vargas).          | TB: Canó 3; Guillorme; McNeil; Rosario, A.
        3B: Hoskins (1, Gsellman).                                                      | Runners left in scoring position, 2 out: Frazier, T 2; Vargas; Smith, Do 2.
        HR: Hoskins (7, 9th inning off Rhame, 1 on, 0 out).                             | GIDP: McNeil.
        TB: Franco; Gosselin; Harper 2; Hernández, C; Hoskins 7; McCutchen; Quinn;      | Team RISP: 0-for-6.
            Realmuto 2; Rodríguez, S 2.                                                 | Team LOB: 9.
        RBI: Franco (19); Gosselin (4); Harper (15); Hoskins 2 (20); Quinn (1).         |
        Runners left in scoring position, 2 out: Hoskins; Hernández, C; Knapp; Realmuto | FIELDING
            2; McCutchen.                                                               | E: Canó (3, fielding); Rosario, A 2 (7, throw, throw).
        SAC: Rodríguez, S; Velasquez.                                                   |
        Team RISP: 4-for-13.                                                            |
        Team LOB: 11.                                                                   |
                                                                                        |
        FIELDING                                                                        |
        DP: (Hernández, C-Rodríguez, S-Hoskins).                                        |
        ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------
        ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------
        Phillies Pitchers                            IP   H   R  ER  BB   K  HR   ERA   | Mets Pitchers                                IP   H   R  ER  BB   K  HR   ERA
        ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------
        Velasquez  (W, 1-0)                         5.0   3   0   0   3   6   0   1.99  | Vargas  (L, 1-1)                            4.2   3   1   1   2   4   0   7.20
        Neshek  (H, 2)                              1.0   1   0   0   0   0   0   2.70  | Lugo, S                                     2.0   0   0   0   0   2   0   4.60
        Domínguez  (H, 3)                           1.0   1   0   0   0   0   0   4.32  | Zamora                                      0.1   0   0   0   0   1   0   0.00
        Morgan                                      1.0   1   0   0   0   2   0   0.00  | Gsellman                                    1.0   5   3   3   0   1   0   4.20
        Nicasio                                     1.0   0   0   0   0   1   0   5.84  | Rhame                                       1.0   2   2   2   1   2   1   8.10
        ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------
        Totals                                      9.0   6   0   0   3   9   0         | Totals                                      9.0  10   6   6   3  10   1
        ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------
        WP: Velasquez; Gsellman.
        HBP: Realmuto (by Vargas); Frazier, T (by Velasquez).
        Pitches-strikes: Velasquez 97-53; Neshek 13-8; Domínguez 9-6; Morgan 14-10; Nicasio 15-10; Vargas 89-53; Lugo, S 32-23; Zamora 5-3; Gsellman 25-17; Rhame 19-12.
        Groundouts-flyouts: Velasquez 6-3; Neshek 1-2; Domínguez 1-1; Morgan 1-0; Nicasio 2-0; Vargas 8-3; Lugo, S 3-2; Zamora 0-0; Gsellman 1-1; Rhame 0-0.
        Batters faced: Velasquez 22; Neshek 4; Domínguez 3; Morgan 4; Nicasio 3; Vargas 21; Lugo, S 8; Zamora; Gsellman 8; Rhame 6.
        Inherited runners-scored: Lugo, S 2-0; Zamora 1-0.
        Umpires: HP: Brian Gorman. 1B: Jansen Visconti. 2B: Mark Carlson. 3B: Scott Barry.
        Weather: 66 degrees, Clear.
        Wind: 12 mph, L To R.
        First pitch: 7:11 PM.
        T: 3:21.
        Att: 27,685.
        Venue: Citi Field.
        April 24, 2019
    """
    try:
        params: Dict[str, Any] = {}
        if gamePk is not None:
            params["gamePk"] = gamePk
        if battingBox is not None:
            params["battingBox"] = battingBox
        if fieldingInfo is not None:
            params["fieldingInfo"] = fieldingInfo
        if pichitingBox is not None:
            params["pitchingBox"] = pichitingBox
        if gameInfo is not None:
            params["gameInfo"] = gameInfo
        if timeCode is not None:
            params["timecode"] = timeCode

        logging.debug(f"Retrieving game details with params: {params}")
        result = statsapi.boxscore(**params)  # adjust to the right statsapi call
        logging.debug("Retrieved game details successfully")
        return {"game": result}

    except Exception as e:
        error_msg = f"Error retrieving game details: {e!s}"
        logging.error(error_msg)
        raise Exception(error_msg) from e


@mcp.tool(name="game_highlight_data")
async def game_highlight_data(
    gameID: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Description:
        Get the highlight video links for a given game

    Args:
        gameID: MLB game ID
    Returns:
        Dictionary with "game highlights"  highlight information.
    Output:
        Truncated to only include the first two highlights)
        Hoskins' RBI double (00:00:16)
        Rhys Hoskins belts a double off the left-center-field wall to score Bryce Harper and give the Phillies a 1-0 lead in the bottom of the 1st
        https://cuts.diamond.mlb.com/FORGE/2019/2019-04/28/b1117503-3df11d8d-6df0dd65-csvm-diamondx64-asset_1280x720_59_4000K.mp4

        Phanatic has birthday party (00:01:15)
        Kids and fellow mascots were at Citizens Bank Park to celebrate the Phillie Phanatic's birthday before the game against the Marlins
        https://cuts.diamond.mlb.com/FORGE/2019/2019-04/28/7d978385-db13f22d-f68c304f-csvm-diamondx64-asset_1280x720_59_4000K.mp4
    """
    try:
        # Fetch game highlights
        game_highlights = statsapi.game_highlight_data(gameID)
        # Truncate to only include the first two highlights
        return {"game highlights": game_highlights}
    except Exception as e:
        # Handle exceptions and return an error message
        return {"error": str(e)}


@mcp.tool(name="game_pace_data")
async def game_pace_data(
    season: Optional[int] = None,
    sportID: int = 1,
) -> Dict[str, Any]:
    """
    Description:
        Get the pace data for a given game.

    Args:
        gameID: MLB game ID
        season: Season year (e.g., '2023')
    Output:

    """

    try:
        params = {}
        if season:
            params["season"] = season
            params["sportId"] = sportID

        logging.debug(f"Printing the pace stats for season: {season}")
        result = statsapi.game_pace_data(**params)
        return {"game_pace_data": result}
    except Exception as e:
        error_msg = f"Error retrieving schedule: {e!s}"
        logging.error(error_msg)
        raise Exception(error_msg) from e


@mcp.tool(name="scoring_play_data")
async def scoring_play_data(
    gameID: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Description:
        Get the scoring play data for a given game.

    Args:
        gameID: MLB game ID

    Returns:
        Dictionary with "scoring plays" information.

    Ouput:
        Rhys Hoskins doubles (6) on a sharp line drive to left fielder Isaac Galloway.   Bryce Harper scores.
        Bottom 1 - Miami Marlins: 0, Philadelphia Phillies: 1

        Rhys Hoskins walks.   Andrew McCutchen scores.    Jean Segura to 3rd.  Wild pitch by pitcher Tayron Guerrero.
        Bottom 8 - Miami Marlins: 1, Philadelphia Phillies: 5
    """
    try:
        # Fetch scoring play data
        scoring_plays = statsapi.game_scoring_plays(gameID)
        return {"scoring plays": scoring_plays}
    except Exception as e:
        # Handle exceptions and return an error message
        return {"error": str(e)}


@mcp.tool(name="last_game")
async def last_game(
    teamID: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Description:
        Get the last game information for a given team.

    Args:
        teamID: MLB team ID
    """
    try:
        # Fetch game highlights
        last_game = statsapi.last_game(teamID)
        # Truncate to only include the first two highlights
        return {"last_game": last_game}
    except Exception as e:
        # Handle exceptions and return an error message
        return {"error": str(e)}


@mcp.tool(name="lastest_season")
async def last_game(
    seasonID: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Description:
        Get the last game information for a given team.
    Args:
        teamID: MLB team ID
    Output:
        season_data = statsapi.latest_season()
        print(season_data['seasonId'])
    """
    try:
        # Fetch game highlights
        last_game = statsapi.last_game(seasonID)
        # Truncate to only include the first two highlights
        return {"last_game": last_game}
    except Exception as e:
        # Handle exceptions and return an error message
        return {"error": str(e)}


@mcp.tool(name="league_leader_data")
async def league_leader_data(
    leaderCategories: Optional[str] = None,
    season: Optional[str] = None,
    limit: Optional[int] = None,
    statGroup: Optional[str] = None,
    leagueID: Optional[int] = None,  # 103=AL, 104=NL
    playerPool: Optional[str] = None,  # <- was int; should be str
    sportID: int = 1,
    statType: Optional[str] = None,
    gameTypes: Optional[str] = None,  # allow comma list like 'R,W,S'
) -> Dict[str, Any]:
    """
    Get stat leaders overall or for a given league (103=AL, 104=NL).

    Notes:
      - statType='statsSingleSeason' often not supported; specify a season or use 'career'.
      - Get available values via meta endpoint types: leagueLeaderTypes, statGroups, gameTypes, statTypes.
      - playerPool in {'all','qualified','rookies'}; default (API) is 'qualified'.

    Args mirror statsapi.league_leaders:
      leaderCategories (str): e.g., 'homeRuns', 'earnedRunAverage'
      season (str): e.g., '2024'
      limit (int): number of leaders (default 10)
      statGroup (str): e.g., 'hitting','pitching','fielding','catching'
      leagueID (int): 103 (AL) or 104 (NL)
      playerPool (str): 'all' | 'qualified' | 'rookies'
      sportID (int): 1 for MLB
      statType (str): e.g., 'career', 'season', etc. (see meta)
      gameTypes (str): e.g., 'R' (regular), 'W' (wild card), 'S' (spring); comma-separated allowed

    Returns:
      {
        "query": { ...exact params passed... },
        "leaders": <raw API result list/dict from statsapi.league_leaders>
      }
    """
    try:
        if not leaderCategories:
            raise ValueError(
                "leaderCategories is required (e.g., 'homeRuns', 'earnedRunAverage')."
            )

        if playerPool is not None:
            playerPool = str(playerPool).strip().lower()
            if playerPool not in _VALID_PLAYER_POOLS:
                raise ValueError(
                    f"playerPool must be one of {_VALID_PLAYER_POOLS}, got '{playerPool}'."
                )

        q_limit = int(limit) if limit is not None else 10
        q_league = int(leagueID) if leagueID is not None else None
        q_season = str(season) if season else None
        q_statGroup = statGroup if statGroup else None
        q_statType = statType if statType else None
        q_gameTypes = gameTypes if gameTypes else None
        q_sportId = int(sportID) if sportID is not None else 1
        q_playerPool = playerPool if playerPool else None

        # Build a clean dict of what we will pass (None values excluded below)
        query_params = {
            "leaderCategories": leaderCategories,
            "season": q_season,
            "limit": q_limit,
            "statGroup": q_statGroup,
            "leagueId": q_league,  # correct param name
            "gameTypes": q_gameTypes,
            "playerPool": q_playerPool,
            "sportId": q_sportId,  # correct param name
            "statType": q_statType,
        }
        # Filter out Nones so we only send meaningful params
        call_params = {k: v for k, v in query_params.items() if v is not None}

        leaders = statsapi.league_leaders(**call_params)

        logging.debug("[league_leader_data] Retrieved data successfully")
        return {"query": call_params, "leaders": leaders}

    except Exception as e:
        error_msg = f"league_leader_data failed: {e!s}"
        logging.error(error_msg)
        raise


##Take a look at this function later....
@mcp.tool(name="linescore")
async def linescore(
    gameID: Optional[int] = None, timecode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Description:
        Get the formatted and raw JSON linescore for a given MLB game.

    Args:
        gameID: MLB game ID (gamePk)
        timecode: Optional timestamp (UTC, format YYYYMMDD_HHMMSS) to retrieve a past version

    Output Example:
    {
        "formatted": "Final    1 2 3 4 5 6 7 8 9  R   H   E\nPhillies 1 ...",
        "json": { ... full structured linescore ... }
    }
    """
    try:
        if not gameID:
            raise ValueError("gameID is required (e.g., 565997).")

        logging.debug(f"[linescore] Retrieving linescore for game ID {gameID}")

        # Formatted text version (same as statsapi example)
        formatted = statsapi.linescore(gameID, timecode=timecode)

        # Raw structured JSON version (direct from MLB endpoint)
        raw_game = statsapi.get("game", {"gamePk": gameID})
        raw_linescore = raw_game.get("liveData", {}).get("linescore", {})

        logging.debug(f"[linescore] Retrieved formatted and raw JSON for game {gameID}")

        return {
            "query": {"gamePk": gameID, "timecode": timecode},
            "formatted": formatted,
            "json": raw_linescore,
        }

    except Exception as e:
        error_msg = f"Error retrieving linescore for gameID {gameID}: {e!s}"
        logging.error(error_msg)
        raise Exception(error_msg) from e


@mcp.tool(name="lookup_player")
async def lookup_player(
    player_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Description:
        Get player information for a given player ID.

    Args:
        playerID: MLB player ID

    """

    try:
        logging.debug(f"Looking up player with name: {player_name}")
        result = statsapi.lookup_player(player_name)

        if result:
            logging.debug(f"Found {len(result)} player(s) matching: {player_name}")
            return {"people": result}
        else:
            logging.info(f"No players found matching: {player_name}")
            raise Exception(f"No players found matching: {player_name}")
    except Exception as e:
        error_msg = f"Error looking up player {player_name}: {e!s}"
        logging.error(error_msg)
        raise Exception(error_msg) from e


@mcp.tool(name="lookup_team")
async def lookup_team(
    lookup_value: Optional[str] = None,
    activeStatus: str = "Y",
    season: Optional[str] = None,
    sportIds: int = 1,
) -> Dict[str, Any]:
    """
    Description:
        Look up MLB team information by name, city, abbreviation, or file code.

    Args:
        lookup_value (str): Search term (e.g., team name, city, abbreviation, or code)
        activeStatus (str): 'Y' (active), 'N' (inactive), or 'B' (both). Default is 'Y'.
        season (str, optional): Year (e.g., '2024') for filtering historical teams.
        sportIds (int): 1 for MLB (default). Can specify other sport IDs if applicable.

    Notes:
        - Returns a list of team dictionaries. Empty list if no matches.
        - For example:
            statsapi.lookup_team('chn')  # Chicago Cubs
            statsapi.lookup_team('ny')   # All NY-based teams

    Returns:
        {
            "query": { ...params used... },
            "count": <number of teams found>,
            "teams": [ {team info dict}, ... ]
        }
    """
    try:
        if not lookup_value:
            raise ValueError("lookup_value is required (e.g., 'ny', 'chn', 'boston').")

        # Normalize and validate parameters
        activeStatus = activeStatus.upper()
        if activeStatus not in {"Y", "N", "B"}:
            raise ValueError("activeStatus must be one of: 'Y', 'N', or 'B'.")

        query_params = {
            "lookup_value": lookup_value,
            "activeStatus": activeStatus,
            "season": season,
            "sportIds": int(sportIds),
        }

        logging.debug(
            f"[lookup_team] Searching for team: {lookup_value} with params {query_params}"
        )

        teams = statsapi.lookup_team(
            lookup_value,
            activeStatus=activeStatus,
            season=season,
            sportIds=sportIds,
        )

        count = len(teams)
        logging.debug(f"[lookup_team] Found {count} match(es) for '{lookup_value}'")

        return {
            "query": query_params,
            "count": count,
            "teams": teams,
        }

    except Exception as e:
        error_msg = f"Error during team lookup for '{lookup_value}': {e!s}"
        logging.error(error_msg)
        raise Exception(error_msg) from e


# next_game
@mcp.tool(name="next_game")
async def next_game(
    teamID: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Description:
        Get the next game information for a given team.

    Args:
        teamID: MLB team ID

    """
    try:
        # Fetch game highlights
        next_game = statsapi.next_game(teamID)
        # Truncate to only include the first two highlights
        return {"next_game": next_game}
    except Exception as e:
        # Handle exceptions and return an error message
        return {"error": str(e)}


@mcp.tool(name="player_stat_data")
async def player_stat_data(
    personID: Optional[int] = None,
    group: Optional[
        str | Iterable[str]
    ] = None,  # 'hitting', 'pitching', 'fielding' or combos
    type: Optional[str | Iterable[str]] = None,  # 'season', 'career' (allow combos)
    season: Optional[str] = None,  # only valid when type includes 'season'
) -> Dict[str, Any]:
    """
    Get player statistics (formatted + raw) for a given player.

    - Returns:
        {
          "query": {...},
          "warnings": [ ... ],
          "formatted": "<string or null>",
          "json": { ... raw player_stat_data ... }
        }
    """
    try:
        if not personID:
            raise ValueError("personID is required (MLB player ID).")

        # Normalize multi-args to bracket-string format that StatsAPI expects
        group_multi = _to_multi_str(group)
        type_multi = _to_multi_str(type)

        # Validate groups
        groups_list = _parse_multi(group_multi) or []
        if groups_list and not set(groups_list).issubset(_ALLOWED_GROUPS):
            raise ValueError(
                f"group must be subset of {_ALLOWED_GROUPS}; got {groups_list}"
            )

        # Validate season rule
        types_list = _parse_multi(type_multi) or []
        warnings: List[str] = []
        if season and "season" not in types_list:
            warnings.append(
                "`season` was provided but `type` does not include 'season'; season will be ignored."
            )
            season_for_calls = None
        else:
            season_for_calls = season

        # ---- Always fetch RAW (data) ----
        # Signature: statsapi.player_stat_data(personId, group=..., type=..., season=...)
        raw_params = dict(personId=personID)
        if group_multi:
            raw_params["group"] = group_multi
        if type_multi:
            raw_params["type"] = type_multi
        if season_for_calls:
            raw_params["season"] = season_for_calls

        logging.debug(f"[player_stat_data] RAW params: {raw_params}")

        loop = asyncio.get_running_loop()
        raw_future = loop.run_in_executor(
            None, lambda: statsapi.player_stat_data(**raw_params)
        )

        # ---- Optionally fetch formatted ----
        # Only valid when ALL requested types are in {'career','season'}.
        can_format = bool(types_list) and set(types_list).issubset(_FORMATTABLE_TYPES)
        if not types_list:
            # default type for player_stats is "season"; if user omitted, we can format season
            can_format = True
            type_multi_for_fmt = "season"
        else:
            type_multi_for_fmt = type_multi  # may be '[career,season]' etc.

        if can_format:
            # statsapi.player_stats(personId, group=..., type=..., season=...)
            fmt_params = dict(personId=personID)
            if group_multi:
                fmt_params["group"] = group_multi
            if type_multi_for_fmt:
                fmt_params["type"] = type_multi_for_fmt
            if season_for_calls:
                fmt_params["season"] = season_for_calls

            logging.debug(f"[player_stat_data] FMT params: {fmt_params}")
            fmt_future = loop.run_in_executor(
                None, lambda: statsapi.player_stats(**fmt_params)
            )
        else:
            fmt_future = None
            if types_list and not set(types_list).issubset(_FORMATTABLE_TYPES):
                warnings.append(
                    "Formatted output not available for requested `type`; returning JSON only."
                )

        raw_result = await raw_future
        formatted_result = await fmt_future if fmt_future else None

        return {
            "query": {
                "personId": personID,
                "group": group_multi,
                "type": type_multi,
                "season": season,
            },
            "warnings": warnings,
            "formatted": formatted_result,
            "json": raw_result,
        }

    except Exception as e:
        msg = f"player_stat_data failed: {e!s}"
        logging.error(msg)
        raise Exception(msg) from e


@mcp.tool(name="roster")
async def get_team_roster(
    team_id: int,
    rosterType: Optional[str] = None,  # e.g. "active", "40Man"
    season: Optional[int] = None,  # defaults server-side to current if omitted
    date: Optional[str] = None,  # MM/DD/YYYY
) -> Dict[str, Any]:
    """
    Get team roster information as structured JSON.

    Args:
        team_id: MLB team ID (e.g., 119 for Dodgers)
        rosterType: "active", "40Man", etc. (see meta: rosterTypes)
        season: Season year (int)
        date: Date in MM/DD/YYYY (overrides season if provided)

    Returns:
        {
          "query": {...original params...},
          "roster": [ { "person": {...}, "jerseyNumber": "...", "position": {...} }, ... ],
          "raw": <full endpoint JSON for debugging>
        }
    """
    try:
        params = {"teamId": team_id}
        if rosterType:
            params["rosterType"] = rosterType
        if season is not None:
            params["season"] = season
        if date:
            # MLB StatsAPI expects MM/DD/YYYY for this param (per docs)
            params["date"] = date

        logging.debug(f"[roster] params -> {params}")

        # Use the raw JSON endpoint instead of the formatted string helper
        data = statsapi.get("team_roster", params)

        # Normalize: most responses have top-level "roster"
        roster_list = data.get("roster", [])

        logging.debug(
            f"[roster] retrieved {len(roster_list)} entries for team {team_id}"
        )
        return {"query": params, "roster": roster_list, "raw": data}

    except Exception as e:
        error_msg = (
            f"[roster] Error retrieving team roster for team ID {team_id}: {e!s}"
        )
        logging.error(error_msg)
        raise Exception(error_msg) from e


@mcp.tool(name="game_schedule")
async def game_schedule(
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    team_id: Optional[int] = None,
    opponent_id: Optional[int] = None,
    sport_id: int = 1,
    game_id: Optional[str] = None,
    season: Optional[str] = None,
    include_series_status: bool = True,
) -> Dict[str, Any]:
    """
    Description:
        Get MLB game schedule information for specified criteria.
        Use this tool to find games by date range, specific teams, or individual games.
        You can search by a single date, date range, specific teams, or combinations.

    Args:
        date: Specific date in format 'MM/DD/YYYY' or 'YYYY-MM-DD'
        start_date: Start of date range in format 'MM/DD/YYYY' or 'YYYY-MM-DD'
        end_date: End of date range in format 'MM/DD/YYYY' or 'YYYY-MM-DD'
        team_id: MLB team ID (e.g., 143 for Phillies, 121 for Mets)
        opponent_id: Opponent team ID to find head-to-head matchups
        sport_id: Sport ID (1 for MLB, default)
        game_id: Specific game ID to get details for one game
        season: Season year (e.g., '2023')
        include_series_status: Whether to include series status info

    Returns:
        Dictionary with "games" key containing list of game dictionaries.
        Each game contains comprehensive info including:
        - Basic info: game_id, game_date, game_datetime, status
        - Teams: away_name, home_name, away_id, home_id
        - Scores: away_score, home_score, winning/losing teams
        - Pitchers: probable starters, winning/losing/save pitchers with notes
        - Venue: venue_id, venue_name
        - Broadcast: national_broadcasts list
        - Game context: doubleheader status, game_num, series_status
        - Live game info: current_inning, inning_state
        - Summary: formatted game summary string

    Examples:
        - Get today's games: get_schedule(date="06/01/2025")
        - Get team's games in date range:
            get_schedule(start_date="07/01/2018", end_date="07/31/2018", team_id=143)
        - Get head-to-head series:
            get_schedule(
                start_date="07/01/2018",
                end_date="07/31/2018",
                team_id=143,
                opponent_id=121
            )
        - Get specific game: get_schedule(game_id="530769")
        - Get full season: get_schedule(season="2023", team_id=143)
    """
    try:
        params = {}
        if date:
            params["date"] = date
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if team_id:
            params["team"] = team_id
        if opponent_id:
            params["opponent"] = opponent_id
        if game_id:
            params["game_id"] = game_id
        if season:
            params["season"] = season
        params["sportId"] = sport_id
        params["include_series_status"] = include_series_status

        logging.debug(f"Retrieving schedule with params: {params}")
        result = statsapi.schedule(**params)
        logging.debug(f"Retrieved schedule data: {len(result)} game(s)")
        return {"games": result}
    except Exception as e:
        error_msg = f"Error retrieving schedule: {e!s}"
        logging.error(error_msg)
        raise Exception(error_msg) from e


@mcp.tool(name="standings")
async def standings(
    leagueID: Optional[Union[List[int], str]] = None,  # e.g., [103, 104] or "103,104"
    division: Optional[str] = "all",  # per docs, "all" or a specific division
    includeWildcard: bool = True,  # include_wildcard in statsapi
    season: Optional[str] = None,  # e.g., "2025"
    standingsTypes: Optional[str] = None,  # passthrough
    date: Optional[str] = None,  # MM/DD/YYYY
    includeJson: bool = True,  # convenience: also fetch standings_data
) -> Dict[str, Any]:
    """
    Get formatted MLB standings (and optionally raw JSON).

    Returns:
        {
          "query": {...exact params...},
          "formatted": "<table string>",
          "json": {...}  # only when includeJson=True
        }
    """
    try:
        league_str = _to_league_str(leagueID)

        if date is not None and not _DATE_RE.match(date):
            raise ValueError("date must be in MM/DD/YYYY format, e.g., '04/24/2019'.")

        # Build params exactly as statsapi.standings expects
        fmt_params: Dict[str, Any] = {}
        if league_str:
            fmt_params["leagueId"] = league_str
        if division:
            fmt_params["division"] = division
        fmt_params["include_wildcard"] = bool(includeWildcard)
        if season:
            fmt_params["season"] = season
        if standingsTypes:
            fmt_params["standingsTypes"] = standingsTypes
        if date:
            fmt_params["date"] = date

        logging.debug(f"[standings] formatted params: {fmt_params}")

        loop = asyncio.get_running_loop()
        formatted_future = loop.run_in_executor(
            None, lambda: statsapi.standings(**fmt_params)
        )

        # Optionally fetch JSON data version in parallel
        if includeJson:
            # standings_data accepts many of the same keys; pass what’s meaningful
            data_params: Dict[str, Any] = {}
            if league_str:
                data_params["leagueId"] = league_str
            if season:
                data_params["season"] = season
            if standingsTypes:
                data_params["standingsType"] = (
                    standingsTypes  # note: singular in many docs; statsapi handles key
                )
            if date:
                data_params["date"] = date

            logging.debug(f"[standings] data params: {data_params}")
            data_future = loop.run_in_executor(
                None, lambda: statsapi.standings_data(**data_params)
            )
        else:
            data_future = None

        formatted = await formatted_future
        raw_json = await data_future if data_future else None

        return {
            "query": {
                "leagueId": league_str,
                "division": division,
                "include_wildcard": includeWildcard,
                "season": season,
                "standingsTypes": standingsTypes,
                "date": date,
                "includeJson": includeJson,
            },
            "formatted": formatted,
            "json": raw_json,
        }

    except Exception as e:
        msg = f"[standings] Failed: {e!s}"
        logging.error(msg)
        raise Exception(msg) from e


# statsapi.standings_data(leagueId="103,104", division="all", include_wildcard=True, season=None, standingsTypes=None, date=None)

# statsapi.team_leaders(teamId, leaderCategories, season=datetime.now().year, leaderGameTypes="R", limit=10)


@mcp.tool(name="team_leaders")
async def team_leaders(
    teamID: int,
    leaderCategories: Union[str, List[str]],
    season: Optional[int] = None,
    leaderGameTypes: str = "R",
    limit: int = 5,
    includeJson: bool = False,  # set True if you also want the raw data
) -> Dict[str, Any]:
    """
    Retrieve team stat leaders (formatted text) for a given team/season.
    Mirrors: statsapi.team_leaders(teamId, leaderCategories, season=..., leaderGameTypes="R", limit=...)
    """
    try:
        season_val = _ensure_season(season)
        categories = _to_list(leaderCategories)

        logging.debug(
            f"[team_leaders] teamID={teamID} season={season_val} gameTypes={leaderGameTypes} limit={limit} cats={categories}"
        )

        loop = asyncio.get_running_loop()

        async def _one(cat: str) -> str:
            return await loop.run_in_executor(
                None,
                lambda: statsapi.team_leaders(
                    teamId=teamID,
                    leaderCategories=cat,  # one category per call (per docs)
                    season=season_val,
                    leaderGameTypes=leaderGameTypes,
                    limit=limit,
                ),
            )

        formatted_map: Dict[str, str] = {}
        for cat in categories:
            formatted_map[cat] = await _one(cat)

        formatted_out: Union[str, Dict[str, str]] = (
            formatted_map[categories[0]] if len(categories) == 1 else formatted_map
        )

        raw_json: Optional[Dict[str, Any]] = None
        if includeJson:
            # team_leader_data accepts a list of categories
            raw_json = await loop.run_in_executor(
                None,
                lambda: statsapi.team_leader_data(
                    teamId=teamID,
                    leaderCategories=categories,
                    season=season_val,
                    leaderGameTypes=leaderGameTypes,
                    limit=limit,
                ),
            )

        return {
            "query": {
                "teamID": teamID,
                "season": season_val,
                "leaderCategories": categories,
                "leaderGameTypes": leaderGameTypes,
                "limit": limit,
            },
            "formatted": formatted_out,
            "json": raw_json,
        }

    except Exception as e:
        msg = f"[team_leaders] Failed for team {teamID}: {e}"
        logging.error(msg)
        raise Exception(msg) from e


def main():
    print("Running server with stdio transport")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
