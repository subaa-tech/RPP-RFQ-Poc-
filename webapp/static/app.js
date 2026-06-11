const $ = (s) => document.querySelector(s);
const fmt = (n) => "$" + (n ?? 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
const fmt0 = (n) => "$" + Math.round(n ?? 0).toLocaleString();

let pickedFile = null;
const state = { rows: [], margin: 0.25, job: null, approved: false, dirty: false, base: null };

// ---- API health ----
fetch("/api/health").then(r => r.json()).then(() => {
  const b = $("#apiBadge"); b.textContent = "● engine online"; b.classList.add("ok");
}).catch(() => { const b = $("#apiBadge"); b.textContent = "● engine offline"; b.classList.add("err"); });

// ---- file selection ----
const dz = $("#dropzone"), fileInput = $("#fileInput"), runBtn = $("#runBtn");
function setFile(f) {
  if (!f || f.type !== "application/pdf") return;
  pickedFile = f; dz.classList.add("loaded"); $("#dzMain").textContent = f.name; runBtn.disabled = false;
}
dz.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", e => setFile(e.target.files[0]));
["dragover", "dragenter"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add("drag"); }));
["dragleave", "drop"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", e => setFile(e.dataTransfer.files[0]));

// ---- loading ----
const STEPS = ["Segregating M-series sheets", "Detecting & pairing duct walls",
  "Reading dimensions (12×22)", "Measuring lengths via scale", "Detecting L/T fittings",
  "Assembling BoQ + SMACNA pricing", "Compiling quotation"];
let stepTimer = null;
function showLoading() {
  $("#emptyState").hidden = true; $("#report").hidden = true; $("#loadingState").hidden = false;
  let i = 0;
  const render = () => $("#loaderSteps").innerHTML = STEPS.map((s, k) =>
    `<div class="${k < i ? 'done' : k === i ? 'active' : 'todo'}">${s}</div>`).join("");
  render(); stepTimer = setInterval(() => { if (i < STEPS.length - 1) { i++; render(); } }, 1400);
}
function stopLoading() { clearInterval(stepTimer); $("#loadingState").hidden = true; }

runBtn.addEventListener("click", async () => {
  if (!pickedFile) return;
  runBtn.disabled = true; showLoading();
  const fd = new FormData();
  fd.append("file", pickedFile);
  fd.append("project", $("#project").value || "Project");
  fd.append("use_llm", $("#useLlm").checked ? "true" : "false");
  try {
    const r = await fetch("/api/analyze", { method: "POST", body: fd });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json(); stopLoading(); render(data);
  } catch (err) {
    stopLoading(); $("#emptyState").hidden = false;
    $("#emptyState").innerHTML = `<div class="empty-art">⚠</div><h3>Analysis failed</h3><p>${err.message}</p>`;
  } finally { runBtn.disabled = false; }
});

// ---- render report ----
function render(d) {
  $("#report").hidden = false;
  state.base = d;
  state.rows = (d.line_items || []).map(li => ({ ...li, included: true, edited: false }));
  state.margin = d.margin_pct ?? 0.25;
  state.job = d.job; state.approved = false; state.dirty = false;
  $("#marginInput").value = Math.round(state.margin * 100);
  $("#approvedBanner").hidden = true;
  const ab = $("#approveBtn"); ab.classList.remove("done"); ab.textContent = "✓ Approve & Finalize"; ab.disabled = false;

  $("#qhTotal").textContent = fmt(d.total_sale_price);
  $("#qhMeta").textContent = `${d.project_name} · scale ${d.scale?.raw || "1/8\"=1'-0\""} · ${Math.round((d.margin_pct || 0) * 100)}% margin`;

  // sheets
  const imgs = d.annotated_images || [];
  $("#sheetCount").textContent = `${imgs.length} rendered`;
  $("#gallery").innerHTML = imgs.map(src => {
    const p = src.match(/annotated_p(\d+)/);
    return `<div class="shot" data-src="${src}"><img src="${src}" loading="lazy"><div class="cap">PAGE ${p ? p[1] : ""}</div></div>`;
  }).join("") || `<p class="tag">No annotated sheets produced.</p>`;
  document.querySelectorAll(".shot").forEach(s => s.addEventListener("click", () => openLight(s.dataset.src)));

  // fittings + thumb rules
  const fs = d.fittings_summary || {};
  const order = ["elbow_90", "elbow_45", "tee", "wye", "reducer", "transition", "offset", "clamps", "bolts"];
  $("#fittings").innerHTML = Object.keys(fs).sort((a, b) => order.indexOf(a) - order.indexOf(b))
    .map(k => `<span class="chip">${k.replace(/_/g, " ")} · <b>${fs[k]}</b></span>`).join("") || `<span class="tag">none detected</span>`;

  // detection review queue
  const low = d.low_confidence_items || [];
  const rp = $("#reviewPanel");
  if (low.length) { rp.hidden = false; $("#reviewChips").innerHTML = low.map(id => `<span class="chip">${id}</span>`).join(""); }
  else { rp.hidden = true; }

  renderBoQ(); renderStat(); renderKpis();
  $("#report").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---- KPIs ----
function renderKpis() {
  const inc = state.rows.filter(r => r.included);
  const total = state.rows.reduce((s, r) => s + (r.included ? (r.sale_price || 0) : 0), 0);
  const kpis = [
    { k: state.approved ? "Approved Quote" : "Quotation", v: fmt0(total), c: "amber" },
    { k: "M-Sheets", v: (state.base?.mechanical_pages || []).length, c: "" },
    { k: "Line items", v: inc.length, c: "teal" },
    { k: "Excluded", v: state.rows.length - inc.length, c: (state.rows.length - inc.length) ? "red" : "" },
  ];
  $("#kpis").innerHTML = kpis.map(x => `<div class="kpi ${x.c}"><div class="v">${x.v}</div><div class="k">${x.k}</div></div>`).join("");
  $("#qhTotal").textContent = fmt(total);
}

// ---- editable BoQ ----
function renderBoQ() {
  const body = $("#boqBody");
  const lock = state.approved ? "disabled" : "";
  body.innerHTML = state.rows.map((r, i) => {
    const isDuct = r.category === "duct", isHw = r.category === "hardware";
    const wIn = `<input class="cell w" type="number" min="0" value="${r.width_in ? Math.round(r.width_in) : ''}" ${isDuct ? lock : 'disabled'}>`;
    const hIn = `<input class="cell h" type="number" min="0" value="${r.height_in ? Math.round(r.height_in) : ''}" ${(isDuct && r.height_in) ? lock : 'disabled'}>`;
    const lIn = `<input class="cell len" type="number" min="0" step="0.1" value="${r.length_ft ? r.length_ft : ''}" ${isHw ? 'disabled' : lock}>`;
    const deriv = (r.derivation || []).map(x => `<span>${x}</span>`).join("");
    return `<tr class="row ${r.included ? '' : 'excluded'} ${r.edited ? 'edited' : ''}" data-i="${i}">
        <td><input class="inc" type="checkbox" ${r.included ? 'checked' : ''} ${lock}></td>
        <td>${i + 1}</td><td class="l">${r.description}</td><td>${r.page_label || ''}</td>
        <td>${wIn}</td><td>${hIn}</td><td>${lIn}</td>
        <td>${r.gauge || '—'}</td><td class="price">${fmt(r.sale_price)}</td>
        <td><button class="exp" title="cost derivation">▸</button></td>
      </tr>
      <tr class="deriv" hidden><td></td><td colspan="9"><div class="d-list">${deriv}</div></td></tr>`;
  }).join("") || `<tr><td colspan="10" style="text-align:center;color:var(--muted);padding:24px">No line items.</td></tr>`;
}

// event delegation on the table body
$("#boqBody").addEventListener("input", e => {
  const tr = e.target.closest("tr.row"); if (!tr) return;
  const r = state.rows[+tr.dataset.i];
  if (e.target.classList.contains("inc")) { r.included = e.target.checked; tr.classList.toggle("excluded", !r.included); markDirty(); renderKpis(); renderStat(); return; }
  if (e.target.classList.contains("w")) r.width_in = parseFloat(e.target.value) || 0;
  else if (e.target.classList.contains("h")) r.height_in = e.target.value === "" ? null : parseFloat(e.target.value);
  else if (e.target.classList.contains("len")) r.length_ft = parseFloat(e.target.value) || 0;
  else return;
  r.edited = true; tr.classList.add("edited"); markDirty();
});
$("#boqBody").addEventListener("click", e => {
  if (!e.target.classList.contains("exp")) return;
  const tr = e.target.closest("tr.row"); const d = tr.nextElementSibling;
  if (d) { d.hidden = !d.hidden; e.target.classList.toggle("open", !d.hidden); }
});

function markDirty() { state.dirty = true; renderStat(); }
function renderStat() {
  const inc = state.rows.filter(r => r.included).length;
  const edited = state.rows.filter(r => r.edited).length;
  $("#reviewStat").innerHTML = `${inc}/${state.rows.length} included`
    + (state.dirty ? ` · <span class="pend">changes pending — Recompute</span>` : (edited ? ` · ${edited} edited` : ``));
  $("#recomputeBtn").classList.toggle("pending", state.dirty);
}

$("#marginInput").addEventListener("input", e => { state.margin = (parseFloat(e.target.value) || 0) / 100; markDirty(); });
$("#recomputeBtn").addEventListener("click", () => callReprice(false));
$("#approveBtn").addEventListener("click", () => { if (!state.approved) callReprice(true); });

async function callReprice(finalize) {
  const payload = { line_items: state.rows.map(r => ({ ...r })), margin_pct: state.margin, finalize };
  const res = await fetch("/api/reprice", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const data = await res.json();
  const q = data.included_items.slice();
  state.rows = state.rows.map(r => r.included ? { ...r, ...q.shift(), included: true, edited: false } : { ...r, edited: false });
  state.dirty = false; state.margin = data.margin_pct;
  $("#qhMeta").textContent = `${state.base.project_name} · scale ${state.base.scale?.raw || "1/8\"=1'-0\""} · ${Math.round(state.margin * 100)}% margin`;
  if (finalize) {
    state.approved = true;
    $("#approvedBanner").hidden = false;
    const ab = $("#approveBtn"); ab.classList.add("done"); ab.textContent = "✓ Approved"; ab.disabled = true;
  }
  renderBoQ(); renderStat(); renderKpis();
}

// ---- lightbox + print ----
let lb;
function openLight(src) {
  if (!lb) { lb = document.createElement("div"); lb.className = "lightbox"; lb.innerHTML = "<img>"; lb.addEventListener("click", () => lb.classList.remove("open")); document.body.appendChild(lb); }
  lb.querySelector("img").src = src; lb.classList.add("open");
}
$("#printBtn").addEventListener("click", () => window.print());
