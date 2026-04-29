const API = "https://syllabushelper.net/api";
const APP = "https://syllabushelper.net";

// --- State ---
let courses = [];
let allDeadlines = [];
let calDate = new Date();
let currentCourse = null;
let authToken = null;
let isRegister = false;

// Authenticated fetch helper
function authFetch(url, opts = {}) {
  opts.headers = opts.headers || {};
  if (authToken) opts.headers["Authorization"] = `Bearer ${authToken}`;
  return fetch(url, opts);
}

// --- Init ---
async function init() {
  const stored = await chrome.storage.local.get(["token", "userName"]);
  if (stored.token) {
    authToken = stored.token;
    showApp(stored.userName || "");
  } else {
    // Try to sync token from main app's localStorage
    const synced = await tryReadTokenFromApp();
    if (synced) {
      showApp(synced.name || "");
    } else {
      showLogin();
    }
  }
}

// Try to read token from the main app's localStorage via a background tab
async function tryReadTokenFromApp() {
  return new Promise((resolve) => {
    chrome.tabs.create({ url: `${APP}/#_sync`, active: false }, (tab) => {
      const tabId = tab.id;
      const timeout = setTimeout(() => { chrome.tabs.remove(tabId).catch(() => {}); resolve(null); }, 3000);
      chrome.tabs.onUpdated.addListener(function listener(id, info) {
        if (id === tabId && info.status === "complete") {
          chrome.tabs.onUpdated.removeListener(listener);
          clearTimeout(timeout);
          chrome.scripting.executeScript({
            target: { tabId },
            func: () => { return localStorage.getItem("token"); },
          }).then(async (results) => {
            chrome.tabs.remove(tabId).catch(() => {});
            const token = results?.[0]?.result;
            if (token) {
              // Validate token with backend
              try {
                const res = await fetch(`${API}/auth/me`, {
                  headers: { authorization: `Bearer ${token}` }
                });
                if (res.ok) {
                  const data = await res.json();
                  authToken = token;
                  await chrome.storage.local.set({ token, userName: data.name || data.email });
                  resolve({ name: data.name || data.email });
                } else {
                  resolve(null);
                }
              } catch {
                resolve(null);
              }
            } else {
              resolve(null);
            }
          }).catch(() => {
            chrome.tabs.remove(tabId).catch(() => {});
            resolve(null);
          });
        }
      });
    });
  });
}

// ==================== AUTH ====================
function showLogin() {
  document.getElementById("login-view").style.display = "flex";
  document.getElementById("app-view").style.display = "none";
  setupLoginHandlers();
}

function showApp(name) {
  document.getElementById("login-view").style.display = "none";
  document.getElementById("app-view").style.display = "block";
  document.getElementById("user-name").textContent = name;
  setupTabs();
  setupAsk();
  setupNav();
  checkHealth();
  loadCourses();
}

function setupLoginHandlers() {
  const emailEl = document.getElementById("login-email");
  const passEl = document.getElementById("login-password");
  const nameEl = document.getElementById("login-name");
  const errEl = document.getElementById("login-error");
  const loginBtn = document.getElementById("login-btn");
  const toggleLink = document.getElementById("toggle-mode");
  const googleBtn = document.getElementById("google-btn");

  toggleLink.addEventListener("click", () => {
    isRegister = !isRegister;
    nameEl.classList.toggle("hidden", !isRegister);
    loginBtn.textContent = isRegister ? "Create account" : "Sign in";
    document.getElementById("login-toggle").innerHTML = isRegister
      ? 'Already have an account? <a id="toggle-mode">Sign in</a>'
      : 'Don\'t have an account? <a id="toggle-mode">Sign up</a>';
    document.getElementById("toggle-mode").addEventListener("click", () => {
      isRegister = !isRegister;
      nameEl.classList.toggle("hidden", !isRegister);
      loginBtn.textContent = isRegister ? "Create account" : "Sign in";
    });
    errEl.textContent = "";
  });

  loginBtn.addEventListener("click", async () => {
    errEl.textContent = "";
    const email = emailEl.value.trim();
    const password = passEl.value;
    if (!email || !password) { errEl.textContent = "Please fill in all fields"; return; }

    loginBtn.disabled = true;
    loginBtn.textContent = isRegister ? "Creating..." : "Signing in...";

    try {
      const endpoint = isRegister ? "/auth/register" : "/auth/login";
      const body = isRegister
        ? { email, password, name: nameEl.value.trim() || email.split("@")[0] }
        : { email, password };
      const res = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Auth failed");

      authToken = data.token;
      const userName = data.name || email.split("@")[0];
      await chrome.storage.local.set({ token: authToken, userName });
      // Sync token to main app's localStorage
      syncTokenToApp(authToken);
      showApp(userName);
    } catch (e) {
      errEl.textContent = e.message;
    }
    loginBtn.disabled = false;
    loginBtn.textContent = isRegister ? "Create account" : "Sign in";
  });

  // Enter key submits
  [emailEl, passEl, nameEl].forEach(el => {
    el.addEventListener("keydown", e => { if (e.key === "Enter") loginBtn.click(); });
  });

  googleBtn.addEventListener("click", () => {
    chrome.tabs.create({ url: `${APP}/#login` });
    window.close();
  });
}

// ==================== HEALTH ====================
async function checkHealth() {
  const dot = document.getElementById("status-dot");
  const txt = document.getElementById("status-text");
  try {
    const res = await authFetch(`${API}/health`);
    if (res.ok) {
      dot.className = "status-dot ok";
      const d = await res.json();
      txt.textContent = `Connected \u00B7 ${d.syllabi_count || 0} syllabi`;
    }
  } catch {
    dot.className = "status-dot err";
    txt.textContent = "Backend offline";
  }
}

// ==================== COURSES ====================
async function loadCourses() {
  try {
    const res = await authFetch(`${API}/courses`);
    courses = await res.json();
    allDeadlines = [];
    for (const c of courses) {
      try {
        const r = await authFetch(`${API}/syllabus/${c.slug}`);
        const data = await r.json();
        if (data.deadlines) {
          data.deadlines.forEach(d => {
            allDeadlines.push({ ...d, course: c.course_code || c.slug });
          });
        }
      } catch {}
    }
    allDeadlines.sort((a, b) => a.date.localeCompare(b.date));
    renderChips();
    renderDeadlines();
    renderCalendar();
    renderGrades();
  } catch {}
}

// ==================== TABS ====================
function setupTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`panel-${tab.dataset.tab}`).classList.add("active");
    });
  });
}

// ==================== CHIPS ====================
function renderChips() {
  const el = document.getElementById("course-chips");
  if (!courses.length) { el.innerHTML = ""; return; }
  el.innerHTML = courses.map(c => {
    const code = c.course_code || c.slug;
    const active = currentCourse === code ? " active" : "";
    return `<span class="chip${active}" data-c="${code}">${code}</span>`;
  }).join("");
  el.querySelectorAll(".chip").forEach(ch => {
    ch.addEventListener("click", () => {
      currentCourse = currentCourse === ch.dataset.c ? null : ch.dataset.c;
      renderChips();
      renderDeadlines();
    });
  });
}

// ==================== DEADLINES ====================
function renderDeadlines() {
  const el = document.getElementById("deadlines-list");
  const today = new Date().toISOString().slice(0, 10);
  let dls = allDeadlines.filter(d => d.date >= today);
  if (currentCourse) dls = dls.filter(d => d.course === currentCourse);
  if (!dls.length) { el.innerHTML = '<div class="empty">No upcoming deadlines</div>'; return; }
  el.innerHTML = dls.slice(0, 8).map(d => `
    <div class="dl-item">
      <div class="dl-bar ${typeClass(d.type)}"></div>
      <div class="dl-body">
        <div class="dl-name">${esc(d.description)}</div>
        <div class="dl-sub">${esc(d.course)}</div>
      </div>
      <div class="dl-date">${fmtDate(d.date)}</div>
    </div>`).join("");
}

// ==================== CALENDAR ====================
function renderCalendar() {
  const label = document.getElementById("cal-label");
  const grid = document.getElementById("cal-grid");
  const MN = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  const y = calDate.getFullYear(), m = calDate.getMonth();
  label.textContent = `${MN[m]} ${y}`;
  const first = new Date(y, m, 1).getDay();
  const days = new Date(y, m + 1, 0).getDate();
  const prev = new Date(y, m, 0).getDate();
  const todayStr = new Date().toISOString().slice(0, 10);
  const evDates = new Set(allDeadlines.map(d => d.date));

  let h = ["S","M","T","W","T","F","S"].map(d => `<div class="cal-dh">${d}</div>`).join("");
  for (let i = first - 1; i >= 0; i--) h += `<div class="cal-d om">${prev - i}</div>`;
  for (let d = 1; d <= days; d++) {
    const ds = `${y}-${String(m+1).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
    const cls = (ds === todayStr ? " today" : "") + (evDates.has(ds) ? " ev" : "");
    h += `<div class="cal-d${cls}">${d}</div>`;
  }
  const rem = (7 - (first + days) % 7) % 7;
  for (let i = 1; i <= rem; i++) h += `<div class="cal-d om">${i}</div>`;
  grid.innerHTML = h;

  // Week events
  const now = new Date();
  const ws = new Date(now); ws.setDate(now.getDate() - now.getDay());
  const we = new Date(ws); we.setDate(ws.getDate() + 6);
  const s = ws.toISOString().slice(0,10), e = we.toISOString().slice(0,10);
  const wev = allDeadlines.filter(d => d.date >= s && d.date <= e);
  const wEl = document.getElementById("week-events");
  wEl.innerHTML = wev.length ? wev.map(d => `
    <div class="dl-item">
      <div class="dl-bar ${typeClass(d.type)}"></div>
      <div class="dl-body">
        <div class="dl-name">${esc(d.description)}</div>
        <div class="dl-sub">${esc(d.course)}</div>
      </div>
      <div class="dl-date">${fmtDate(d.date)}</div>
    </div>`).join("") : '<div class="empty">No events this week</div>';

  document.getElementById("cal-prev").onclick = () => { calDate.setMonth(calDate.getMonth() - 1); renderCalendar(); };
  document.getElementById("cal-next").onclick = () => { calDate.setMonth(calDate.getMonth() + 1); renderCalendar(); };
}

// ==================== GRADES ====================
function renderGrades() {
  const el = document.getElementById("grades-list");
  if (!courses.length) { el.innerHTML = '<div class="empty">Upload syllabi to see grades</div>'; return; }
  el.innerHTML = courses.map(c => {
    const code = c.course_code || c.slug;
    const n = c.grading ? c.grading.length : 0;
    return `<div class="gr-item">
      <div><div class="gr-name">${esc(code)}</div><div class="gr-detail">${n} grade components</div></div>
      <div class="gr-badge">${n > 0 ? "Loaded" : "\u2014"}</div>
    </div>`;
  }).join("");
}

// ==================== ASK ====================
function setupAsk() {
  const input = document.getElementById("ask-input");
  const btn = document.getElementById("ask-send");
  const msgs = document.getElementById("ask-msgs");

  async function send() {
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    btn.disabled = true;
    msgs.innerHTML += `<div class="bubble user">${esc(q)}</div>`;
    msgs.scrollTop = msgs.scrollHeight;

    const slug = currentCourse
      ? courses.find(c => (c.course_code || c.slug) === currentCourse)?.slug
      : courses[0]?.slug;

    if (!slug) {
      msgs.innerHTML += '<div class="bubble bot">No syllabus uploaded yet.</div>';
      btn.disabled = false;
      return;
    }
    try {
      const res = await authFetch(`${API}/ask/${slug}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q })
      });
      const data = await res.json();
      msgs.innerHTML += `<div class="bubble bot">${esc(data.answer || "No answer found.")}</div>`;
    } catch {
      msgs.innerHTML += '<div class="bubble bot">Cannot reach backend.</div>';
    }
    btn.disabled = false;
    msgs.scrollTop = msgs.scrollHeight;
  }

  btn.addEventListener("click", send);
  input.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
}

// ==================== NAV ====================
function setupNav() {
  document.getElementById("btn-fullapp").addEventListener("click", () => {
    chrome.tabs.create({ url: APP }); window.close();
  });
  document.getElementById("btn-fullapp-footer").addEventListener("click", e => {
    e.preventDefault(); chrome.tabs.create({ url: APP }); window.close();
  });
  document.getElementById("btn-logout").addEventListener("click", async () => {
    await chrome.storage.local.remove(["token", "userName"]);
    clearTokenFromApp();
    authToken = null;
    showLogin();
  });
}

// ==================== SYNC TOKEN TO MAIN APP ====================
function syncTokenToApp(token) {
  // Open a hidden tab to the app, inject token into localStorage, then close
  chrome.tabs.create({ url: `${APP}/#_sync`, active: false }, (tab) => {
    const tabId = tab.id;
    chrome.tabs.onUpdated.addListener(function listener(id, info) {
      if (id === tabId && info.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        chrome.scripting.executeScript({
          target: { tabId },
          func: (t) => { localStorage.setItem("token", t); },
          args: [token]
        }).then(() => {
          chrome.tabs.remove(tabId);
        }).catch(() => {
          chrome.tabs.remove(tabId);
        });
      }
    });
  });
}

function clearTokenFromApp() {
  chrome.tabs.create({ url: `${APP}/#_sync`, active: false }, (tab) => {
    const tabId = tab.id;
    chrome.tabs.onUpdated.addListener(function listener(id, info) {
      if (id === tabId && info.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        chrome.scripting.executeScript({
          target: { tabId },
          func: () => { localStorage.removeItem("token"); },
        }).then(() => {
          chrome.tabs.remove(tabId);
        }).catch(() => {
          chrome.tabs.remove(tabId);
        });
      }
    });
  });
}

// ==================== HELPERS ====================
function typeClass(t) {
  if (!t) return "other";
  if (/exam|midterm|final/i.test(t)) return "exam";
  if (/homework|hw|assignment/i.test(t)) return "hw";
  if (/project|presentation/i.test(t)) return "project";
  if (/quiz/i.test(t)) return "quiz";
  return "other";
}
function fmtDate(s) {
  const d = new Date(s + "T00:00:00");
  return ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][d.getMonth()] + " " + d.getDate();
}
function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

init();
