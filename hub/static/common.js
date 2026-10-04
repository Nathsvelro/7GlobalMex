// Cafetal hub: shared helpers (vanilla JS, no build step).
const PAGES = [
  ["/", "Home"], ["/hub/register.html", "Registration"], ["/hub/simulator.html", "SMS simulator"],
  ["/hub/outbox.html", "Outbox"], ["/hub/map.html", "Map"], ["/hub/officer.html", "Officer worklist"],
  ["/hub/content.html", "Content"],
];

const CODE_INFO = {
  RUST: { name: "Rust", color: "#e8590c" },
  MINR: { name: "Leaf miner", color: "#7c3aed" },
  PHOM: { name: "Phoma", color: "#6b4423" },
  CERC: { name: "Cercospora", color: "#0e7490" },
  MITE: { name: "Red spider mite", color: "#be123c" },
  UNSR: { name: "Unsure", color: "#1d4ed8" },
  OTHR: { name: "Not a coffee leaf", color: "#475569" },
  HLTH: { name: "Healthy", color: "#15803d" },
};
const NEEDS_PERSON = ["UNSR", "OTHR"];  // fail-safe codes: no confidence shown, a person must look
const LANG_NAME = { en: "English", sw: "Kiswahili", kik: "Gĩkũyũ" };

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
  return d.toLocaleString("en-KE", opts);
}

function codeBadge(code, conf) {
  const i = CODE_INFO[code] || { name: code, color: "#555" };
  const c = conf !== undefined && conf !== null && !NEEDS_PERSON.includes(code) ? ` ${conf}%` : "";
  return `<span class="dot" style="background:${i.color}"></span>${esc(i.name)}${c}`;
}

function codeDot(code) {
  return `<span class="dot" style="background:${(CODE_INFO[code] || { color: "#555" }).color}"></span>`;
}

function statusBadge(status) {
  return status === "verified" ? '<span class="badge ok">verified</span>' : '<span class="badge unv">UNVERIFIED</span>';
}

// Header with navigation, DEMO badge and SIMULATED gateway label on every page.
async function initPage() {
  const here = location.pathname === "/hub/" ? "/" : location.pathname;
  const nav = PAGES.map(([href, label]) => `<a href="${href}" class="${href === here ? "on" : ""}">${label}</a>`).join("");
  const h = document.createElement("header");
  h.className = "top";
  h.innerHTML = `<a class="brand" href="/">Cafetal · Co-op hub</a><nav>${nav}</nav>
    <span id="hdr-badges" style="margin-left:auto"></span>`;
  document.body.prepend(h);
  const f = document.createElement("footer");
  f.className = "foot";
  f.textContent = "Hub data stays on the co-op computer. It is for co-op staff and the extension officer, but the hub has no password yet: anyone on this network can see it. SIMULATED SMS gateway: no real SMS is sent.";
  document.body.append(f);
  try {
    const s = await api("/api/summary");
    document.getElementById("hdr-badges").innerHTML =
      (s.demo ? '<span class="badge demo">DEMO: sample data</span> ' : "") + '<span class="badge sim">SMS SIMULATED</span>';
    if (s.public_demo) {
      // Public online DEMO copy (CAFETAL_PUBLIC_DEMO): everyone with the link shares the same fake data.
      const b = document.createElement("div");
      b.className = "public-demo";
      b.textContent = "PUBLIC ONLINE DEMO: fake data that anyone with this link can see and change. It is reset whenever the server restarts. Do not type real names or phone numbers. SMS SIMULATED: no real SMS is sent.";
      h.after(b);
      f.textContent = "Public online DEMO copy of the co-op hub. A real co-op runs the hub on its own computer, where member data stays.";
    }
    return s;
  } catch (e) {
    return null;
  }
}
