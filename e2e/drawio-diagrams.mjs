// Sends each Mermaid diagram in docs/diagrams to the draw.io MCP server and records the editable draw.io URL.
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import fs from "node:fs";
import path from "node:path";
const dir = path.resolve(new URL("../docs/diagrams", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const t = new StdioClientTransport({ command: process.platform === "win32" ? "npx.cmd" : "npx", args: ["-y", "@drawio/mcp@latest"], env: { ...process.env }, stderr: "pipe" });
const c = new Client({ name: "salespilot-diagrams", version: "1.0.0" });
await c.connect(t);
const links = [];
for (const f of fs.readdirSync(dir).filter((f) => f.endsWith(".mmd")).sort()) {
  const content = fs.readFileSync(path.join(dir, f), "utf8");
  const args = { content };
  if (content.startsWith("flowchart")) args.postLayout = "elk";
  const r = await c.callTool({ name: "open_drawio_mermaid", arguments: args });
  const url = (r.content?.[0]?.text ?? "").match(/https:\/\/app\.diagrams\.net\/\S+/)?.[0];
  console.log(f, r.isError ? "ERROR" : "ok");
  if (url) links.push(`- [${f.replace(".mmd", "")}](${url})`);
}
fs.writeFileSync(path.join(dir, "DRAWIO_LINKS.md"), "# Editable draw.io versions\n\nGenerated with the draw.io MCP server (`e2e/drawio-diagrams.mjs`). Each link opens the diagram in the free draw.io web editor; use File > Save as to keep a .drawio copy.\n\n" + links.join("\n") + "\n");
await c.close();
