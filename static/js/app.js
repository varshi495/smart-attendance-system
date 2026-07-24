/**
 * app.js - Global JavaScript for Smart Attendance System
 * Handles: clock, sidebar toggle, toast notifications, shared utilities
 */

// ── Live Clock ──────────────────────────────────────────────
(function startClock() {
  function update() {
    const now  = new Date();
    const time = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const date = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });

    const clockEl = document.getElementById('topbar-clock');
    const dateEl  = document.getElementById('topbar-date');
    if (clockEl) clockEl.textContent = time;
    if (dateEl)  dateEl.textContent  = date;
  }
  update();
  setInterval(update, 1000);
})();

// ── Sidebar Toggle ──────────────────────────────────────────
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// Click outside sidebar to close on mobile
document.addEventListener('click', (e) => {
  const sidebar = document.getElementById('sidebar');
  const toggle  = document.getElementById('sidebar-toggle');
  if (window.innerWidth <= 700 &&
      !sidebar.contains(e.target) &&
      !toggle.contains(e.target)) {
    sidebar.classList.remove('open');
  }
});

// ── Toast Notification System ───────────────────────────────
let toastTimer = null;

/**
 * Show a toast notification.
 * @param {string} message - Message to display
 * @param {string} type    - 'success' | 'error' | 'warning' | 'info'
 * @param {number} duration - Duration in ms (default 3500)
 */
function showToast(message, type = 'info', duration = 3500) {
  const toast = document.getElementById('toast');
  if (!toast) return;

  // Clear existing timer
  if (toastTimer) clearTimeout(toastTimer);

  // Remove old type classes
  toast.className = 'toast';

  // Set content and type
  toast.textContent = message;
  toast.classList.add(`toast-${type}`, 'show');

  // Auto-hide
  toastTimer = setTimeout(() => {
    toast.classList.remove('show');
  }, duration);
}

// ── Button Loading State ────────────────────────────────────
/**
 * Toggle loading state on a button.
 * @param {string}  btnId      - ID of the button element
 * @param {string}  textId     - ID of the text span
 * @param {string}  spinnerId  - ID of the spinner span
 * @param {boolean} loading    - Whether to show loading state
 */
function setBtnLoading(btnId, textId, spinnerId, loading) {
  const btn     = document.getElementById(btnId);
  const text    = document.getElementById(textId);
  const spinner = document.getElementById(spinnerId);
  if (!btn) return;

  btn.disabled              = loading;
  if (text)    text.style.display    = loading ? 'none'         : 'inline';
  if (spinner) spinner.style.display = loading ? 'inline-block' : 'none';
}

// ── Stop media stream helper ────────────────────────────────
function stopStream(stream) {
  if (stream) {
    stream.getTracks().forEach(track => track.stop());
  }
}

// ── Auto-dismiss flash messages ─────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(f => {
    setTimeout(() => {
      f.style.opacity    = '0';
      f.style.transition = 'opacity 0.4s';
      setTimeout(() => f.remove(), 400);
    }, 4000);
  });
});
