# MCP servers used to build and verify SalesPilot

All five are free and open source. None needs a paid key. They are **developer tools** for an AI coding assistant; the running product does not depend on them.

## Configuration (project level, nothing global changed)
| Client | File |
|---|---|
| Claude Code | `.mcp.json` (uses `cmd /c npx` for Windows) |
| VS Code (Copilot agent mode) | `.vscode/mcp.json` |
| Cursor | `.cursor/mcp.json` |

Your existing global MCP configs (Claude, Cursor, Gemini, Codex, Kiro…) are not touched. If a client asks to approve project MCP servers on first open, approve these five.

## The servers
| Server | Package | Helps with | Notes |
|---|---|---|---|
| **shadcn/ui MCP** | `shadcn@latest mcp` | Search/view/add shadcn registry components, audit checklist. Reads `frontend/components.json` | Needs internet to `ui.shadcn.com` |
| **Playwright MCP** | `@playwright/mcp` (Microsoft) | Drive a real browser through accessibility snapshots: user flows, screenshots, responsive sizes, console | Uses installed Chrome/Edge; else `npx playwright install chromium` |
| **Chrome DevTools MCP** | `chrome-devtools-mcp` (Google) | Console messages, network requests, Lighthouse, performance traces (LCP/CLS), CPU/network throttling | Uses installed Chrome |
| **Context7 MCP** | `@upstash/context7-mcp` | Up-to-date docs for React, Vite, Tailwind v4, FastAPI, SQLAlchemy… instead of stale memory | Free without key (rate-limited); optional free key from context7.com raises limits |
| **draw.io MCP** | `@drawio/mcp` (official, JGraph) | Turns Mermaid or draw.io XML into editable diagrams in the free draw.io editor | Opens app.diagrams.net in your browser |

Not installed on purpose: 21st.dev Magic MCP, Figma paid integrations, other freemium services. Magic UI and Aceternity UI are **component libraries** (copy-paste code), not MCP servers; they weren't needed for this restrained dashboard.

## Verify on your PC
```powershell
cd e2e
npm install
npm run verify-mcp   # starts each server exactly like the configs, lists tools, makes one real call
```

## What happened in the build environment (cloud sandbox, Linux)
| Server | Started + listed tools | Real call | How it was used |
|---|---|---|---|
| Playwright | ✅ 25 tools | ✅ navigate | Ran the 20-step workflow test (`e2e/playwright-workflow.mjs`): **20/20 passed**, 19 screenshots (desktop, dark, tablet 820px, mobile 390px), 0 console errors |
| Chrome DevTools | ✅ 33 tools | ✅ list_pages, Lighthouse, trace | `e2e/devtools-audit.mjs`: 0 console errors and 0 failed requests on all 7 pages; Lighthouse Accessibility 100 / Best Practices 100 on Overview, Live agent, Leads (mobile); LCP ~1.4-1.5 s on the Vite dev server, CLS 0.00 |
| shadcn | ✅ 7 tools | ⚠️ `get_project_registries` OK; registry search blocked (sandbox network allow-list excludes ui.shadcn.com) | Components written by hand following shadcn/ui (new-york) source patterns on Radix; `components.json` added so the MCP and CLI work on your PC |
| Context7 | ✅ 2 tools | ❌ `fetch failed` (context7.com blocked in sandbox) | Library versions checked from the npm registry instead; works on your PC |
| draw.io | ✅ 8 tools | ✅ open_drawio_mermaid | Generated editable versions of the 5 architecture diagrams: `docs/diagrams/DRAWIO_LINKS.md` |

Issues met and fixed:
1. MCP clients spawn servers with a minimal environment; through a proxy `npx` then hung. Scripts now pass the full environment (`env: { ...process.env }`).
2. Playwright MCP renamed the element argument `ref` → `target`; large snapshots are written to files. The workflow script handles both.
3. Screenshots taken during lazy-route loading were blank; tests now wait for page text first.
4. Chrome DevTools MCP only writes Lighthouse/trace files inside its workspace roots; scripts use its defaults.

Microphone/speech recognition cannot be exercised in a headless browser (no mic, and Chrome's recogniser needs Google's service). The tests cover the unsupported/blocked-mic paths and the full flow via the text box, which uses the same API as voice.
