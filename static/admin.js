// Admin Dashboard Client Script

let enrolledUsers = [];
let auditLogs = [];
let enrollMediaStream = null;
let currentPhotoBase64 = null;

// Tab Switching
function switchTab(tabId, btnElem) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

  const target = document.getElementById(`tab-${tabId}`);
  if (target) target.classList.add('active');
  if (btnElem) btnElem.classList.add('active');

  if (tabId === 'roster') loadUsers();
  if (tabId === 'logs') loadLogs();
}

// ---------------------------------------------------------------------------
// 1. Authorized Personnel Roster
// ---------------------------------------------------------------------------

async function loadUsers() {
  try {
    const res = await fetch('/api/admin/users');
    const data = await res.json();
    enrolledUsers = data.users || [];
    renderUsers(enrolledUsers);
  } catch (err) {
    console.error("Failed to load users:", err);
  }
}

function renderUsers(users) {
  const grid = document.getElementById('roster-grid');
  grid.innerHTML = '';

  if (users.length === 0) {
    grid.innerHTML = '<div style="color:var(--text-muted); padding:30px;">No authorized personnel found in the database.</div>';
    return;
  }

  users.forEach(u => {
    const card = document.createElement('div');
    card.className = 'person-card';
    card.innerHTML = `
      <img src="${u.photo_url}" alt="${u.name}" class="person-avatar" onerror="this.src='/api/user_photo/${u.user_id}'">
      <div class="person-info">
        <div class="person-name">${u.name}</div>
        <div class="person-id">${u.user_id} &bull; ${u.access_tier}</div>
        <div class="person-detail"><strong>Role:</strong> ${u.role}</div>
        <div class="person-detail"><strong>Dept:</strong> ${u.department}</div>
        <div class="person-detail"><strong>Device:</strong> ${u.registered_phone} (${u.registered_mac})</div>
        <span class="person-badge">Enrolled: ${u.enrolled_at.split(' ')[0] || u.enrolled_at}</span>
      </div>
      <button class="btn-revoke" title="Revoke Access" onclick="deleteUser('${u.user_id}', '${u.name}')">🗑️</button>
    `;
    grid.appendChild(card);
  });
}

function filterRoster() {
  const query = document.getElementById('roster-search').value.toLowerCase().trim();
  const filtered = enrolledUsers.filter(u => 
    u.name.toLowerCase().includes(query) ||
    u.user_id.toLowerCase().includes(query) ||
    u.department.toLowerCase().includes(query) ||
    u.role.toLowerCase().includes(query)
  );
  renderUsers(filtered);
}

async function deleteUser(userId, userName) {
  if (!confirm(`Are you sure you want to revoke access and delete ${userName} (${userId}) from the authorized database?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/admin/users/${userId}`, { method: 'DELETE' });
    if (res.ok) {
      alert(`User ${userName} revoked successfully.`);
      loadUsers();
    } else {
      alert('Failed to delete user.');
    }
  } catch (err) {
    alert('Network error while deleting user.');
  }
}

// ---------------------------------------------------------------------------
// 2. Face Enrollment (Webcam & File Upload)
// ---------------------------------------------------------------------------

async function openEnrollCamera() {
  const video = document.getElementById('enroll-video');
  const preview = document.getElementById('enroll-preview');
  const placeholder = document.getElementById('enroll-placeholder');
  const btnOpen = document.getElementById('btn-open-cam');
  const btnSnap = document.getElementById('btn-snap-photo');
  const btnRetake = document.getElementById('btn-retake-photo');

  try {
    enrollMediaStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
    });
    video.srcObject = enrollMediaStream;
    await video.play();
    video.style.display = 'block';
    preview.style.display = 'none';
    placeholder.style.display = 'none';

    btnOpen.style.display = 'none';
    btnSnap.style.display = 'inline-flex';
    btnRetake.style.display = 'none';
  } catch (err) {
    alert('Could not access webcam. Please check browser permissions or upload an image file.');
  }
}

function snapEnrollPhoto() {
  const video = document.getElementById('enroll-video');
  const canvas = document.getElementById('enroll-canvas');
  const preview = document.getElementById('enroll-preview');
  const btnSnap = document.getElementById('btn-snap-photo');
  const btnRetake = document.getElementById('btn-retake-photo');

  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  currentPhotoBase64 = canvas.toDataURL('image/jpeg', 0.9);
  preview.src = currentPhotoBase64;
  preview.style.display = 'block';
  video.style.display = 'none';

  // Stop camera tracks
  if (enrollMediaStream) {
    enrollMediaStream.getTracks().forEach(t => t.stop());
    enrollMediaStream = null;
  }

  btnSnap.style.display = 'none';
  btnRetake.style.display = 'inline-flex';
}

function retakeEnrollPhoto() {
  currentPhotoBase64 = null;
  openEnrollCamera();
}

function onFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    currentPhotoBase64 = e.target.result;
    
    const preview = document.getElementById('enroll-preview');
    const placeholder = document.getElementById('enroll-placeholder');
    const video = document.getElementById('enroll-video');

    if (enrollMediaStream) {
      enrollMediaStream.getTracks().forEach(t => t.stop());
      enrollMediaStream = null;
    }

    video.style.display = 'none';
    placeholder.style.display = 'none';
    preview.src = currentPhotoBase64;
    preview.style.display = 'block';

    document.getElementById('btn-open-cam').style.display = 'inline-flex';
    document.getElementById('btn-snap-photo').style.display = 'none';
    document.getElementById('btn-retake-photo').style.display = 'none';
  };
  reader.readAsDataURL(file);
}

async function submitEnrollment(e) {
  e.preventDefault();

  if (!currentPhotoBase64) {
    alert('Please snap a photo using the camera or select an image file first!');
    return;
  }

  const payload = {
    user_id: document.getElementById('inp-uid') ? document.getElementById('inp-uid').value.trim() : undefined,
    name: document.getElementById('inp-name').value.trim(),
    role: document.getElementById('inp-role').value.trim(),
    department: document.getElementById('inp-dept').value.trim(),
    access_tier: document.getElementById('inp-tier').value,
    phone: document.getElementById('inp-phone').value.trim(),
    mac: document.getElementById('inp-mac').value.trim(),
    image_base64: currentPhotoBase64
  };

  const btnSubmit = document.getElementById('btn-submit-enroll');
  btnSubmit.disabled = true;
  btnSubmit.innerText = 'Enrolling & Extracting Embeddings...';

  try {
    const res = await fetch('/api/admin/enroll_webcam', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (res.ok) {
      alert(`✅ Successfully enrolled ${payload.name} (Assigned ID: ${data.user_id})!`);
      // Reset form
      document.getElementById('enroll-form').reset();
      currentPhotoBase64 = null;
      document.getElementById('enroll-preview').style.display = 'none';
      document.getElementById('enroll-placeholder').style.display = 'block';
      document.getElementById('btn-open-cam').style.display = 'inline-flex';
      document.getElementById('btn-snap-photo').style.display = 'none';
      document.getElementById('btn-retake-photo').style.display = 'none';

      // Switch back to roster & reload users immediately
      switchTab('roster', document.querySelectorAll('.nav-btn')[0]);
      loadUsers();
    } else {
      alert(`Enrollment failed: ${data.error || 'Unknown error'}`);
    }
  } catch (err) {
    alert('Network error during enrollment.');
  } finally {
    btnSubmit.disabled = false;
    btnSubmit.innerText = '💾 Save & Enroll Person to Database';
  }
}

// ---------------------------------------------------------------------------
// 3. Premises Entry Logs & Attendance History
// ---------------------------------------------------------------------------

async function loadLogs() {
  try {
    const res = await fetch('/api/admin/logs');
    const data = await res.json();
    auditLogs = data.logs || [];
    renderLogs(auditLogs);
  } catch (err) {
    console.error("Failed to load logs:", err);
  }
}

function renderLogs(logs) {
  const tbody = document.getElementById('logs-tbody');
  tbody.innerHTML = '';

  if (logs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:30px;">No entry history recorded yet.</td></tr>';
    return;
  }

  logs.forEach(entry => {
    const isGranted = (entry.decision === 'ACCESS_GRANTED');
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${entry.timestamp}</strong></td>
      <td>
        <div style="font-weight:700;">${entry.user_name || 'Visitor'}</div>
        <div style="font-size:0.75rem; color:var(--text-muted);">${entry.user_id || 'UNKNOWN'}</div>
      </td>
      <td>
        <span class="status-tag ${isGranted ? 'granted' : 'denied'}">
          ${entry.decision}
        </span>
      </td>
      <td><strong>${Math.round((entry.composite_score || 0) * 100)}%</strong></td>
      <td style="max-width:320px; font-size:0.8rem; color:var(--text-secondary);">${entry.reason || 'Authentication cycle'}</td>
      <td style="color:var(--text-muted);">Door 04A (AI Lab)</td>
    `;
    tbody.appendChild(tr);
  });
}

function filterLogs() {
  const query = document.getElementById('logs-search').value.toLowerCase().trim();
  const filtered = auditLogs.filter(l => 
    (l.user_name && l.user_name.toLowerCase().includes(query)) ||
    (l.decision && l.decision.toLowerCase().includes(query)) ||
    (l.timestamp && l.timestamp.toLowerCase().includes(query))
  );
  renderLogs(filtered);
}

function exportLogsCSV() {
  window.location.href = '/api/admin/export_logs_csv';
}

async function clearLogs() {
  if (!confirm('Are you sure you want to clear the premises entry history?')) return;
  try {
    await fetch('/api/admin/clear_logs', { method: 'POST' });
    loadLogs();
  } catch (err) {
    alert('Failed to clear logs.');
  }
}

// Initial load
window.onload = () => {
  loadUsers();
};
