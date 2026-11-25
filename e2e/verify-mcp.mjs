// Spawns each MCP server over stdio, lists tools, optionally calls one tool.
// Usage: node verify.mjs <name>
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

// Spawns each server exactly like .mcp.json does (npx), then lists tools and makes one real call.
// Usage: node verify-mcp.mjs <playwright|devtools|shadcn|context7|drawio|all>
const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const linux = process.platform === "linux";
const servers = {
  playwright: { args: ["-y", "@playwright/mcp@latest", "--headless", "--isolated", ...(linux ? ["--no-sandbox"] : [])],
    call: ["browser_navigate", { url: "data:text/html,<h1>MCP OK</h1>" }] },
  devtools: { args: ["-y", "chrome-devtools-mcp@latest", "--headless", "--isolated", ...(linux ? ["--chromeArg=--no-sandbox"] : [])],
    call: ["list_pages", {}] },
  shadcn: { args: ["-y", "shadcn@latest", "mcp"], cwd: new URL("../frontend", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"),
    call: ["search_items_in_registries", { registries: ["@shadcn"], query: "dialog" }] },
  context7: { args: ["-y", "@upstash/context7-mcp@latest"], call: ["resolve-library-id", { libraryName: "react", query: "react hooks" }] },
  drawio: { args: ["-y", "@drawio/mcp@latest"], call: null },
};

const names = process.argv[2] === "all" || !process.argv[2] ? Object.keys(servers) : [process.argv[2]];
for (const name of names) await check(name);
process.exit(0);

async function check(name) {
const s = servers[name];
const t = new StdioClientTransport({ command: npx, args: s.args, cwd: s.cwd, env: { ...process.env }, stderr: process.env.DEBUG ? "inherit" : "pipe" });
const c = new Client({ name: "verify", version: "1.0.0" });
const timer = setTimeout(() => { console.log(name, "TIMEOUT"); process.exit(2); }, 120000);
try {
  await c.connect(t);
  const { tools } = await c.listTools();
  console.log(`${name}: ${tools.length} tools ->`, tools.map((x) => x.name).join(", "));
  if (s.call) {
    const r = await c.callTool({ name: s.call[0], arguments: s.call[1] });
    const txt = (r.content || []).map((x) => x.text || `[${x.type}]`).join("\n");
    console.log(`call ${s.call[0]} isError=${!!r.isError}:\n${txt.slice(0, 600)}`);
  }
} catch (e) { console.log("ERROR", e.message); }
clearTimeout(timer);
await c.close().catch(() => {});
}
