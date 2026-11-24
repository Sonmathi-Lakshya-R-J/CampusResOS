// Shared state, API helper, and UI helpers. Load before feature modules.
const $ = (id) => document.getElementById(id);

const today = new Date();
const localToday =
  `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

let currentUser = null;
let selectedRoom = null;
let searchedDates = [];
let availableRoomResults = [];

// -------------------- API HELPER --------------------

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.error || `Request failed (${response.status})`);
  }

  return data;
}

// -------------------- UI HELPERS --------------------

function message(id, text, type = "success") {
  const el = $(id);
  if (!el) return;

  el.textContent = text;
  el.className = `message ${type}`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character]);
}

function prettyTime(value) {
  return String(value || "").slice(0, 5);
}

// -------------------- ROOM AND BOOKING DATA --------------------

