# MCP + SolidWorks + Claude Code Setup Guide

How to configure the SolidWorks MCP server and Parts Intelligence MCP server
for use with Claude Desktop and Claude Code.

## Prerequisites

| Requirement        | Version         | Notes                                    |
|--------------------|-----------------|------------------------------------------|
| Windows            | 10 or 11        | SolidWorks COM requires Windows          |
| SolidWorks         | 2023, 2024, 2025| Must be installed and licensed            |
| Python             | 3.10+           | Both servers require 3.10 or higher      |
| Claude Desktop     | Latest           | OR Claude Code CLI — either works        |

## Repository Layout

This setup involves two repositories side by side:

```
agents/CAD/
├── Solidworks-MCP/              # SolidWorks COM automation (22 tools)
│   ├── solidworks_mcp_server.py # STDIO entry point
│   └── requirements.txt
└── robotics-design-advisor/     # Parts intelligence + design copilot
    ├── parts_server.py          # Parts Intelligence MCP (5 tools)
    └── data/profiles/           # Cached part profiles (generated)
```

## Step 1: Install Solidworks-MCP

```powershell
cd C:\path\to\Solidworks-MCP
pip install -r requirements.txt
```

Dependencies installed: `mcp>=1.0.0`, `pywin32>=306`, `python-dotenv>=1.0.0`.

Verify the install:

```powershell
python solidworks_mcp_server.py --help
```

## Step 2: Install robotics-design-advisor

```powershell
cd C:\path\to\robotics-design-advisor
pip install -e ".[server,step]"
```

This installs the `mcp[cli]` and `cadquery` dependencies needed for the
parts server and STEP profile generation.

## Step 3: Generate the Part Profile Cache

Before the Parts Intelligence server can serve part data, you need to scan
your STEP files and generate JSON profiles:

```powershell
cd C:\path\to\robotics-design-advisor
python -c "
from robotics_design_advisor.step.batch_profiler import run_batch

run_batch(
    step_dirs=[
        r'C:\path\to\goBILDA-CAD-STEP-with-images',
    ],
    output_dir='data/profiles/gobilda',
)
"
```

This scans all `.step`/`.stp` files, extracts geometry profiles, and writes
them as flat JSON files to `data/profiles/gobilda/` with an `_index.json`.
The scan is idempotent — existing profiles are skipped on re-run.

## Step 4: Configure Claude Desktop

Edit (or create) the config file at:

```
C:\Users\YOUR_NAME\AppData\Roaming\Claude\claude_desktop_config.json
```

Add both servers under `mcpServers`:

```json
{
  "mcpServers": {
    "solidworks": {
      "command": "python",
      "args": ["C:\\path\\to\\Solidworks-MCP\\solidworks_mcp_server.py"]
    },
    "parts-intelligence": {
      "command": "python",
      "args": [
        "C:\\path\\to\\robotics-design-advisor\\parts_server.py",
        "--profiles-dir",
        "C:\\path\\to\\robotics-design-advisor\\data\\profiles\\gobilda"
      ]
    }
  }
}
```

Replace `C:\\path\\to\\` with your actual paths. Use double backslashes in JSON.

**Restart Claude Desktop** after saving the config.

## Step 5: Configure Claude Code

Create or edit `~/.claude/mcp_servers.json`:

```json
{
  "solidworks": {
    "type": "stdio",
    "command": "python",
    "args": ["C:\\path\\to\\Solidworks-MCP\\solidworks_mcp_server.py"]
  },
  "parts-intelligence": {
    "type": "stdio",
    "command": "python",
    "args": [
      "C:\\path\\to\\robotics-design-advisor\\parts_server.py",
      "--profiles-dir",
      "C:\\path\\to\\robotics-design-advisor\\data\\profiles\\gobilda"
    ]
  }
}
```

Claude Code picks up MCP server changes on the next session start.

## Step 6: Verify the Setup

### SolidWorks Server

1. Open SolidWorks (the application must be running).
2. In Claude, say: **"Connect to SolidWorks"**.
3. Claude calls `connect_solidworks` and reports the version and connection status.
4. Try: **"Create a new part and draw a circle with radius 20mm"**.

### Parts Intelligence Server

1. In Claude, say: **"List all part categories"**.
2. Claude calls `list_categories` and returns category names with counts.
3. Try: **"Search for goBILDA channels longer than 200mm"**.
4. Try: **"Suggest mates between 1120-0001-0288 and 2900-0005-0002"**.

## Available Tools

### SolidWorks MCP (22 tools)

| Category       | Tools                                                        |
|----------------|--------------------------------------------------------------|
| Connection     | `connect_solidworks`, `get_solidworks_info`                  |
| Documents      | `create_new_part`, `create_new_assembly`, `open_document`, `close_document`, `save_document`, `list_open_documents` |
| Sketches       | `create_sketch`, `close_sketch`, `draw_circle`, `draw_rectangle`, `draw_line`, `draw_arc`, `draw_polygon` |
| Features       | `extrude_sketch`, `cut_extrude`, `fillet_edges`, `chamfer_edges`, `list_features` |
| Utilities      | `set_units`, `execute_python`                                |

### Parts Intelligence MCP (5 tools)

| Tool                   | Description                                        |
|------------------------|----------------------------------------------------|
| `search_parts`         | Search by keyword, category, and size range        |
| `get_part_profile`     | Full engineering profile for a SKU                 |
| `find_compatible_parts`| Find parts matching a compatibility tag            |
| `list_categories`      | List all categories with part counts               |
| `suggest_mates`        | Suggest SolidWorks mate constraints between parts  |

## Troubleshooting

### "SolidWorks not found" or COM connection fails

- SolidWorks must be **running** before Claude connects.
- Run `python` as the same user that launched SolidWorks.
- If SolidWorks was installed but not opened since reboot, open it manually first.
- Check that `pywin32` is installed: `python -c "import win32com.client"`.

### "Catalog not loaded" from Parts Intelligence

- Verify the `--profiles-dir` path exists and contains `.json` profile files.
- Run the batch profiler (Step 3) if the directory is empty.
- Check that `_index.json` exists in the profiles directory.

### Server not appearing in Claude

- **Claude Desktop**: Restart the app after editing `claude_desktop_config.json`.
- **Claude Code**: Start a new session after editing `mcp_servers.json`.
- Verify the `python` command resolves to Python 3.10+: `python --version`.
- Check paths use double backslashes in JSON (`C:\\Users\\...`).

### Permission errors on Windows

- Run Claude Desktop or Claude Code from a terminal with the same user privileges as SolidWorks.
- If SolidWorks runs as admin, the MCP server process also needs admin privileges.
