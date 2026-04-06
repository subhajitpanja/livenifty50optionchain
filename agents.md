# Agents Configuration & Code Review Graph Integration

## Overview

This project uses [code-review-graph](https://github.com/tirth8205/code-review-graph) to build
a structural knowledge graph of the codebase with Tree-sitter. AI assistants receive precise
context via MCP, achieving **8.2x average token reduction** in code reviews.

- **All processing is local** — SQLite in `.code-review-graph/`, no cloud, no external servers.
- **Credentials are never exposed** — `Credential/` is excluded via `.code-review-graphignore`.

## Quick Start

```bash
# 1. Install
pip install code-review-graph

# 2. Auto-detect IDE/AI tools and configure MCP
code-review-graph install

# 3. Parse the codebase and build the knowledge graph
code-review-graph build
```

Initial build takes ~10 seconds. Incremental updates (on commit/save) complete in <2 seconds.

## How It Works

1. **AST Parsing** — Repository is parsed into an AST with Tree-sitter, stored as a graph of
   nodes (functions, classes, imports) and edges (calls, inheritance, test coverage).
2. **Blast Radius** — When files change, the system traces affected callers, dependents, and
   related tests to identify exactly which code requires review.
3. **Incremental Updates** — On every git commit or file save, a hook fires and re-parses only
   changed files (detected via SHA-256 hash checks).

## MCP Tools (22 available)

Once configured, AI assistants can use these tools:

| Category        | Tools                                                         |
|-----------------|---------------------------------------------------------------|
| Build/Update    | Build graph, update incrementally, rebuild                    |
| Impact Analysis | Blast radius, review context, dependency tracing              |
| Search          | Semantic search, definition lookup, usage search              |
| Flow Tracing    | Call graphs, data flow, framework-specific flows              |
| Refactoring     | Rename preview, move preview, extract preview                 |
| Community       | Module clustering, cohesion/coupling metrics                  |

## Security & Credential Protection

### What is excluded from the graph

The `.code-review-graphignore` file ensures sensitive paths are never parsed:

```
Credential/          # API keys (Dhan, Zerodha, Upstox)
.env / .env.*        # Environment variables
*.key / *.pem        # Private keys
secrets/             # Secret files
```

### Storage

- Graph data: `.code-review-graph/` (local SQLite, gitignored)
- No authentication or remote connectivity required
- No code is sent to external servers

## Project File Map

```
livenifty50optionchain/
├── optionchain_gradio.py        # Main Gradio web dashboard
├── oc_data_fetcher.py           # Data fetching & API logic
├── run.py                       # Entry point
├── color_constants.py           # UI color constants
├── ui_labels.py                 # UI text/label constants
├── tui_components.py            # Terminal UI components
├── tui_theme.py                 # Terminal UI theming
├── paths.py                     # Centralized path config
├── Credential/                  # API credentials (EXCLUDED from graph)
│   ├── __init__.py
│   └── Credential.py            # gitignored
├── data/                        # Runtime data (cache, source, output, logs)
├── templates/                   # HTML/CSS templates
│   ├── css/                     # Stylesheets
│   └── html/                    # 48 HTML template files
├── tests/                       # Test suite (14 test files)
├── scripts/                     # Helper scripts
├── docs/                        # Documentation
├── .code-review-graphignore     # Excludes credentials from graph
├── agents.md                    # This file
├── requirements.txt             # Python dependencies
├── setup.bat / setup.sh         # Environment setup (Windows/Unix)
└── run_tests.bat / run_tests.sh # Test runners (Windows/Unix)
```

## Development Workflow

### Initial Setup

```bash
# Windows
setup.bat

# Linux / macOS
bash setup.sh
```

Both scripts install all dependencies and configure code-review-graph automatically.

### During Development

```bash
# Terminal 1: Run the dashboard
python optionchain_gradio.py

# Graph updates automatically on git commit via hooks
# For live updates during editing (optional):
code-review-graph build    # manual rebuild after major changes
```

### Before Committing

```bash
# Run tests
run_tests.bat              # Windows
bash run_tests.sh          # Linux / macOS

# Commit — graph updates automatically via post-commit hook
git commit -m "Your message"
```

## Performance

| Metric                   | Value                        |
|--------------------------|------------------------------|
| Average Token Reduction  | 8.2x                         |
| Initial Graph Build      | ~10 sec (500 files)          |
| Incremental Updates      | <2 sec                       |
| Monorepo Optimization    | Up to 49x tokens saved       |
| Database Size            | ~5-10 MB per 1000 files      |

## Supported Languages

Python (primary), TypeScript/TSX, JavaScript, Vue, Go, Rust, Java, Scala, C#, Ruby,
Kotlin, Swift, PHP, Solidity, C/C++, Dart, R, Perl, Lua, Jupyter notebooks.

## Troubleshooting

```bash
# Rebuild graph from scratch
code-review-graph build

# Check version
code-review-graph --version

# Re-run MCP detection
code-review-graph install
```

## Resources

- **GitHub**: https://github.com/tirth8205/code-review-graph
- **Website**: https://code-review-graph.com
- **MCP Integration**: Claude Code, Cursor, Windsurf, Zed
- **License**: MIT

---
Last Updated: 2026-04-06 | Version: 2.1.0
