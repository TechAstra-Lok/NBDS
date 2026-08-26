/**
 * NBDS Blood Bank Real-Time Alerts & Notification Engine
 * Handles Socket.IO live updates, popup modals, audio alerts, and polling fallback.
 */

'use strict';

const BBAlerts = {
  socket: null,
  soundEnabled: true,
  audioCtx: null,
  pollInterval: null,
  lastNotifId: 0,
  unreadCount: 0,

  init() {
    this.soundEnabled = localStorage.getItem('nbds_bb_sound_enabled') !== 'false';
    this.initSoundToggle();
    this.initSocket();
  },

  initSoundToggle() {
    const toggleBtn = document.getElementById('bbSoundToggle');
    if (!toggleBtn) return;
    this.updateSoundButtonUI();

    toggleBtn.addEventListener('click', () => {
      this.soundEnabled = !this.soundEnabled;
      localStorage.setItem('nbds_bb_sound_enabled', this.soundEnabled ? 'true' : 'false');
      this.updateSoundButtonUI();
      if (this.soundEnabled) {
        this.playAlert();
      }
    });
  },

  updateSoundButtonUI() {
    const toggleBtn = document.getElementById('bbSoundToggle');
    const icon = document.getElementById('bbSoundIcon');
    if (!toggleBtn || !icon) return;

    if (this.soundEnabled) {
      icon.className = 'fas fa-volume-high text-success';
      toggleBtn.title = 'Audio Alerts: ON (Click to mute)';
    } else {
      icon.className = 'fas fa-volume-xmark text-muted';
      toggleBtn.title = 'Audio Alerts: MUTED (Click to unmute)';
    }
  },

  initSocket() {
    if (typeof io === 'undefined') {
      console.warn('Socket.IO library not loaded — starting polling fallback.');
      this.startPolling();
      return;
    }

    try {
      this.socket = io({
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 2000
      });

      this.socket.on('connect', () => {
        console.log('Socket.IO connected. Requesting blood bank room subscription...');
        this.socket.emit('join_bloodbank');
        this.stopPolling();
      });

      this.socket.on('joined_bloodbank', (data) => {
        console.log('Successfully joined Blood Bank room:', data.room);
      });

      this.socket.on('blood_reservation_received', (data) => {
        console.log('Real-time Blood Reservation received:', data);
        this.handleReservationAlert(data);
      });

      this.socket.on('nearby_blood_request', (data) => {
        console.log('Real-time Nearby Blood Request received:', data);
        this.handleNearbyRequestAlert(data);
      });

      this.socket.on('disconnect', (reason) => {
        console.warn('Socket.IO disconnected (' + reason + ') — activating polling fallback.');
        this.startPolling();
      });

      this.socket.on('connect_error', (err) => {
        console.warn('Socket connection error — polling fallback active:', err);
        this.startPolling();
      });

    } catch (e) {
      console.error('Socket.IO init exception:', e);
      this.startPolling();
    }
  },

  startPolling() {
    if (this.pollInterval) return;
    this.pollInterval = setInterval(() => this.pollNotifications(), 15000);
    this.pollNotifications();
  },

  stopPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  },

  async pollNotifications() {
    try {
      const res = await fetch(`/bloodbank/api/notifications/poll?since_id=${this.lastNotifId}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === 'ok') {
        this.updateBadge(data.unread_count);
        if (data.notifications && data.notifications.length > 0) {
          data.notifications.forEach(n => {
            if (n.id > this.lastNotifId) this.lastNotifId = n.id;
            if (n.type === 'RESERVATION') {
              this.handleReservationAlert(n.meta || n);
            } else if (n.type === 'NEARBY_REQUEST') {
              this.handleNearbyRequestAlert(n.meta || n);
            }
          });
        }
      }
    } catch (e) {
      // Polling network fail — silent retry next cycle
    }
  },

  updateBadge(count) {
    this.unreadCount = count;
    const badge = document.getElementById('bbNotifBadge');
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count > 99 ? '99+' : count;
      badge.classList.remove('d-none');
    } else {
      badge.classList.add('d-none');
    }
  },

  playAlert() {
    if (!this.soundEnabled) return;
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      
      if (!this.audioCtx) {
        this.audioCtx = new AudioContextClass();
      }
      if (this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }

      const now = this.audioCtx.currentTime;

      // Note 1: 587.33 Hz (D5)
      const osc1 = this.audioCtx.createOscillator();
      const gain1 = this.audioCtx.createGain();
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(587.33, now);
      gain1.gain.setValueAtTime(0.25, now);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
      osc1.connect(gain1);
      gain1.connect(this.audioCtx.destination);
      osc1.start(now);
      osc1.stop(now + 0.3);

      // Note 2: 880 Hz (A5)
      const osc2 = this.audioCtx.createOscillator();
      const gain2 = this.audioCtx.createGain();
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(880, now + 0.15);
      gain2.gain.setValueAtTime(0.3, now + 0.15);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.55);
      osc2.connect(gain2);
      gain2.connect(this.audioCtx.destination);
      osc2.start(now + 0.15);
      osc2.stop(now + 0.55);

    } catch (e) {
      console.warn('Audio alert playback suppressed by browser policy:', e);
    }
  },

  handleReservationAlert(data) {
    this.playAlert();
    this.updateBadge(this.unreadCount + 1);

    const modalEl = document.getElementById('bbRealtimeAlertModal');
    if (!modalEl) return;

    document.getElementById('bbAlertTitle').innerHTML = '<i class="fas fa-hand-holding-medical text-danger me-2"></i>Blood Reservation Request Received';
    document.getElementById('bbAlertHeader').className = 'modal-header bg-danger text-white';
    
    document.getElementById('bbAlertBody').innerHTML = `
      <div class="alert alert-danger bg-opacity-10 border-0 rounded-3 mb-3 p-3">
        <h6 class="fw-bold text-danger mb-1"><i class="fas fa-circle-exclamation me-1"></i>New Blood Reservation Submitted</h6>
        <p class="small text-muted mb-0">A patient has submitted a request requiring hospital verification.</p>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-borderless mb-0">
          <tbody>
            <tr><th class="text-muted w-35">Request ID:</th><td class="fw-bold mono-code text-danger">#RES-${String(data.reservation_id || '').padStart(5, '0')}</td></tr>
            <tr><th class="text-muted">Patient Name:</th><td class="fw-bold">${data.patient_name || 'N/A'}</td></tr>
            <tr><th class="text-muted">Blood Group:</th><td><span class="badge bg-danger fs-6 px-2 py-1">${data.blood_group || 'N/A'}</span> <span class="text-muted small">(${data.component || 'Whole Blood'})</span></td></tr>
            <tr><th class="text-muted">Units:</th><td class="fw-bold">${data.units || 1} Unit(s)</td></tr>
            <tr><th class="text-muted">Hospital:</th><td>${data.hospital_name || 'N/A'}</td></tr>
            <tr><th class="text-muted">Urgency:</th><td><span class="badge ${data.urgency === 'Emergency' ? 'bg-danger pulse-emergency' : 'bg-warning text-dark'}">${data.urgency || 'Normal'}</span></td></tr>
            ${data.required_date ? `<tr><th class="text-muted">Required Date:</th><td>${data.required_date}</td></tr>` : ''}
          </tbody>
        </table>
      </div>
    `;

    const actionBtn = document.getElementById('bbAlertActionBtn');
    actionBtn.className = 'btn btn-danger rounded-pill px-4 shadow-sm';
    actionBtn.innerHTML = '<i class="fas fa-file-medical me-1"></i> View Reservation';
    actionBtn.onclick = () => {
      window.location.href = '/bloodbank/reservations';
    };

    const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    bsModal.show();
  },

  handleNearbyRequestAlert(data) {
    this.playAlert();
    this.updateBadge(this.unreadCount + 1);

    const modalEl = document.getElementById('bbRealtimeAlertModal');
    if (!modalEl) return;

    const isEmergency = (data.urgency === 'Emergency');
    document.getElementById('bbAlertTitle').innerHTML = `<i class="fas fa-location-dot ${isEmergency ? 'text-danger' : 'text-warning'} me-2"></i>Blood Request Posted Near Your Location`;
    document.getElementById('bbAlertHeader').className = `modal-header ${isEmergency ? 'bg-danger text-white' : 'bg-dark text-white'}`;

    const distStr = (data.distance_km !== null && data.distance_km !== undefined) ? `~${data.distance_km} km` : 'Local Community';

    document.getElementById('bbAlertBody').innerHTML = `
      <div class="alert ${isEmergency ? 'alert-danger' : 'alert-warning'} bg-opacity-10 border-0 rounded-3 mb-3 p-3">
        <h6 class="fw-bold mb-1">${isEmergency ? '🚨 Emergency Blood Request' : '📢 Community Blood Request'}</h6>
        <p class="small text-muted mb-0">A new blood request has been posted near your blood bank facility.</p>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-borderless mb-0">
          <tbody>
            <tr><th class="text-muted w-35">Request ID:</th><td class="fw-bold mono-code text-primary">#REQ-${data.request_id || ''}</td></tr>
            <tr><th class="text-muted">Blood Group:</th><td><span class="badge bg-danger fs-6 px-2 py-1">${data.blood_group || 'N/A'}</span></td></tr>
            <tr><th class="text-muted">Patient:</th><td class="fw-bold">${data.patient_name || 'Patient'}</td></tr>
            <tr><th class="text-muted">Hospital:</th><td>${data.hospital || 'N/A'}</td></tr>
            <tr><th class="text-muted">Location:</th><td>${[data.local_level, data.district].filter(Boolean).join(', ')}</td></tr>
            <tr><th class="text-muted">Distance:</th><td><span class="badge bg-secondary-subtle text-dark border">${distStr}</span></td></tr>
            <tr><th class="text-muted">Urgency:</th><td><span class="badge ${isEmergency ? 'bg-danger pulse-emergency' : 'bg-secondary'}">${data.urgency || 'Normal'}</span></td></tr>
          </tbody>
        </table>
      </div>
    `;

    const actionBtn = document.getElementById('bbAlertActionBtn');
    actionBtn.className = isEmergency ? 'btn btn-danger rounded-pill px-4 shadow-sm' : 'btn btn-primary rounded-pill px-4 shadow-sm';
    actionBtn.innerHTML = '<i class="fas fa-external-link me-1"></i> View Blood Request';
    actionBtn.onclick = () => {
      window.open(`/blood-request/${data.request_id}`, '_blank');
    };

    const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    bsModal.show();
  }
};

document.addEventListener('DOMContentLoaded', () => {
  BBAlerts.init();
});
