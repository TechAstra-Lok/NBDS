/**
 * NBD Society - Main JavaScript
 * Handles: Theme, Forms, Search, PWA, Animations
 */

'use strict';

// ── Theme Manager ─────────────────────────────
const ThemeManager = {
  key: 'nbd-theme',
  
  init() {
    const saved = localStorage.getItem(this.key) || 'light';
    this.apply(saved);
    
    document.getElementById('themeToggle')?.addEventListener('click', () => this.toggle());
    document.getElementById('themeToggleMobile')?.addEventListener('click', () => this.toggle());
  },
  
  apply(theme) {
    document.getElementById('htmlRoot').setAttribute('data-bs-theme', theme);
    const icon = document.getElementById('themeIcon');
    const iconM = document.getElementById('themeIconMobile');
    if (icon) icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    if (iconM) iconM.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    localStorage.setItem(this.key, theme);
  },
  
  toggle() {
    const current = document.getElementById('htmlRoot').getAttribute('data-bs-theme');
    this.apply(current === 'dark' ? 'light' : 'dark');
  }
};

// ── Toast Notifications ───────────────────────
const Toast = {
  show(message, type = 'success', duration = 4000) {
    const container = document.querySelector('.flash-container') || this.createContainer();
    const toast = document.createElement('div');
    const icons = { success: '✅', danger: '❌', warning: '⚠️', info: 'ℹ️' };
    
    toast.className = `toast show align-items-center text-bg-${type} border-0 mb-2 shadow`;
    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body" style="max-width:300px;">
          ${icons[type] || ''} ${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                onclick="this.closest('.toast').remove()"></button>
      </div>
    `;
    
    container.appendChild(toast);
    setTimeout(() => toast.remove(), duration);
  },
  
  createContainer() {
    const c = document.createElement('div');
    c.className = 'flash-container position-fixed top-0 end-0 p-3';
    c.style.cssText = 'z-index:9999; margin-top:70px;';
    document.body.appendChild(c);
    return c;
  }
};

// ── Form Enhancements ─────────────────────────
const FormEnhancements = {
  init() {
    // Bootstrap validation
    document.querySelectorAll('form.needs-validation').forEach(form => {
      form.addEventListener('submit', e => {
        if (!form.checkValidity()) {
          e.preventDefault();
          e.stopPropagation();
          const firstInvalid = form.querySelector(':invalid');
          firstInvalid?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          firstInvalid?.focus();
        }
        form.classList.add('was-validated');
      });
    });
    
    // Phone number formatter
    document.querySelectorAll('input[type="tel"], input[name*="phone"]').forEach(input => {
      input.addEventListener('input', function() {
        this.value = this.value.replace(/[^0-9]/g, '').slice(0, 10);
      });
    });
    
    // Image preview
    document.querySelectorAll('input[type="file"]').forEach(input => {
      input.addEventListener('change', function() {
        const preview = document.getElementById(this.id + '_preview') || 
                        this.parentElement.querySelector('.img-preview');
        if (preview && this.files[0]) {
          const reader = new FileReader();
          reader.onload = e => {
            preview.src = e.target.result;
            preview.style.display = 'block';
          };
          reader.readAsDataURL(this.files[0]);
        }
      });
    });
    
    // Auto-hide old toasts
    document.querySelectorAll('.toast').forEach(toast => {
      setTimeout(() => {
        if (toast.parentElement) {
          toast.classList.remove('show');
          setTimeout(() => toast.remove(), 300);
        }
      }, 5000);
    });
  }
};

// ── Live Donor Search ─────────────────────────
const LiveSearch = {
  init() {
    const searchInput = document.getElementById('liveSearch');
    if (!searchInput) return;
    
    let debounceTimer;
    searchInput.addEventListener('input', function() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => LiveSearch.search(this.value), 400);
    });
  },
  
  async search(query) {
    const bg = document.getElementById('searchBG')?.value || '';
    const resultsContainer = document.getElementById('liveResults');
    if (!resultsContainer) return;
    
    if (query.length < 2 && !bg) {
      resultsContainer.innerHTML = '';
      return;
    }
    
    try {
      const params = new URLSearchParams({ q: query, bg: bg, limit: 5 });
      const res = await fetch(`/api/v1/donors/search?${params}`);
      const data = await res.json();
      
      if (data.donors.length === 0) {
        resultsContainer.innerHTML = '<div class="p-3 text-muted small">No donors found</div>';
        return;
      }
      
      resultsContainer.innerHTML = data.donors.map(d => `
        <div class="d-flex align-items-center p-2 border-bottom hover-bg" 
             onclick="window.location='/donor/${d.donor_id}'" style="cursor:pointer;">
          <div class="blood-badge-sm bg-danger text-white rounded fw-bold px-2 py-1 me-3 fs-6">
            ${d.blood_group}
          </div>
          <div>
            <div class="fw-semibold small">${d.full_name}</div>
            <div class="text-muted" style="font-size:0.75rem;">
              ${d.city}, ${d.district} · ${d.donor_type}
              <span class="badge bg-${d.availability === 'available' ? 'success' : 'secondary'} ms-1">
                ${d.availability}
              </span>
            </div>
          </div>
        </div>
      `).join('');
    } catch (err) {
      console.error('Search error:', err);
    }
  }
};

// ── Scroll Animations ─────────────────────────
const ScrollAnimations = {
  init() {
    if (!('IntersectionObserver' in window)) return;
    
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animate__animated', 'animate__fadeInUp');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });
    
    document.querySelectorAll('.stat-card, .blood-req-card, .donor-card, .card.hover-lift')
            .forEach(el => observer.observe(el));
  }
};

// ── Counter Animation ─────────────────────────
const CounterAnimation = {
  init() {
    document.querySelectorAll('[data-count]').forEach(el => {
      const target = parseInt(el.getAttribute('data-count'));
      const duration = 1500;
      const start = performance.now();
      
      const update = (time) => {
        const elapsed = time - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.floor(eased * target);
        if (progress < 1) requestAnimationFrame(update);
      };
      
      requestAnimationFrame(update);
    });
  }
};

// ── Ad Impression Tracking ────────────────────
const AdTracker = {
  init() {
    if (!('IntersectionObserver' in window)) return;
    
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const adId = entry.target.getAttribute('data-ad-id');
          if (adId) {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
            fetch(`/api/v1/ad/impression/${adId}`, {
              method: 'POST',
              headers: {
                'X-CSRFToken': csrfToken
              }
            }).catch(() => {});
            observer.unobserve(entry.target);
          }
        }
      });
    }, { threshold: 0.5 });
    
    document.querySelectorAll('[data-ad-id]').forEach(el => observer.observe(el));
  }
};

// ── Clipboard Copy ────────────────────────────
function copyText(text) {
  navigator.clipboard?.writeText(text).then(() => {
    Toast.show(`📋 "${text}" copied to clipboard!`, 'success', 2500);
  }).catch(() => {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
    Toast.show(`📋 Copied!`, 'success', 2000);
  });
}

// ── Global Early PWA Install Prompt Capture ───
window.__nbdsDeferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  window.__nbdsDeferredPrompt = e;
  if (typeof ActionPopup !== 'undefined') {
    ActionPopup.deferredPrompt = e;
    const btn = document.getElementById('btnInstallApp');
    if (btn) btn.classList.remove('d-none');
  }
});

// ── Action Opening Popup & PWA Installation ───
const ActionPopup = {
  STORAGE_KEY: 'nbds_action_popup_seen',
  COOLDOWN_HOURS: 48,
  deferredPrompt: window.__nbdsDeferredPrompt || null,

  init() {
    if (window.__nbdsDeferredPrompt) {
      this.deferredPrompt = window.__nbdsDeferredPrompt;
    }

    window.addEventListener('appinstalled', () => {
      this.recordInstalled();
      const modalEl = document.getElementById('nbdsActionModal');
      if (modalEl && typeof bootstrap !== 'undefined') {
        const modal = bootstrap.Modal.getInstance(modalEl);
        modal?.hide();
      }
    });

    // Bind install button
    document.getElementById('btnInstallApp')?.addEventListener('click', () => this.handleInstallClick());

    // Bind dismiss button
    document.getElementById('btnDismissActionPopup')?.addEventListener('click', () => this.recordDismissed());

    // Allow opening globally via helper
    window.openInstallPopup = (force = true) => this.show(force);

    // Evaluate display after DOM load
    if (this.shouldShow()) {
      setTimeout(() => this.show(false), 1200);
    }
  },

  isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches ||
           window.navigator.standalone === true ||
           document.referrer.includes('android-app://');
  },

  shouldShow() {
    if (this.isStandalone()) return false;
    
    // Check URL parameters for testing force-open (e.g. ?install=1 or ?popup=1)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('install') || urlParams.has('popup') || urlParams.has('pwa')) {
      return true;
    }

    // Do not show on portal/admin pages
    const path = window.location.pathname;
    if (path.startsWith('/bloodbank') || path.startsWith('/admin')) return false;

    try {
      const state = JSON.parse(localStorage.getItem(this.STORAGE_KEY) || '{}');
      if (state.installed) return false;
      if (!state.lastDismissed) return true;

      const hoursPassed = (Date.now() - state.lastDismissed) / (1000 * 60 * 60);
      return hoursPassed >= this.COOLDOWN_HOURS;
    } catch (e) {
      return true;
    }
  },

  show(force = false) {
    const modalEl = document.getElementById('nbdsActionModal');
    if (!modalEl || typeof bootstrap === 'undefined') return;

    if (this.isStandalone()) {
      document.getElementById('pwaInstallContainer')?.classList.add('d-none');
    }

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  },

  recordDismissed() {
    try {
      const state = JSON.parse(localStorage.getItem(this.STORAGE_KEY) || '{}');
      state.lastDismissed = Date.now();
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(state));
    } catch (e) {}
  },

  recordInstalled() {
    try {
      const state = JSON.parse(localStorage.getItem(this.STORAGE_KEY) || '{}');
      state.installed = true;
      state.lastDismissed = Date.now();
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(state));
    } catch (e) {}
  },

  async handleInstallClick() {
    const promptEvent = this.deferredPrompt || window.__nbdsDeferredPrompt;
    if (promptEvent) {
      promptEvent.prompt();
      const choice = await promptEvent.userChoice;
      if (choice && choice.outcome === 'accepted') {
        this.recordInstalled();
        const modalEl = document.getElementById('nbdsActionModal');
        if (modalEl && typeof bootstrap !== 'undefined') {
          const modal = bootstrap.Modal.getInstance(modalEl);
          modal?.hide();
        }
      }
      this.deferredPrompt = null;
      window.__nbdsDeferredPrompt = null;
    } else {
      // Dynamic platform instruction fallback
      const manualBox = document.getElementById('installManualInstructions');
      if (manualBox) {
        manualBox.classList.remove('d-none');
        
        const ua = navigator.userAgent || '';
        const isIOS = /iPad|iPhone|iPod/.test(ua) && !window.MSStream;
        const isAndroid = /Android/.test(ua);

        if (isIOS) {
          manualBox.innerHTML = `
            <div class="d-flex align-items-start gap-2">
              <i class="fab fa-apple fs-4 text-dark mt-1"></i>
              <div>
                <strong>Install on iPhone / iPad:</strong><br>
                1. Tap the <i class="fas fa-arrow-up-from-bracket mx-1 text-primary"></i> <strong>Share</strong> button in Safari toolbar.<br>
                2. Scroll down and tap <i class="fas fa-plus-square mx-1 text-dark"></i> <strong>"Add to Home Screen"</strong>.
              </div>
            </div>
          `;
        } else if (isAndroid) {
          manualBox.innerHTML = `
            <div class="d-flex align-items-start gap-2">
              <i class="fab fa-android fs-4 text-success mt-1"></i>
              <div>
                <strong>Install on Android:</strong><br>
                1. Tap the <i class="fas fa-ellipsis-vertical mx-1"></i> <strong>Menu</strong> (3 dots) in your browser.<br>
                2. Select <i class="fas fa-mobile-screen mx-1"></i> <strong>"Install app"</strong> or <strong>"Add to Home Screen"</strong>.
              </div>
            </div>
          `;
        } else {
          manualBox.innerHTML = `
            <div class="d-flex align-items-start gap-2">
              <i class="fas fa-desktop fs-4 text-primary mt-1"></i>
              <div>
                <strong>Install on Computer / Laptop:</strong><br>
                1. Click the <i class="fas fa-download mx-1 text-danger"></i> <strong>Install icon</strong> in your browser address bar.<br>
                2. Or open browser Menu <i class="fas fa-ellipsis-vertical mx-1"></i> $\\rightarrow$ <strong>"Install Nepali Blood Donors"</strong>.
              </div>
            </div>
          `;
        }
      }
    }
  }
};

// ── Initialize All ────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  try { ThemeManager?.init(); } catch (e) {}
  try { FormEnhancements?.init(); } catch (e) {}
  try { LiveSearch?.init(); } catch (e) {}
  try { ScrollAnimations?.init(); } catch (e) {}
  try { CounterAnimation?.init(); } catch (e) {}
  try { AdTracker?.init(); } catch (e) {}
  try { ActionPopup?.init(); } catch (e) {}
  
  // Initialize Bootstrap tooltips
  if (typeof bootstrap !== 'undefined') {
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
      .forEach(el => new bootstrap.Tooltip(el));
    
    // Initialize Bootstrap popovers
    document.querySelectorAll('[data-bs-toggle="popover"]')
      .forEach(el => new bootstrap.Popover(el));
  }
});