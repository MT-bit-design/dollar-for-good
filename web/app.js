// Dollar for Good front end. Everything shown from data or the agent is escaped.
const $ = (s, el = document) => el.querySelector(s);
const CAVEATS = {
  health: "Figures come from different evaluators and years. The Against Malaria Foundation estimate is from 2016; GiveWell's current cost per life saved suggests today's cost per DALY is higher.",
  poverty: "GiveDirectly is the benchmark program itself. One Acre Fund and Village Enterprise figures are self-reported by the charities, and Village Enterprise's own site also states a different, higher figure.",
  education: "Outcomes are not all the same unit: Youth Impact is learning-adjusted years; CAMFED and deworming are additional years of schooling. Deworming's figure is for deworming in general, not one charity.",
  climate: "These are highly uncertain expected-value estimates for policy advocacy, which their own authors say to compare only by order of magnitude. The benchmark is the social cost of a tonne of CO2, not another charity.",
};
const ICONS = { health: "🩺", poverty: "💵", education: "📚", climate: "🌍" };

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function safeUrl(u) {
  try { const x = new URL(u); return (x.protocol === "https:" || x.protocol === "http:") ? x.href : null; }
  catch { return null; }
}
function link(u, text) {
  const s = safeUrl(u);
  return s ? `<a href="${esc(s)}" target="_blank" rel="noopener noreferrer">${esc(text || new URL(s).hostname)}</a>` : esc(text || "");
}
const money = n => n == null ? "—" : "$" + Math.round(n).toLocaleString();

async function api(path, opts) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || `Request failed (${r.status})`);
  return body;
}

// ---------------- tabs
document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === t));
  document.querySelectorAll(".panel").forEach(p => p.hidden = p.id !== "tab-" + t.dataset.tab);
}));

// ---------------- position chip + bar (log scale, 1x in the middle)
function positionHtml(pos) {
  if (!pos || !pos.ok) return `<span class="chip none">${esc(pos?.reason || "No comparison")}</span>`;
  const t = pos.times_benchmark;
  const clamp = Math.max(-2, Math.min(2, Math.log10(t)));   // 0.01x .. 100x
  const pct = (clamp / 2) * 50;
  const color = { well_above: "var(--good)", above: "var(--ok)", below: "var(--warn)", well_below: "var(--bad)" }[pos.band];
  const left = pct >= 0 ? 50 : 50 + pct, width = Math.abs(pct);
  return `<span class="chip ${pos.band}">${esc(pos.label)}</span>
    <div class="bar" title="log scale: middle line = benchmark"><div class="fill" style="left:${left}%;width:${width}%;background:${color}"></div><div class="mid"></div></div>`;
}

function sourceHtml(item) {
  const date = item.source_date ? esc(item.source_date) : "undated";
  const warn = (item.warnings || []).map(w => `<span class="chip warn" title="${esc(w)}">undated source</span>`).join(" ");
  return `${link(item.source_url, item.publisher || "source")} · ${date}<br><span>accessed ${esc(item.accessed || "")}</span> ${warn}
    <details><summary>Quote and notes</summary><p><q>${esc(item.quote)}</q></p>${item.notes ? `<p>${esc(item.notes)}</p>` : ""}</details>`;
}

// ---------------- donor view
let CAUSES = [];
async function loadCauses() {
  CAUSES = await api("/api/causes");
  $("#cause-cards").innerHTML = CAUSES.map(c => `
    <button class="cause-card" data-cause="${c.cause}">
      <div class="icon">${ICONS[c.cause]}</div>
      <div class="name">${esc(c.label)}</div>
      <div class="unit">${esc(c.metric_label)}</div>
    </button>`).join("");
  document.querySelectorAll(".cause-card").forEach(b => b.addEventListener("click", () => showCause(b.dataset.cause)));
}

async function showCause(cause) {
  document.querySelectorAll(".cause-card").forEach(b => b.classList.toggle("active", b.dataset.cause === cause));
  const v = await api("/api/cause/" + cause);
  $("#cause-detail").hidden = false;
  const b = v.benchmark;
  $("#bench-value").textContent = b && b.status === "sourced" ? v.benchmark_display : "Missing";
  $("#bench-label").textContent = b ? `${b.label} · ${v.metric_label}` : "No benchmark";
  $("#bench-src").innerHTML = b && b.status === "sourced"
    ? `Source: ${link(b.source_url, b.source_title || b.publisher)} (${esc(b.publisher || "")}, ${esc(b.source_date || "undated")}; accessed ${esc(b.accessed)})<q>${esc(b.quote)}</q><details><summary>Notes</summary><p>${esc(b.notes || "")}</p></details>`
    : `<b>Benchmark missing:</b> ${esc(b?.missing_reason || "no source found")}`;
  $("#rank-hint").textContent = v.lower_is_better
    ? `Lower cost is better. Ranked cheapest first.`
    : `More income per dollar is better. Ranked highest first.`;

  const rows = v.ranked.map(r => `
    <tr>
      <td class="rank-n">${r.rank}</td>
      <td><b>${link(r.website, r.name)}</b><div class="prog">${esc(r.program || "")}</div></td>
      <td class="metric">${esc(r.display)}</td>
      <td>${positionHtml(r.position)}</td>
      <td class="src">${sourceHtml(r)}</td>
    </tr>`).join("");
  $("#rank-table").innerHTML = `<thead><tr><th>#</th><th>Charity</th><th>${esc(v.metric_label)}</th><th>vs benchmark</th><th>Source</th></tr></thead><tbody>${rows || `<tr><td colspan="5">No charity in this cause has a sourced number yet.</td></tr>`}</tbody>`;

  $("#cause-caveat").hidden = false;
  $("#cause-caveat").innerHTML = `<b>Read with care:</b> ${esc(CAVEATS[cause])}`;
  $("#nc-wrap").hidden = !v.not_computable.length;
  $("#nc-list").innerHTML = v.not_computable.map(r => `
    <li><b>${link(r.website, r.name)}</b><div class="why">${esc(String(r.result.reason).replace(/^MISSING:\s*/i, ""))}</div></li>`).join("");
  $("#research-form [name=cause]").value = cause;
}

// ---------------- research a charity
function usageHtml(u, cached) {
  if (!u) return "";
  if (cached) return `<div class="usage"><span>Answer reused from cache: <b>0</b> new tokens</span></div>`;
  return `<div class="usage">
    <span>Input tokens <b>${u.input_tokens.toLocaleString()}</b></span>
    <span>Cached input <b>${u.cached_input_tokens.toLocaleString()}</b></span>
    <span>Output tokens <b>${u.output_tokens.toLocaleString()}</b></span>
    <span>Model calls <b>${u.requests}</b> · page fetches <b>${u.tool_calls}</b></span>
    <span>Cost <b>$${u.cost_usd.toFixed(4)}</b></span>
    <span>Time <b>${u.seconds}s</b></span></div>`;
}

function traceHtml(trace) {
  return `<ul class="trace">${(trace || []).map(t => t.step === "fetch"
    ? `<li class="${t.ok ? "" : "fail"}">Fetched ${link(t.url, t.url)} ${t.ok ? `· ${t.chars.toLocaleString()} characters${t.truncated ? " (trimmed)" : ""}` : `· <span class="notverified">${esc(t.error)}</span>`}</li>`
    : `<li class="${t.ok ? "" : "fail"}">Code check: ${t.ok ? '<span class="verified">quote found word-for-word on the page ✓</span>' : `<span class="notverified">${esc(t.reason)}</span>`}</li>`).join("")}</ul>`;
}

function researchResultHtml(r) {
  if (r.status === "budget" || r.status === "error") return `<div class="alert">${esc(r.reason)}</div>${traceHtml(r.trace)}${usageHtml(r.usage, r.cached)}`;
  const ex = r.extraction || {};
  const warn = r.suspicious_instructions_seen ? `<div class="alert">⚠ The page contained text that tried to give the agent instructions. It was ignored.</div>` : "";
  const head = r.status === "computed"
    ? `<div class="headline"><span class="big">${esc(r.display)}</span><span>${esc(CAUSES.find(c => c.cause === r.cause)?.metric_label || "")}</span>${positionHtml(r.position)}<span class="hint">benchmark ${esc(r.benchmark_display)}</span></div>
       <p><span class="verified">Verified quote</span> from ${link(ex.source_url)}: <q>${esc(ex.quote)}</q></p>`
    : `<div class="headline"><span class="big">Can't compute</span></div><p class="notverified">${esc(r.reason)}</p>`;
  return `${warn}${head}<h4>What the agent did</h4>${traceHtml(r.trace)}${usageHtml(r.usage, r.cached)}`;
}

$("#research-form").addEventListener("submit", async e => {
  e.preventDefault();
  const f = new FormData(e.target);
  const btn = e.target.querySelector("button");
  const out = $("#research-out");
  btn.disabled = true;
  out.innerHTML = `<div class="result"><span class="spinner"></span>Reading the charity's pages… (usually 10–30 seconds)</div>`;
  try {
    const r = await api("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: f.get("name"), website: f.get("website"), cause: f.get("cause") || null }) });
    out.innerHTML = `<div class="result">${researchResultHtml(r)}</div>`;
  } catch (err) {
    out.innerHTML = `<div class="alert">${esc(err.message)}</div>`;
  } finally { btn.disabled = false; loadStatus(); }
});

// ---------------- funder view
let chosenFile = null;
$("#csv-file").addEventListener("change", e => {
  chosenFile = e.target.files[0] || null;
  $("#csv-name").textContent = chosenFile ? chosenFile.name : "";
  $("#csv-go").disabled = !chosenFile;
});
$("#csv-go").addEventListener("click", () => chosenFile && runPortfolio(chosenFile));
$("#sample-go").addEventListener("click", async () => {
  const text = await (await fetch("/api/sample.csv")).text();
  runPortfolio(new File([text], "sample_portfolio.csv", { type: "text/csv" }));
});

const SRC_LABEL = { your_file: "your numbers", sourced_table: "sourced table", agent: "research agent", none: "no data" };

async function runPortfolio(file) {
  const out = $("#portfolio-out");
  out.innerHTML = `<p><span class="spinner"></span>Checking each charity… rows that need research can take up to a minute.</p>`;
  const fd = new FormData(); fd.append("file", file);
  try {
    const r = await api("/api/portfolio", { method: "POST", body: fd });
    const s = r.summary;
    const share = s.share_of_dollars_at_or_above == null ? "—" : Math.round(s.share_of_dollars_at_or_above * 100) + "%";
    const rows = r.rows.map(x => `
      <tr>
        <td><b>${link(x.website, x.name)}</b><div class="prog">${esc(CAUSES.find(c => c.cause === x.cause)?.label || x.cause_input || "cause unknown")}</div></td>
        <td>${money(x.amount_granted_usd)}</td>
        <td class="metric">${x.result.ok ? esc(x.display) : "—"}</td>
        <td>${x.result.ok ? positionHtml(x.position) : `<span class="chip none">Can't compute</span><div class="prog">${esc(x.result.reason)}</div>`}</td>
        <td class="src"><span class="chip src-${x.data_source}">${SRC_LABEL[x.data_source] || ""}</span>
          ${x.source_url ? `<br>${link(x.source_url)}${x.source_date ? " · " + esc(x.source_date) : ""}` : ""}
          ${x.quote ? `<details><summary>Quote</summary><p><q>${esc(x.quote)}</q></p></details>` : ""}
          ${x.agent ? `<details><summary>Agent run</summary>${traceHtml(x.agent.trace)}${usageHtml(x.agent.usage, x.agent.cached)}</details>` : ""}
          ${x.agent?.suspicious_instructions_seen ? `<div class="alert">Page tried to instruct the agent; ignored.</div>` : ""}</td>
      </tr>`).join("");
    out.innerHTML = `
      <div class="tiles">
        <div class="tile"><div class="n">${s.computed} / ${s.charities}</div><div class="l">charities we could compute</div></div>
        <div class="tile"><div class="n">${s.at_or_above_benchmark} / ${s.compared}</div><div class="l">at or above their cause benchmark</div></div>
        <div class="tile"><div class="n">${share}</div><div class="l">of granted dollars at or above benchmark (${money(s.granted_at_or_above_usd)} of ${money(s.granted_total_usd)})</div></div>
        <div class="tile"><div class="n">$${s.tokens.cost_usd.toFixed(4)}</div><div class="l">AI cost for this check (${(s.tokens.input_tokens + s.tokens.output_tokens).toLocaleString()} tokens${r.rows.some(x => x.agent?.cached) ? "; research answers reused from cache" : ""})</div></div>
      </div>
      <div class="table-wrap"><table class="rank"><thead><tr><th>Charity</th><th>Granted</th><th>Metric</th><th>vs benchmark</th><th>Where the number came from</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  } catch (err) {
    out.innerHTML = `<div class="alert">${esc(err.message)}</div>`;
  } finally { loadStatus(); }
}

// ---------------- footer status
async function loadStatus() {
  try {
    const s = await api("/api/status");
    $("#foot").innerHTML = `Model: <b>${esc(s.model)}</b> via Portkey · API key: ${s.has_api_key ? "found" : "<b>not set</b> (research agent off)"} · Tokens used today: ${s.tokens_today.toLocaleString()} of ${s.daily_token_budget.toLocaleString()} daily budget`;
  } catch { /* ignore */ }
}

loadCauses().then(() => showCause("health"));
loadStatus();
