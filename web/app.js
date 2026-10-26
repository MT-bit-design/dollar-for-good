// Dollar for Good front end. Everything shown from data or the agent is escaped.
const $ = (s, el = document) => el.querySelector(s);

// Thin line icons (stroke only, one colour).
const ICON = {
  health: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/><path d="M5.5 12h3l1.5-3 2 6 1.5-3h5"/></svg>',
  poverty: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="6" rx="7" ry="2.5"/><path d="M5 6v4c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V6"/><path d="M5 10v4c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-4"/><path d="M5 14v4c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-4"/></svg>',
  education: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 5.5c3-1.3 6-1.3 9 .5 3-1.8 6-1.8 9-.5V19c-3-1.3-6-1.3-9 .5-3-1.8-6-1.8-9-.5z"/><path d="M12 6v13.5"/></svg>',
  climate: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-8 5-13 14-14 0 9-5 14-12 14z"/><path d="M5 19c3-4 6-7 10-9"/></svg>',
};
const RANGE_KIND = { interval: "published range", scenarios: "published scenarios", alternative_estimates: "other published estimates" };

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
  if (!r.ok) throw new Error(body.detail || "Something went wrong. Please try again.");
  return body;
}

// ---------------- tabs
document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === t));
  document.querySelectorAll(".panel").forEach(p => p.hidden = p.id !== "tab-" + t.dataset.tab);
  if (t.dataset.tab === "aisafety") loadAiSafety();
}));

// ---------------- shared pieces
function positionHtml(pos) {
  if (!pos || !pos.ok) return `<span class="pos none">${esc(pos?.reason || "Not compared.")}</span>`;
  const t = pos.times_benchmark;
  const pct = (Math.max(-2, Math.min(2, Math.log10(t))) / 2) * 50;   // log scale, 0.01x .. 100x
  const left = pct >= 0 ? 50 : 50 + pct, width = Math.abs(pct);
  const up = t >= 1;
  return `<span class="pos ${up ? "up" : "down"}">${esc(pos.label)}</span>
    <div class="bar" title="Middle line = benchmark (log scale)"><div class="fill" style="left:${left}%;width:${width}%;background:${up ? "var(--accent)" : "var(--faint)"}"></div><div class="mid"></div></div>`;
}

function rangeHtml(row) {
  if (!row.range) return `<span class="range">no range published</span>`;
  return `<span class="range">${esc(row.range.display)}<span class="kind">${esc(RANGE_KIND[row.range.kind] || "published range")}</span></span>`;
}

function sourceHtml(item) {
  const date = item.source_date ? esc(item.source_date) : "undated";
  const rq = item.range ? `<p>Range quote: <q>${esc(item.range.quote)}</q>${item.range.note ? " " + esc(item.range.note) : ""}</p>` : "";
  return `${link(item.source_url, item.publisher || "source")} · ${date}
    <details><summary>Show details</summary><p><q>${esc(item.quote)}</q></p>${item.notes ? `<p>${esc(item.notes)}</p>` : ""}${rq}<p>Accessed ${esc(item.accessed || "")}.</p></details>`;
}

function detailsHtml(text) {
  return text ? `<details><summary>Show details</summary><p>${esc(text)}</p></details>` : "";
}

// ---------------- compare charities
let CAUSES = [];
const VIEWS = {};

async function loadCauses() {
  CAUSES = await api("/api/causes");
  const views = await Promise.all(CAUSES.map(c => api("/api/cause/" + c.cause)));
  views.forEach(v => VIEWS[v.cause] = v);
  $("#cause-cards").innerHTML = CAUSES.map(c => `
    <button class="cause-card" data-cause="${c.cause}">
      ${ICON[c.cause] || ""}
      <div class="name">${esc(c.label)}</div>
      <div class="unit">${esc(c.metric_label)}</div>
      <div class="explain">${esc(VIEWS[c.cause].explainer)}</div>
    </button>`).join("");
  document.querySelectorAll(".cause-card").forEach(b => b.addEventListener("click", () => showCause(b.dataset.cause)));
}

function groupTable(v, g) {
  const rows = g.ranked.map(r => `
    <tr>
      <td class="rank-n">${r.rank}</td>
      <td><b>${link(r.website, r.name)}</b><div class="prog">${esc(r.program || "")}</div></td>
      <td class="metric">${esc(r.display)}</td>
      <td>${rangeHtml(r)}</td>
      <td>${positionHtml(r.position)}</td>
      <td class="src">${sourceHtml(r)}</td>
    </tr>`).join("");
  const title = g.compared_to_benchmark
    ? `Ranked by ${esc(v.metric_label.replace(/ \(USD\)$/, "").toLowerCase())}`
    : `Measured differently <span class="sub">(${esc(g.measure_label)}; ranked only among themselves, not compared with the benchmark)</span>`;
  return `<div class="group-title">${title}</div>
    <div class="table-wrap"><table class="rank"><thead><tr><th>#</th><th>Charity</th><th>Estimate</th><th>Range</th><th>vs benchmark</th><th>Source</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function showCause(cause) {
  document.querySelectorAll(".cause-card").forEach(b => b.classList.toggle("active", b.dataset.cause === cause));
  const v = VIEWS[cause];
  $("#cause-detail").hidden = false;
  const b = v.benchmark;
  const ok = b && b.status === "sourced";
  $("#bench-value").textContent = ok ? v.benchmark_display : "Missing";
  $("#bench-label").textContent = ok ? `${b.label} · ${v.metric_label}` : "No sourced benchmark";
  $("#bench-range").textContent = ok ? (b.range ? `${RANGE_KIND[b.range.kind] || "Range"}: ${b.range.display}` : "No range published") : "";
  $("#bench-src").innerHTML = ok
    ? `Source: ${link(b.source_url, b.source_title || b.publisher)} (${esc(b.publisher || "")}, ${esc(b.source_date || "undated")})<q>${esc(b.quote)}</q>${detailsHtml(b.notes)}`
    : `No sourced benchmark for this cause yet.`;
  $("#cause-caveat").hidden = false;
  $("#cause-caveat").innerHTML = `<b>Read with care.</b> ${esc(v.caveat)}`;
  $("#rank-hint").textContent = v.lower_is_better ? "Lower cost is better, so the cheapest comes first." : "More income per dollar is better, so the highest comes first.";

  $("#groups").innerHTML = v.groups.length ? v.groups.map(g => groupTable(v, g)).join("")
    : `<p class="hint">No charity in this cause has a sourced number yet.</p>`;

  $("#prog-wrap").hidden = !v.programs.length;
  $("#prog-table").innerHTML = `<thead><tr><th>Program type</th><th>Estimate</th><th>Range</th><th>Source</th></tr></thead><tbody>${v.programs.map(p => `
    <tr>
      <td><b>${esc(p.name)}</b><div class="prog">${esc(p.program_note || p.program || "")}</div></td>
      <td class="metric">${p.result.ok ? esc(p.display) : "—"}${p.result.ok ? `<div class="prog">per ${esc(p.measure_label.replace(/s$/, "").replace(/^extra years/, "extra year"))}</div>` : ""}</td>
      <td>${p.result.ok ? rangeHtml(p) : ""}</td>
      <td class="src">${p.result.ok ? sourceHtml(p) : `${esc(p.donor_note)}${detailsHtml(p.details)}`}</td>
    </tr>`).join("")}</tbody>`;

  $("#nc-wrap").hidden = !v.not_computable.length;
  $("#nc-list").innerHTML = v.not_computable.map(r => `
    <li><b>${link(r.website, r.name)}</b><div class="why">${esc(r.donor_note)}</div>${detailsHtml(r.details)}</li>`).join("");
  $("#research-form [name=cause]").value = cause;
}

// ---------------- look up a charity
function usageHtml(u, cached) {
  if (!u) return "";
  if (cached) return `<div class="usage"><span>Answer reused from an earlier lookup: 0 new tokens</span></div>`;
  return `<div class="usage">
    <span>Input tokens ${u.input_tokens.toLocaleString()}</span>
    <span>Cached input ${u.cached_input_tokens.toLocaleString()}</span>
    <span>Output tokens ${u.output_tokens.toLocaleString()}</span>
    <span>Model calls ${u.requests} · pages opened ${u.tool_calls}</span>
    <span>Cost $${u.cost_usd.toFixed(4)}</span>
    <span>Time ${u.seconds}s</span></div>`;
}

function traceHtml(trace) {
  return `<ul class="trace">${(trace || []).map(t => t.step === "fetch"
    ? `<li class="${t.ok ? "" : "fail"}">Opened ${link(t.url, t.url)}${t.ok ? "" : ` · ${esc(t.error)}`}</li>`
    : `<li class="${t.ok ? "" : "fail"}">Check: ${t.ok ? "the quote is word for word on the page" : esc(t.reason)}${t.retry ? " (asked to try again)" : ""}</li>`).join("")}</ul>`;
}

function researchResultHtml(r) {
  const ex = r.extraction || {};
  const more = `<details><summary>Show details</summary>
      ${r.reason && r.status !== "computed" ? `<p>${esc(r.reason)}</p>` : ""}
      ${traceHtml(r.trace)}${usageHtml(r.usage, r.cached)}</details>`;
  if (r.status !== "computed") {
    return `<div class="headline"><span class="big">Can't compute</span></div><p class="plain">${esc(r.donor_reason || "No estimate could be checked.")}</p>${more}`;
  }
  const label = CAUSES.find(c => c.cause === r.cause)?.metric_label || "";
  return `<div class="headline"><span class="big">${esc(r.display)}</span><span>${esc(label)}</span>${positionHtml(r.position)}<span class="hint">benchmark ${esc(r.benchmark_display)}</span></div>
    <p class="plain">Quote checked on ${link(ex.source_url)}: <q>${esc(ex.quote)}</q></p>${more}`;
}

$("#research-form").addEventListener("submit", async e => {
  e.preventDefault();
  const f = new FormData(e.target);
  const btn = e.target.querySelector("button");
  const out = $("#research-out");
  btn.disabled = true;
  out.innerHTML = `<div class="result"><span class="spinner"></span>Reading the charity's pages. This usually takes 10 to 30 seconds.</div>`;
  try {
    const r = await api("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: f.get("name"), website: f.get("website"), cause: f.get("cause") || null }) });
    out.innerHTML = `<div class="result">${researchResultHtml(r)}</div>`;
  } catch (err) {
    out.innerHTML = `<div class="alert">${esc(err.message)}</div>`;
  } finally { btn.disabled = false; loadStatus(); }
});

// ---------------- portfolio
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

const SRC_LABEL = { your_file: "your numbers", sourced_table: "sourced table", agent: "research assistant", none: "no data" };

async function runPortfolio(file) {
  const out = $("#portfolio-out");
  out.innerHTML = `<p><span class="spinner"></span>Checking each charity. Charities that need a lookup can take up to a minute.</p>`;
  const fd = new FormData(); fd.append("file", file);
  try {
    const r = await api("/api/portfolio", { method: "POST", body: fd });
    const s = r.summary;
    const share = s.share_of_dollars_at_or_above == null ? "—" : Math.round(s.share_of_dollars_at_or_above * 100) + "%";
    const rows = r.rows.map(x => `
      <tr>
        <td><b>${link(x.website, x.name)}</b><div class="prog">${esc(CAUSES.find(c => c.cause === x.cause)?.label || x.cause_input || "cause unknown")}</div></td>
        <td>${money(x.amount_granted_usd)}</td>
        <td class="metric">${x.result.ok ? esc(x.display) : "—"}${x.range_display ? `<div class="range">${esc(x.range_display)}</div>` : ""}</td>
        <td>${x.result.ok ? positionHtml(x.position) : `<span class="pos none">${esc(x.donor_note || "Can't compute.")}</span>`}</td>
        <td class="src"><span class="src-tag">${SRC_LABEL[x.data_source] || ""}</span>
          ${x.source_url ? `<br>${link(x.source_url)}${x.source_date ? " · " + esc(x.source_date) : ""}` : ""}
          <details><summary>Show details</summary>
            ${!x.result.ok && x.result.reason ? `<p>${esc(x.result.reason)}</p>` : ""}
            ${x.quote ? `<p><q>${esc(x.quote)}</q></p>` : ""}
            ${x.agent ? traceHtml(x.agent.trace) + usageHtml(x.agent.usage, x.agent.cached) : ""}
          </details></td>
      </tr>`).join("");
    const cachedNote = r.rows.some(x => x.agent?.cached) ? "; earlier lookups reused" : "";
    out.innerHTML = `
      <div class="tiles">
        <div class="tile"><div class="n">${s.computed} / ${s.charities}</div><div class="l">charities with a sourced estimate</div></div>
        <div class="tile"><div class="n">${s.at_or_above_benchmark} / ${s.compared}</div><div class="l">at or above their cause benchmark</div></div>
        <div class="tile"><div class="n">${share}</div><div class="l">of granted dollars at or above the benchmark (${money(s.granted_at_or_above_usd)} of ${money(s.granted_total_usd)})</div></div>
        <div class="tile"><div class="n">$${s.tokens.cost_usd.toFixed(4)}</div><div class="l">AI cost for this check (${(s.tokens.input_tokens + s.tokens.output_tokens).toLocaleString()} tokens${cachedNote})</div></div>
      </div>
      <div class="table-wrap"><table class="rank"><thead><tr><th>Charity</th><th>Granted</th><th>Estimate</th><th>vs benchmark</th><th>Where the number came from</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  } catch (err) {
    out.innerHTML = `<div class="alert">${esc(err.message)}</div>`;
  } finally { loadStatus(); }
}

// ---------------- AI safety
let aisLoaded = false;
async function loadAiSafety() {
  if (aisLoaded) return;
  const d = await api("/api/ai_safety");
  $("#ais-note").textContent = d.note;
  $("#ais-list").innerHTML = d.organizations.map(o => `
    <li><b>${link(o.website, o.name)}</b><div class="own">“${esc(o.own_words)}”</div><div class="meta">In their own words, from ${esc(new URL(o.website).hostname)}, accessed ${esc(o.accessed)}. Not ranked.</div></li>`).join("");
  aisLoaded = true;
}

// ---------------- footer
async function loadStatus() {
  try {
    const s = await api("/api/status");
    $("#foot").textContent = `Model ${s.model} via Portkey · API key ${s.has_api_key ? "found" : "not set (lookups off)"} · tokens used today ${s.tokens_today.toLocaleString()} of ${s.daily_token_budget.toLocaleString()}`;
  } catch { /* ignore */ }
}

loadCauses().then(() => showCause("health"));
loadStatus();
