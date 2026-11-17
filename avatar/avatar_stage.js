/**
 * ui/avatar/avatar_stage.js
 * =========================
 * 60 FPS Responsive WebGL 3D Avatar Controller for Brahma Sol.
 * 
 * Features:
 * 1. Independent Three.js Render Loop (Never freezes during local AI inference).
 * 2. Complete 62-clip AnimationMixer with seamless cross-fading.
 * 3. Procedural Head & Neck IK Tracking (Tracks mouse cursor or screen targets).
 * 4. Holographic Speech Bubble with dynamic typing & auto-fade.
 * 5. Interactive Animation Testing & Diagnostic Panel (F12 or gear icon).
 * 6. Native Drag-and-Drop file perception.
 * 7. Two-way QWebChannel bridge to Python Proprioception & Action Planner.
 */

let scene, camera, renderer, mixer, clock;
let avatarModel = null;
let currentAction = null;
let activeClipName = "Idle Subtle";
let allClips = [];
const actionsMap = new Map();

// Procedural Bone Tracking & Heading
let neckBone = null;
let headBone = null;
let headBoneBaseQuat = null;
let targetLookAt = { x: 0, y: 0 };
let currentLookAt = { x: 0, y: 0 };
let headIKEnabled = false;
let targetHeading = 0.0;
let currentHeading = 0.0;

const _headEuler = new THREE.Euler(0, 0, 0, 'YXZ');
const _neckEuler = new THREE.Euler(0, 0, 0, 'XYZ');
const _headQuat = new THREE.Quaternion();
const _neckQuat = new THREE.Quaternion();
const _tempBoneQuat = new THREE.Quaternion();
const _identityQuat = new THREE.Quaternion();
const _lastHeadQuat = new THREE.Quaternion();
const _tempInvQuat = new THREE.Quaternion();
let smoothedDelta = 0.016;
let lastAnimateTime = performance.now();

// Telemetry & FPS
let lastFrameTime = performance.now();
let frameCount = 0;
let currentFps = 60;

// Speech Bubble Timeout
let speechTimeout = null;

// Python QWebChannel Bridge
let pyBridge = null;

// =============================================================================
// 1. INITIALIZATION & STAGE SETUP
// =============================================================================

function initStage() {
  const container = document.getElementById("stage-container");
  clock = new THREE.Clock();

  // Scene
  scene = new THREE.Scene();

  // Camera (Isometric-angled perspective for desktop companion)
  const aspect = window.innerWidth / window.innerHeight;
  camera = new THREE.PerspectiveCamera(34, aspect, 0.1, 100);
  camera.position.set(0, 0.22, 2.45);
  camera.lookAt(0, 0.02, 0);

  // Renderer (Hardware-native zero-copy premultipliedAlpha blit)
  renderer = new THREE.WebGLRenderer({
    alpha: true,
    antialias: true,
    premultipliedAlpha: true,
    powerPreference: "high-performance",
    precision: "mediump",
    stencil: false,
    depth: true
  });
  renderer.setClearColor(0x000000, 0);
  renderer.autoClear = true;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1.0, 1.25));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  container.appendChild(renderer.domElement);

  // Lighting
  setupLighting();

  // Load Model
  loadAvatarModel();

  // Event Listeners
  window.addEventListener("resize", onWindowResize);
  setupMouseAndDragListeners(container);
  setupDiagnosticPanel();
  setupWebChannel();

  // Start 60 FPS Render Loop
  animate();
}

function setupLighting() {
  // Soft ambient fill
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
  scene.add(ambientLight);

  // Key directional light (front-left high)
  const keyLight = new THREE.DirectionalLight(0xffffff, 1.2);
  keyLight.position.set(2, 4, 3);
  scene.add(keyLight);

  // Rim back-light (cyberpunk cyan accent outline)
  const rimLight = new THREE.DirectionalLight(0x00f0ff, 1.5);
  rimLight.position.set(-2, 3, -3);
  scene.add(rimLight);

  // Warm secondary fill
  const fillLight = new THREE.DirectionalLight(0x3b82f6, 0.6);
  fillLight.position.set(0, -1, 2);
  scene.add(fillLight);
}

// =============================================================================
// 2. MODEL & ANIMATION LOADING
// =============================================================================

function loadAvatarModel() {
  const loader = new THREE.GLTFLoader();
  const localModelPath = "../assets/avatar/robot.glb";
  const cdnModelPath = "https://raw.githubusercontent.com/titechprabhasolutions/Brahma-sol/main/assets/models/robot.glb";

  function attemptLoad(targetUrl, isFallback = false) {
    console.log(`[BrahmaSol 3D] Loading GLB model from (${isFallback ? "Cloud CDN" : "Local Disk"}): ${targetUrl}`);

    loader.load(
      targetUrl,
      (gltf) => {
        avatarModel = gltf.scene;
        allClips = gltf.animations || [];
        console.log(`[BrahmaSol 3D] Model loaded successfully. Found ${allClips.length} animation clips.`);

        // Position & Scale
        avatarModel.scale.set(1.0, 1.0, 1.0);
        avatarModel.position.set(0, 0, 0);
        scene.add(avatarModel);

        // Inspect skeleton for procedural IK bones
        avatarModel.traverse((node) => {
          if (node.isBone) {
            const name = node.name.toLowerCase();
            if (name === "neck_01" || name.includes("neck")) {
              neckBone = node;
              console.log("[BrahmaSol 3D] Located neck bone:", node.name);
            } else if (name === "head") {
              headBone = node;
              headBoneBaseQuat = node.quaternion.clone();
              console.log("[BrahmaSol 3D] Located head bone:", node.name);
            }
          }
        });

        // Setup AnimationMixer
        mixer = new THREE.AnimationMixer(avatarModel);

        // Register all clips into actionsMap
        allClips.forEach((clip) => {
          const action = mixer.clipAction(clip);
          actionsMap.set(clip.name, action);
        });

        // Populate diagnostic dropdown
        populateClipDropdowns();

        // Listen for non-looping animation completions
        mixer.addEventListener("finished", (e) => {
          const finishedClipName = e.action.getClip().name;
          console.log("[BrahmaSol 3D] Clip finished:", finishedClipName);
          if (pyBridge && pyBridge.onClipFinished) {
            pyBridge.onClipFinished(finishedClipName);
          }
          // ONLY if the finished action is the currently active action AND it was non-looping
          // This ensures fading-out previous clips never prematurely interrupt newly started animations!
          if (e.action === currentAction && e.action.loop === THREE.LoopOnce) {
            if (finishedClipName !== "Sleeping" && finishedClipName !== "Kneeling Tired" && finishedClipName !== "Sitting Enter" && finishedClipName !== "Sitting Exit") {
              const fallback = (activeClipName && activeClipName.includes("Sitting")) ? "Sitting Idle" : "Idle Subtle";
              playAnimation(fallback, 0.35, true);
            }
          }
        });

        // Start initial ground state: "Idle Subtle"
        playAnimation("Idle Subtle", 0.1, true);

        // Trigger landing welcome
        setTimeout(() => {
          showSpeechBubble("Brahma Sol online and operational. Ready when you are.", 4.0);
        }, 800);
      },
      (xhr) => {
        if (xhr.total > 0) {
          const pct = Math.round((xhr.loaded / xhr.total) * 100);
          console.log(`[BrahmaSol 3D] Loading progress: ${pct}%`);
        }
      },
      (err) => {
        console.warn(`[BrahmaSol 3D] Notice loading from ${targetUrl}:`, err);
        if (!isFallback) {
          console.log("[BrahmaSol 3D] Falling back to high-speed cloud CDN stream...");
          attemptLoad(cdnModelPath, true);
        } else {
          console.error("[BrahmaSol 3D] Both local and cloud avatar streams failed.");
        }
      }
    );
  }

  attemptLoad(localModelPath);
}

// =============================================================================
// 3. ANIMATION CONTROLLER & CROSS-FADING
// =============================================================================

// Natural human motion-capture playback rates (1.0x baseline)
const CLIP_SPEEDS = {
  "Walk_2": 0.95,
  "Jog": 1.05,
  "Sprint": 1.15,
  "Turn Left 90": 1.05,
  "Turn Right 90": 1.05,
  "Turn Left 180": 1.05,
  "Turn Right 180": 1.05,
  "Sitting Exit": 1.05,
  "Sitting Enter": 1.0,
  "Greeting": 1.0,
  "Victory Fist Pump": 1.05,
  "Victory": 1.05,
  "Land Three Point": 1.1,
  "Jump Land": 1.1,
  "Kneeling Tired": 1.0,
  "Confused": 1.0,
  "Interact": 1.05,
};

function playAnimation(clipName, blendDuration = 0.3, loop = true) {
  if (!mixer || !actionsMap.has(clipName)) {
    console.warn(`[BrahmaSol 3D] Animation clip not found: "${clipName}"`);
    return false;
  }

  const newAction = actionsMap.get(clipName);

  if (currentAction === newAction && newAction.isRunning()) {
    return true; // Already running
  }

  console.log(`[BrahmaSol 3D] Transitioning to: "${clipName}" (blend: ${blendDuration}s, loop: ${loop})`);

  newAction.reset();
  const speed = CLIP_SPEEDS[clipName] || 1.0;
  newAction.setEffectiveTimeScale(speed);
  newAction.setEffectiveWeight(1.0);

  if (!loop) {
    newAction.setLoop(THREE.LoopOnce);
    newAction.clampWhenFinished = true;
  } else {
    newAction.setLoop(THREE.LoopRepeat);
    newAction.clampWhenFinished = false;
  }

  if (currentAction && currentAction !== newAction) {
    currentAction.crossFadeTo(newAction, blendDuration, true);
  } else {
    newAction.play();
  }

  newAction.play();
  currentAction = newAction;
  activeClipName = clipName;

  // Automatically disable procedural head tracking for resting / acrobatic clips
  const nonIKClips = [
    "Sleeping", "Kneeling Tired", "Meditate", "Roll", "Death D",
    "Jump air", "Jump Land", "Land Three Point", "Turn Left 90",
    "Turn Right 90", "Turn Left 180", "Turn Right 180", "Walk_2",
    "Jog", "Sprint", "Greeting", "Sitting Enter", "Sitting Exit"
  ];
  headIKEnabled = !nonIKClips.includes(clipName);
  if (!headIKEnabled) {
    targetLookAt.x = 0;
    targetLookAt.y = 0;
    currentLookAt.x = 0;
    currentLookAt.y = 0;
  }

  // Update diagnostic UI
  const sel = document.getElementById("clip-select");
  if (sel && sel.value !== clipName) {
    sel.value = clipName;
  }
  const actionTel = document.getElementById("tel-action");
  if (actionTel) {
    actionTel.innerText = clipName.toUpperCase();
  }

  return true;
}

// =============================================================================
// 4. PROCEDURAL HEAD & NECK TRACKING (IK)
// =============================================================================

function updateProceduralLookAt(delta) {
  if (!headBone) return;

  if (!headIKEnabled) {
    targetLookAt.x = 0;
    targetLookAt.y = 0;
    currentLookAt.x = 0;
    currentLookAt.y = 0;
    return;
  }

  // Smooth, organic human eye/head glance dampening (3.0x dt)
  const dt = delta || 0.016;
  const lerpFactor = Math.min(1.0, dt * 3.0);
  currentLookAt.x += (targetLookAt.x - currentLookAt.x) * lerpFactor;
  currentLookAt.y += (targetLookAt.y - currentLookAt.y) * lerpFactor;

  // If gaze is practically centered, leave bone 100% clean
  if (Math.abs(currentLookAt.x) < 0.01 && Math.abs(currentLookAt.y) < 0.01) {
    return;
  }

  // Realistic human head glance limits: max yaw ~11.5 deg (0.20 rad), max pitch ~7 deg (0.12 rad)
  const maxYaw = 0.20;
  const maxPitch = 0.12;

  const yaw = THREE.MathUtils.clamp(-currentLookAt.x * maxYaw, -maxYaw, maxYaw);
  const pitch = THREE.MathUtils.clamp(-currentLookAt.y * maxPitch, -maxPitch, maxPitch);

  _headEuler.set(pitch, yaw, 0, 'YXZ');
  _headQuat.setFromEuler(_headEuler);

  // Soft distance falloff
  const lookWeight = Math.min(1.0, Math.hypot(currentLookAt.x, currentLookAt.y));
  _tempBoneQuat.set(0, 0, 0, 1).slerp(_headQuat, lookWeight * 0.70);

  // Apply to bone and store for next frame's clean undo
  headBone.quaternion.multiply(_tempBoneQuat);
  _lastHeadQuat.copy(_tempBoneQuat);
}

// =============================================================================
// 5. HOLOGRAPHIC SPEECH BUBBLE
// =============================================================================

function showSpeechBubble(text, durationSeconds = 3.5) {
  const bubble = document.getElementById("speech-bubble");
  const content = document.getElementById("bubble-content");
  if (!bubble || !content) return;

  const cleanText = (text || "").trim();
  if (!cleanText) {
    bubble.classList.remove("active");
    return;
  }

  // Clear previous timeout
  if (speechTimeout) {
    clearTimeout(speechTimeout);
    speechTimeout = null;
  }

  content.innerText = cleanText;
  bubble.classList.add("active");

  const durationMs = Math.max(3000, Math.round((durationSeconds || Math.max(3.2, cleanText.length / 13.0)) * 1000));
  speechTimeout = setTimeout(() => {
    bubble.classList.remove("active");
  }, durationMs);
}

function hideSpeechBubble() {
  const bubble = document.getElementById("speech-bubble");
  if (bubble) bubble.classList.remove("active");
  if (speechTimeout) {
    clearTimeout(speechTimeout);
    speechTimeout = null;
  }
}

// =============================================================================
// 6. 60 FPS RENDER LOOP
// =============================================================================

function animate(nowMs) {
  requestAnimationFrame(animate);

  const now = nowMs || performance.now();
  const rawDelta = clock ? clock.getDelta() : (now - lastAnimateTime) / 1000.0;
  lastAnimateTime = now;

  // Clamped clean delta between 4ms (240fps) and 50ms (20fps)
  const delta = Math.min(Math.max(rawDelta, 0.004), 0.05);

  // Smooth 3D model heading rotation
  if (avatarModel) {
    const headingLerp = Math.min(1.0, delta * 8.0);
    currentHeading += (targetHeading - currentHeading) * headingLerp;
    avatarModel.rotation.y = currentHeading;
  }

  // 1. Cleanly undo previous frame's procedural head offset if IK was active
  if (headBone && !_lastHeadQuat.equals(_identityQuat)) {
    _tempInvQuat.copy(_lastHeadQuat).invert();
    headBone.quaternion.multiply(_tempInvQuat);
    _lastHeadQuat.set(0, 0, 0, 1);
  }

  // 2. AnimationMixer Tick (evaluates pure, untainted animation keyframes)
  if (mixer) {
    mixer.update(delta);
  }

  // 3. Procedural Head IK (only if explicitly enabled)
  if (headIKEnabled) {
    updateProceduralLookAt(delta);
  }

  // 4. Render Frame
  renderer.render(scene, camera);

  // Measure FPS
  frameCount++;
  if (now - lastFrameTime >= 1000) {
    currentFps = Math.round((frameCount * 1000) / (now - lastFrameTime));
    frameCount = 0;
    lastFrameTime = now;
    const fpsBadge = document.getElementById("fps-counter");
    if (fpsBadge) {
      fpsBadge.innerText = `${currentFps} FPS`;
    }
  }
}

// =============================================================================
// 7. INPUT, DRAG & DROP AND DIAGNOSTIC PANEL
// =============================================================================

// Raycasting for accurate 3D model interaction
const raycaster = new THREE.Raycaster();
const mouseCoords = new THREE.Vector2();
let lastHoverCheckTime = 0;
let cachedHoverResult = false;

function isPointerOverAvatar(clientX, clientY) {
  if (!avatarModel || !camera || !renderer) return false;
  const rect = renderer.domElement.getBoundingClientRect();
  mouseCoords.x = ((clientX - rect.left) / rect.width) * 2 - 1;
  mouseCoords.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(mouseCoords, camera);
  const intersects = raycaster.intersectObjects(avatarModel.children, true);
  return intersects.length > 0;
}

function isPointerOverAvatarThrottled(clientX, clientY) {
  const now = performance.now();
  if (now - lastHoverCheckTime < 30) {
    return cachedHoverResult;
  }
  lastHoverCheckTime = now;
  cachedHoverResult = isPointerOverAvatar(clientX, clientY);
  return cachedHoverResult;
}

function setupMouseAndDragListeners(container) {
  let isPointerDownOnAvatar = false;
  let isDraggingAvatar = false;
  let dragStartScreenX = 0;
  let dragStartScreenY = 0;

  // RAF drag move throttler (smooth 60-144fps IPC without queue backlog)
  let pendingDragX = null;
  let pendingDragY = null;
  let dragRafPending = false;

  function dispatchDragMove() {
    dragRafPending = false;
    if (isDraggingAvatar && pyBridge && pyBridge.onDragMove && pendingDragX !== null) {
      pyBridge.onDragMove(pendingDragX, pendingDragY);
    }
  }

  container.addEventListener("mouseleave", () => {
    targetLookAt.x = 0;
    targetLookAt.y = 0;
  });

  // Track hover & dragging with high responsiveness
  window.addEventListener("pointermove", (e) => {
    if (isDraggingAvatar) {
      document.body.style.cursor = "grabbing";
      return;
    }

    if (isPointerDownOnAvatar) {
      const dist = Math.hypot(e.screenX - dragStartScreenX, e.screenY - dragStartScreenY);
      if (dist > 5) {
        isDraggingAvatar = true;
        document.body.style.cursor = "grabbing";
        console.log("[BrahmaSol 3D] Avatar drag started");
        if (pyBridge && pyBridge.onDragStart) {
          pyBridge.onDragStart(Math.round(e.screenX), Math.round(e.screenY));
        }
      }
      return;
    }

    // Throttled hover check for optimal CPU efficiency
    if (isPointerOverAvatarThrottled(e.clientX, e.clientY)) {
      document.body.style.cursor = "grab";
    } else {
      document.body.style.cursor = "default";
    }
  });

  window.addEventListener("pointerdown", (e) => {
    if (e.button === 0) { // Left click
      if (e.target.closest("#diagnostic-panel") || e.target.id === "dev-panel-toggle") {
        return;
      }
      if (isPointerOverAvatar(e.clientX, e.clientY)) {
        isPointerDownOnAvatar = true;
        isDraggingAvatar = false;
        dragStartScreenX = e.screenX;
        dragStartScreenY = e.screenY;
        document.body.style.cursor = "grab";
        try { container.setPointerCapture(e.pointerId); } catch (_) {}
      } else {
        isPointerDownOnAvatar = false;
        isDraggingAvatar = false;
      }
    }
  });

  window.addEventListener("pointerup", (e) => {
    if (e.button === 0 && isPointerDownOnAvatar) {
      try { container.releasePointerCapture(e.pointerId); } catch (_) {}
      if (isDraggingAvatar) {
        isDraggingAvatar = false;
        dragRafPending = false;
        document.body.style.cursor = "grab";
        console.log("[BrahmaSol 3D] Avatar drag finished");
        if (pyBridge && pyBridge.onDragEnd) {
          pyBridge.onDragEnd(Math.round(e.screenX), Math.round(e.screenY));
        }
      } else {
        // Immediate clean single click! Pointerdown was already confirmed on avatar.
        console.log("[BrahmaSol 3D] Direct hit on companion -> onAvatarClicked");
        if (pyBridge && pyBridge.onAvatarClicked) {
          pyBridge.onAvatarClicked();
        } else {
          playAnimation("Greeting", 0.15, false);
          showSpeechBubble("Hey! What can I help you build or explore today?", 3.5);
        }
      }
      isPointerDownOnAvatar = false;
    }
  });

  // Native context menu bridge
  window.addEventListener("contextmenu", (e) => {
    if (e.target.closest("#diagnostic-panel")) return;
    e.preventDefault();
    if (pyBridge && pyBridge.onContextMenu) {
      pyBridge.onContextMenu(Math.round(e.screenX), Math.round(e.screenY));
    }
  });

  // Native Drag and Drop perception
  container.addEventListener("dragover", (e) => {
    e.preventDefault();
    container.classList.add("drag-over");
    targetLookAt.x = (e.clientX / window.innerWidth) * 2 - 1;
    targetLookAt.y = -(e.clientY / window.innerHeight) * 2 + 1;
  });

  container.addEventListener("dragleave", (e) => {
    e.preventDefault();
    container.classList.remove("drag-over");
  });

  container.addEventListener("drop", (e) => {
    e.preventDefault();
    container.classList.remove("drag-over");

    const files = e.dataTransfer ? e.dataTransfer.files : [];
    if (files.length > 0) {
      const file = files[0];
      console.log("[BrahmaSol 3D] File dropped onto avatar:", file.name, file.size);
      
      playAnimation("Interact", 0.2, false);
      showSpeechBubble(`Inspecting "${file.name}"... let's see what's inside.`, 3.5);

      if (pyBridge && pyBridge.onFileDropped) {
        pyBridge.onFileDropped(file.name, file.size || 0);
      }
    }
  });

  // Hotkey F12 for Diagnostic Panel
  window.addEventListener("keydown", (e) => {
    if (e.key === "F12") {
      e.preventDefault();
      toggleDiagnosticPanel();
    }
  });
}

function setupDiagnosticPanel() {
  const toggleBtn = document.getElementById("dev-panel-toggle");
  toggleBtn.addEventListener("click", toggleDiagnosticPanel);

  document.getElementById("btn-play-clip").addEventListener("click", () => {
    const sel = document.getElementById("clip-select");
    if (sel && sel.value) {
      playAnimation(sel.value, 0.3, true);
    }
  });

  document.getElementById("btn-test-transition").addEventListener("click", () => {
    const target = document.getElementById("clip-transition-target");
    if (target && target.value) {
      playAnimation(target.value, 0.35, true);
    }
  });

  document.getElementById("btn-pause").addEventListener("click", () => {
    if (currentAction) currentAction.paused = true;
  });

  document.getElementById("btn-resume").addEventListener("click", () => {
    if (currentAction) currentAction.paused = false;
  });

  document.getElementById("btn-reset-idle").addEventListener("click", () => {
    playAnimation("Idle Subtle", 0.3, true);
  });

  const speedSlider = document.getElementById("speed-slider");
  speedSlider.addEventListener("input", (e) => {
    const val = parseFloat(e.target.value);
    document.getElementById("speed-val").innerText = `${val.toFixed(2)}x`;
    if (currentAction) currentAction.setEffectiveTimeScale(val);
  });

  document.getElementById("btn-test-speech").addEventListener("click", () => {
    playAnimation("Idle Talking", 0.25, false);
    showSpeechBubble("I am Brahma Sol. My body is an extension of my intelligence.", 4.0);
  });
}

function toggleDiagnosticPanel() {
  const panel = document.getElementById("diagnostic-panel");
  if (panel) {
    panel.classList.toggle("visible");
  }
}

function populateClipDropdowns() {
  const sel1 = document.getElementById("clip-select");
  const sel2 = document.getElementById("clip-transition-target");
  if (!sel1 || !sel2) return;

  sel1.innerHTML = "";
  sel2.innerHTML = "";

  allClips.forEach((clip) => {
    const opt1 = document.createElement("option");
    opt1.value = clip.name;
    opt1.innerText = `${clip.name} (${clip.duration.toFixed(2)}s)`;
    sel1.appendChild(opt1);

    const opt2 = document.createElement("option");
    opt2.value = clip.name;
    opt2.innerText = `${clip.name} (${clip.duration.toFixed(2)}s)`;
    sel2.appendChild(opt2);
  });

  sel1.value = "Idle Subtle";
  sel2.value = "Sitting Enter";
}

function onWindowResize() {
  if (!camera || !renderer) return;
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

// =============================================================================
// 8. QWEBCHANNEL & PYTHON INTEROP
// =============================================================================

function setupWebChannel() {
  if (typeof QWebChannel !== "undefined") {
    new QWebChannel(qt.webChannelTransport, (channel) => {
      pyBridge = channel.objects.pyBridge;
      console.log("[BrahmaSol 3D] QWebChannel connected to Python pyBridge.");
    });
  }
}

// Global API exposed to Python via QWebEngineView.runJavaScript
window.brahmaSolAPI = {
  playClip: (name, blendTime = 0.25, loop = true) => playAnimation(name, blendTime, loop),
  say: (text, duration = 3.5) => showSpeechBubble(text, duration),
  hideSpeech: () => hideSpeechBubble(),
  lookAt: (nx, ny) => {
    targetLookAt.x = nx;
    targetLookAt.y = ny;
  },
  setHeading: (yawRad, immediate = false) => {
    targetHeading = yawRad;
    if (immediate) currentHeading = yawRad;
  },
  getHeading: () => currentHeading,
  setHeadIKEnabled: (enabled) => {
    headIKEnabled = !!enabled;
    if (!enabled) {
      targetLookAt.x = 0;
      targetLookAt.y = 0;
      currentLookAt.x = 0;
      currentLookAt.y = 0;
      if (headBone && !_lastHeadQuat.equals(_identityQuat)) {
        _tempInvQuat.copy(_lastHeadQuat).invert();
        headBone.quaternion.multiply(_tempInvQuat);
        _lastHeadQuat.set(0, 0, 0, 1);
      }
    }
  },
  getFps: () => currentFps,
  getActiveClip: () => activeClipName,
  onDragFinished: () => {
    isDraggingAvatar = false;
    isPointerDownOnAvatar = false;
    document.body.style.cursor = "default";
  },
};

// Start on DOM ready
document.addEventListener("DOMContentLoaded", initStage);
