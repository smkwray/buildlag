// ───────────────────────────────────────────────────────────────
//  Underbuilt vs. Overpriced Atlas — main application
// ───────────────────────────────────────────────────────────────

const state = {
  panel: [],
  metaData: null,
  metroPoints: null,
  detailIndex: null,
  detailContexts: {},
  detailCounties: {},
  _detailDictsLoaded: false,
  sourceCatalog: null,
  selectedCbsa: null,
  scoreMode: "overall",      // overall | underbuilt | overpriced
  sortKey: "overall_score",
  sortAsc: false,
  compareSet: new Set(),      // cbsa codes
  nationalMap: null,
  nationalTileLayer: null,
  nationalMarkers: new Map(),
  detailMap: null,
  detailTileLayer: null,
  detailCache: {},
  detailBounds: null,         // saved bounds for reset
  hoveredCbsa: null,
  initialLoadDone: false,
};

// ───── Helpers ─────
const fmt = {
  int: (v) => v == null ? "—" : new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(v),
  money: (v) => v == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(v),
  pct: (v) => v == null ? "—" : `${Number(v).toFixed(1)}%`,
  dec: (v, d = 1) => v == null ? "—" : Number(v).toFixed(d),
};

function scoreForMode(row, mode) {
  if (mode === "underbuilt") return Number(row.underbuilt_component);
  if (mode === "overpriced") return Number(row.overpriced_component);
  return Number(row.overall_score);
}

// ───── Continuous color scale ─────
// 10-stop gradient: green(0) -> teal(15) -> lime(30) -> yellow(45) -> gold(55)
//                 -> orange(65) -> deep-orange(75) -> red(85) -> crimson(95) -> dark-red(100)
const COLOR_STOPS = [
  [0,   [34, 139, 34]],    // forest green
  [15,  [46, 160, 67]],    // green
  [25,  [74, 180, 72]],    // lime green
  [35,  [162, 179, 36]],   // yellow-green
  [45,  [202, 166, 8]],    // gold
  [55,  [218, 140, 10]],   // amber
  [65,  [225, 108, 14]],   // orange
  [75,  [220, 72, 18]],    // deep orange
  [85,  [204, 40, 28]],    // red
  [100, [153, 18, 18]],    // dark crimson
];

function scoreColorRaw(score) {
  const s = Math.max(0, Math.min(100, Number(score)));
  // Find the two stops we sit between
  let lo = COLOR_STOPS[0], hi = COLOR_STOPS[COLOR_STOPS.length - 1];
  for (let i = 0; i < COLOR_STOPS.length - 1; i++) {
    if (s >= COLOR_STOPS[i][0] && s <= COLOR_STOPS[i + 1][0]) {
      lo = COLOR_STOPS[i];
      hi = COLOR_STOPS[i + 1];
      break;
    }
  }
  const t = hi[0] === lo[0] ? 0 : (s - lo[0]) / (hi[0] - lo[0]);
  const r = Math.round(lo[1][0] + t * (hi[1][0] - lo[1][0]));
  const g = Math.round(lo[1][1] + t * (hi[1][1] - lo[1][1]));
  const b = Math.round(lo[1][2] + t * (hi[1][2] - lo[1][2]));
  return `rgb(${r},${g},${b})`;
}

function bucketLabel(score) {
  if (score >= 75) return "Acute";
  if (score >= 55) return "Elevated";
  if (score >= 35) return "Watch";
  return "Lower";
}

function pop(row) { return Number(row.population ?? 0); }
function fmr(row) { return Number(row.hud_fmr_2br ?? row.fmr_2br ?? 0); }

async function loadJson(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`Failed: ${path}`);
  return r.json();
}

// ───── Score‑mode toggle ─────
function initModeToggle() {
  const toggle = document.getElementById("score-mode-toggle");
  toggle.addEventListener("click", (e) => {
    const btn = e.target.closest(".mode-btn");
    if (!btn) return;
    state.scoreMode = btn.dataset.mode;
    toggle.querySelectorAll(".mode-btn").forEach((b) => b.classList.toggle("is-active", b === btn));
    document.getElementById("map-color-label").textContent = state.scoreMode;
    renderNationalMap();
    renderScatterplot();
    renderTable();
  });
}

// ───── Vintage strip ─────
function renderVintageStrip() {
  const v = state.metaData?.data_vintages;
  if (!v) return;
  const chips = [
    ["Building Permits", v.bps],
    ["ACS Metro", v.acs_metro],
    ["ACS County", v.acs_county],
    ["HUD FMR", v.hud],
    ["HUD SAFMR", v.hud_safmr],
    ["Delineation", v.delineation],
    ["ZCTA Geometry", v.zcta_boundaries],
    ["County Geometry", v.county_boundaries],
  ];
  document.getElementById("vintage-strip").innerHTML = chips
    .map(([label, val]) => `<span class="vintage-chip"><strong>${val}</strong> ${label}</span>`)
    .join("");
}

// ───── National map ─────
const NATIONAL_DEFAULT_VIEW = { center: [38.5, -96], zoom: 4 };

function renderNationalMap() {
  const geojson = state.metroPoints;
  if (!geojson) return;

  if (!state.nationalMap) {
    state.nationalMap = L.map("national-map", { zoomControl: true }).setView(NATIONAL_DEFAULT_VIEW.center, NATIONAL_DEFAULT_VIEW.zoom);
    state.nationalTileLayer = L.tileLayer(getTileUrl(), {
      maxZoom: 18,
      attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
      subdomains: "abcd",
    }).addTo(state.nationalMap);

    // Reset control
    addResetControl(state.nationalMap, () => {
      state.nationalMap.setView(NATIONAL_DEFAULT_VIEW.center, NATIONAL_DEFAULT_VIEW.zoom);
    });
  }

  // Clear existing markers
  state.nationalMarkers.forEach((m) => m.remove());
  state.nationalMarkers.clear();

  geojson.features.forEach((f) => {
    const p = f.properties;
    const [lon, lat] = f.geometry.coordinates;
    const score = scoreForMode(p, state.scoreMode);
    const radius = Math.max(6, Math.sqrt(pop(p)) / 70);
    const isSelected = p.cbsa_code === state.selectedCbsa;

    const marker = L.circleMarker([lat, lon], {
      radius,
      color: isSelected ? "#fff" : scoreColorRaw(score),
      fillColor: scoreColorRaw(score),
      fillOpacity: 0.7,
      weight: isSelected ? 3 : 1.2,
      opacity: isSelected ? 1 : 0.85,
    });

    marker.bindPopup(`
      <strong>${p.metro_name}</strong><br/>
      Overall: ${p.overall_score} · Underbuilt: ${p.underbuilt_component} · Overpriced: ${p.overpriced_component}<br/>
      Permits/1k HH: ${p.permits_per_1000_households} · 2BR FMR: ${fmt.money(fmr(p))}<br/>
      Pop: ${fmt.int(pop(p))}
    `);

    marker.on("click", () => selectMetro(p.cbsa_code));
    marker.on("mouseover", () => { state.hoveredCbsa = p.cbsa_code; highlightTableRow(p.cbsa_code); });
    marker.on("mouseout", () => { state.hoveredCbsa = null; highlightTableRow(null); });
    marker.addTo(state.nationalMap);
    state.nationalMarkers.set(p.cbsa_code, marker);
  });

  // Gradient legend
  const gradStops = COLOR_STOPS.map(([pct, rgb]) => `rgb(${rgb.join(",")}) ${pct}%`).join(", ");
  document.getElementById("national-legend").innerHTML = `
    <div class="gradient-legend">
      <div class="gradient-legend-bar" style="background:linear-gradient(to right, ${gradStops})"></div>
      <div class="gradient-legend-labels">
        <span>0 Lower</span><span>35 Watch</span><span>55 Elevated</span><span>75 Acute</span><span>100</span>
      </div>
    </div>
  `;
}

// ───── Scatterplot (canvas) ─────
function renderScatterplot() {
  const canvas = document.getElementById("scatterplot");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  const W = rect.width;
  const H = rect.height;
  const pad = { top: 20, right: 20, bottom: 36, left: 50 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  const data = state.panel;
  if (!data.length) return;

  // Extents
  const xs = data.map((d) => d.permits_per_1000_households);
  const ys = data.map((d) => d.rent_burdened_share_pct);
  const xMin = 0;
  const xMax = Math.ceil(Math.max(...xs) / 5) * 5;
  const yMin = Math.floor(Math.min(...ys) / 5) * 5;
  const yMax = Math.ceil(Math.max(...ys) / 5) * 5;

  const xScale = (v) => pad.left + ((v - xMin) / (xMax - xMin)) * plotW;
  const yScale = (v) => pad.top + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

  // Clear
  ctx.clearRect(0, 0, W, H);

  // Read theme-aware colors from CSS
  const compStyle = getComputedStyle(document.documentElement);
  const gridColor = compStyle.getPropertyValue("--scatter-grid").trim() || "rgba(136,153,176,0.1)";
  const medianColor = compStyle.getPropertyValue("--scatter-median").trim() || "rgba(136,153,176,0.25)";
  const labelColor = compStyle.getPropertyValue("--scatter-label").trim() || "#5e6b7d";

  // Grid
  ctx.strokeStyle = gridColor;
  ctx.lineWidth = 1;
  for (let x = 0; x <= xMax; x += 5) {
    const px = xScale(x);
    ctx.beginPath(); ctx.moveTo(px, pad.top); ctx.lineTo(px, pad.top + plotH); ctx.stroke();
  }
  for (let y = yMin; y <= yMax; y += 5) {
    const py = yScale(y);
    ctx.beginPath(); ctx.moveTo(pad.left, py); ctx.lineTo(pad.left + plotW, py); ctx.stroke();
  }

  // Axis labels
  ctx.fillStyle = labelColor;
  ctx.font = "11px Inter, sans-serif";
  ctx.textAlign = "center";
  for (let x = 0; x <= xMax; x += 5) {
    ctx.fillText(x, xScale(x), pad.top + plotH + 16);
  }
  ctx.textAlign = "right";
  for (let y = yMin; y <= yMax; y += 5) {
    ctx.fillText(y + "%", pad.left - 6, yScale(y) + 4);
  }

  // Quadrant medians
  const medX = [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];
  const medY = [...ys].sort((a, b) => a - b)[Math.floor(ys.length / 2)];
  ctx.strokeStyle = medianColor;
  ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(xScale(medX), pad.top); ctx.lineTo(xScale(medX), pad.top + plotH); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(pad.left, yScale(medY)); ctx.lineTo(pad.left + plotW, yScale(medY)); ctx.stroke();
  ctx.setLineDash([]);

  // Dots
  data.forEach((d) => {
    const cx = xScale(d.permits_per_1000_households);
    const cy = yScale(d.rent_burdened_share_pct);
    const score = scoreForMode(d, state.scoreMode);
    const r = Math.max(4, Math.sqrt(pop(d)) / 180);
    const isSelected = d.cbsa_code === state.selectedCbsa;
    const isHovered = d.cbsa_code === state.hoveredCbsa;

    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = scoreColorRaw(score);
    ctx.globalAlpha = isSelected || isHovered ? 1 : 0.6;
    ctx.fill();
    const ringStroke = isLightMode() ? "#1a1d23" : "#fff";
    if (isSelected) {
      ctx.strokeStyle = ringStroke;
      ctx.lineWidth = 2;
      ctx.stroke();
    } else if (isHovered) {
      ctx.strokeStyle = isLightMode() ? "rgba(0,0,0,0.5)" : "rgba(255,255,255,0.6)";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  });

  // Store dot positions for hit detection
  canvas._dots = data.map((d) => ({
    cbsa: d.cbsa_code,
    x: xScale(d.permits_per_1000_households),
    y: yScale(d.rent_burdened_share_pct),
    r: Math.max(4, Math.sqrt(pop(d)) / 180),
    row: d,
  }));
}

function initScatterInteraction() {
  const canvas = document.getElementById("scatterplot");
  if (!canvas) return;

  let tooltip = document.getElementById("scatter-tooltip");
  if (!tooltip) {
    tooltip = document.createElement("div");
    tooltip.id = "scatter-tooltip";
    tooltip.className = "hover-tooltip";
    tooltip.style.display = "none";
    document.body.appendChild(tooltip);
  }

  canvas.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const dots = canvas._dots || [];
    let hit = null;
    for (const dot of dots) {
      const dx = mx - dot.x;
      const dy = my - dot.y;
      if (dx * dx + dy * dy < (dot.r + 4) * (dot.r + 4)) {
        hit = dot;
        break;
      }
    }
    if (hit) {
      canvas.style.cursor = "pointer";
      state.hoveredCbsa = hit.cbsa;
      highlightTableRow(hit.cbsa);
      tooltip.style.display = "block";
      tooltip.style.left = (e.clientX + 12) + "px";
      tooltip.style.top = (e.clientY - 8) + "px";
      const r = hit.row;
      tooltip.innerHTML = `
        <strong>${r.metro_name}</strong>
        Permits/1k HH: ${r.permits_per_1000_households}<br/>
        Rent burden: ${fmt.pct(r.rent_burdened_share_pct)}<br/>
        Overall: ${r.overall_score} · Underbuilt: ${r.underbuilt_component} · Overpriced: ${r.overpriced_component}
      `;
    } else {
      canvas.style.cursor = "default";
      state.hoveredCbsa = null;
      highlightTableRow(null);
      tooltip.style.display = "none";
    }
  });

  canvas.addEventListener("mouseleave", () => {
    tooltip.style.display = "none";
    state.hoveredCbsa = null;
    highlightTableRow(null);
  });

  canvas.addEventListener("click", (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const dots = canvas._dots || [];
    for (const dot of dots) {
      const dx = mx - dot.x;
      const dy = my - dot.y;
      if (dx * dx + dy * dy < (dot.r + 4) * (dot.r + 4)) {
        selectMetro(dot.cbsa);
        return;
      }
    }
  });
}

// ───── Ranking table ─────
function sortedPanel(filterText = "") {
  const query = filterText.trim().toLowerCase();
  let rows = state.panel.filter((r) => !query || r.metro_name.toLowerCase().includes(query));
  const key = state.sortKey;
  rows.sort((a, b) => {
    let va = a[key], vb = b[key];
    if (typeof va === "string") {
      return state.sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    }
    va = Number(va); vb = Number(vb);
    return state.sortAsc ? va - vb : vb - va;
  });
  return rows;
}

function renderTable() {
  const filterVal = document.getElementById("table-filter").value;
  const rows = sortedPanel(filterVal);
  document.getElementById("table-count").textContent = rows.length;
  const sortLabel = {
    overall_score: "overall score",
    underbuilt_component: "underbuilt",
    overpriced_component: "overpriced",
    permits_per_1000_households: "permits/1k HH",
    hud_fmr_2br: "2BR FMR",
    median_household_income: "income",
    rent_burdened_share_pct: "rent burden",
    metro_name: "name",
  };
  document.getElementById("sort-label").textContent = sortLabel[state.sortKey] || state.sortKey;

  // Update active sort header
  document.querySelectorAll("#ranking-table th .sortable, #ranking-table th.sortable").forEach((el) => {
    el.classList.toggle("is-active-sort", el.dataset.sort === state.sortKey);
  });

  const body = document.getElementById("ranking-body");
  body.innerHTML = rows.map((r, i) => {
    const isSelected = r.cbsa_code === state.selectedCbsa;
    const isCompared = state.compareSet.has(r.cbsa_code);
    const score = r.overall_score;
    return `
      <tr data-cbsa="${r.cbsa_code}" class="${isSelected ? "is-selected" : ""}">
        <td class="rank-num">${i + 1}</td>
        <td class="metro-name-cell">${shortName(r.metro_name)}<span class="metro-state">${r.state_abbrs || ""}</span></td>
        <td class="score-cell" style="color:${scoreColorRaw(score)}">${score}</td>
        <td>
          <div class="decomp-bar"><div class="decomp-fill" style="width:${r.underbuilt_component}%;background:var(--underbuilt)"></div></div>
          <span style="font-size:0.78rem;color:var(--text-secondary)">${r.underbuilt_component}</span>
        </td>
        <td>
          <div class="decomp-bar"><div class="decomp-fill" style="width:${r.overpriced_component}%;background:var(--overpriced)"></div></div>
          <span style="font-size:0.78rem;color:var(--text-secondary)">${r.overpriced_component}</span>
        </td>
        <td>${r.permits_per_1000_households}</td>
        <td>${fmt.money(fmr(r))}</td>
        <td>${fmt.money(r.median_household_income)}</td>
        <td>${fmt.pct(r.rent_burdened_share_pct)}</td>
      </tr>`;
  }).join("");

  // Attach click handlers
  body.querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("click", (e) => {
      selectMetro(tr.dataset.cbsa);
    });
    tr.addEventListener("dblclick", (e) => {
      e.preventDefault();
      toggleCompare(tr.dataset.cbsa);
    });
  });
}

function shortName(name) {
  // Trim after second comma for display
  const parts = name.split(",");
  return parts.length > 2 ? parts.slice(0, 2).join(",") : name.split(",")[0];
}

function highlightTableRow(cbsa) {
  document.querySelectorAll("#ranking-body tr.is-highlighted").forEach((el) => el.classList.remove("is-highlighted"));
  if (cbsa) {
    const row = document.querySelector(`#ranking-body tr[data-cbsa="${cbsa}"]`);
    if (row) row.classList.add("is-highlighted");
  }
}

function initTableSort() {
  document.querySelectorAll("#ranking-table .sortable").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      const key = el.dataset.sort;
      if (state.sortKey === key) {
        state.sortAsc = !state.sortAsc;
      } else {
        state.sortKey = key;
        state.sortAsc = key === "metro_name";
      }
      renderTable();
    });
  });
  document.getElementById("table-filter").addEventListener("input", () => renderTable());
}

// ───── Compare tray ─────
function toggleCompare(cbsa) {
  if (state.compareSet.has(cbsa)) {
    state.compareSet.delete(cbsa);
  } else if (state.compareSet.size < 4) {
    state.compareSet.add(cbsa);
  }
  renderCompareTray();
  renderTable();
}

function renderCompareTray() {
  const tray = document.getElementById("compare-tray");
  if (state.compareSet.size === 0) {
    tray.classList.remove("is-open");
    return;
  }
  tray.classList.add("is-open");

  const cards = [...state.compareSet].map((cbsa) => {
    const r = state.panel.find((d) => d.cbsa_code === cbsa);
    if (!r) return "";
    return `
      <div class="compare-card">
        <div class="compare-card-name">${r.metro_name}</div>
        <div class="compare-metric"><span class="compare-metric-label">Overall</span><span class="compare-metric-value" style="color:${scoreColorRaw(r.overall_score)}">${r.overall_score}</span></div>
        <div class="compare-metric"><span class="compare-metric-label">Underbuilt</span><span class="compare-metric-value">${r.underbuilt_component}</span></div>
        <div class="compare-metric"><span class="compare-metric-label">Overpriced</span><span class="compare-metric-value">${r.overpriced_component}</span></div>
        <div class="compare-metric"><span class="compare-metric-label">Permits/1k HH</span><span class="compare-metric-value">${r.permits_per_1000_households}</span></div>
        <div class="compare-metric"><span class="compare-metric-label">2BR FMR</span><span class="compare-metric-value">${fmt.money(fmr(r))}</span></div>
        <div class="compare-metric"><span class="compare-metric-label">Income</span><span class="compare-metric-value">${fmt.money(r.median_household_income)}</span></div>
        <div class="compare-metric"><span class="compare-metric-label">Burden</span><span class="compare-metric-value">${fmt.pct(r.rent_burdened_share_pct)}</span></div>
      </div>`;
  }).join("");
  document.getElementById("compare-cards").innerHTML = cards;
}

function initCompareTray() {
  document.getElementById("compare-clear").addEventListener("click", () => {
    state.compareSet.clear();
    renderCompareTray();
    renderTable();
  });
}

// ───── Selected metro detail ─────
function getDetailEntry(cbsa) {
  return state.detailIndex?.supported_details?.find((e) => e.cbsa_code === cbsa) ?? null;
}

async function ensureDetailDicts() {
  if (!state._detailDictsLoaded) {
    const [ctx, cty] = await Promise.all([
      loadJson("data/detail_contexts.json").catch(() => ({})),
      loadJson("data/detail_counties.json").catch(() => ({})),
    ]);
    state.detailContexts = ctx;
    state.detailCounties = cty;
    state._detailDictsLoaded = true;
  }
}

async function loadDetailBundle(cbsa) {
  const entry = getDetailEntry(cbsa);
  if (!entry) return null;
  if (!state.detailCache[cbsa]) {
    await ensureDetailDicts();
    const context = state.detailContexts?.[cbsa] ?? null;
    const counties = state.detailCounties?.[cbsa] ?? null;
    const zips = await loadJson(entry.zips_path);
    state.detailCache[cbsa] = { zips, counties, context };
  }
  return state.detailCache[cbsa];
}

async function selectMetro(cbsa) {
  state.selectedCbsa = cbsa;
  const row = state.panel.find((d) => d.cbsa_code === cbsa);
  if (!row) return;

  // Header
  document.getElementById("detail-metro-name").textContent = row.metro_name;
  const scoreVal = document.getElementById("detail-score-value");
  scoreVal.textContent = row.overall_score;
  scoreVal.style.color = scoreColorRaw(row.overall_score);
  const ring = document.getElementById("detail-score-ring");
  ring.style.borderColor = scoreColorRaw(row.overall_score);

  // Component bars
  document.getElementById("detail-bar-under").style.width = row.underbuilt_component + "%";
  document.getElementById("detail-val-under").textContent = row.underbuilt_component;
  document.getElementById("detail-bar-over").style.width = row.overpriced_component + "%";
  document.getElementById("detail-val-over").textContent = row.overpriced_component;

  // Explainer
  renderExplainer(row);

  // Detail metrics
  renderDetailMetrics(row);

  // Load detail bundle
  const bundle = await loadDetailBundle(cbsa);
  renderDetailMap(bundle);
  renderCountyStrip(bundle);

  // Update other views
  renderNationalMap();
  renderScatterplot();
  renderTable();

  // Only scroll to detail on user-initiated selections, not on initial page load
  if (state.initialLoadDone) {
    document.getElementById("detail-section").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function renderExplainer(row) {
  const el = document.getElementById("explainer-panel");
  const bullets = [];
  const p1k = row.permits_per_1000_households;
  const fmrIncome = row.fmr_to_income;
  const burden = row.rent_burdened_share_pct;

  if (row.underbuilt_component >= 70) {
    bullets.push(`<strong>Very low construction intensity.</strong> Only ${p1k} permits per 1,000 households — in the bottom quartile nationally. This drives a high underbuilt score of ${row.underbuilt_component}.`);
  } else if (row.underbuilt_component >= 40) {
    bullets.push(`Moderate construction activity at ${p1k} permits per 1,000 households. Underbuilt score: ${row.underbuilt_component}.`);
  } else {
    bullets.push(`Relatively strong permitting at ${p1k} permits per 1,000 households. Underbuilt score: ${row.underbuilt_component}.`);
  }

  if (row.overpriced_component >= 70) {
    bullets.push(`<strong>High rent-to-income pressure.</strong> The 2BR FMR of ${fmt.money(fmr(row))} is ${fmt.pct(fmrIncome * 100)} of median household income, and ${fmt.pct(burden)} of renters are cost-burdened. Overpriced score: ${row.overpriced_component}.`);
  } else if (row.overpriced_component >= 40) {
    bullets.push(`Moderate affordability stress — ${fmt.pct(burden)} of renters are cost-burdened. Overpriced score: ${row.overpriced_component}.`);
  } else {
    bullets.push(`Lower affordability stress relative to peers. Overpriced score: ${row.overpriced_component}.`);
  }

  const overall = row.overall_score;
  const label = bucketLabel(overall);
  bullets.push(`Combined, this metro screens as <strong>${label.toLowerCase()} pressure</strong> (${overall}/100).`);

  el.innerHTML = `
    <p class="explainer-title">Why does ${shortName(row.metro_name)} score ${overall}?</p>
    <ul class="explainer-bullets">${bullets.map((b) => `<li>${b}</li>`).join("")}</ul>
  `;
}

function renderDetailMetrics(row) {
  const metrics = [
    ["Population", fmt.int(pop(row))],
    ["Households", fmt.int(row.households)],
    [`Permits (${state.metaData?.data_vintages?.bps ?? "Annual"})`, fmt.int(row.permits_annual)],
    ["Permits / 1k HH", row.permits_per_1000_households],
    ["2BR FMR", fmt.money(fmr(row))],
    ["Median income", fmt.money(row.median_household_income)],
    ["FMR / income", fmt.pct((row.fmr_to_income ?? 0) * 100)],
    ["Renter burden 35%+", fmt.pct(row.rent_burdened_share_pct)],
  ];
  document.getElementById("detail-metrics").innerHTML = metrics.map(([label, value]) => `
    <div class="detail-metric-card">
      <span class="detail-metric-label">${label}</span>
      <span class="detail-metric-value">${value}</span>
    </div>
  `).join("");
}

// ───── Detail ZIP map ─────
function safmrColor(value) {
  const v = Number(value);
  if (v >= 2400) return "#dc2626";
  if (v >= 2000) return "#ea580c";
  if (v >= 1600) return "#ca8a04";
  if (v >= 1200) return "#2563eb";
  return "#16a34a";
}

function renderDetailMap(bundle) {
  const placeholder = document.getElementById("detail-placeholder");
  const mapEl = document.getElementById("detail-map");

  if (!bundle) {
    placeholder.classList.remove("hidden");
    mapEl.classList.add("hidden");
    document.getElementById("detail-map-note").textContent = "No ZIP detail available";
    return;
  }

  placeholder.classList.add("hidden");
  mapEl.classList.remove("hidden");
  document.getElementById("detail-map-note").textContent = `${bundle.context?.cbsa_summary?.zip_count ?? "?"} ZIPs · HUD SAFMR ${state.metaData?.data_vintages?.hud_safmr ?? "FY2026"} · ZCTA geometry`;

  if (state.detailMap) state.detailMap.remove();

  state.detailMap = L.map("detail-map", { zoomControl: true });
  state.detailTileLayer = L.tileLayer(getTileUrl(), {
    maxZoom: 18,
    attribution: '&copy; CARTO &copy; OSM',
    subdomains: "abcd",
  }).addTo(state.detailMap);

  // Median SAFMR for the metro
  const medSafmr = bundle.context?.cbsa_summary?.safmr_2br_median;

  const zipLayer = L.geoJSON(bundle.zips, {
    style: (f) => ({
      color: "rgba(255,255,255,0.25)",
      weight: 0.8,
      fillColor: safmrColor(f.properties.safmr_2br),
      fillOpacity: 0.5,
    }),
    onEachFeature: (f, layer) => {
      const p = f.properties;
      const vs = medSafmr != null ? ` (metro median: ${fmt.money(medSafmr)})` : "";
      layer.bindPopup(`
        <strong>ZIP ${p.zip_code}</strong><br/>
        2BR SAFMR: ${fmt.money(p.safmr_2br)}${vs}<br/>
        Band: ${p.pressure_band}
      `);
    },
  }).addTo(state.detailMap);

  const countyLayer = L.geoJSON(bundle.counties, {
    style: () => ({
      color: "#f8fafc",
      weight: 2,
      fillOpacity: 0,
      dashArray: "6 3",
    }),
    onEachFeature: (f, layer) => {
      const p = f.properties;
      layer.bindPopup(`
        <strong>${p.county_name}</strong><br/>
        Permits: ${p.permits_annual != null ? fmt.int(p.permits_annual) : "n/a"}<br/>
        Permits/1k HH: ${p.permits_per_1000_households ?? "n/a"}<br/>
        Rent burden: ${p.rent_burdened_share_pct != null ? fmt.pct(p.rent_burdened_share_pct) : "n/a"}
      `);
    },
  }).addTo(state.detailMap);

  const bounds = L.featureGroup([zipLayer, countyLayer]).getBounds().pad(0.08);
  state.detailMap.fitBounds(bounds);
  state.detailBounds = bounds;

  // Reset control
  addResetControl(state.detailMap, () => {
    if (state.detailBounds) state.detailMap.fitBounds(state.detailBounds);
  });
}

// ───── County strip ─────
function renderCountyStrip(bundle) {
  const host = document.getElementById("county-strip");
  if (!bundle || !bundle.context) {
    host.innerHTML = `<p style="color:var(--text-dim);padding:16px;">No county data available.</p>`;
    return;
  }
  const counties = bundle.context.counties || [];
  host.innerHTML = counties.map((c) => `
    <div class="county-card">
      <div class="county-card-name">${c.county_name}</div>
      <div class="county-metrics">
        <div class="county-metric">
          <span class="county-metric-label">Population</span>
          <span class="county-metric-value">${fmt.int(c.population)}</span>
        </div>
        <div class="county-metric">
          <span class="county-metric-label">Permits</span>
          <span class="county-metric-value">${fmt.int(c.permits_annual)}</span>
        </div>
        <div class="county-metric">
          <span class="county-metric-label">Permits/1k HH</span>
          <span class="county-metric-value">${fmt.dec(c.permits_per_1000_households)}</span>
        </div>
        <div class="county-metric">
          <span class="county-metric-label">Rent burden</span>
          <span class="county-metric-value">${c.rent_burdened_share_pct != null ? fmt.pct(c.rent_burdened_share_pct) : "—"}</span>
        </div>
        <div class="county-metric">
          <span class="county-metric-label">Median income</span>
          <span class="county-metric-value">${fmt.money(c.median_household_income)}</span>
        </div>
        <div class="county-metric">
          <span class="county-metric-label">Households</span>
          <span class="county-metric-value">${fmt.int(c.households)}</span>
        </div>
      </div>
    </div>
  `).join("");
}

// ───── Source cards ─────
function renderSourceCards() {
  const cat = state.sourceCatalog;
  if (!cat) return;
  const vintages = cat.data_vintages || {};
  const sources = cat.data_sources || [];

  // Map source IDs to their vintage label by prefix pattern.
  // IDs are now parameterized by year, so match on stable prefixes.
  function vintageForId(id) {
    if (id.startsWith("census_bps")) return vintages.bps;
    if (id.startsWith("acs1_")) return vintages.acs_metro;
    if (id.startsWith("acs5_")) return vintages.acs_county;
    if (id.startsWith("hud_fmr")) return vintages.hud;
    if (id.startsWith("hud_safmr")) return vintages.hud_safmr;
    if (id.startsWith("delineation_")) return vintages.delineation;
    if (id.startsWith("metro_population")) return vintages.population;
    if (id === "census_cbsa_gazetteer_2023") return vintages.gazetteer;
    if (id.startsWith("census_zcta")) return vintages.zcta_boundaries;
    if (id.startsWith("census_county_boundaries")) return vintages.county_boundaries;
    return "";
  }

  // Show curated subset: exclude docs/reference-only entries
  const hidePrefixes = ["census_bps_home", "census_bps_master", "hud_fmr_docs", "hud_fmr_api_docs", "census_cbsa_gazetteer"];
  const filtered = sources.filter((s) => !hidePrefixes.some((p) => s.id.startsWith(p)));

  document.getElementById("source-grid").innerHTML = filtered.map((s) => `
    <div class="source-card">
      <div class="source-card-name">${s.name}</div>
      <div class="source-card-vintage">${vintageForId(s.id) || ""}</div>
      <div class="source-card-purpose">${s.purpose}</div>
      <a href="${s.url}" target="_blank" rel="noopener">View source &rarr;</a>
    </div>
  `).join("");
}

// ───── Theme ─────
function isLightMode() {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit) return explicit === "light";
  return window.matchMedia("(prefers-color-scheme: light)").matches;
}

function getTileUrl() {
  const variant = isLightMode() ? "light_all" : "dark_all";
  return `https://{s}.basemaps.cartocdn.com/${variant}/{z}/{x}/{y}{r}.png`;
}

function swapTileLayers() {
  const url = getTileUrl();
  if (state.nationalTileLayer) state.nationalTileLayer.setUrl(url);
  if (state.detailTileLayer) state.detailTileLayer.setUrl(url);
}

function updateThemeIcon() {
  const icon = document.getElementById("theme-icon");
  if (icon) icon.innerHTML = isLightMode() ? "&#9728;" : "&#9790;";
}

function initThemeToggle() {
  // Restore saved preference
  const saved = localStorage.getItem("atlas-theme");
  if (saved) {
    document.documentElement.setAttribute("data-theme", saved);
  }
  updateThemeIcon();

  document.getElementById("theme-toggle").addEventListener("click", () => {
    const current = isLightMode();
    const next = current ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("atlas-theme", next);
    updateThemeIcon();
    swapTileLayers();
    renderScatterplot();
  });

  // Listen for system theme changes
  window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
    if (!localStorage.getItem("atlas-theme")) {
      updateThemeIcon();
      swapTileLayers();
      renderScatterplot();
    }
  });
}

// ───── Map reset control ─────
function addResetControl(map, resetFn) {
  const ResetControl = L.Control.extend({
    options: { position: "topleft" },
    onAdd() {
      const btn = L.DomUtil.create("a", "leaflet-control-reset");
      btn.href = "#";
      btn.title = "Reset view";
      btn.setAttribute("role", "button");
      btn.setAttribute("aria-label", "Reset map view");
      btn.innerHTML = "&#8962;"; // house/home symbol
      L.DomEvent.disableClickPropagation(btn);
      L.DomEvent.on(btn, "click", (e) => {
        L.DomEvent.preventDefault(e);
        resetFn();
      });
      return btn;
    },
  });
  new ResetControl().addTo(map);
}

// ───── Init ─────
async function init() {
  const [panel, points, meta, detailIndex, catalog] = await Promise.all([
    loadJson("data/metro_panel.json"),
    loadJson("data/metro_points.geojson"),
    loadJson("data/meta.json"),
    loadJson("data/detail_index.json").catch(() => null),
    loadJson("data/source_catalog.json").catch(() => null),
  ]);

  state.panel = panel;
  state.metroPoints = points;
  state.metaData = meta;
  state.detailIndex = detailIndex;
  state.sourceCatalog = catalog;
  state.selectedCbsa = meta.detail_metro_code || panel[0]?.cbsa_code;

  initThemeToggle();
  initModeToggle();
  initTableSort();
  initCompareTray();
  renderVintageStrip();
  renderNationalMap();
  renderScatterplot();
  renderTable();
  renderSourceCards();
  initScatterInteraction();

  // Select default metro (without scrolling)
  await selectMetro(state.selectedCbsa);
  state.initialLoadDone = true;

  // Resize handler for scatterplot
  window.addEventListener("resize", () => renderScatterplot());
}

init().catch((err) => {
  console.error(err);
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<div style="padding:16px 20px;background:#7f1d1d;color:#fee2e2;font-size:0.9rem;">Failed to load data: ${err.message}</div>`,
  );
});
