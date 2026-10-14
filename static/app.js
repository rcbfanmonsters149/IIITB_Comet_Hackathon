// IIIT-B Contactless Access Control (Clean 3-Feed Frontend)

let isScanning = false;
let audioAnimationId = null;
let webcamStream = null;

// Audio wave animation state
const audioCanvas = document.getElementById('audio-canvas');
const audioCtx = audioCanvas ? audioCanvas.getContext('2d') : null;
let wavePhase = 0;

function drawAudioWave(isActive = false) {
  if (!audioCtx) return;
  const w = audioCanvas.width;
  const h = audioCanvas.height;

  audioCtx.clearRect(0, 0, w, h);

  // Background grid lines
  audioCtx.strokeStyle = '#f1f5f9';
  audioCtx.lineWidth = 1;
  for (let x = 0; x < w; x += 30) {
    audioCtx.beginPath();
    audioCtx.moveTo(x, 0);
    audioCtx.lineTo(x, h);
    audioCtx.stroke();
  }
  for (let y = 0; y < h; y += 25) {
    audioCtx.beginPath();
    audioCtx.moveTo(0, y);
    audioCtx.lineTo(w, y);
    audioCtx.stroke();
  }

  // Wave line
  audioCtx.beginPath();
  audioCtx.lineWidth = 2.5;
  audioCtx.strokeStyle = isActive ? '#2563eb' : '#cbd5e1';

  const centerY = h / 2;
  const amplitude = isActive ? 28 : 3;
  const frequency = isActive ? 0.05 : 0.02;

  for (let x = 0; x < w; x++) {
    const y = centerY + Math.sin(x * frequency + wavePhase) * amplitude 
                      + Math.sin(x * 0.12 + wavePhase * 1.5) * (amplitude * 0.35);
    if (x === 0) audioCtx.moveTo(x, y);
    else audioCtx.lineTo(x, y);
  }
  audioCtx.stroke();

  wavePhase += isActive ? 0.09 : 0.02;
  audioAnimationId = requestAnimationFrame(() => drawAudioWave(isActive));
}

// Start idle wave on page load
drawAudioWave(false);

let isProcessingFrame = false;
let recognitionLoopTimeout = null;

// Exact object-fit: cover coordinate transformation for face bounding box
function updateFaceBoxPosition(cam) {
  const faceBox = document.getElementById('face-box');
  const cameraBox = document.getElementById('camera-box');
  const videoElem = document.getElementById('camera-video');
  if (!faceBox || !cameraBox) return;

  if (!cam || !cam.bbox || cam.bbox.length < 4) {
    return;
  }

  const [bx, by, bw, bh] = cam.bbox;

  // Frame dimensions returned by deep vision engine or client video
  let frameW = cam.frame_width;
  let frameH = cam.frame_height;

  if (!frameW || !frameH) {
    if (videoElem && videoElem.videoWidth > 0 && videoElem.videoHeight > 0) {
      frameW = videoElem.videoWidth;
      frameH = videoElem.videoHeight;
    } else {
      frameW = 640;
      frameH = 480;
    }
  }

  const boxW = cameraBox.clientWidth;
  const boxH = cameraBox.clientHeight;

  if (boxW === 0 || boxH === 0 || frameW === 0 || frameH === 0) return;

  // object-fit: cover computes the scaling factor that fills the container completely
  const scale = Math.max(boxW / frameW, boxH / frameH);
  const renderedW = frameW * scale;
  const renderedH = frameH * scale;
  const offsetX = (boxW - renderedW) / 2;
  const offsetY = (boxH - renderedH) / 2;

  // Transform face coordinates from video frame space to camera box viewport space
  const cssX = offsetX + (bx * scale);
  const cssY = offsetY + (by * scale);
  const cssW = bw * scale;
  const cssH = bh * scale;

  // Keep securely within camera frame bounds
  const clampedX = Math.max(2, Math.min(boxW - cssW - 2, cssX));
  const clampedY = Math.max(2, Math.min(boxH - cssH - 2, cssY));

  faceBox.style.left = `${Math.round(clampedX)}px`;
  faceBox.style.top = `${Math.round(clampedY)}px`;
  faceBox.style.width = `${Math.round(cssW)}px`;
  faceBox.style.height = `${Math.round(cssH)}px`;
  faceBox.style.display = 'block';
}

async function startRecognition() {
  if (isScanning) return;

  const btn = document.getElementById('btn-recognize');
  const btnText = document.getElementById('btn-text');
  const btnIcon = document.getElementById('btn-icon');
  const banner = document.getElementById('status-banner');

  banner.className = 'status-banner scanning';
  banner.innerText = 'Requesting camera access... Please click "Allow" when prompted by your browser.';

  // 1. OPEN CAMERA & EXPLICITLY PROMPT PERMISSION
  const opened = await openCamera();
  if (!opened) {
    return;
  }

  isScanning = true;

  // Set scanning state - stays active for continuous live tracking
  btn.classList.add('scanning');
  btnText.innerText = 'Tracking Face...';
  btnIcon.innerText = '🟢';

  // Activate badges
  document.getElementById('vision-badge').className = 'feed-badge active';
  document.getElementById('vision-badge').innerText = 'Active';

  document.getElementById('prox-badge').className = 'feed-badge active';
  document.getElementById('prox-badge').innerText = 'Active';

  document.getElementById('acoustic-badge').className = 'feed-badge active';
  document.getElementById('acoustic-badge').innerText = 'Active';

  // Start animated active audio waveform
  if (audioAnimationId) cancelAnimationFrame(audioAnimationId);
  drawAudioWave(true);

  // Start continuous recognition loop
  runRecognitionLoop();
}

async function runRecognitionLoop() {
  if (!isScanning) return;

  if (!isProcessingFrame) {
    isProcessingFrame = true;
    try {
      await runRecognitionFrame();
    } catch (err) {
      console.warn("Recognition cycle error:", err);
    } finally {
      isProcessingFrame = false;
    }
  }

  // Smooth periodic tracking loop: 100ms interval between finished frame and next capture
  if (isScanning) {
    recognitionLoopTimeout = setTimeout(runRecognitionLoop, 100);
  }
}

async function runRecognitionFrame() {
  if (!isScanning) return;

  const videoElem = document.getElementById('camera-video');
  let frameBase64 = null;

  if (videoElem && videoElem.videoWidth > 0 && !videoElem.paused && !videoElem.ended) {
    try {
      const snapCanvas = document.createElement('canvas');
      // Normalize to 640px width preserving aspect ratio for high-speed low-latency deep inference
      const targetW = Math.min(640, videoElem.videoWidth);
      const targetH = Math.round(targetW * (videoElem.videoHeight / videoElem.videoWidth));
      snapCanvas.width = targetW;
      snapCanvas.height = targetH;
      const ctx = snapCanvas.getContext('2d');
      ctx.drawImage(videoElem, 0, 0, targetW, targetH);
      frameBase64 = snapCanvas.toDataURL('image/jpeg', 0.82);
    } catch (e) {
      console.warn("Canvas capture error:", e);
    }
  }

  const persona = document.getElementById('demo-persona').value;

  try {
    const res = await fetch('/api/recognize_frame', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image_base64: frameBase64,
        scenario_override: (persona === 'NORMAL' && frameBase64) ? null : persona
      })
    });
    const data = await res.json();
    applyRecognitionResults(data, persona);
  } catch (err) {
    console.warn("Server inference error, falling back to local simulation:", err);
    applyLocalPersonaResult(persona);
  }
}

async function openCamera() {
  const videoElem = document.getElementById('camera-video');
  const streamImg = document.getElementById('camera-stream');
  const placeholder = document.getElementById('camera-placeholder');
  const faceBox = document.getElementById('face-box');
  const cameraBox = document.getElementById('camera-box');
  const banner = document.getElementById('status-banner');

  if (placeholder) placeholder.style.display = 'none';

  let opened = false;

  // 1. Try requesting browser webcam
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    try {
      console.log("[CAM] Requesting camera permission via getUserMedia...");
      webcamStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user'
        },
        audio: false
      });

      if (videoElem) {
        videoElem.srcObject = webcamStream;
        await videoElem.play().catch(e => console.warn("Video play notice:", e));
        videoElem.style.display = 'block';
      }
      if (streamImg) streamImg.style.display = 'none';
      opened = true;
      console.log("[CAM] Browser webcam opened successfully!");
    } catch (err) {
      console.warn("[CAM] Browser webcam error / permission denied:", err);
      if (banner) {
        banner.className = 'status-banner';
        banner.innerText = "Camera access denied or busy. Switching to simulated testbed feed...";
      }
    }
  }

  // 2. If browser webcam was not opened, fallback to live security feed
  if (!opened) {
    if (videoElem) videoElem.style.display = 'none';
    if (streamImg) {
      streamImg.src = '/api/stream?' + Date.now();
      streamImg.style.display = 'block';
    }
  }

  // Position initial face bounding box in center of viewport
  if (faceBox && cameraBox) {
    const boxW = cameraBox.clientWidth || 400;
    const boxH = cameraBox.clientHeight || 300;
    const initialW = Math.round(boxW * 0.45);
    const initialH = Math.round(boxH * 0.58);
    const initialX = Math.round((boxW - initialW) / 2);
    const initialY = Math.round((boxH - initialH) / 2);

    faceBox.style.left = `${initialX}px`;
    faceBox.style.top = `${initialY}px`;
    faceBox.style.width = `${initialW}px`;
    faceBox.style.height = `${initialH}px`;
    faceBox.style.display = 'block';
    faceBox.style.borderColor = '#22c55e';
    faceBox.style.boxShadow = '0 0 16px rgba(34, 197, 94, 0.45)';
    document.getElementById('face-tag').innerText = 'Detecting Face...';
  }

  return true;
}

function applyRecognitionResults(data, persona) {
  const banner = document.getElementById('status-banner');
  const faceBox = document.getElementById('face-box');
  const faceTag = document.getElementById('face-tag');

  const dec = data.decision || 'ACCESS_GRANTED';
  const isGranted = (dec === 'ACCESS_GRANTED');
  const cam = data.components?.cam || {};

  // Dynamically position face bounding box on exact face location
  if (cam.bbox && cam.bbox.length >= 4) {
    updateFaceBoxPosition(cam);
  }

  // Update Status Banner and Visual Colors
  if (dec === 'IDLE_NO_FACE_DETECTED') {
    banner.className = 'status-banner';
    banner.innerText = '⚠️ Position your face in front of the camera...';
    if (faceBox) {
      faceBox.style.borderColor = '#94a3b8';
      faceBox.style.boxShadow = 'none';
      faceTag.style.backgroundColor = '#64748b';
      faceTag.innerText = 'Searching Face...';
    }
  } else if (isGranted) {
    banner.className = 'status-banner granted';
    banner.innerText = `✅ ACCESS GRANTED: ${data.user_name} (Door Unlocked)`;
    if (faceBox) {
      faceBox.style.borderColor = '#16a34a';
      faceBox.style.boxShadow = '0 0 16px rgba(22, 163, 74, 0.5)';
      faceTag.style.backgroundColor = '#16a34a';
      faceTag.innerText = `${data.user_name} (${Math.round((cam.similarity || 0.94) * 100)}%)`;
    }
  } else if (dec.includes('PRESENTATION_ATTACK')) {
    banner.className = 'status-banner denied';
    banner.innerText = `❌ ACCESS DENIED: Presentation Attack Detected (Failed Biological Liveness)`;
    if (faceBox) {
      faceBox.style.borderColor = '#dc2626';
      faceBox.style.boxShadow = '0 0 16px rgba(220, 38, 38, 0.5)';
      faceTag.style.backgroundColor = '#dc2626';
      faceTag.innerText = `SPOOF / PHOTO DETECTED`;
    }
  } else if (dec.includes('DEVICE_ABSENT')) {
    banner.className = 'status-banner denied';
    banner.innerText = `❌ ACCESS DENIED: Face Recognized (${data.user_name}), but Registered Phone is Out of Range`;
    if (faceBox) {
      faceBox.style.borderColor = '#dc2626';
      faceBox.style.boxShadow = '0 0 16px rgba(220, 38, 38, 0.5)';
      faceTag.style.backgroundColor = '#dc2626';
      faceTag.innerText = `${data.user_name} (Phone Missing)`;
    }
  } else if (dec.includes('STOLEN_DEVICE')) {
    banner.className = 'status-banner denied';
    banner.innerText = `❌ ACCESS DENIED: Authorized Phone Present, but Face is an Unauthorized Stranger!`;
    if (faceBox) {
      faceBox.style.borderColor = '#dc2626';
      faceBox.style.boxShadow = '0 0 16px rgba(220, 38, 38, 0.5)';
      faceTag.style.backgroundColor = '#dc2626';
      faceTag.innerText = `UNREGISTERED STRANGER`;
    }
  } else {
    banner.className = 'status-banner denied';
    banner.innerText = `❌ ACCESS DENIED: Unregistered Person (Not found in authorized database)`;
    if (faceBox) {
      faceBox.style.borderColor = '#dc2626';
      faceBox.style.boxShadow = '0 0 16px rgba(220, 38, 38, 0.5)';
      faceTag.style.backgroundColor = '#dc2626';
      faceTag.innerText = `UNREGISTERED STRANGER`;
    }
  }

  // 1. Vision Feed Metrics
  document.getElementById('vis-user-name').innerText = data.user_name || 'Dr. Ramesh Kumar';
  
  const matchPct = Math.round((cam.similarity || 0.94) * 100);
  document.getElementById('vis-match-score').innerText = `${matchPct}%`;
  document.getElementById('vis-match-bar').style.width = `${matchPct}%`;
  document.getElementById('vis-match-bar').style.backgroundColor = isGranted ? '#16a34a' : (persona === 'STOLEN_PHONE' ? '#dc2626' : '#2563eb');

  const livePct = Math.round((cam.liveness || (persona === 'PHOTO_ATTACK' ? 0.28 : 0.94)) * 100);
  document.getElementById('vis-liveness-score').innerText = `${livePct}% (${cam.is_live ? 'LIVE' : 'SPOOF'})`;
  document.getElementById('vis-liveness-bar').style.width = `${livePct}%`;
  document.getElementById('vis-liveness-bar').style.backgroundColor = (livePct >= 70) ? '#16a34a' : '#dc2626';

  // 2. Proximity Feed Metrics
  const wifi = data.components?.wifi || {};
  const rssiVal = wifi.rssi || (persona === 'WALK_BY' ? -65 : (persona === 'PHOTO_ATTACK' ? -88 : -42));
  const distVal = wifi.distance_m || (persona === 'WALK_BY' ? 3.8 : (persona === 'PHOTO_ATTACK' ? 12.0 : 0.8));
  
  document.getElementById('prox-rssi').innerText = `${rssiVal} dBm`;
  document.getElementById('prox-device-name').innerText = wifi.device_name || 'Ramesh_Pixel8 (F4:F5:DB:89:12:34)';
  document.getElementById('prox-distance').innerText = `${distVal} meters (${distVal <= 1.0 ? 'At Door' : 'Out of Range'})`;
  document.getElementById('prox-subtext').innerText = (distVal <= 1.0) ? 'Phone Detected in Near-Field' : 'Device Exceeds 1.0m Perimeter';

  const proxPct = Math.max(0, Math.min(100, Math.round(100 + rssiVal)));
  document.getElementById('prox-signal-score').innerText = `${proxPct}%`;
  document.getElementById('prox-signal-bar').style.width = `${proxPct}%`;
  document.getElementById('prox-signal-bar').style.backgroundColor = (distVal <= 1.0) ? '#16a34a' : '#d97706';

  // 3. Acoustic Feed Metrics
  const audio = data.components?.audio || {};
  const hasAcoustic = (persona !== 'PHOTO_ATTACK' && persona !== 'WALK_BY');
  
  document.getElementById('acoustic-token-status').innerText = hasAcoustic ? 'Validated (19 kHz)' : 'Faint / Unverified';
  document.getElementById('acoustic-freq-val').innerText = hasAcoustic ? '19,000 Hz (Inaudible)' : 'None';
  document.getElementById('acoustic-freq-bar').style.width = hasAcoustic ? '95%' : '20%';
  document.getElementById('acoustic-freq-bar').style.backgroundColor = hasAcoustic ? '#16a34a' : '#dc2626';
  document.getElementById('acoustic-snr-val').innerText = hasAcoustic ? '26.4 dB' : '4.2 dB (Attenuated)';

  // Continuous tracking remains active: we do NOT reset isScanning to false here!
}

function applyLocalPersonaResult(persona) {
  const isGranted = (persona === 'NORMAL');
  applyRecognitionResults({
    decision: isGranted ? 'ACCESS_GRANTED' : (
      persona === 'PHOTO_ATTACK' ? 'DENIED_PRESENTATION_ATTACK' : (
        persona === 'WALK_BY' ? 'DENIED_DEVICE_ABSENT' : 'DENIED_STOLEN_DEVICE'
      )
    ),
    user_name: (persona === 'STOLEN_PHONE') ? 'Unregistered Intruder' : 'Dr. Ramesh Kumar',
    components: {
      cam: {
        similarity: (persona === 'STOLEN_PHONE') ? 0.22 : 0.94,
        liveness: (persona === 'PHOTO_ATTACK') ? 0.28 : 0.94,
        is_live: (persona !== 'PHOTO_ATTACK')
      },
      wifi: {
        verified: (persona === 'NORMAL' || persona === 'STOLEN_PHONE'),
        rssi: (persona === 'WALK_BY' ? -65 : (persona === 'PHOTO_ATTACK' ? -88 : -42)),
        distance_m: (persona === 'WALK_BY' ? 3.8 : (persona === 'PHOTO_ATTACK' ? 12.0 : 0.8)),
        device_name: 'Ramesh_Pixel8 (F4:F5:DB:89:12:34)'
      },
      audio: {
        verified: (persona === 'NORMAL' || persona === 'STOLEN_PHONE'),
        frequency_peak_hz: (persona === 'NORMAL' || persona === 'STOLEN_PHONE') ? 19000 : 0,
        snr_db: (persona === 'NORMAL' || persona === 'STOLEN_PHONE') ? 26.4 : 4.1
      }
    }
  }, persona);
}

function onPersonaChange() {
  const banner = document.getElementById('status-banner');
  const persona = document.getElementById('demo-persona').value;
  banner.className = 'status-banner';
  banner.innerText = `Selected profile: ${document.getElementById('demo-persona').selectedOptions[0].text}. Click "Recognize Face".`;
}

function stopRecognition() {
  isScanning = false;
  isProcessingFrame = false;
  if (recognitionLoopTimeout) {
    clearTimeout(recognitionLoopTimeout);
    recognitionLoopTimeout = null;
  }
  if (recognitionInterval) {
    clearInterval(recognitionInterval);
    recognitionInterval = null;
  }

  // 1. Turn off webcam stream tracks
  if (webcamStream) {
    webcamStream.getTracks().forEach(track => {
      track.stop();
    });
    webcamStream = null;
  }

  // 2. Reset video elements and placeholder
  const videoElem = document.getElementById('camera-video');
  const streamImg = document.getElementById('camera-stream');
  const placeholder = document.getElementById('camera-placeholder');
  const faceBox = document.getElementById('face-box');

  if (videoElem) {
    videoElem.srcObject = null;
    videoElem.style.display = 'none';
  }
  if (streamImg) {
    streamImg.src = '';
    streamImg.style.display = 'none';
  }
  if (placeholder) {
    placeholder.style.display = 'block';
    placeholder.innerHTML = '<span class="camera-placeholder-icon">📷</span>Camera Turned Off<br><small>Click "Recognize Face" to start</small>';
  }
  if (faceBox) {
    faceBox.style.display = 'none';
  }

  // 3. Reset feed badges to Standby
  document.getElementById('vision-badge').className = 'feed-badge';
  document.getElementById('vision-badge').innerText = 'Standby';

  document.getElementById('prox-badge').className = 'feed-badge';
  document.getElementById('prox-badge').innerText = 'Standby';

  document.getElementById('acoustic-badge').className = 'feed-badge';
  document.getElementById('acoustic-badge').innerText = 'Standby';

  // 4. Reset audio waveform to idle
  if (audioAnimationId) cancelAnimationFrame(audioAnimationId);
  drawAudioWave(false);

  // 5. Reset metrics across all 3 feeds
  document.getElementById('vis-user-name').innerText = '—';
  document.getElementById('vis-match-score').innerText = '0%';
  document.getElementById('vis-match-bar').style.width = '0%';
  document.getElementById('vis-liveness-score').innerText = '0%';
  document.getElementById('vis-liveness-bar').style.width = '0%';

  document.getElementById('prox-rssi').innerText = '-- dBm';
  document.getElementById('prox-device-name').innerText = '—';
  document.getElementById('prox-distance').innerText = '—';
  document.getElementById('prox-subtext').innerText = 'Awaiting device beacon';
  document.getElementById('prox-signal-score').innerText = '0%';
  document.getElementById('prox-signal-bar').style.width = '0%';

  document.getElementById('acoustic-token-status').innerText = '—';
  document.getElementById('acoustic-freq-val').innerText = '-- Hz';
  document.getElementById('acoustic-freq-bar').style.width = '0%';
  document.getElementById('acoustic-snr-val').innerText = '—';

  // 6. Reset button and status banner
  const btn = document.getElementById('btn-recognize');
  const btnText = document.getElementById('btn-text');
  const btnIcon = document.getElementById('btn-icon');
  const banner = document.getElementById('status-banner');

  btn.classList.remove('scanning');
  btnText.innerText = 'Recognize Face';
  btnIcon.innerText = '📷';

  banner.className = 'status-banner';
  banner.innerText = 'Camera turned off. Click "Recognize Face" to start verification.';

  isScanning = false;
}
