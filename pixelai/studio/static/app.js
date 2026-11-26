import { mountIcons } from "/icons.js";

const state = {
  filePath: null,
  spec: null,
  mode: "voxel",
  tool: "pencil",
  zSlice: 0,
  selectedLayerIdx: 0,
  selectedValue: 2,
  mirrorX: false,
  yaw: 30,
  elevation: 30,
  frameIdx: 0,
  fxOutline: true,
  fxBounce: false,
  fxGlint: false,
  undoStack: [],
  redoStack: [],
};

const canvas = document.getElementById("edit-canvas");
const ctx = canvas.getContext("2d");
const previewImg = document.getElementById("preview-img");

function snapshotUndo() {
  state.undoStack.push(JSON.stringify(state.spec));
  if (state.undoStack.length > 50) state.undoStack.shift();
  state.redoStack = [];
}

async function fetchProject() {
  const res = await fetch("/api/project");
  const data = await res.json();
  state.filePath = data.file_path;
  state.spec = data.spec;
  document.getElementById("file-label").textContent = data.file_path || "untitled.vox.json";
  renderUI();
  await refreshOracle();
}

async function refreshOracle() {
  if (!state.spec) return;
  const res = await fetch("/api/render", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      spec: state.spec,
      yaw: state.yaw,
      elevation: state.elevation,
      ppu: 2,
      style: state.fxOutline ? "ext_outline" : "lineless",
      frame_idx: state.frameIdx,
      total_frames: 4,
      micro_fx: { bounce: state.fxBounce, glint: state.fxGlint },
    }),
  });
  const data = await res.json();
  if (data.image) previewImg.src = data.image;
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
    li.textContent = `${layer.id} (${layer.role})`;
    li.onclick = () => { state.selectedLayerIdx = idx; renderUI(); drawSlice(); };
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
      btn.onclick = () => { state.selectedValue = val; renderUI(); };
      swatchBox.appendChild(btn);
    });
  });

  drawSlice();
}

function drawSlice() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
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
  for (const [x, y, z, val] of layer.voxels || []) {
    if (z === state.zSlice || z === state.zSlice - 1) {
      const gx = x + half;
      const gy = half - 1 - y;
      ctx.fillStyle = z === state.zSlice ? "#4fa4c4" : "rgba(79, 164, 196, 0.22)";
      ctx.fillRect(gx * cell + 1, gy * cell + 1, cell - 2, cell - 2);
    }
  }
}

function paintAtEvent(ev) {
  const layer = state.spec?.layers?.[state.selectedLayerIdx];
  if (!layer || layer.locked) return;
  const rect = canvas.getBoundingClientRect();
  const grid = 16;
  const cell = canvas.width / grid;
  const half = grid / 2;
  const x = Math.floor((ev.clientX - rect.left) / cell) - half;
  const y = half - 1 - Math.floor((ev.clientY - rect.top) / cell);
  const z = state.zSlice;

  document.getElementById("status-cell").textContent = `Cell: (${x}, ${y}, ${z})`;
  snapshotUndo();

  const coords = state.mirrorX ? [[x, y, z], [-x, y, z]] : [[x, y, z]];
  for (const [cx, cy, cz] of coords) {
    layer.voxels = (layer.voxels || []).filter(([vx, vy, vz]) => !(vx === cx && vy === cy && vz === cz));
    if (state.tool === "pencil") {
      layer.voxels.push([cx, cy, cz, state.selectedValue]);
    }
  }
  renderUI();
  refreshOracle();
}

canvas.addEventListener("mousedown", paintAtEvent);

document.getElementById("z-slider").addEventListener("input", (e) => {
  state.zSlice = Number(e.target.value);
  document.getElementById("z-label").textContent = String(state.zSlice);
  drawSlice();
});
document.getElementById("mirror-x").addEventListener("change", (e) => { state.mirrorX = e.target.checked; });
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

document.querySelectorAll(".tool").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tool").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.tool = btn.dataset.tool;
  });
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
document.getElementById("btn-copy-cli").addEventListener("click", () => {
  const cmd = `pixelai render ${state.filePath || "studio_model.vox.json"} -o out.png`;
  navigator.clipboard?.writeText(cmd);
});

mountIcons();
fetchProject();
