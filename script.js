// =========================================================
// CineGraph — Frontend Logic
// Berkomunikasi dengan backend Flask yang mengimplementasikan
// struktur data Graph (Adjacency List) untuk rekomendasi film.
// =========================================================

const state = {
  movies: [],
  currentSourceId: null,
  fullNetwork: null,
  egoNetwork: null,
  pathSelection: [], // menyimpan max 2 id node yang diklik di graf penuh
};

const el = (id) => document.getElementById(id);

// ---------------------------------------------------------
// INIT
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  await loadMovieList();
  bindEvents();
});

async function loadMovieList() {
  const res = await fetch("/api/movies");
  const movies = await res.json();
  state.movies = movies;

  const select = el("movieSelect");
  select.innerHTML = '<option value="" disabled selected>Pilih film…</option>';
  movies.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = `${m.title} (${m.year})`;
    select.appendChild(opt);
  });
}

function bindEvents() {
  el("searchForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const movieId = el("movieSelect").value;
    if (!movieId) return;
    await runRecommendation(movieId);
  });

  el("btnFullGraph").addEventListener("click", openFullGraphModal);

  document.querySelectorAll("[data-close]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      closeModal(e.target.closest(".modal-overlay"));
    });
  });

  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeModal(overlay);
    });
  });
}

function closeModal(overlay) {
  overlay.classList.add("hidden");
}
function openModal(overlay) {
  overlay.classList.remove("hidden");
}

// ---------------------------------------------------------
// UTIL: poster placeholder (tanpa gambar eksternal)
// ---------------------------------------------------------
function posterStyle(movie) {
  return `background: linear-gradient(150deg, ${movie.color}, #0b0e17);`;
}
function vertexTag(movieId) {
  const idx = state.movies.findIndex((m) => m.id === movieId);
  if (idx === -1) return "";
  return `V${String(idx + 1).padStart(2, "0")}`;
}
function initials(title) {
  return title
    .split(" ")
    .filter((w) => w.length > 1 || /[A-Za-z]/.test(w))
    .slice(0, 3)
    .map((w) => w[0])
    .join("");
}

function genreTagsHtml(genres) {
  return genres.map((g) => `<span class="tag">${g}</span>`).join("");
}

function normalizeReasons(reasons) {
  // Gabungkan reasons dengan tipe sama (Genre/Sutradara/Aktor) jadi satu,
  // menghindari duplikasi tampilan saat sebuah film terhubung lewat >1 jalur graf.
  const groups = {};
  const order = [];
  reasons.forEach((r) => {
    const [type, value] = r.split(":");
    if (!groups[type]) {
      groups[type] = new Set();
      order.push(type);
    }
    if (value) value.split("/").forEach((v) => groups[type].add(v));
  });
  return order.map((type) => (groups[type].size ? `${type}:${[...groups[type]].join("/")}` : type));
}

function reasonChipsHtml(reasons) {
  return reasons
    .map((r) => {
      const [type, value] = r.split(":");
      const cls = type.toLowerCase() === "genre" ? "genre" : type.toLowerCase() === "sutradara" ? "sutradara" : "aktor";
      const label = value ? `${type}: ${value.replace(/\//g, ", ")}` : type;
      return `<span class="reason-chip ${cls}">${label}</span>`;
    })
    .join("");
}

function humanReasonSentence(movie, reasons) {
  const genres = reasons.filter((r) => r.startsWith("Genre")).map((r) => r.split(":")[1]);
  const directors = reasons.filter((r) => r.startsWith("Sutradara")).map((r) => r.split(":")[1]);
  const actors = reasons.filter((r) => r.startsWith("Aktor")).map((r) => r.split(":")[1]);

  const parts = [];
  if (genres.length) parts.push(`genre <b>${[...new Set(genres.join("/").split("/"))].join(", ")}</b> yang sama`);
  if (directors.length) parts.push(`disutradarai oleh <b>${[...new Set(directors)].join(", ")}</b>`);
  if (actors.length) parts.push(`dibintangi aktor yang sama: <b>${[...new Set(actors.join("/").split("/"))].join(", ")}</b>`);

  if (!parts.length) return "Direkomendasikan berdasarkan kedekatan tidak langsung di dalam graf.";
  return `Direkomendasikan karena memiliki ${parts.join(", dan ")}.`;
}

// ---------------------------------------------------------
// RENDER: kartu detail film sumber
// ---------------------------------------------------------
function renderSourceCard(movie) {
  el("sourceCard").innerHTML = `
    <div class="poster" style="${posterStyle(movie)}"><span class="vertex-tag">${vertexTag(movie.id)}</span>${initials(movie.title)}</div>
    <div class="movie-detail-info">
      <h4>${movie.title}</h4>
      <div class="meta-row">
        <span>${movie.year}</span>
        <span class="dot"></span>
        <span>${movie.duration} menit</span>
        <span class="dot"></span>
        <span>Sutradara: ${movie.director}</span>
      </div>
      <div class="meta-row"><span>Pemeran: ${movie.actors.join(", ")}</span></div>
      <div class="genre-tags">${genreTagsHtml(movie.genre)}</div>
      <div class="score-badge">⭐ Skor Kurator: ${movie.curator_score}/10</div>
      <p class="synopsis">${movie.synopsis}</p>
      <div class="detail-actions">
        <a class="btn btn-trailer" style="width:auto;" target="_blank" rel="noopener"
           href="https://www.youtube.com/watch?v=${movie.trailer}">▶ Tonton Trailer Resmi</a>
        <button class="btn btn-outline" onclick="openEgoGraph('${movie.id}')">🕸️ Lihat Hubungan Film</button>
      </div>
    </div>
  `;
  el("sourceSection").classList.remove("hidden");
}

// ---------------------------------------------------------
// RENDER: grid rekomendasi
// ---------------------------------------------------------
function renderRecommendations(recs) {
  const grid = el("resultsGrid");
  if (!recs.length) {
    grid.innerHTML = `<p style="color:var(--text-dim)">Belum ada hubungan graf yang cukup kuat untuk memberi rekomendasi.</p>`;
    el("resultsSection").classList.remove("hidden");
    return;
  }

  grid.innerHTML = recs
    .map((r) => {
      const m = r.movie;
      const cleanReasons = normalizeReasons(r.reasons);
      return `
      <div class="result-card card">
        <span class="score-pill">Skor ${r.score}</span>
        <div class="result-card-top">
          <div class="poster-sm" style="${posterStyle(m)}"><span class="vertex-tag">${vertexTag(m.id)}</span>${initials(m.title)}</div>
          <div>
            <p class="result-card-title">${m.title}</p>
            <p class="result-card-meta">${m.year} • ${m.director}</p>
            <div class="genre-tags">${genreTagsHtml(m.genre)}</div>
          </div>
        </div>
        <div class="reason-box">
          ${humanReasonSentence(m, cleanReasons)}
          <div class="reason-list">${reasonChipsHtml(cleanReasons)}</div>
        </div>
        <div class="result-actions">
          <a class="btn btn-trailer btn-sm" target="_blank" rel="noopener"
             href="https://www.youtube.com/watch?v=${m.trailer}">▶ Trailer</a>
          <button class="btn btn-outline btn-sm" onclick="showDetailModal('${m.id}')">Detail</button>
          <button class="btn btn-outline btn-sm" onclick="openEgoGraph('${m.id}')">🕸️ Graf</button>
        </div>
      </div>`;
    })
    .join("");

  el("resultsSection").classList.remove("hidden");
}

// ---------------------------------------------------------
// FLOW: jalankan rekomendasi untuk 1 film
// ---------------------------------------------------------
async function runRecommendation(movieId) {
  state.currentSourceId = movieId;
  el("emptyState").classList.add("hidden");

  const res = await fetch(`/api/recommend/${movieId}?depth=2&top_n=6`);
  const data = await res.json();

  renderSourceCard(data.source);
  renderRecommendations(data.recommendations);

  el("resultsSection").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ---------------------------------------------------------
// MODAL: detail film (untuk kartu rekomendasi)
// ---------------------------------------------------------
async function showDetailModal(movieId) {
  const res = await fetch(`/api/movie/${movieId}`);
  const m = await res.json();

  el("modalDetailContent").innerHTML = `
    <div class="movie-detail" style="padding:0;border:none;background:none;">
      <div class="poster" style="${posterStyle(m)}"><span class="vertex-tag">${vertexTag(m.id)}</span>${initials(m.title)}</div>
      <div class="movie-detail-info">
        <h4>${m.title}</h4>
        <div class="meta-row">
          <span>${m.year}</span><span class="dot"></span><span>${m.duration} menit</span>
          <span class="dot"></span><span>Sutradara: ${m.director}</span>
        </div>
        <div class="meta-row"><span>Pemeran: ${m.actors.join(", ")}</span></div>
        <div class="genre-tags">${genreTagsHtml(m.genre)}</div>
        <div class="score-badge">⭐ Skor Kurator: ${m.curator_score}/10</div>
        <p class="synopsis">${m.synopsis}</p>
        <div class="detail-actions">
          <a class="btn btn-trailer" style="width:auto;" target="_blank" rel="noopener"
             href="https://www.youtube.com/watch?v=${m.trailer}">▶ Tonton Trailer Resmi</a>
          <button class="btn btn-outline" onclick="closeModal(document.getElementById('modalDetail')); runRecommendation('${m.id}')">Jadikan Node Awal</button>
        </div>
      </div>
    </div>
  `;
  openModal(el("modalDetail"));
}
window.showDetailModal = showDetailModal;

// ---------------------------------------------------------
// VISUALISASI: EGO GRAPH (hubungan seputar 1 film)
// ---------------------------------------------------------
async function openEgoGraph(movieId) {
  const res = await fetch(`/api/graph/ego/${movieId}?depth=1`);
  const { nodes, edges } = await res.json();
  const movie = state.movies.find((m) => m.id === movieId);

  el("graphModalTitle").textContent = `Hubungan Film: ${movie ? movie.title : ""}`;
  el("graphHint").textContent = "Setiap simpul mewakili sebuah film, garis mewakili hubungan genre/sutradara/aktor.";

  openModal(el("modalGraph"));
  drawNetwork("egoNetwork", nodes, edges, movieId, "egoNetwork");
}
window.openEgoGraph = openEgoGraph;

// ---------------------------------------------------------
// VISUALISASI: SELURUH GRAF + PATH FINDER
// ---------------------------------------------------------
async function openFullGraphModal() {
  const res = await fetch("/api/graph");
  const { nodes, edges } = await res.json();

  openModal(el("modalFullGraph"));
  state.pathSelection = [];
  el("pathResultBox").classList.add("hidden");

  drawNetwork("fullNetwork", nodes, edges, null, "fullNetwork", true);
}

function edgeColorByType(type) {
  if (type === "Genre") return "#3fb8a6";      // Signal Teal
  if (type === "Sutradara") return "#e8b64a";  // Marquee Gold
  if (type === "Aktor") return "#c1443a";      // Reel Crimson
  return "#5b6280";
}

function drawNetwork(containerId, rawNodes, rawEdges, centerId, networkKey, enablePathClick = false) {
  const container = document.getElementById(containerId);

  const visNodes = rawNodes.map((n) => ({
    id: n.id,
    label: n.label,
    shape: "dot",
    size: n.id === centerId || n.is_center ? 26 : 16,
    color: {
      background: n.color || "#6366f1",
      border: n.id === centerId || n.is_center ? "#fff" : "rgba(255,255,255,0.3)",
      highlight: { background: n.color || "#6366f1", border: "#fff" },
    },
    font: { color: "#f1f3fb", size: 13, face: "Inter" },
    borderWidth: n.id === centerId || n.is_center ? 3 : 1,
  }));

  const visEdges = rawEdges.map((e, i) => ({
    id: i,
    from: e.from,
    to: e.to,
    color: { color: edgeColorByType(e.type), opacity: 0.55 },
    width: Math.min(1 + (e.weight || 1) * 0.5, 5),
    title: e.relation,
    smooth: { type: "continuous" },
  }));

  const data = { nodes: new vis.DataSet(visNodes), edges: new vis.DataSet(visEdges) };
  const options = {
    layout: { improvedLayout: true },
    physics: {
      solver: "forceAtlas2Based",
      forceAtlas2Based: { gravitationalConstant: -60, springLength: 110, springConstant: 0.06 },
      stabilization: { iterations: 120 },
    },
    interaction: { hover: true, tooltipDelay: 100 },
    nodes: { shadow: true },
    edges: { shadow: false },
  };

  const network = new vis.Network(container, data, options);

  if (networkKey === "egoNetwork") state.egoNetwork = network;
  if (networkKey === "fullNetwork") state.fullNetwork = network;

  network.once("stabilized", () => network.fit({ animation: false }));

  if (enablePathClick) {
    network.on("click", async (params) => {
      if (!params.nodes.length) return;
      const clickedId = params.nodes[0];

      if (!state.pathSelection.includes(clickedId)) {
        state.pathSelection.push(clickedId);
      }
      if (state.pathSelection.length > 2) {
        state.pathSelection = [clickedId];
      }

      if (state.pathSelection.length === 2) {
        await findAndShowPath(state.pathSelection[0], state.pathSelection[1]);
      } else {
        el("pathResultBox").classList.remove("hidden");
        const m = state.movies.find((mm) => mm.id === clickedId);
        el("pathResultBox").innerHTML = `Simpul pertama dipilih: <b>${m ? m.title : clickedId}</b>. Klik satu simpul lagi untuk melihat jalur relasi.`;
      }
    });
  }
}

async function findAndShowPath(id1, id2) {
  const res = await fetch(`/api/path/${id1}/${id2}`);
  const data = await res.json();
  const box = el("pathResultBox");
  box.classList.remove("hidden");

  if (!data.connected) {
    box.innerHTML = `Kedua film belum terhubung langsung maupun tidak langsung dalam graf saat ini.`;
    return;
  }

  const chain = data.path
    .map((p, idx) => {
      const nodeHtml = `<span class="path-node">${p.title}</span>`;
      if (idx < data.edges.length) {
        const [type, val] = data.edges[idx].split(":");
        return `${nodeHtml}<span class="path-arrow">→ <span class="path-edge-label">${type}${val ? ": " + val.replace(/\//g, ", ") : ""}</span> →</span>`;
      }
      return nodeHtml;
    })
    .join("");

  box.innerHTML = `
    <div>Jalur relasi terpendek (<b>${data.path.length - 1} langkah</b>) antara
    <b>${data.path[0].title}</b> dan <b>${data.path[data.path.length - 1].title}</b>:</div>
    <div class="path-chain">${chain}</div>
  `;

  // reset agar bisa memilih pasangan baru
  state.pathSelection = [];
}
