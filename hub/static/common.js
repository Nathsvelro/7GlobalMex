// Cafetal hub: shared helpers (vanilla JS, no build step).
const PAGES = [
  ["/", "Inicio"], ["/hub/registro.html", "Registro"], ["/hub/simulador.html", "Simulador SMS"],
  ["/hub/bandeja.html", "Bandeja de salida"], ["/hub/mapa.html", "Mapa"], ["/hub/tecnico.html", "Técnico"],
  ["/hub/contenido.html", "Contenido"],
];

const CODE_INFO = {
  ROYA: { name: "Roya", color: "#e8590c" },
  MINA: { name: "Minador", color: "#7c3aed" },
  PHOM: { name: "Phoma", color: "#6b4423" },
  CERC: { name: "Cercospora", color: "#0e7490" },
  ACAR: { name: "Ácaro rojo", color: "#be123c" },
  DUDA: { name: "Duda", color: "#1d4ed8" },
  OTRO: { name: "No es hoja de café", color: "#475569" },
  SANO: { name: "Sano", color: "#15803d" },
};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(path, opts = {}) {
  const o = { ...opts, headers: { ...(opts.headers || {}) } };
  if (o.json !== undefined) {
    o.method = o.method || "POST";
    o.headers["Content-Type"] = "application/json";
    o.body = JSON.stringify(o.json);
    delete o.json;
  }
  const r = await fetch(path, o);
  let data = null;
  try { data = await r.json(); } catch (e) { data = null; }
  if (!r.ok) {
    let msg = (data && data.detail) || r.statusText;
    if (Array.isArray(msg)) msg = msg.map((d) => (d.loc ? d.loc.slice(1).join(".") + ": " : "") + d.msg).join("; ");
    throw new Error(msg);
  }
  return data;
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? iso + "T12:00:00" : iso);
  if (isNaN(d)) return iso;
  const opts = iso.length === 10 ? { day: "numeric", month: "short" } : { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" };
  return d.toLocaleString("es-MX", opts);
}

function codeBadge(code, conf) {
  const i = CODE_INFO[code] || { name: code, color: "#555" };
  const c = conf !== undefined && conf !== null && !["DUDA", "OTRO"].includes(code) ? ` ${conf}%` : "";
  return `<span class="dot" style="background:${i.color}"></span>${esc(i.name)}${c}`;
}

function codeDot(code) {
  return `<span class="dot" style="background:${(CODE_INFO[code] || { color: "#555" }).color}"></span>`;
}

function statusBadge(status) {
  return status === "verified" ? '<span class="badge ok">verificado</span>' : '<span class="badge unv">SIN VERIFICAR</span>';
}

// Header with navigation, DEMO badge and SIMULATED gateway label on every page.
async function initPage() {
  const here = location.pathname === "/hub/" ? "/" : location.pathname;
  const nav = PAGES.map(([href, label]) => `<a href="${href}" class="${href === here ? "on" : ""}">${label}</a>`).join("");
  const h = document.createElement("header");
  h.className = "top";
  h.innerHTML = `<a class="brand" href="/">Cafetal · Hub de la cooperativa</a><nav>${nav}</nav>
    <span id="hdr-badges" style="margin-left:auto"></span>`;
  document.body.prepend(h);
  const f = document.createElement("footer");
  f.className = "foot";
  f.textContent = "Los datos del hub se quedan en la computadora de la cooperativa. Son para el personal y el técnico, pero el hub todavía no tiene contraseña: cualquiera en esta red puede verlos. Pasarela SMS SIMULADA: no se envían SMS reales.";
  document.body.append(f);
  try {
    const s = await api("/api/summary");
    document.getElementById("hdr-badges").innerHTML =
      (s.demo ? '<span class="badge demo">DEMO: datos de ejemplo</span> ' : "") + '<span class="badge sim">SMS SIMULADO</span>';
    return s;
  } catch (e) {
    return null;
  }
}
