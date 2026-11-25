# Browser tests through MCP servers

These scripts talk to the **same MCP servers** configured in `../.mcp.json`, using the official MCP client SDK.

| Script | MCP server | What it checks |
|---|---|---|
| `verify-mcp.mjs` | all five | each server starts, lists its tools, answers one real call |
| `playwright-workflow.mjs` | Playwright MCP | full sales workflow in Chromium (20 steps), screenshots desktop/tablet/mobile, dark mode, console errors |
| `devtools-audit.mjs` | Chrome DevTools MCP | console errors + failed network requests on every page, Lighthouse, performance trace (LCP/CLS) |

```powershell
cd e2e
npm install
npm run verify-mcp
# with backend (fresh DB: .\reset-demo-data.ps1) and frontend running:
npm run workflow     # screenshots in e2e\output\img
npm run audit
```
Set `CHROME_PATH` if Chrome is not in the default location. The workflow test expects an **empty database** (it checks empty states first).
