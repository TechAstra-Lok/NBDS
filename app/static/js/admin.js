/**
 * NBD Admin Panel JavaScript
 */

'use strict';

// ── Admin Theme ───────────────────────────────
const AdminTheme = {
  key: 'nbd-admin-theme',
  
  init() {
    const saved = localStorage.getItem(this.key) || 'light';
    document.getElementById('htmlRoot')?.setAttribute('data-bs-theme', saved);
    this.updateIcon(saved);
    
    document.getElementById('adminThemeToggle')?.addEventListener('click', () => this.toggle());
  },
  
  toggle() {
    const current = document.getElementById('htmlRoot')?.getAttribute('data-bs-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.getElementById('htmlRoot')?.setAttribute('data-bs-theme', next);
    localStorage.setItem(this.key, next);
    this.updateIcon(next);
  },
  
  updateIcon(theme) {
    const icon = document.getElementById('adminThemeIcon');
    if (icon) icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
  }
};

// ── Sidebar Toggle (Mobile) ───────────────────
const Sidebar = {
  init() {
    const sidebar  = document.getElementById('adminSidebar');
    const overlay  = document.getElementById('sidebarOverlay');
    const toggle   = document.getElementById('sidebarToggle');
    const close    = document.getElementById('sidebarClose');
    
    toggle?.addEventListener('click', () => this.show(sidebar, overlay));
    close?.addEventListener('click', () => this.hide(sidebar, overlay));
    overlay?.addEventListener('click', () => this.hide(sidebar, overlay));
    
    // Escape key
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') this.hide(sidebar, overlay);
    });
  },
  
  show(sidebar, overlay) {
    sidebar?.classList.add('show');
    overlay?.classList.add('show');
    document.body.style.overflow = 'hidden';
  },
  
  hide(sidebar, overlay) {
    sidebar?.classList.remove('show');
    overlay?.classList.remove('show');
    document.body.style.overflow = '';
  }
};

// ── Confirm Delete ────────────────────────────
const ConfirmDelete = {
  init() {
    document.querySelectorAll('[data-confirm]').forEach(btn => {
      btn.addEventListener('click', function(e) {
        const msg = this.getAttribute('data-confirm') || 'Are you sure?';
        if (!confirm(msg)) {
          e.preventDefault();
          e.stopPropagation();
        }
      });
    });
    
    // Delete forms
    document.querySelectorAll('form[data-confirm]').forEach(form => {
      form.addEventListener('submit', function(e) {
        const msg = this.getAttribute('data-confirm') || 'Are you sure you want to delete this?';
        if (!confirm(msg)) {
          e.preventDefault();
        }
      });
    });
  }
};

// ── Toggle Status via AJAX ────────────────────
const StatusToggle = {
  init() {
    document.querySelectorAll('.status-toggle').forEach(btn => {
      btn.addEventListener('click', function() {
        const url = this.getAttribute('data-url');
        const row = this.closest('tr');
        
        fetch(url, { method: 'POST', headers: { 'X-CSRFToken': getCSRFToken() } })
          .then(r => r.json())
          .then(data => {
            const badge = this.closest('td')?.querySelector('.status-badge');
            if (badge) {
              if (data.status === 'available' || data.is_active === true) {
                badge.className = 'badge bg-success status-badge';
                badge.textContent = 'Active';
              } else {
                badge.className = 'badge bg-secondary status-badge';
                badge.textContent = 'Inactive';
              }
            }
          })
          .catch(err => console.error('Toggle error:', err));
      });
    });
  }
};

// ── CSRF Token Helper ─────────────────────────
function getCSRFToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

// ── Data Table Search ─────────────────────────
const TableSearch = {
  init() {
    const searchInput = document.getElementById('tableSearch');
    if (!searchInput) return;
    
    searchInput.addEventListener('input', function() {
      const query = this.value.toLowerCase();
      document.querySelectorAll('table tbody tr').forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
      });
    });
  }
};

// ── Rich Text Editor ──────────────────────────
const RichEditor = {
  init() {
    const editorEl = document.getElementById('rich-editor');
    if (!editorEl) return;
    
    // Load Quill dynamically
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://cdn.quilljs.com/1.3.7/quill.snow.css';
    document.head.appendChild(link);
    
    const script = document.createElement('script');
    script.src = 'https://cdn.quilljs.com/1.3.7/quill.min.js';
    script.onload = () => {
      // Dynamically create Quill container and hide textarea
      const container = document.createElement('div');
      container.id = 'rich-editor-container';
      container.style.height = '300px';
      editorEl.parentNode.insertBefore(container, editorEl);
      editorEl.style.display = 'none';
      
      const quill = new Quill(container, {
        theme: 'snow',
        modules: {
          toolbar: [
            ['bold', 'italic', 'underline', 'strike'],
            ['blockquote', 'code-block'],
            [{ 'header': [1, 2, 3, false] }],
            [{ 'list': 'ordered' }, { 'list': 'bullet' }],
            ['link', 'image'],
            ['clean']
          ]
        }
      });
      
      // Sync with textarea
      const form = editorEl.closest('form');
      form?.addEventListener('submit', () => {
        editorEl.value = quill.root.innerHTML;
      });
      
      // Set initial content
      if (editorEl.value) {
        quill.root.innerHTML = editorEl.value;
      }
    };
    document.head.appendChild(script);
  }
};

// ── Initialize ────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  AdminTheme.init();
  Sidebar.init();
  ConfirmDelete.init();
  StatusToggle.init();
  TableSearch.init();
  RichEditor.init();
  
  // Bootstrap tooltips
  document.querySelectorAll('[data-bs-toggle="tooltip"]')
    .forEach(el => new bootstrap.Tooltip(el));
  
  // Auto-dismiss alerts
  document.querySelectorAll('.alert:not(.alert-permanent)').forEach(alert => {
    setTimeout(() => {
      new bootstrap.Alert(alert).close();
    }, 6000);
  });
});