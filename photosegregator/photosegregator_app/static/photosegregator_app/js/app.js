/* ──────────────────────────────────────────────────────────────────
   PhotoFind  ·  app.js
────────────────────────────────────────────────────────────────── */

"use strict";

// ── DOM refs ─────────────────────────────────────────────────────
const uploadZone      = document.getElementById("upload-zone");
const uploadZoneInner = document.getElementById("upload-zone-inner");
const selfieInput     = document.getElementById("selfie-input");
const previewWrap     = document.getElementById("preview-wrap");
const selfiePreview   = document.getElementById("selfie-preview");
const changePhotoBtn  = document.getElementById("change-photo-btn");
const findBtn         = document.getElementById("find-btn");

const stepUpload      = document.getElementById("step-upload");
const stepLoading     = document.getElementById("step-loading");
const stepResults     = document.getElementById("step-results");
const stepNoMatch     = document.getElementById("step-no-match");
const stepError       = document.getElementById("step-error");

const loadingMessage  = document.getElementById("loading-message");
const resultsTitle    = document.getElementById("results-title");
const resultsDesc     = document.getElementById("results-desc");
const downloadAllBtn  = document.getElementById("download-all-btn");
const searchAgainBtn  = document.getElementById("search-again-btn");
const photoGrid       = document.getElementById("photo-grid");
const confBar         = document.getElementById("conf-bar");
const confValue       = document.getElementById("conf-value");

const tryAgainBtn     = document.getElementById("try-again-btn");
const errorRetryBtn   = document.getElementById("error-retry-btn");
const errorMessage    = document.getElementById("error-message");

const lightbox        = document.getElementById("lightbox");
const lightboxImg     = document.getElementById("lightbox-img");
const lightboxClose   = document.getElementById("lightbox-close");
const lightboxBg      = document.getElementById("lightbox-backdrop");
const lightboxDl      = document.getElementById("lightbox-download");
const lightboxFname   = document.getElementById("lightbox-filename");

const toast           = document.getElementById("toast");

// ── State ─────────────────────────────────────────────────────────
let selectedFile     = null;
let currentPerson    = null;
let toastTimer       = null;

// ── SECTIONS ─────────────────────────────────────────────────────
const ALL_STEPS = [stepUpload, stepLoading, stepResults, stepNoMatch, stepError];

function showStep(step) {
  ALL_STEPS.forEach(s => s.classList.add("hidden"));
  step.classList.remove("hidden");
}

// ── TOAST ─────────────────────────────────────────────────────────
function showToast(msg, duration = 3000) {
  toast.textContent = msg;
  toast.classList.remove("hidden");
  // Force reflow
  toast.offsetHeight;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.classList.add("hidden"), 300);
  }, duration);
}

// ── FILE SELECTION ────────────────────────────────────────────────
function handleFileSelected(file) {
  if (!file) return;
  const allowed = ["image/jpeg", "image/png", "image/webp", "image/bmp"];
  if (!allowed.includes(file.type)) {
    showToast("❌ Please upload a JPG, PNG, WebP, or BMP image.");
    return;
  }
  if (file.size > 15 * 1024 * 1024) {
    showToast("❌ File too large. Max 15 MB.");
    return;
  }

  selectedFile = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    selfiePreview.src = e.target.result;
    uploadZoneInner.classList.add("hidden");
    previewWrap.classList.remove("hidden");
  };
  reader.readAsDataURL(file);
}

selfieInput.addEventListener("change", () => handleFileSelected(selfieInput.files[0]));

changePhotoBtn.addEventListener("click", () => {
  selectedFile = null;
  selfieInput.value = "";
  previewWrap.classList.add("hidden");
  uploadZoneInner.classList.remove("hidden");
});

// Click on zone → open file picker
uploadZone.addEventListener("click", (e) => {
  if (e.target.closest(".preview-wrap")) return;
  if (e.target.closest("label")) return;
  selfieInput.click();
});

// Drag & Drop
uploadZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadZone.classList.add("dragover");
});

uploadZone.addEventListener("dragleave", () => {
  uploadZone.classList.remove("dragover");
});

uploadZone.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadZone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  handleFileSelected(file);
});

// ── FIND MY PHOTOS ────────────────────────────────────────────────
const loadingMessages = [
  "Detecting face in your selfie…",
  "Scanning the gallery for matches…",
  "Comparing facial features…",
  "Almost there, finalizing results…",
];
let loadingMsgIndex = 0;
let loadingMsgTimer = null;

function startLoadingMessages() {
  loadingMsgIndex = 0;
  loadingMessage.textContent = loadingMessages[0];
  loadingMsgTimer = setInterval(() => {
    loadingMsgIndex = (loadingMsgIndex + 1) % loadingMessages.length;
    loadingMessage.textContent = loadingMessages[loadingMsgIndex];
  }, 2200);
}

function stopLoadingMessages() {
  clearInterval(loadingMsgTimer);
}

findBtn.addEventListener("click", async () => {
  if (!selectedFile) {
    showToast("Please select a selfie first.");
    return;
  }

  showStep(stepLoading);
  startLoadingMessages();

  const formData = new FormData();
  formData.append("selfie", selectedFile);

  try {
    const response = await fetch("/api/find-my-photos/", {
      method: "POST",
      body: formData,
    });

    stopLoadingMessages();

    const data = await response.json();

    if (!data.success) {
      showStep(stepError);
      errorMessage.textContent = data.error || "An unknown error occurred.";
      return;
    }

    if (!data.matched) {
      showStep(stepNoMatch);
      return;
    }

    // ── SHOW RESULTS ──
    currentPerson = data.person_label;
    resultsTitle.textContent = `${data.total_photos} Photo${data.total_photos !== 1 ? "s" : ""} Found!`;
    resultsDesc.textContent  = `We found ${data.total_photos} photo${data.total_photos !== 1 ? "s" : ""} of you in the gallery.`;

    // Confidence bar
    const conf = data.confidence || 0;
    confBar.style.width  = `${Math.min(conf, 100)}%`;
    confValue.textContent = `${conf.toFixed(1)}%`;

    // Download all button
    downloadAllBtn.dataset.person = currentPerson;

    // Build photo grid
    photoGrid.innerHTML = "";
    data.photos.forEach((filename) => {
      const item = document.createElement("div");
      item.className = "photo-item";

      const img = document.createElement("img");
      img.src  = `/api/photo/${currentPerson}/${filename}/`;
      img.alt  = filename;
      img.loading = "lazy";

      const overlay = document.createElement("div");
      overlay.className = "photo-item-overlay";

      const dlBtn = document.createElement("button");
      dlBtn.className   = "photo-item-dl";
      dlBtn.textContent = "↓ Download";
      dlBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        downloadSinglePhoto(currentPerson, filename);
      });

      overlay.appendChild(dlBtn);
      item.appendChild(img);
      item.appendChild(overlay);

      // Click → lightbox
      item.addEventListener("click", () => openLightbox(currentPerson, filename));

      photoGrid.appendChild(item);
    });

    showStep(stepResults);

  } catch (err) {
    stopLoadingMessages();
    showStep(stepError);
    errorMessage.textContent = "Network error. Make sure the server is running.";
    console.error(err);
  }
});

// ── RESET ─────────────────────────────────────────────────────────
function resetToUpload() {
  selectedFile = null;
  selfieInput.value = "";
  currentPerson = null;
  previewWrap.classList.add("hidden");
  uploadZoneInner.classList.remove("hidden");
  selfiePreview.src = "";
  showStep(stepUpload);
}

searchAgainBtn.addEventListener("click", resetToUpload);
tryAgainBtn.addEventListener("click", resetToUpload);
errorRetryBtn.addEventListener("click", resetToUpload);

// ── DOWNLOAD ALL ──────────────────────────────────────────────────
downloadAllBtn.addEventListener("click", () => {
  if (!currentPerson) return;
  showToast("⏳ Preparing your ZIP file…");
  window.location.href = `/api/download-all/${currentPerson}/`;
});

// ── SINGLE DOWNLOAD ───────────────────────────────────────────────
function downloadSinglePhoto(person, filename) {
  const a = document.createElement("a");
  a.href     = `/api/download/${person}/${filename}/`;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  showToast("⬇ Downloading…");
}

// ── LIGHTBOX ──────────────────────────────────────────────────────
function openLightbox(person, filename) {
  lightboxImg.src         = `/api/photo/${person}/${filename}/`;
  lightboxDl.href         = `/api/download/${person}/${filename}/`;
  lightboxDl.download     = filename;
  lightboxFname.textContent = filename;
  lightbox.classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closeLightbox() {
  lightbox.classList.add("hidden");
  document.body.style.overflow = "";
  lightboxImg.src = "";
}

lightboxClose.addEventListener("click", closeLightbox);
lightboxBg.addEventListener("click", closeLightbox);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeLightbox();
});

// ── INIT ──────────────────────────────────────────────────────────
showStep(stepUpload);