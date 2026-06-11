const $ = (s) => document.querySelector(s);
const fmt = (n) => "$" + (n ?? 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
const fmt0 = (n) => "$" + Math.round(n ?? 0).toLocaleString();

let pickedFile = null;

// ---- API health badge ----
fetch("/api/health").then(r => r.json()).then(d => {
  const b = $("#apiBadge"); b.textContent = "● engine online"; b.classList.add("ok");
}).catch(() => {
  const b = $("#apiBadge"); b.textContent = "● engine offline"; b.classList.add("err");
});

// ---- file selection ----
const dz = $("#dropzone"), fileInput = $("#fileInput"), runBtn = $("#runBtn");
function setFile(f) {
  if (!f || f.type !== "application/pdf") return;
  pickedFile = f;
  dz.classList.add("loaded");
  $("#dzMain").textContent = f.name;
  runBtn.disabled = false;
}
dz.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", e => setFile(e.target.files[0]));
["dragover", "dragenter"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add("drag"); }));
["dragleave", "drop"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", e => setFile(e.dataTransfer.files[0]));

// ---- run ----
const STEPS = ["Segregating M-series sheets", "Detecting & pairing duct walls",
  "Reading dimensions (12×22)", "Measuring lengths via scale", "Detecting L/T fittings",
  "Assembling BoQ + SMACNA pricing", "Compiling quotation"];
let stepTimer = null;
function showLoading() {
  $("#emptyState").hidden = true; $("#report").hidden = true; $("#loadingState").hidden = false;
  let i = 0;
  const render = () => $("#loaderSteps").innerHTML = STEPS.map((s, k) =>
    `<div class="${k < i ? 'done' : k === i ? 'active' : 'todo'}">${s}</div>`).join("");
  render();
  stepTimer = setInterval(() => { if (i < STEPS.length - 1) { i++; render(); } }, 1400);
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
    const data = await r.json();
    stopLoading(); render(data);
  } catch (err) {
    stopLoading(); $("#emptyState").hidden = false;
    $("#emptyState").innerHTML = `<div class="empty-art">⚠</div><h3>Analysis failed</h3><p>${err.message}</p>`;
  } finally { runBtn.disabled = false; }
});

// ---- render report ----
function render(d) {
  $("#report").hidden = false;

  const items = d.line_items || [];
  const kpis = [
    { k: "Quotation", v: fmt0(d.total_sale_price), c: "amber" },
    { k: "M-Sheets", v: (d.mechanical_pages || []).length, c: "" },
    { k: "Line items", v: items.length, c: "teal" },
    { k: "Need review", v: (d.low_confidence_items || []).length, c: (d.low_confidence_items || []).length ? "red" : "" },
  ];
  $("#kpis").innerHTML = kpis.map(x => `<div class="kpi ${x.c}"><div class="v">${x.v}</div><div class="k">${x.k}</div></div>`).join("");

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

  // BoQ
  $("#boqBody").innerHTML = items.map(i => {
    const deriv = (i.derivation || []).map(x => `<span>${x}</span>`).join("");
    return `<tr class="row">
        <td>${i.item_no}</td><td class="l">${i.description}</td><td>${i.page_label}</td>
        <td>${i.length_ft}</td><td>${i.surface_area_sqft}</td><td>${i.gauge || "—"}</td>
        <td>${i.weight_lbs}</td><td>${fmt(i.total_cost)}</td><td>${fmt(i.sale_price)}</td>
      </tr>
      <tr class="deriv" hidden><td></td><td colspan="8"><div class="d-list">${deriv}</div></td></tr>`;
  }).join("") || `<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:24px">No dimensioned duct runs found.</td></tr>`;
  document.querySelectorAll("#boqBody tr.row").forEach(row => {
    row.addEventListener("click", () => { const n = row.nextElementSibling; if (n) n.hidden = !n.hidden; });
  });

  // fittings + thumb rules
  const fs = d.fittings_summary || {};
  const order = ["elbow_90", "elbow_45", "tee", "wye", "reducer", "transition", "offset", "clamps", "bolts"];
  const chips = Object.keys(fs).sort((a, b) => order.indexOf(a) - order.indexOf(b))
    .map(k => `<span class="chip">${k.replace(/_/g, " ")} · <b>${fs[k]}</b></span>`).join("");
  $("#fittings").innerHTML = chips || `<span class="tag">none detected</span>`;

  // review
  const low = d.low_confidence_items || [];
  const rp = $("#reviewPanel");
  if (low.length) {
    rp.hidden = false;
    $("#reviewChips").innerHTML = low.map(id => `<span class="chip">${id}</span>`).join("");
  } else { rp.hidden = true; }

  $("#report").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---- lightbox ----
let lb;
function openLight(src) {
  if (!lb) { lb = document.createElement("div"); lb.className = "lightbox"; lb.innerHTML = "<img>";
    lb.addEventListener("click", () => lb.classList.remove("open")); document.body.appendChild(lb); }
  lb.querySelector("img").src = src; lb.classList.add("open");
}

$("#printBtn").addEventListener("click", () => window.print());
