/**
 * Pixvault upload.js
 * Handles drag-and-drop, file queuing, and XHR upload with progress.
 */

const dropZone   = document.getElementById("drop-zone");
const fileInput  = document.getElementById("file-input");
const queueList  = document.getElementById("upload-queue");
const albumSel   = document.getElementById("album-select");
const tagsInput  = document.getElementById("tags-hidden");
const uploadBtn  = document.getElementById("upload-btn");
const browseBtn  = document.getElementById("browse-btn");

let pendingFiles = [];  // files waiting to be uploaded

// ── Drag-and-drop ─────────────────────────────────────────────
dropZone.addEventListener("dragenter", (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragover",  (e) => { e.preventDefault(); });
dropZone.addEventListener("dragleave", (e) => { if (!dropZone.contains(e.relatedTarget)) dropZone.classList.remove("drag-over"); });
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  enqueue(Array.from(e.dataTransfer.files));
});

browseBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => enqueue(Array.from(fileInput.files)));

// ── Enqueue files ─────────────────────────────────────────────
function enqueue(files) {
  files.forEach((file) => {
    if (!isAllowed(file)) {
      showToast(`${file.name}: unsupported type`, "error");
      return;
    }
    const idx = pendingFiles.length;
    pendingFiles.push(file);
    renderQueueItem(file, idx);
  });

  uploadBtn.disabled = pendingFiles.length === 0;
}

function isAllowed(file) {
  return /\.(jpe?g|png|gif|webp|svg|heic|mp4|mov|avi|webm|mkv|wmv)$/i.test(file.name);
}

// ── Render a queue row ────────────────────────────────────────
function renderQueueItem(file, idx) {
  const row = document.createElement("div");
  row.id = `qi-${idx}`;
  row.className = "flex items-center gap-4 bg-white rounded-2xl p-4 shadow-sm border border-gray-100";

  // Thumbnail
  const thumb = document.createElement("div");
  thumb.className = "w-14 h-14 rounded-xl overflow-hidden bg-gray-100 flex-shrink-0 flex items-center justify-center";

  if (file.type.startsWith("image/")) {
    const img = document.createElement("img");
    img.className = "w-full h-full object-cover";
    const reader = new FileReader();
    reader.onload = (e) => (img.src = e.target.result);
    reader.readAsDataURL(file);
    thumb.appendChild(img);
  } else {
    thumb.innerHTML = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#6E6E73" stroke-width="1.5">
      <polygon points="5 3 19 12 5 21 5 3"/></svg>`;
  }

  // Info + progress
  const info = document.createElement("div");
  info.className = "flex-1 min-w-0";
  info.innerHTML = `
    <p class="text-sm font-medium text-[#1D1D1F] truncate">${escHtml(file.name)}</p>
    <p class="text-xs text-[#6E6E73] mb-2">${fmtSize(file.size)}</p>
    <div class="bg-gray-100 rounded-full h-1 overflow-hidden">
      <div id="pb-${idx}" class="progress-bar" style="width:0%"></div>
    </div>
    <p id="st-${idx}" class="text-xs text-[#6E6E73] mt-1">Waiting…</p>
  `;

  // Remove button
  const rm = document.createElement("button");
  rm.className = "flex-shrink-0 p-1.5 rounded-full hover:bg-gray-100 text-[#6E6E73] hover:text-red-500 transition-colors";
  rm.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none">
    <path d="M4 4l8 8M12 4L4 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;
  rm.title = "Remove";
  rm.onclick = () => {
    pendingFiles[idx] = null;
    row.remove();
    uploadBtn.disabled = pendingFiles.filter(Boolean).length === 0;
  };

  row.appendChild(thumb);
  row.appendChild(info);
  row.appendChild(rm);
  queueList.appendChild(row);
}

// ── Upload all ────────────────────────────────────────────────
uploadBtn.addEventListener("click", async () => {
  const files = pendingFiles.map((f, i) => ({ file: f, idx: i })).filter((x) => x.file);
  if (!files.length) return;

  uploadBtn.disabled = true;
  uploadBtn.textContent = "Uploading…";

  for (const { file, idx } of files) {
    await uploadOne(file, idx);
  }

  uploadBtn.textContent = "All done!";
  setTimeout(() => { window.location.href = "/dashboard"; }, 1200);
});

function uploadOne(file, idx) {
  return new Promise((resolve) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("album_id", albumSel ? albumSel.value : "");
    fd.append("tags", tagsInput ? tagsInput.value : "");

    const xhr = new XMLHttpRequest();
    const pb  = document.getElementById(`pb-${idx}`);
    const st  = document.getElementById(`st-${idx}`);

    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      const pct = Math.round((e.loaded / e.total) * 100);
      if (pb) pb.style.width = pct + "%";
      if (st) st.textContent = `Uploading… ${pct}%`;
    };

    xhr.onload = () => {
      try {
        const data = JSON.parse(xhr.responseText);
        if (data.success) {
          if (pb) { pb.style.width = "100%"; pb.style.background = "#34c759"; }
          if (st) st.textContent = "Done ✓";
        } else {
          markError(pb, st, data.error || "Upload failed");
        }
      } catch {
        markError(pb, st, "Invalid server response");
      }
      resolve();
    };

    xhr.onerror = () => { markError(pb, st, "Network error"); resolve(); };

    xhr.open("POST", "/upload");
    xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    xhr.send(fd);
  });
}

function markError(pb, st, msg) {
  if (pb) { pb.style.width = "100%"; pb.style.background = "#ff3b30"; }
  if (st) st.textContent = "Error: " + msg;
}

// ── Tag chip UI ───────────────────────────────────────────────
const tagInput   = document.getElementById("tag-input");
const tagDisplay = document.getElementById("tag-display");
let tags = [];

if (tagInput) {
  tagInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const val = tagInput.value.trim().replace(/,$/, "");
      if (val && !tags.includes(val)) {
        tags.push(val);
        renderTags();
      }
      tagInput.value = "";
    }
    if (e.key === "Backspace" && !tagInput.value) {
      tags.pop();
      renderTags();
    }
  });
}

function renderTags() {
  if (!tagDisplay) return;
  tagDisplay.innerHTML = tags.map((t, i) => `
    <span class="tag-chip">
      ${escHtml(t)}
      <button type="button" onclick="removeTag(${i})" class="ml-1 opacity-60 hover:opacity-100">×</button>
    </span>
  `).join("");
  if (tagsInput) tagsInput.value = tags.join(",");
}

window.removeTag = (i) => { tags.splice(i, 1); renderTags(); };

// ── Helpers ───────────────────────────────────────────────────
function fmtSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

function escHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function showToast(msg, type) {
  const el = document.createElement("div");
  el.className = "fixed bottom-6 right-6 z-50 bg-white shadow-lg rounded-2xl px-5 py-3 text-sm font-medium border border-gray-100 flash-msg";
  el.style.color = type === "error" ? "#ff3b30" : "#34c759";
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}
