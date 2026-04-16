# Claude Code — Project Instructions

This project runs **5 integrated optimization tools in parallel**. They are not alternatives — each owns a different layer of the pipeline. Use them together.

## 1. The Five-Tool Stack

| # | Tool | Layer | Role | How it fires |
| - | ---- | ----- | ---- | ------------ |
| 1 | **claude-mem** (`@thedotmack`) | Session memory | Persistent cross-session memory compaction | Lifecycle hooks (SessionStart / UserPromptSubmit / PostToolUse / Stop / SessionEnd) — **auto** |
| 2 | **caveman** (`@JuliusBrussee`) | File compression | Compresses heavy `.md` files (~46% token savings); creates `<file>.original.md` backup | `/caveman:compress <file>` — **on demand** |
| 3 | **code-review-graph** (`@tirth8205`) | Code knowledge graph | Local SQLite graph of symbols + call edges (~8× cheaper than Read sweeps for code Q&A) | MCP tools + `.venv/Scripts/code-review-graph` CLI — **auto via MCP, incremental on SessionStart** |
| 4 | **ruflo / claude-flow V3** (`@ruvnet`) | Orchestration | Multi-agent swarm, hooks framework, AgentDB (HNSW/ONNX vectors), 314 MCP tools | Project-scoped `.claude/helpers/` hooks + `.mcp.json` — **auto on session, daemon off by default** |
| 5 | **everything-claude-code** (`@affaan-m`) | Token caps | Cherry-picked env vars: `MAX_THINKING_TOKENS=10000`, `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50`, trimmed MCP list | `.claude/settings.json` env block — **auto every session** |

**Role separation (why you want all five, not one):**

```
┌─────────────────────────────────────────────────────────────┐
│  User turn in Claude Code                                    │
└───────────────┬─────────────────────────────────────────────┘
                │
      ┌─────────▼──────────┐      (5) env caps thinking → 10k
      │  Prompt router     │          + compact @50% ctx
      │  (ruflo hooks)     │      (4) ruflo route hook
      └─────────┬──────────┘
                │
     ┌──────────┼──────────┬──────────────┐
     ▼          ▼          ▼              ▼
  Read/Edit   MCP graph  MCP agentdb   Skill invocation
 (small diff) (3) code-  (4) ruflo     (2) caveman
              review-    memory_search     compress
              graph
                │
                ▼
   ┌──────────────────────────┐
   │ Stop / SessionEnd hooks  │
   │ (1) claude-mem sync      │
   │ (4) ruflo post-task learn│
   └──────────────────────────┘
```

Each tool optimizes a layer the others don't touch: claude-mem kills **cross-session** re-derivation; caveman kills **static doc** bloat; code-review-graph kills **code-exploration** Reads; ruflo gives **orchestration + AgentDB vectors**; everything-claude-code caps **thinking + compact** behaviour.

## 2. What happens when you open Claude Code here

```
claude code  →  SessionStart hooks fire in parallel:
  │
  ├── [ruflo]        hook-handler.cjs session-restore     (15s)
  ├── [claude-mem]   auto-memory-hook.mjs import          (8s)
  └── [graph]        code-review-graph.exe update         (20s, silent)

claude-mem plugin auto-loads:    memory compaction hooks active
caveman   plugin auto-loads:     /caveman:compress skill available
env caps applied:                MAX_THINKING_TOKENS=10000, autocompact@50%
disabled MCPs:                   chrome-devtools, mongodb
MCP servers started:             code-review-graph (auto), claude-flow (on demand)
```

You don't run anything. The session is ready the moment Claude Code finishes launching.

## 3. What happens when you open a terminal here

```
cmd.exe / bash opens  →  you run ONCE per fresh terminal:

  Windows:   scripts\dev-shell.bat
  Git Bash:  source scripts/dev-shell.sh

which does:
  1. cd to project root
  2. activate .venv
  3. code-review-graph update  (silent, incremental, seconds)
  4. code-review-graph status  (prints: Nodes/Edges/Files/Last updated)
  5. prints: "[dev-shell] venv active, graph fresh. Ready."
```

Skip it only if you just want `git` commands — any Python work or graph query needs the venv active.

## 4. Command cheat-sheet

| # | What you want | When | Command | Auto? |
| - | ------------- | ---- | ------- | ----- |
| 1 | Ask Claude where a function is called | Code Q&A, refactor planning | *(just ask)* "where is `should_auto_download` called from?" | yes — graph MCP |
| 2 | Recall prior-session decision | Starting new session on same feature | *(just ask)* "what did we decide about the OI cache?" or `/mem-search <kw>` | yes — claude-mem loads index |
| 3 | Compress a heavy `.md` file | After materially editing CLAUDE.md / README.md | `/caveman:compress CLAUDE.md` | on demand |
| 4 | Full graph rebuild | After big refactor / mass rename | `.venv/Scripts/code-review-graph build` | no |
| 5 | Incremental graph update | After editing a few files | `.venv/Scripts/code-review-graph update` | yes on SessionStart |
| 6 | Background graph watcher | Long coding session, want auto-update on save | `.venv/Scripts/code-review-graph watch` | no (spare terminal) |
| 7 | Graph status | Sanity check | `.venv/Scripts/code-review-graph status` | yes via dev-shell |
| 8 | Change impact radius | Before risky rename | `.venv/Scripts/code-review-graph detect-changes --base HEAD~1` | no |
| 9 | Manual compact | After research phase, before implementation | `/compact` | no |
| 10 | Ruflo: semantic memory search | Find similar past patterns | `npx @claude-flow/cli@latest memory search --query "<q>"` | no |
| 11 | Ruflo: import all Claude memories into AgentDB | After bulk memory edits | `node .claude/helpers/auto-memory-hook.mjs import-all` | partial (import on SessionStart) |
| 12 | Ruflo: self-diagnosis | Hooks misbehaving | `npx @claude-flow/cli@latest doctor --fix` | no |
| 13 | Ruflo: spawn a swarm | Genuinely multi-agent task (rare) | `npx @claude-flow/cli@latest swarm init --v3-mode` | no |
| 14 | Switch model | Routine task → cheap tier | `/model sonnet` then back `/model opus` | no |
| 15 | Terminal bootstrap | Fresh terminal | `scripts\dev-shell.bat` (Windows) or `source scripts/dev-shell.sh` | no |
| 16 | Visualize graph as HTML | Architecture review | `.venv/Scripts/code-review-graph visualize` | no |

## 5. Concrete example session (all 5 tools)

**Goal:** rename `should_auto_download` to `needs_fresh_download` safely.

```
Step 1 — You:  "Where is should_auto_download called from, and what breaks if I rename it?"

          tool layer used:  (3) code-review-graph MCP
          cost:             1 MCP call (vs. ~5 Read calls)
          Claude replies:   nse_status_html.py:132 (def)
                            optionchain_gradio.py:3799 (1 caller)
                            tests/test_nse_download_button.py (4 refs)

Step 2 — You:  "Did we discuss this rename before?"

          tool layer used:  (1) claude-mem — searches session index
          cost:             index lookup, no file reads
          Claude replies:   "No prior mentions — this is a new rename."

Step 3 — You:  "Do the rename."

          tool layer used:  (5) env caps keep thinking ≤10k
                            Edit tool hits the 5 sites directly
          Claude does:      5× Edit (surgical, not rewrites)

Step 4 — You:  "/compact"

          tool layer used:  (5) compacts at your breakpoint, not at 95%

Step 5 — You:  run tests, commit.
          SessionEnd fires:
            - (1) claude-mem sync  → decision persisted for next session
            - (4) ruflo post-task  → pattern-learns the rename shape
            - (3) graph auto-updates on next SessionStart

Step 6 — Later, CLAUDE.md edited.  You:  "/caveman:compress CLAUDE.md"

          tool layer used:  (2) caveman — shrinks CLAUDE.md ~46%,
                            backs up CLAUDE.original.md
```

Same task without the stack: ~20 Reads + Grep sweeps + re-explaining context next session + 3× the thinking-token cost. **The stack is the point — don't shortcut to one tool.**

## 6. code-review-graph usage rules

| Ask Claude this | Graph answers with | Saves |
| --- | --- | --- |
| "Where is `X` called from?" | all call-sites + file paths | ~5 Reads |
| "What depends on `Y`?" | reverse-dependency subgraph | ~10 Reads |
| "Call chain from `refresh_data` to NSE fetch" | ordered path | ~15 Reads |
| "Which modules import `paths.py`?" | import-edge list | 1 Grep + N Reads |
| "Summarize the OI-history pipeline" | community summary | large sweep |
| "If I rename `_run_nse_download`, what breaks?" | impact radius | many Grep+Read |

**Still use Read/Grep for:** specific line content, README typos, literal text search (TODOs).

**Rebuild vs update:**

| Situation | Command |
| --- | --- |
| Edited 1–2 files | `update` |
| Pulled / merged | `update` |
| Mass rename / refactor | `build` |
| `status` shows `never` | `build` |

## 7. Rules for Claude (routing preference)

1. **Code-structure questions** → code-review-graph MCP before Read/Grep.
2. **"What did we decide about X?"** → claude-mem / `/mem-search` before re-deriving.
3. **Heavy `.md` sibling with `.original.md`** → already caveman-compressed; read as-is, don't recompress.
4. **Multi-agent orchestration genuinely needed** → ruflo swarm; otherwise single Agent tool call.
5. **Routine edits (typos, simple rewrites)** → `/model sonnet` for ~60% savings.
6. **Before large Read batches** → `/compact` first.

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Graph MCP tools missing | `.mcp.json` missing `code-review-graph` entry | restore from this doc; restart Claude Code |
| Graph says "Last updated: never" | fresh clone, graph unbuilt | `.venv/Scripts/code-review-graph build` |
| Ruflo hooks silently fail | `.claude/helpers/` empty | `npx ruflo@latest init --only-claude --force` (drop `--minimal`) |
| CLAUDE.md reverted to defaults | ruflo reinit overwrote it | restore from git; re-merge env vars in `settings.json` |
| Caveman skill not callable | installed mid-session | restart Claude Code once |
| Thinking feels slow / pricey | env caps not loaded | verify `MAX_THINKING_TOKENS=10000` in `.claude/settings.json` |
| claude-mem memory not loading | user-scope plugin missing | `claude plugin install claude-mem@thedotmack` |

## 9. ⚠️ Warning — DO NOT re-run `ruflo init` casually

`npx ruflo init --force` **overwrites** `CLAUDE.md` and `.claude/settings.json` with ruflo defaults, wiping the 5-tool integration. If you must re-run it:

1. Back up both files first (`git stash` or copy).
2. Run the init.
3. Restore this CLAUDE.md and re-merge into `settings.json`:
   - `env.MAX_THINKING_TOKENS = "10000"`
   - `env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE = "50"`
   - top-level `"disabledMcpServers": ["chrome-devtools", "mongodb"]`
   - SessionStart hook: `cmd /c %CLAUDE_PROJECT_DIR%\.venv\Scripts\code-review-graph.exe update >nul 2>&1`
4. Verify `.claude/helpers/` is populated (not empty) — if empty, drop `--minimal`.
5. Verify `.mcp.json` still has the `code-review-graph` entry.

## 10. Scope

All of the above applies **inside Claude Code sessions only**. GitHub Copilot, Google Antigravity, Cursor, etc. have their own context pipelines — configure those natively.
