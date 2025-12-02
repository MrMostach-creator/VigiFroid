// javascript.js 

(function () {
  'use strict';
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return (root || document).querySelectorAll(sel); }

  function parseYMD(s) {
    if (!s) return null;
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s).trim());
    if (!m) return null;
    const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    return isNaN(d) ? null : d;
  }

  function updateDaysBadges() {
    const cards = $$('.lot-card');
    if (!cards.length) return;
    const today = new Date();
    today.setHours(0,0,0,0);
    cards.forEach(card => {
      const expiryStr = card.getAttribute('data-expiry');
      const badge = $('.days-badge', card);
      const expiry = parseYMD(expiryStr);
      if (!badge) return;
      if (!expiry) { badge.textContent = '--'; return; }
      expiry.setHours(0,0,0,0);
      const d = Math.ceil((expiry - today) / (24*60*60*1000));
      badge.textContent = d < 0 ? '0' : String(Math.abs(d));
    });
  }

  // Function to prevent the same image from being selected twice
  function setupImageChangeGuard() {
    const imageInput = $('#image');
    if (!imageInput) return;
    let lastFile = '';
    imageInput.addEventListener('change', e => {
      const f = e.target.files[0];
      const name = f ? f.name : '';
      if (name && name === lastFile) {
        const msg = (window.i18n && window.i18n.alreadySelected) || 'You already selected this file';
        alert(msg);
        e.target.value = '';
        return;
      }
      lastFile = name;
      if (typeof window.validateAdd === 'function') window.validateAdd();
      if (typeof window.validateEdit === 'function') window.validateEdit();
    });
    window.addEventListener('beforeunload', e => {
      if (imageInput.files && imageInput.files.length) { e.preventDefault(); e.returnValue=''; }
    });
  }

  // Add resize listener for responsive updates
  window.addEventListener('resize', () => {
    updateDaysBadges(); // Update on resize if needed
  });

  // On page load, run the functions
  document.addEventListener('DOMContentLoaded', () => {
    try { updateDaysBadges(); } catch(_) {}
    try { setupImageChangeGuard(); } catch(_) {}
  });
})();

// Toggle language menu
document.addEventListener('DOMContentLoaded', () => {
  const wrap = document.querySelector('.lang-menu-wrap');
  const btn = wrap ? wrap.querySelector('.lang-toggle') : null;
  const menu = wrap ? wrap.querySelector('.lang-container') : null;

  if (!wrap || !btn || !menu) return;

  const closeMenu = () => wrap.classList.remove('active');

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    wrap.classList.toggle('active');
  });

  document.addEventListener('click', (e) => {
    if (wrap.classList.contains('active') && !wrap.contains(e.target)) {
      closeMenu();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeMenu();
  });
});

// Theme toggle
document.addEventListener('DOMContentLoaded', () => {
  const buttons = document.querySelectorAll('.theme-toggle');

  function applyTheme(raw) {
    const map = { clair: 'light', sombre: 'dark', light: 'light', dark: 'dark' };
    const normalized = map[raw] || 'light';

    document.body.setAttribute('data-theme', normalized);
    localStorage.setItem('theme', raw);

    buttons.forEach(b => b.classList.remove('active'));
    buttons.forEach(b => {
      if (b.dataset.theme === raw) b.classList.add('active');
    });
  }

  // Restore
  const saved = localStorage.getItem('theme') || 'clair';
  applyTheme(saved);

  // On click
  buttons.forEach(btn => {
    btn.addEventListener('click', () => applyTheme(btn.dataset.theme));
  });
});