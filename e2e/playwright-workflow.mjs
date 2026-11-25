// Browser E2E for SalesPilot AI driven through the Playwright MCP server (stdio).
// Runs the main business workflow in a real Chromium, captures screenshots + console errors.
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import fs from "node:fs";

const BASE = process.env.BASE ?? "http://127.0.0.1:5173";
import path from "node:path";
const OUT = path.resolve(process.env.OUT ?? new URL("./output", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
fs.mkdirSync(`${OUT}/img`, { recursive: true });
// Uses the same npx package that your MCP client config uses.
const extra = process.env.CHROME_PATH ? ["--executable-path", process.env.CHROME_PATH] : [];
if (process.platform === "linux") extra.push("--no-sandbox");
const t = new StdioClientTransport({ command: process.platform === "win32" ? "npx.cmd" : "npx",
  args: ["-y", "@playwright/mcp@latest", "--headless", "--isolated", "--viewport-size", "1440,900", "--output-dir", OUT, ...extra],
  env: { ...process.env }, stderr: "pipe" });
const c = new Client({ name: "salespilot-e2e", version: "1.0.0" });
await c.connect(t);

const results = [];
const text = (r) => (r.content || []).filter((x) => x.type === "text").map((x) => x.text).join("\n");
async function call(name, args = {}) {
  const r = await c.callTool({ name, arguments: args });
  if (r.isError) throw new Error(`${name} failed: ${text(r).slice(0, 400)}`);
  return r;
}
async function snapshot() {
  const t = text(await call("browser_snapshot"));
  // Large snapshots are written to a file and only linked in the response.
  const link = t.match(/\]\(([^)]+\.yml)\)/);
  if (link) {
    const p = link[1].startsWith("/") ? link[1] : `${OUT}/${link[1].replace(/^.*?\.playwright-mcp\//, "").replace(/^\.\//, "")}`;
    for (const cand of [p, `${OUT}/${link[1].split("/").pop()}`]) if (fs.existsSync(cand)) return t + "\n" + fs.readFileSync(cand, "utf8");
  }
  return t;
}
function ref(snap, role, name) {
  const re = new RegExp(`- ${role} "${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}"[^\\n]*?\\[ref=([a-z0-9]+)\\]`);
  const m = snap.match(re);
  if (!m) throw new Error(`ref not found: ${role} "${name}"`);
  return m[1];
}
// Poll the accessibility snapshot until the element exists (pages are lazy-loaded).
async function refWait(role, name, timeoutMs = 10000) {
  const end = Date.now() + timeoutMs
  for (;;) {
    try { return ref(await snapshot(), role, name) } catch (e) {
      if (Date.now() > end) throw e
      await new Promise((r) => setTimeout(r, 400))
    }
  }
}
async function click(role, name) { await call("browser_click", { element: name, target: await refWait(role, name) }); }
async function shot(file) { await call("browser_take_screenshot", { filename: `${OUT}/img/${file}`, type: "png", scale: "css" }); }
async function waitText(t, time = 15) { await call("browser_wait_for", { text: t, time }); }
async function step(name, fn) {
  try { await fn(); results.push(["PASS", name]); console.log("PASS", name); }
  catch (e) { results.push(["FAIL", name, e.message]); console.log("FAIL", name, e.message); }
}
async function sendChat(msg, expect) {
  await call("browser_type", { element: "Message", target: await refWait("textbox", "Message"), text: msg, submit: true });
  if (expect) await waitText(expect);
}

await step("Overview loads (empty state)", async () => {
  await call("browser_navigate", { url: `${BASE}/` });
  await waitText("No conversations yet");
  await shot("01-overview-empty.png");
});

await step("Start call, agent greets", async () => {
  await call("browser_navigate", { url: `${BASE}/agent` });
  await click("button", "Start call");
  await waitText("Nova");
});

await step("Course question answered from knowledge base with source", async () => {
  await sendChat("Hello, I want to learn AI and machine learning. Can you tell me about your courses?", "₹45,000");
  await waitText("course_catalog.txt");
  await waitText("May I know your name?");
});
await step("Profile captured: name, budget, timeline", async () => {
  await sendChat("My name is Rahul", "What budget");
  await sendChat("My budget is around 20,000", "When are you hoping to start");
  await sendChat("I want to start next month", "counselling session");
  const s = await snapshot();
  if (!s.includes("Rahul") || !s.includes("₹20,000")) throw new Error("caller panel not updated");
});
await step("Price objection -> hesitant + EMI answer", async () => {
  await sendChat("That's too expensive for me", "EMI");
  await waitText("hesitant");
});
await step("Unknown topic -> not in knowledge base", async () => {
  await sendChat("Do you offer a blockchain course?", "not in our knowledge base");
});
await step("Hindi message -> Hindi reply", async () => {
  await sendChat("रिफंड की नीति क्या है?", "नॉलेज बेस");
});
await step("Appointment: slots offered, select, confirm, booked", async () => {
  await sendChat("Can I book a counselling appointment?", "next available counselling slots");
  await shot("02-agent-slots.png");
  await sendChat("2", "Please say yes to confirm");
  await sendChat("yes", "booking #");
  await shot("03-agent-booked.png");
});
await step("Agent action trace expands", async () => {
  const s = await snapshot();
  const m = [...s.matchAll(/- button "(\d+) agent actions"[^\n]*\[ref=([a-z0-9]+)\]/g)].pop();
  await call("browser_click", { element: "agent actions", target: m[2] });
  await waitText("book_appointment");
  await shot("04-agent-trace.png");
});
await step("End call -> summary saved", async () => {
  await click("button", "End call");
  await waitText("Call summary");
  await shot("05-agent-summary.png");
});
await step("CRM shows lead; drawer shows profile + transcript", async () => {
  await call("browser_navigate", { url: `${BASE}/crm` });
  await waitText("Rahul");
  await shot("06-crm.png");
  await click("button", "Rahul");
  await waitText("Saved facts");
  await shot("07-crm-drawer.png");
  await call("browser_press_key", { key: "Escape" });
});
await step("CRM search filters", async () => {
  await call("browser_type", { element: "Search leads", target: await refWait("textbox", "Search leads"), text: "zzz-nobody" });
  await waitText("No leads match these filters");
});
await step("Appointments page shows booking", async () => {
  await call("browser_navigate", { url: `${BASE}/appointments` });
  await waitText("Rahul");
  await shot("08-appointments.png");
});
await step("Knowledge base retrieval test", async () => {
  await call("browser_navigate", { url: `${BASE}/knowledge` });
  await waitText("course_catalog.txt");
  await call("browser_type", { element: "Test question", target: await refWait("textbox", "Test question"), text: "What is the refund policy?", submit: true });
  await waitText("Answerable from knowledge base");
  await shot("09-knowledge.png");
});
await step("Analytics from real data", async () => {
  await call("browser_navigate", { url: `${BASE}/analytics` });
  await waitText("Conversion trend");
  await shot("10-analytics.png");
});
await step("Overview populated", async () => {
  await call("browser_navigate", { url: `${BASE}/` });
  await waitText("Recent leads");
  await shot("11-overview.png");
});
await step("Settings + environment status", async () => {
  await call("browser_navigate", { url: `${BASE}/settings` });
  await waitText("Environment");
  await shot("12-settings.png");
});
await step("Dark theme", async () => {
  await call("browser_navigate", { url: `${BASE}/` });
  await click("button", "Switch to dark theme");
  await waitText("Recent leads");
  await shot("13-overview-dark.png");
  await call("browser_navigate", { url: `${BASE}/agent` });
  await waitText("Talk to Nova");
  await shot("14-agent-dark.png");
  await call("browser_navigate", { url: `${BASE}/analytics` });
  await waitText("Conversion trend");
  await shot("14b-analytics-dark.png");
  await click("button", "Switch to light theme");
});
await step("Mobile 390px: menu + agent", async () => {
  await call("browser_resize", { width: 390, height: 844 });
  await call("browser_navigate", { url: `${BASE}/` });
  await waitText("Recent leads");
  await shot("15-mobile-overview.png");
  await click("button", "Open menu");
  await shot("16-mobile-menu.png");
  await call("browser_navigate", { url: `${BASE}/agent` });
  await waitText("Talk to Nova");
  await shot("17-mobile-agent.png");
  await call("browser_resize", { width: 820, height: 1180 });
  await call("browser_navigate", { url: `${BASE}/crm` });
  await waitText("Rahul");
  await shot("18-tablet-crm.png");
});
await step("No console errors", async () => {
  const r = text(await call("browser_console_messages", { level: "error", all: true }));
  fs.writeFileSync(`${OUT}/console-errors.txt`, r);
  if (/\[error\]|Error:/i.test(r) && !/Total messages: 0|No console messages/i.test(r)) throw new Error(r.slice(0, 600));
});

await c.close();
const failed = results.filter((r) => r[0] === "FAIL");
console.log(`\n${results.length - failed.length}/${results.length} browser steps passed`);
fs.writeFileSync(`${OUT}/playwright-results.json`, JSON.stringify(results, null, 2));
process.exit(failed.length ? 1 : 0);
