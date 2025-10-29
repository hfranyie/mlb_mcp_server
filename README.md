# MLB MCP Server

A Model Context Protocol (MCP) server that provides comprehensive MLB statistics and data through the MLB Stats API. This server offers both a command-line interface and a web-based Streamlit chat interface for interacting with MLB data.

## Features

### Core MLB Data Tools
- **Game Information**: Boxscores, highlights, scoring plays, pace data
- **Team Data**: Rosters, standings, team leaders, schedules
- **Player Statistics**: Individual player stats (hitting, pitching, fielding)
- **League Information**: League leaders, standings by division
- **Live Data**: Current games, next games, last games

### Available MCP Tools
- `boxscore` - Get formatted boxscore for games
- `game_highlight_data` - Retrieve game highlight videos
- `game_pace_data` - Get game pace statistics
- `scoring_play_data` - Get scoring plays for games
- `last_game` / `next_game` - Team's recent/upcoming games
- `league_leader_data` - League statistical leaders
- `linescore` - Formatted and raw JSON linescore
- `lookup_player` / `lookup_team` - Search players and teams
- `player_stat_data` - Comprehensive player statistics
- `roster` - Team roster information
- `game_schedule` - Game schedules by date/team
- `standings` - League/division standings
- `team_leaders` - Team statistical leaders

## Credits

This project is built on top of the excellent [MLB-StatsAPI](https://github.com/toddrob99/MLB-StatsAPI) Python library by **Todd Roberts** (@toddrob99). The MLB-StatsAPI library provides a clean, Pythonic interface to MLB's official Stats API and handles all the heavy lifting for data retrieval and formatting.

**MLB-StatsAPI Features Used:**
- Game data retrieval (boxscores, highlights, schedules)
- Player and team statistics
- League standings and leader boards
- Real-time game information
- Historical data access

We extend our gratitude to Todd Roberts and all contributors to the MLB-StatsAPI project for making MLB data easily accessible to Python developers.

## Quick Start

### Prerequisites
- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mlb_mcp_server-main
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Run the MCP server**
   ```bash
   uv run mcp run mlb_mcp_server.py
   ```

### Web Interface (Streamlit)

For a user-friendly chat interface:

1. **Set up environment variables** (create `.env` file):
   ```env
   AWS_REGION=us-east-1
   BEDROCK_MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0
   SERVER_CMD=uv run mcp run mlb_mcp_server.py
   ```

2. **Run the Streamlit app**:
   ```bash
   uv run streamlit run streamlit_app.py
   ```

3. **Access the interface** at `http://localhost:8501`

## Usage Examples

### Command Line (via MCP)
```bash
# Get today's MLB standings
echo '{"method": "call_tool", "params": {"name": "standings"}}' | uv run mcp run mlb_mcp_server.py

# Get team roster
echo '{"method": "call_tool", "params": {"name": "roster", "arguments": {"team_id": 119}}}' | uv run mcp run mlb_mcp_server.py
```

### Web Interface
- "Show me today's standings"
- "Get the roster for the Dodgers"
- "Who are the home run leaders this season?"
- "Show me the boxscore for game 716663"

## Configuration

### Environment Variables
- `AWS_REGION` - AWS region for Bedrock (default: us-east-1)
- `BEDROCK_MODEL_ID` - Bedrock model ID for AI responses
- `SERVER_CMD` - Command to start MCP server

### Team IDs Reference
Common MLB team IDs (see `current_mlb_teams.json` for complete list):
- Los Angeles Dodgers: 119
- New York Yankees: 147
- Philadelphia Phillies: 143
- Atlanta Braves: 144
- Boston Red Sox: 111

## Deployment Options

### 1. Local Development
```bash
# Install and run locally
uv sync
uv run streamlit run streamlit_app.py
```

### 2. Docker Deployment
Create a `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install uv
RUN uv sync

EXPOSE 8501

CMD ["uv", "run", "streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0"]
```

Build and run:
```bash
docker build -t mlb-mcp-server .
docker run -p 8501:8501 mlb-mcp-server
```

### 3. Cloud Deployment

#### AWS EC2/ECS
1. Use the Docker approach above
2. Configure AWS credentials for Bedrock access
3. Deploy to ECS or run on EC2 instance

#### Heroku
1. Add `Procfile`:
   ```
   web: uv run streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
   ```
2. Deploy via Git or Heroku CLI

#### Railway/Render
1. Connect your GitHub repository
2. Set environment variables in platform dashboard
3. Use automatic deployment from main branch

## Architecture

### MCP Server (`mlb_mcp_server.py`)
- FastMCP-based server providing MLB data tools
- Connects to MLB Stats API via `mlb-statsapi` package
- Supports both formatted text and raw JSON responses

### Streamlit Interface (`streamlit_app.py`)
- Web-based chat interface
- Supports both Strands Agent (advanced) and fallback modes
- Real-time tool discovery and execution

### Dependencies
- `mcp[cli]` - Model Context Protocol framework
- `mlb-statsapi` - MLB Stats API client
- `streamlit` - Web interface framework
- `strands-agents` - Advanced AI agent framework (optional)
- `httpx` - HTTP client for API requests

## API Reference

### Key Tool Parameters

#### `game_schedule`
```python
{
    "date": "MM/DD/YYYY",           # Specific date
    "start_date": "MM/DD/YYYY",     # Date range start
    "end_date": "MM/DD/YYYY",       # Date range end
    "team_id": 119,                 # Team ID
    "season": "2024"                # Season year
}
```

#### `player_stat_data`
```python
{
    "personID": 545361,             # Player ID
    "group": "hitting",             # hitting/pitching/fielding
    "type": "season",               # season/career
    "season": "2024"                # Season year
}
```

#### `standings`
```python
{
    "leagueID": "103,104",          # AL=103, NL=104
    "division": "all",              # Division filter
    "season": "2024",               # Season year
    "date": "MM/DD/YYYY"            # Historical date
}
```

## Troubleshooting

### Common Issues

1. **MCP Server Won't Start**
   - Ensure Python 3.11+ is installed
   - Run `uv sync` to install dependencies
   - Check that `mlb_mcp_server.py` is executable

2. **Streamlit Connection Errors**
   - Verify MCP server command in environment variables
   - Check AWS credentials for Bedrock access
   - Ensure all dependencies are installed

3. **Tool Call Failures**
   - Validate required parameters (team IDs, dates)
   - Check MLB Stats API availability
   - Review error logs for specific issues

### Debug Mode
Enable debug logging by setting:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request



## License

This project is open source. Please check the repository for license details.

The underlying MLB-StatsAPI library is also open source - see their [repository](https://github.com/toddrob99/MLB-StatsAPI) for license information.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the [MLB-StatsAPI documentation](https://github.com/toddrob99/MLB-StatsAPI)
3. Review the MLB Stats API documentation
4. Open an issue in the repository

## Related Projects

- [MLB-StatsAPI](https://github.com/toddrob99/MLB-StatsAPI) - The core Python library for MLB Stats API
- [Model Context Protocol](https://github.com/modelcontextprotocol/python-sdk) - MCP Python SDK
- [FastMCP](https://github.com/jlowin/fastmcp) - Simplified MCP server framework

---

**Note**: This server requires internet access to connect to the MLB Stats API. Some features may be limited during MLB off-season or maintenance periods.
