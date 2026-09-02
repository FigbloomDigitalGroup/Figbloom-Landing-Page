/* Shared helpers for the admin dashboard. Loaded before each page's own
   inline <script>, which then calls these instead of redefining them —
   every existing call site (apiFetch(...), getCsrfToken()) keeps working
   unchanged since the signatures match what was already there.

   API_BASE is always the empty string (relative fetch, same-origin) —
   the previous per-page copies of this hardcoded http://127.0.0.1:8000
   for "local" and '' for everywhere else, which meant login.html (the one
   page that never got a hostname-based fallback at all) tried to talk to
   127.0.0.1:8000 even in production. Relative URLs work in both
   environments with no branching needed. */

const API_BASE = '';

function getCsrfToken() {
  return (
    document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrftoken='))
      ?.split('=')[1] || ''
  );
}

async function apiFetch(url, options = {}) {
  const csrfToken = getCsrfToken();

  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    credentials: 'include',
    headers: {
      ...(options.headers || {}),
      'X-CSRFToken': csrfToken,
    },
  });

  if (response.status === 401 || response.status === 403) {
    window.location.href = '/admin-dashboard/login';
    throw new Error('Not authenticated');
  }

  return response;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function initAdminHeader() {
  document.getElementById('admin-logout-btn')?.addEventListener('click', async () => {
    try {
      await apiFetch('/api/auth/logout/', { method: 'POST' });
    } catch (error) {
      console.error('Logout error:', error);
    }
    window.location.href = '/admin-dashboard/login';
  });
}

/* Light/dark toggle for the admin dashboard. admin.css defines three
   states: unset (follows the OS/browser preference), data-theme="light",
   and data-theme="dark" — the toggle only ever sets an explicit light/dark
   override once clicked, so until then the page keeps following system
   preference like it always did. The choice is remembered per-browser via
   localStorage so it persists across admin pages and future visits. */

const THEME_STORAGE_KEY = 'figbloom-admin-theme';

function getSystemPrefersDark() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function applyAdminTheme(theme) {
  const root = document.documentElement;

  if (theme === 'light' || theme === 'dark') {
    root.dataset.theme = theme;
  } else {
    delete root.dataset.theme;
  }

  const toggle = document.getElementById('theme-toggle');
  if (!toggle) return;

  const isDark = theme === 'dark' || (theme !== 'light' && getSystemPrefersDark());
  toggle.setAttribute('aria-checked', String(isDark));
}

function initThemeToggle() {
  let saved = null;

  try {
    saved = localStorage.getItem(THEME_STORAGE_KEY);
  } catch (error) {
    // localStorage unavailable (private browsing) — falls back to
    // following system preference every load, same as before this existed.
  }

  applyAdminTheme(saved);

  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    const current = document.documentElement.dataset.theme
      || (getSystemPrefersDark() ? 'dark' : 'light');
    const next = current === 'dark' ? 'light' : 'dark';

    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch (error) {
      // ignore — toggle still works for this page load, just won't persist
    }

    applyAdminTheme(next);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initAdminHeader();
  initThemeToggle();
});

/* In-app replacements for window.confirm()/alert() — those render as
   raw browser chrome (address bar, OS dialog styling) instead of
   matching the rest of the admin UI. Both build their DOM on first
   use, so no markup changes are needed on any page that loads this
   file. */

function showConfirm(message, options = {}) {
  const { confirmText = 'Confirm', cancelText = 'Cancel', danger = false } = options;

  return new Promise((resolve) => {
    let backdrop = document.getElementById('ad-confirm-backdrop');

    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'ad-confirm-backdrop';
      backdrop.className = 'ad-modal-backdrop';
      backdrop.style.display = 'none';
      backdrop.innerHTML = `
        <div class="ad-modal" style="max-width: 420px;">
          <div class="ad-modal-header">Please confirm</div>
          <div class="ad-modal-body" id="ad-confirm-message"></div>
          <div class="ad-modal-footer">
            <button type="button" class="ad-btn-secondary" id="ad-confirm-cancel"></button>
            <button type="button" id="ad-confirm-ok"></button>
          </div>
        </div>
      `;
      document.body.appendChild(backdrop);
    }

    const messageEl = backdrop.querySelector('#ad-confirm-message');
    const okBtn = backdrop.querySelector('#ad-confirm-ok');
    const cancelBtn = backdrop.querySelector('#ad-confirm-cancel');

    messageEl.textContent = message;
    okBtn.textContent = confirmText;
    cancelBtn.textContent = cancelText;
    okBtn.className = danger ? 'ad-btn-danger' : 'ad-btn-primary';

    function cleanup(result) {
      backdrop.style.display = 'none';
      okBtn.removeEventListener('click', onOk);
      cancelBtn.removeEventListener('click', onCancel);
      backdrop.removeEventListener('click', onBackdropClick);
      resolve(result);
    }

    function onOk() {
      cleanup(true);
    }

    function onCancel() {
      cleanup(false);
    }

    function onBackdropClick(event) {
      if (event.target === backdrop) {
        cleanup(false);
      }
    }

    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
    backdrop.addEventListener('click', onBackdropClick);

    backdrop.style.display = 'flex';
  });
}

function showToast(message, type = 'info') {
  let container = document.getElementById('ad-toast-container');

  if (!container) {
    container = document.createElement('div');
    container.id = 'ad-toast-container';
    container.className = 'ad-toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `ad-toast ad-toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  requestAnimationFrame(() => toast.classList.add('ad-toast-visible'));

  setTimeout(() => {
    toast.classList.remove('ad-toast-visible');
    setTimeout(() => toast.remove(), 250);
  }, 4500);
}
