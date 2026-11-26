import { mountIcons } from "/icons.js";

const state = {
  filePath: null,
  spec: null,
  mode: "voxel2d",       // "voxel2d" | "voxel3d" | "frame2d"
  tool: "pencil",        // "pencil" | "eraser" | "repaint" | "eyedropper" | "box" | "bucket"
  zSlice: 0,
  selectedLayerIdx: 0,
  selectedValue: 2,
  selectedHex: "#e0ac69",
  mirrorX: false,
  yaw: 30,
  elevation: 30,
  frameIdx: 0,
  totalFrames: 4,
  playing: false,
  playTimer: null,
  fxOutline: true,
  fxBounce: false,
  fxGlint: false,
  aiDiff: false,
  boxStart: null,
  orbitDrag: null,
  lastOracleImg: null,
  undoStack: [],
  redoStack: [],
};

const canvas = document.getElementById("edit-canvas");
const ctx = canvas.getContext("2d");
const previewImg = document.getElementById("preview-img");

function snapshotUndo() {
  state.undoStack.push(JSON.stringify(state.spec));
  if (state.undoStack.length > 60) state.undoStack.shift();
  state.redoStack = [];
}

function getRenderPayload() {
  return {
    spec: state.spec,
    yaw: state.yaw,
    elevation: state.elevation,
    ppu: 2,
    width: 48,
    height: 48,
    style: state.fxOutline ? "ext_outline" : "lineless",
    pixel_overrides: state.spec?.pixel_overrides || {},
    frame_idx: state.frameIdx,
    total_frames: state.totalFrames,
    micro_fx: { bounce: state.fxBounce, glint: state.fxGlint },
  };
}

async function fetchProject() {
  const res = await fetch("/api/project");
  const data = await res.json();
  state.filePath = data.file_path;
  state.spec = data.spec;
  if (!state.spec.pixel_overrides) state.spec.pixel_overrides = {};
  document.getElementById("file-label").textContent = data.file_path || "untitled.vox.json";
  renderUI();
  await refreshOracle();
}

async function refreshOracle() {
  if (!state.spec) return;
  const res = await fetch("/api/render", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(getRenderPayload()),
  });
  const data = await res.json();
  if (data.image) {
    previewImg.src = data.image;
    const img = new Image();
    img.onload = () => {
      state.lastOracleImg = img;
      if (state.mode !== "voxel2d") drawViewport();
    };
    img.src = data.image;
  }
}

function renderUI() {
  if (!state.spec || !state.spec.layers) return;
  const list = document.getElementById("layer-list");
  list.innerHTML = "";
  let totalVoxels = 0;
  state.spec.layers.forEach((layer, idx) => {
    totalVoxels += (layer.voxels || []).length;
    const li = document.createElement("li");
    li.className = "layer-item" + (idx === state.selectedLayerIdx ? " selected" : "");
    const label = document.createElement("span");
    label.textContent = `${layer.id} (${layer.role})`;
    label.onclick = () => { state.selectedLayerIdx = idx; renderUI(); drawViewport(); };
    const controls = document.createElement("span");
    const visBtn = document.createElement("button");
    visBtn.textContent = layer.visible === false ? "off" : "on";
    visBtn.onclick = (e) => { e.stopPropagation(); snapshotUndo(); layer.visible = layer.visible === false; renderUI(); refreshOracle(); };
    const lockBtn = document.createElement("button");
    lockBtn.textContent = layer.locked ? "L" : "U";
    lockBtn.title = "Toggle Lock";
    lockBtn.onclick = (e) => { e.stopPropagation(); snapshotUndo(); layer.locked = !layer.locked; renderUI(); };
    controls.append(visBtn, lockBtn);
    li.append(label, controls);
    list.appendChild(li);
  });
  document.getElementById("status-count").textContent = `Voxels: ${totalVoxels}`;

  const swatchBox = document.getElementById("ramp-swatches");
  swatchBox.innerHTML = "";
  (state.spec.ramps || []).forEach((ramp, rIdx) => {
    (ramp.colors || []).forEach((col, sIdx) => {
      const val = rIdx * 16 + sIdx + 1;
      const btn = document.createElement("button");
      btn.className = "swatch" + (val === state.selectedValue ? " selected" : "");
      btn.style.background = col.startsWith("#") ? col : "#888888";
      btn.title = `${ramp.name}[${sIdx}]`;
      btn.onclick = () => {
        state.selectedValue = val;
        state.selectedHex = col.startsWith("#") ? col : "#e0ac69";
        renderUI();
      };
      swatchBox.appendChild(btn);
    });
  });

  drawViewport();
}

function drawViewport() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.imageSmoothingEnabled = false;

  if (state.mode === "voxel2d") {
    const grid = 16;
    const cell = canvas.width / grid;
    const half = grid / 2;
    ctx.strokeStyle = "#222733";
    for (let i = 0; i <= grid; i++) {
      ctx.beginPath(); ctx.moveTo(i * cell, 0); ctx.lineTo(i * cell, canvas.height); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, i * cell); ctx.lineTo(canvas.width, i * cell); ctx.stroke();
    }
    const layer = state.spec?.layers?.[state.selectedLayerIdx];
    if (!layer) return;
    for (const [x, y, z] of layer.voxels || []) {
      if (z === state.zSlice || z === state.zSlice - 1) {
        const gx = x + half;
        const gy = half - 1 - y;
        ctx.fillStyle = z === state.zSlice ? "#4fa4c4" : "rgba(79, 164, 196, 0.22)";
        ctx.fillRect(gx * cell + 1, gy * cell + 1, cell - 2, cell - 2);
      }
    }
    return;
  }

  // Both voxel3d and frame2d display the crisp integer-scaled oracle image
  if (state.lastOracleImg) {
    ctx.drawImage(state.lastOracleImg, 0, 0, canvas.width, canvas.height);
  }
  if (state.mode === "frame2d" && state.aiDiff) {
    const fkey = `frame_${state.frameIdx}`;
    const patch = state.spec?.pixel_overrides?.[fkey];
    const scale = canvas.width / 48;
    ctx.strokeStyle = "#ff4fd8";
    ctx.lineWidth = 1.5;
    for (const [px, py] of [...(patch?.set || []), ...(patch?.erase || [])]) {
      ctx.strokeRect(px * scale, py * scale, scale, scale);
    }
  }
}

function setVoxel(layer, x, y, z, val) {
  const coords = state.mirrorX ? [[x, y, z], [-x, y, z]] : [[x, y, z]];
  for (const [cx, cy, cz] of coords) {
    const idx = (layer.voxels || []).findIndex(([vx, vy, vz]) => vx === cx && vy === cy && vz === cz);
    if (val === 0) {
      if (idx >= 0) layer.voxels.splice(idx, 1);
    } else if (state.tool === "repaint") {
      if (idx >= 0) layer.voxels[idx][3] = val;
    } else {
      if (idx >= 0) layer.voxels[idx][3] = val;
      else layer.voxels.push([cx, cy, cz, val]);
    }
  }
}

function floodFillSlice(layer, startX, startY, z, targetVal, newVal) {
  if (targetVal === newVal) return;
  const map = new Map();
  for (const [vx, vy, vz, vv] of layer.voxels || []) {
    if (vz === z) map.set(`${vx},${vy}`, vv);
  }
  const queue = [[startX, startY]];
  const visited = new Set([`${startX},${startY}`]);
  while (queue.length) {
    const [cx, cy] = queue.shift();
    setVoxel(layer, cx, cy, z, newVal);
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nx = cx + dx, ny = cy + dy;
      if (nx < -8 || nx > 7 || ny < -8 || ny > 7) continue;
      const k = `${nx},${ny}`;
      if (visited.has(k)) continue;
      if ((map.get(k) || 0) === targetVal) {
        visited.add(k);
        queue.push([nx, ny]);
      }
    }
  }
}

async function handleCanvasClick(ev) {
  if (ev.button === 2) return; // RMB reserved for 3D orbit
  const rect = canvas.getBoundingClientRect();
  const lx = ev.clientX - rect.left;
  const ly = ev.clientY - rect.top;

  if (state.mode === "frame2d") {
    const px = Math.floor((lx / canvas.width) * 48);
    const py = Math.floor((ly / canvas.height) * 48);
    document.getElementById("status-cell").textContent = `2D Pixel: (${px}, ${py}) [frame_${state.frameIdx}]`;
    snapshotUndo();
    const fkey = `frame_${state.frameIdx}`;
    if (!state.spec.pixel_overrides[fkey]) state.spec.pixel_overrides[fkey] = { set: [], erase: [] };
    const patch = state.spec.pixel_overrides[fkey];
    patch.set = patch.set.filter(([x, y]) => !(x === px && y === py));
    patch.erase = patch.erase.filter(([x, y]) => !(x === px && y === py));
    if (state.tool === "eraser") patch.erase.push([px, py]);
    else patch.set.push([px, py, state.selectedHex]);
    await refreshOracle();
    return;
  }

  const layer = state.spec?.layers?.[state.selectedLayerIdx];
  if (!layer || layer.locked) return;

  if (state.mode === "voxel3d") {
    const px = Math.floor((lx / canvas.width) * 48);
    const py = Math.floor((ly / canvas.height) * 48);
    const res = await fetch("/api/pick", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spec: state.spec, px, py, yaw: state.yaw, elevation: state.elevation, ppu: 2, width: 48, height: 48 }),
    });
    const hit = await res.json();
    if (!hit.hit) return;
    document.getElementById("status-cell").textContent = `3D Hit: (${hit.coord.join(", ")})`;
    snapshotUndo();
    if (state.tool === "eraser") setVoxel(layer, hit.coord[0], hit.coord[1], hit.coord[2], 0);
    else if (state.tool === "repaint") setVoxel(layer, hit.coord[0], hit.coord[1], hit.coord[2], state.selectedValue);
    else setVoxel(layer, hit.place[0], hit.place[1], hit.place[2], state.selectedValue);
    renderUI();
    await refreshOracle();
    return;
  }

  // voxel2d Z-Slice mode
  const grid = 16;
  const cell = canvas.width / grid;
  const half = grid / 2;
  const x = Math.floor(lx / cell) - half;
  const y = half - 1 - Math.floor(ly / cell);
  const z = state.zSlice;
  document.getElementById("status-cell").textContent = `Cell: (${x}, ${y}, ${z})`;

  if (state.tool === "eyedropper") {
    const found = (layer.voxels || []).find(([vx, vy, vz]) => vx === x && vy === y && vz === z);
    if (found) { state.selectedValue = found[3]; renderUI(); }
    return;
  }
  if (state.tool === "box") {
    if (!state.boxStart) { state.boxStart = [x, y]; return; }
    snapshotUndo();
    const [x0, y0] = state.boxStart;
    for (let bx = Math.min(x0, x); bx <= Math.max(x0, x); bx++) {
      for (let by = Math.min(y0, y); by <= Math.max(y0, y); by++) {
        setVoxel(layer, bx, by, z, state.selectedValue);
      }
    }
    state.boxStart = null;
    renderUI();
    await refreshOracle();
    return;
  }
  if (state.tool === "bucket") {
    snapshotUndo();
    const cur = (layer.voxels || []).find(([vx, vy, vz]) => vx === x && vy === y && vz === z);
    floodFillSlice(layer, x, y, z, cur ? cur[3] : 0, state.selectedValue);
    renderUI();
    await refreshOracle();
    return;
  }

  snapshotUndo();
  setVoxel(layer, x, y, z, state.tool === "eraser" ? 0 : state.selectedValue);
  renderUI();
  await refreshOracle();
}

canvas.addEventListener("mousedown", (ev) => {
  if (ev.button === 2 && state.mode === "voxel3d") {
    state.orbitDrag = { x: ev.clientX, y: ev.clientY, yaw: state.yaw, elev: state.elevation };
    return;
  }
  handleCanvasClick(ev);
});
canvas.addEventListener("contextmenu", (e) => e.preventDefault());
window.addEventListener("mousemove", (ev) => {
  if (!state.orbitDrag) return;
  const dx = ev.clientX - state.orbitDrag.x;
  const dy = ev.clientY - state.orbitDrag.y;
  state.yaw = ((state.orbitDrag.yaw + dx) % 360 + 360) % 360;
  state.elevation = Math.max(0, Math.min(60, state.orbitDrag.elev + dy * 0.5));
  document.getElementById("yaw-label").textContent = `${Math.round(state.yaw)}°`;
  document.getElementById("elev-label").textContent = `${Math.round(state.elevation)}°`;
  refreshOracle();
});
window.addEventListener("mouseup", () => { state.orbitDrag = null; });

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    state.mode = tab.dataset.mode;
    drawViewport();
  });
});

document.querySelectorAll(".tool").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tool").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.tool = btn.dataset.tool;
    state.boxStart = null;
  });
});

document.getElementById("z-slider").addEventListener("input", (e) => {
  state.zSlice = Number(e.target.value);
  document.getElementById("z-label").textContent = String(state.zSlice);
  drawViewport();
});
document.getElementById("mirror-x").addEventListener("change", (e) => { state.mirrorX = e.target.checked; });
document.getElementById("ai-diff-toggle").addEventListener("change", (e) => { state.aiDiff = e.target.checked; drawViewport(); });
document.getElementById("yaw-slider").addEventListener("input", (e) => {
  state.yaw = Number(e.target.value);
  document.getElementById("yaw-label").textContent = `${state.yaw}°`;
  refreshOracle();
});
document.getElementById("elev-slider").addEventListener("input", (e) => {
  state.elevation = Number(e.target.value);
  document.getElementById("elev-label").textContent = `${state.elevation}°`;
  refreshOracle();
});
document.getElementById("fx-outline").addEventListener("change", (e) => { state.fxOutline = e.target.checked; refreshOracle(); });
document.getElementById("fx-bounce").addEventListener("change", (e) => { state.fxBounce = e.target.checked; refreshOracle(); });
document.getElementById("fx-glint").addEventListener("change", (e) => { state.fxGlint = e.target.checked; refreshOracle(); });
document.getElementById("frame-slider").addEventListener("input", (e) => {
  state.frameIdx = Number(e.target.value);
  document.getElementById("frame-label").textContent = String(state.frameIdx);
  refreshOracle();
});

document.getElementById("btn-play").addEventListener("click", () => {
  state.playing = !state.playing;
  if (state.playing) {
    state.playTimer = setInterval(() => {
      state.frameIdx = (state.frameIdx + 1) % state.totalFrames;
      document.getElementById("frame-slider").value = String(state.frameIdx);
      document.getElementById("frame-label").textContent = String(state.frameIdx);
      refreshOracle();
    }, 180);
  } else {
    clearInterval(state.playTimer);
  }
});

document.getElementById("btn-add-layer").addEventListener("click", () => {
  snapshotUndo();
  const n = state.spec.layers.length;
  state.spec.layers.push({ id: `layer_${n}`, role: "outfit", priority: n * 10, visible: true, locked: false, voxels: [] });
  state.selectedLayerIdx = n;
  renderUI();
});

document.getElementById("btn-add-ramp").addEventListener("click", async () => {
  const hex = document.getElementById("new-ramp-color").value;
  const res = await fetch("/api/ramp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ color: hex, steps: 4, name: `ramp_${state.spec.ramps.length}` }),
  });
  const data = await res.json();
  if (data.ramp) {
    snapshotUndo();
    state.spec.ramps.push(data.ramp);
    renderUI();
  }
});

document.getElementById("btn-undo").addEventListener("click", () => {
  if (!state.undoStack.length) return;
  state.redoStack.push(JSON.stringify(state.spec));
  state.spec = JSON.parse(state.undoStack.pop());
  renderUI();
  refreshOracle();
});
document.getElementById("btn-redo").addEventListener("click", () => {
  if (!state.redoStack.length) return;
  state.undoStack.push(JSON.stringify(state.spec));
  state.spec = JSON.parse(state.redoStack.pop());
  renderUI();
  refreshOracle();
});
document.getElementById("btn-save").addEventListener("click", async () => {
  await fetch("/api/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spec: state.spec, path: state.filePath || "studio_model.vox.json" }),
  });
});
document.getElementById("btn-export").addEventListener("click", async () => {
  const fmt = document.getElementById("export-fmt").value;
  const ext = fmt === "godot" ? "tres" : (fmt === "sheet" ? "png" : fmt);
  await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...getRenderPayload(), format: fmt, path: `studio_export.${ext}` }),
  });
});
document.getElementById("btn-copy-cli").addEventListener("click", () => {
  const cmd = `pixelai render ${state.filePath || "studio_model.vox.json"} -o out.png`;
  navigator.clipboard?.writeText(cmd);
});

window.addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    e.preventDefault();
    state.mode = state.mode === "voxel2d" ? "voxel3d" : "voxel2d";
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.mode === state.mode));
    drawViewport();
  } else if (e.key === "b" || e.key === "B") state.tool = "pencil";
  else if (e.key === "e" || e.key === "E") state.tool = "eraser";
  else if (e.key === "p" || e.key === "P") state.tool = "repaint";
  else if (e.key === "i" || e.key === "I") state.tool = "eyedropper";
  else if (e.key === "r" || e.key === "R") state.tool = "box";
  else if (e.key === "g" || e.key === "G") state.tool = "bucket";
});

mountIcons();
fetchProject();
