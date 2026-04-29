// --- Floating Action Button (FAB) with drag-and-drop upload ---
(function() {
  const API = "https://syllabushelper.net/api";

  // Create FAB
  const fab = document.createElement("div");
  fab.id = "syllabus-helper-fab";
  fab.innerHTML = "S";
  document.body.appendChild(fab);

  // Create drop zone overlay
  const dropzone = document.createElement("div");
  dropzone.id = "syllabus-helper-dropzone";
  dropzone.innerHTML = `
    <div class="sh-dz-inner">
      <div class="sh-dz-icon">+</div>
      <div class="sh-dz-text">Drop syllabus file here</div>
      <div class="sh-dz-sub">PDF, DOCX, or TXT</div>
      <input type="file" id="sh-file-input" accept=".pdf,.docx,.doc,.txt" style="display:none" />
      <button class="sh-dz-browse">or click to browse</button>
    </div>
    <div class="sh-dz-status" id="sh-dz-status" style="display:none"></div>
  `;
  document.body.appendChild(dropzone);

  let dzOpen = false;

  fab.addEventListener("click", () => {
    dzOpen = !dzOpen;
    dropzone.classList.toggle("open", dzOpen);
    fab.classList.toggle("active", dzOpen);
  });

  // Browse button
  dropzone.querySelector(".sh-dz-browse").addEventListener("click", () => {
    document.getElementById("sh-file-input").click();
  });

  document.getElementById("sh-file-input").addEventListener("change", (e) => {
    if (e.target.files.length) uploadFile(e.target.files[0]);
  });

  // Drag and drop
  const inner = dropzone.querySelector(".sh-dz-inner");
  inner.addEventListener("dragover", (e) => { e.preventDefault(); inner.classList.add("dragover"); });
  inner.addEventListener("dragleave", () => { inner.classList.remove("dragover"); });
  inner.addEventListener("drop", (e) => {
    e.preventDefault();
    inner.classList.remove("dragover");
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
  });

  async function uploadFile(file) {
    const status = document.getElementById("sh-dz-status");
    const innerEl = dropzone.querySelector(".sh-dz-inner");
    innerEl.style.display = "none";
    status.style.display = "flex";
    status.textContent = "Uploading...";
    status.className = "sh-dz-status uploading";

    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/upload`, { method: "POST", body: form });
      if (res.ok) {
        status.textContent = "Added!";
        status.className = "sh-dz-status success";
      } else {
        const data = await res.json();
        status.textContent = data.detail || "Upload failed";
        status.className = "sh-dz-status error";
      }
    } catch {
      status.textContent = "Cannot reach backend";
      status.className = "sh-dz-status error";
    }

    setTimeout(() => {
      status.style.display = "none";
      innerEl.style.display = "flex";
    }, 2000);
  }

  // --- Detect syllabus links on LMS pages ---
  function detectSyllabusLinks() {
    const links = document.querySelectorAll('a[href*=".pdf"], a[href*=".docx"]');
    links.forEach(link => {
      if (link.dataset.syllabusHelperProcessed) return;
      link.dataset.syllabusHelperProcessed = "true";

      const text = link.textContent.toLowerCase();
      const href = link.href.toLowerCase();
      const isSyllabus = ["syllabus", "outline", "schedule", "course info"].some(
        kw => text.includes(kw) || href.includes(kw)
      );

      if (isSyllabus) {
        const btn = document.createElement("button");
        btn.className = "syllabus-helper-btn";
        btn.textContent = "Add to Syllabus Helper";
        btn.addEventListener("click", async (e) => {
          e.preventDefault();
          e.stopPropagation();
          btn.textContent = "Uploading...";
          btn.disabled = true;
          try {
            const blob = await (await fetch(link.href)).blob();
            const form = new FormData();
            form.append("file", blob, link.href.split("/").pop() || "syllabus.pdf");
            await fetch(`${API}/upload`, { method: "POST", body: form });
            btn.textContent = "Added!";
            btn.style.background = "#27ae60";
          } catch {
            btn.textContent = "Failed";
            btn.style.background = "#eb5757";
            setTimeout(() => { btn.textContent = "Add to Syllabus Helper"; btn.disabled = false; btn.style.background = ""; }, 2000);
          }
        });
        link.parentElement.insertBefore(btn, link.nextSibling);
      }
    });
  }

  detectSyllabusLinks();
  new MutationObserver(detectSyllabusLinks).observe(document.body, { childList: true, subtree: true });

  // --- Sync auth token from main app to extension ---
  // Watch for localStorage changes (login/logout on the main app)
  if (location.origin === "https://syllabushelper.net") {
    // On page load, sync current token
    syncToken();

    // Listen for storage events (changes from other tabs)
    window.addEventListener("storage", (e) => {
      if (e.key === "token") syncToken();
    });

    // Also poll for changes in the same tab (storage event doesn't fire for same-tab writes)
    let lastToken = localStorage.getItem("token");
    setInterval(() => {
      const current = localStorage.getItem("token");
      if (current !== lastToken) {
        lastToken = current;
        syncToken();
      }
    }, 1000);
  }

  function syncToken() {
    const token = localStorage.getItem("token");
    if (token) {
      // Validate and get user name, then save to extension storage
      fetch(`${API}/auth/me`, { headers: { authorization: `Bearer ${token}` } })
        .then(r => r.ok ? r.json() : Promise.reject())
        .then(data => {
          chrome.storage.local.set({ token, userName: data.name || data.email || "" });
        })
        .catch(() => {});
    } else {
      chrome.storage.local.remove(["token", "userName"]);
    }
  }
})();
