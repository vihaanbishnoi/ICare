/**
 * ICare Frontend — app.js
 * Development fixtures clearly labelled throughout.
 * All fixture data must be replaced with genuine /api/v1 responses before public release.
 * Person 2 supplies the backend. Person 4 supplies approved example clips.
 */

'use strict';

// =============================================================================
// DEVELOPMENT FIXTURES — NOT REAL INFERENCE OUTPUT
// These are labelled mock data used while the backend is not yet connected.
// Do NOT publish these as model results. Replace with genuine /api/v1 responses.
// =============================================================================
const FIXTURES = {
  fall: {
    _fixture_label: 'DEVELOPMENT FIXTURE — mock data, not real inference',
    duration: 15,
    expected_outcome: 'fall',
    // Predictions at ~0.75s intervals (20 predictions over 15s).
    // Pattern: low confidence during walking, rises sharply at fall (~6s), high briefly, then re-arms.
    predictions: [
      { t: 0.00, p: 0.03 }, { t: 0.75, p: 0.05 }, { t: 1.50, p: 0.04 },
      { t: 2.25, p: 0.07 }, { t: 3.00, p: 0.06 }, { t: 3.75, p: 0.08 },
      { t: 4.50, p: 0.11 }, { t: 5.25, p: 0.18 }, { t: 6.00, p: 0.42 },
      { t: 6.75, p: 0.95 }, // ← FALL DETECTED (≥ 0.50 threshold)
      { t: 7.50, p: 0.88 }, { t: 8.25, p: 0.76 }, { t: 9.00, p: 0.62 },
      { t: 9.75, p: 0.44 }, { t: 10.50, p: 0.28 }, // re-arm window (< 0.35 × 3)
      { t: 11.25, p: 0.22 }, { t: 12.00, p: 0.19 },
      { t: 12.75, p: 0.14 }, { t: 13.50, p: 0.09 }, { t: 14.25, p: 0.06 },
    ],
    incidents: [
      { detected_at_seconds: 6.75, confidence: 0.950, status: 'detected' }
    ],
  },
  normal: {
    _fixture_label: 'DEVELOPMENT FIXTURE — mock data, not real inference',
    duration: 15,
    expected_outcome: 'no_fall',
    // Predictions stay well below 0.50 threshold throughout normal walking.
    predictions: [
      { t: 0.00, p: 0.04 }, { t: 0.75, p: 0.06 }, { t: 1.50, p: 0.08 },
      { t: 2.25, p: 0.05 }, { t: 3.00, p: 0.09 }, { t: 3.75, p: 0.07 },
      { t: 4.50, p: 0.11 }, { t: 5.25, p: 0.13 }, { t: 6.00, p: 0.08 },
      { t: 6.75, p: 0.10 }, { t: 7.50, p: 0.07 }, { t: 8.25, p: 0.09 },
      { t: 9.00, p: 0.12 }, { t: 9.75, p: 0.08 }, { t: 10.50, p: 0.06 },
      { t: 11.25, p: 0.09 }, { t: 12.00, p: 0.07 },
      { t: 12.75, p: 0.08 }, { t: 13.50, p: 0.05 }, { t: 14.25, p: 0.04 },
    ],
    incidents: [],
  },
};

// =============================================================================
// HERO CANVAS — Animated particle network background
// =============================================================================
class HeroCanvas {
  constructor(canvasEl) {
    this.canvas = canvasEl;
    this.ctx = canvasEl.getContext('2d');
    this.particles = [];
    this.mouseX = -999;
    this.mouseY = -999;
    this.raf = null;
    this.maxDist = 130;
    this.numParticles = 70;
    this._init();
  }

  _init() {
    this._resize();
    window.addEventListener('resize', () => this._resize());
    document.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      this.mouseX = e.clientX - rect.left;
      this.mouseY = e.clientY - rect.top;
    });

    for (let i = 0; i < this.numParticles; i++) {
      this.particles.push({
        x: Math.random() * this.canvas.width,
        y: Math.random() * this.canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        r: Math.random() * 1.5 + 0.8,
      });
    }
    this._loop();
  }

  _resize() {
    const heroEl = document.getElementById('hero');
    this.canvas.width  = heroEl.offsetWidth;
    this.canvas.height = heroEl.offsetHeight;
  }

  _loop() {
    this._update();
    this._draw();
    this.raf = requestAnimationFrame(() => this._loop());
  }

  _update() {
    const W = this.canvas.width, H = this.canvas.height;
    this.particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0 || p.x > W) { p.vx *= -1; p.x = Math.max(0, Math.min(W, p.x)); }
      if (p.y < 0 || p.y > H) { p.vy *= -1; p.y = Math.max(0, Math.min(H, p.y)); }
    });
  }

  _draw() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    const ps = this.particles;
    for (let i = 0; i < ps.length; i++) {
      for (let j = i + 1; j < ps.length; j++) {
        const dx = ps[i].x - ps[j].x;
        const dy = ps[i].y - ps[j].y;
        const d  = Math.sqrt(dx * dx + dy * dy);
        if (d < this.maxDist) {
          const alpha = (1 - d / this.maxDist) * 0.22;
          ctx.strokeStyle = `rgba(88,166,255,${alpha})`;
          ctx.lineWidth = 0.6;
          ctx.beginPath();
          ctx.moveTo(ps[i].x, ps[i].y);
          ctx.lineTo(ps[j].x, ps[j].y);
          ctx.stroke();
        }
      }
    }

    ps.forEach(p => {
      const dx = p.x - this.mouseX;
      const dy = p.y - this.mouseY;
      const d  = Math.sqrt(dx * dx + dy * dy);
      const alpha = d < 150 ? 0.85 - d / 150 * 0.5 : 0.3;
      ctx.fillStyle = `rgba(88,166,255,${alpha})`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  destroy() {
    cancelAnimationFrame(this.raf);
  }
}

// =============================================================================
// SKELETON RENDERER — Procedural animated stick figure on canvas
// =============================================================================
class DemoRenderer {
  constructor(mode) {
    this.mode = mode; // 'fall' | 'normal'
    this.canvas = document.getElementById(`${mode}-canvas`);
    this.ctx = this.canvas.getContext('2d');
    this.duration = FIXTURES[mode === 'fall' ? 'fall' : 'normal'].duration;
    this.currentTime = 0;
    this.playing = false;
    this.startTime = null;
    this.raf = null;
    this._drawFrame(0);
  }

  play() {
    if (this.currentTime >= this.duration) this.currentTime = 0;
    this.playing = true;
    this.startTime = performance.now() - this.currentTime * 1000;
    this._loop();
  }

  pause() {
    this.playing = false;
    cancelAnimationFrame(this.raf);
  }

  seek(t) {
    this.currentTime = Math.max(0, Math.min(this.duration, t));
    if (!this.playing) this._drawFrame(this.currentTime);
    if (this.playing) this.startTime = performance.now() - this.currentTime * 1000;
  }

  _loop() {
    if (!this.playing) return;
    const elapsed = (performance.now() - this.startTime) / 1000;
    this.currentTime = Math.min(elapsed, this.duration);
    this._drawFrame(this.currentTime);
    this._syncUI();
    if (this.currentTime < this.duration) {
      this.raf = requestAnimationFrame(() => this._loop());
    } else {
      this.playing = false;
      this._syncUI();
      const playBtn = document.getElementById(`${this.mode}-play-btn`);
      if (playBtn) {
        document.getElementById(`${this.mode}-play-icon`).textContent = '⏹';
        document.getElementById(`${this.mode}-play-text`).textContent = 'Replay';
      }
    }
  }

  _syncUI() {
    const t = this.currentTime;
    const d = this.duration;
    const pct = d > 0 ? t / d : 0;

    // Progress bar
    const fill  = document.getElementById(`${this.mode}-progress`);
    const thumb = document.getElementById(`${this.mode}-thumb`);
    if (fill)  fill.style.width = (pct * 100) + '%';
    if (thumb) thumb.style.left = (pct * 100) + '%';

    // Time display
    const timeEl = document.getElementById(`${this.mode}-time`);
    if (timeEl) timeEl.textContent = `${this._fmt(t)} / ${this._fmt(d)}`;

    // Fall alert
    if (this.mode === 'fall') {
      const conf = this._getConf(t);
      const alert = document.getElementById('fall-alert');
      if (alert) alert.style.display = (conf >= 0.5) ? 'flex' : 'none';
    }

    // Chart playhead
    updateChartPlayhead(this.mode, t);
  }

  _fmt(s) {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${String(sec).padStart(2, '0')}`;
  }

  _getConf(t) {
    const preds = FIXTURES[this.mode === 'fall' ? 'fall' : 'normal'].predictions;
    if (t <= preds[0].t) return preds[0].p;
    if (t >= preds[preds.length - 1].t) return preds[preds.length - 1].p;
    for (let i = 0; i < preds.length - 1; i++) {
      if (t >= preds[i].t && t <= preds[i + 1].t) {
        const alpha = (t - preds[i].t) / (preds[i + 1].t - preds[i].t);
        return preds[i].p + alpha * (preds[i + 1].p - preds[i].p);
      }
    }
    return 0;
  }

  _drawFrame(t) {
    const ctx = this.ctx;
    const W = this.canvas.width;
    const H = this.canvas.height;

    // Background
    ctx.fillStyle = '#070c16';
    ctx.fillRect(0, 0, W, H);

    // Subtle grid
    ctx.strokeStyle = 'rgba(148,163,184,0.04)';
    ctx.lineWidth = 1;
    for (let x = 0; x < W; x += 40) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let y = 0; y < H; y += 40) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }

    // Floor line
    ctx.strokeStyle = 'rgba(148,163,184,0.15)';
    ctx.lineWidth = 1;
    ctx.setLineDash([8, 6]);
    ctx.beginPath();
    ctx.moveTo(0, H * 0.9);
    ctx.lineTo(W, H * 0.9);
    ctx.stroke();
    ctx.setLineDash([]);

    // Camera info
    ctx.fillStyle = 'rgba(34,211,238,0.7)';
    ctx.font = `500 12px 'JetBrains Mono', monospace`;
    const mm = String(Math.floor(t / 60)).padStart(2, '0');
    const ss = String(Math.floor(t % 60)).padStart(2, '0');
    const ms = String(Math.floor((t % 1) * 100)).padStart(2, '0');
    ctx.fillText(`${mm}:${ss}.${ms}`, 10, 22);
    ctx.textAlign = 'right';
    ctx.fillText('CAM-01 ●', W - 10, 22);
    ctx.textAlign = 'left';

    // Compute and draw figure
    const conf = this._getConf(t);
    const pose = this.mode === 'fall' ? this._getFallPose(t, W, H) : this._getNormalPose(t, W, H);
    this._drawFigure(ctx, pose, conf);
    this._drawBBox(ctx, pose, conf, H);
    this._drawConfBar(ctx, conf, W, H);
  }

  _getFallPose(t, W, H) {
    const floorY = H * 0.88;

    if (t < 5) {
      // Walking normally
      const walkCycle = t * Math.PI * 1.5;
      return {
        cx: W * 0.38 + Math.sin(t * 0.5) * 15,
        cy: floorY - H * 0.36,
        height: H * 0.7,
        tilt: Math.sin(walkCycle) * 0.04,
        lLeg: Math.sin(walkCycle) * 0.35,
        rLeg: -Math.sin(walkCycle) * 0.35,
        lArm: -Math.sin(walkCycle) * 0.45,
        rArm: Math.sin(walkCycle) * 0.45,
      };
    } else if (t < 7.2) {
      // Falling
      const p = (t - 5) / 2.2;
      const ep = p * p * (3 - 2 * p); // smoothstep
      const targetTilt = Math.PI * 0.48;
      return {
        cx: W * 0.38 + ep * W * 0.28,
        cy: floorY - H * 0.36 + ep * H * 0.18,
        height: H * 0.7,
        tilt: ep * targetTilt,
        lLeg: ep * 0.6 + Math.sin(t * 3) * 0.1 * (1 - ep),
        rLeg: -ep * 0.3,
        lArm: ep * Math.PI * 0.35,
        rArm: -ep * 0.2 + Math.random() * 0.05,
      };
    } else {
      // Lying on ground, slight settling
      return {
        cx: W * 0.66 + Math.sin((t - 7) * 0.4) * 3,
        cy: floorY - H * 0.08,
        height: H * 0.7,
        tilt: Math.PI * 0.48 + Math.sin((t - 7) * 0.3) * 0.03,
        lLeg: 0.4,
        rLeg: -0.15,
        lArm: 0.65,
        rArm: -0.1,
      };
    }
  }

  _getNormalPose(t, W, H) {
    const floorY = H * 0.88;
    const walkCycle = t * Math.PI * 1.4;
    const xOffset = ((t / 15) * W * 0.55);
    const xBase = W * 0.15 + xOffset;
    return {
      cx: xBase > W * 0.85 ? W * 0.85 : xBase,
      cy: floorY - H * 0.36,
      height: H * 0.7,
      tilt: Math.sin(walkCycle) * 0.03,
      lLeg: Math.sin(walkCycle) * 0.38,
      rLeg: -Math.sin(walkCycle) * 0.38,
      lArm: -Math.sin(walkCycle) * 0.45,
      rArm: Math.sin(walkCycle) * 0.45,
    };
  }

  _drawFigure(ctx, { cx, cy, height: H, tilt, lLeg, rLeg, lArm, rArm }, conf) {
    const sinT = Math.sin(tilt);
    const cosT = Math.cos(tilt);
    const spine = { x: sinT, y: -cosT };
    const perp  = { x: cosT, y: sinT };

    const torsoLen    = H * 0.27;
    const headR       = H * 0.08;
    const uArmL       = H * 0.18;
    const lArmL       = H * 0.15;
    const uLegL       = H * 0.25;
    const lLegL       = H * 0.23;
    const hipHalfW    = H * 0.065;
    const shoulderW   = H * 0.09;

    // Key anchor joints
    const hip      = { x: cx, y: cy };
    const shoulder = add(hip, scale(spine, torsoLen));
    const head     = add(shoulder, scale(spine, headR * 1.8));

    // Shoulder nodes
    const ls = add(shoulder, scale(perp, -shoulderW));
    const rs = add(shoulder, scale(perp,  shoulderW));

    // Arms
    const la = this._rot(spine, lArm);
    const ra = this._rot(spine, rArm);
    const le = add(ls, scale(la, uArmL));
    const re = add(rs, scale(ra, uArmL));
    const lw = add(le, scale(la, lArmL));
    const rw = add(re, scale(ra, lArmL));

    // Legs
    const legBase = { x: -spine.x, y: -spine.y };
    const lla = this._rot(legBase, lLeg);
    const rla = this._rot(legBase, rLeg);
    const lh = add(hip, scale(perp, -hipHalfW));
    const rh = add(hip, scale(perp,  hipHalfW));
    const lk = add(lh, scale(lla, uLegL));
    const rk = add(rh, scale(rla, uLegL));
    const lAnk = add(lk, scale(lla, lLegL));
    const rAnk = add(rk, scale(rla, lLegL));

    // Color based on confidence
    const hue = conf >= 0.5 ? 4 : (conf > 0.25 ? 38 : 213);
    const sat = '85%';
    const lit = conf >= 0.5 ? '63%' : (conf > 0.25 ? '60%' : '68%');
    const color = `hsl(${hue},${sat},${lit})`;

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.shadowColor = color;
    ctx.shadowBlur = 10;
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;

    // Bones
    const bones = [
      [hip, shoulder], [shoulder, head],
      [ls, le], [le, lw],
      [rs, re], [re, rw],
      [lh, lk], [lk, lAnk],
      [rh, rk], [rk, rAnk],
    ];
    bones.forEach(([a, b]) => {
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    });

    // Joints (dot)
    ctx.fillStyle = color;
    [hip, shoulder, ls, rs, le, re, lw, rw, lh, rh, lk, rk, lAnk, rAnk].forEach(j => {
      ctx.beginPath();
      ctx.arc(j.x, j.y, 4, 0, Math.PI * 2);
      ctx.fill();
    });

    // Head circle
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(head.x, head.y, headR, 0, Math.PI * 2);
    ctx.stroke();

    ctx.shadowBlur = 0;
  }

  _drawBBox(ctx, { cx, cy, height: H, tilt }, conf, canvasH) {
    const color = conf >= 0.5 ? 'rgba(248,113,113,0.7)' : 'rgba(34,211,238,0.4)';
    const w = H * 0.45;
    const h = H * 0.85;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(cx - w / 2, cy - h * 0.55, w, h);
    ctx.setLineDash([]);
    ctx.fillStyle = color;
    ctx.font = `500 10px 'JetBrains Mono', monospace`;
    ctx.fillText(`person  0.93`, cx - w / 2, cy - h * 0.55 - 5);
  }

  _drawConfBar(ctx, conf, W, H) {
    const bX = W - 135, bY = H - 44, bW = 120, bH = 10;
    ctx.fillStyle = 'rgba(13,17,23,0.8)';
    roundRect(ctx, bX - 8, bY - 22, bW + 16, bH + 30, 6);
    ctx.fill();

    ctx.fillStyle = 'rgba(139,148,158,0.6)';
    ctx.font = `500 10px 'JetBrains Mono', monospace`;
    ctx.fillText('P(Fall)', bX, bY - 6);
    ctx.textAlign = 'right';
    ctx.fillText(conf.toFixed(2), bX + bW, bY - 6);
    ctx.textAlign = 'left';

    ctx.fillStyle = 'rgba(33,38,45,0.9)';
    roundRect(ctx, bX, bY, bW, bH, 4);
    ctx.fill();

    const c = conf >= 0.5 ? '#f85149' : (conf > 0.3 ? '#d29922' : '#58a6ff');
    ctx.fillStyle = c;
    roundRect(ctx, bX, bY, bW * conf, bH, 4);
    ctx.fill();

    // Threshold tick
    ctx.strokeStyle = 'rgba(139,148,158,0.4)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(bX + bW * 0.5, bY - 2);
    ctx.lineTo(bX + bW * 0.5, bY + bH + 2);
    ctx.stroke();

    ctx.fillStyle = 'rgba(139,148,158,0.35)';
    ctx.font = `400 8px 'JetBrains Mono', monospace`;
    ctx.textAlign = 'center';
    ctx.fillText('0.5', bX + bW * 0.5, bY + bH + 12);
    ctx.textAlign = 'left';
  }

  _rot(v, angle) {
    return {
      x: v.x * Math.cos(angle) - v.y * Math.sin(angle),
      y: v.x * Math.sin(angle) + v.y * Math.cos(angle),
    };
  }
}

// Vector helpers
function add(a, b)      { return { x: a.x + b.x, y: a.y + b.y }; }
function scale(v, s)    { return { x: v.x * s,   y: v.y * s   }; }
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

// =============================================================================
// CONFIDENCE CHART — SVG confidence timeline
// =============================================================================
function drawChart(mode) {
  const svgId = `${mode}-chart`;
  const svg = document.getElementById(svgId);
  if (!svg) return;

  const preds = FIXTURES[mode === 'fall' ? 'fall' : 'normal'].predictions;
  const W = 600, H = 160;
  const padL = 28, padR = 12, padT = 12, padB = 28;
  const cW = W - padL - padR;
  const cH = H - padT - padB;
  const dur = FIXTURES[mode === 'fall' ? 'fall' : 'normal'].duration;

  const toX = t => padL + (t / dur) * cW;
  const toY = p => padT + (1 - p) * cH;

  let html = '';

  // Defs: gradient fills
  html += `<defs>
    <linearGradient id="grad-safe-${mode}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3fb950" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="#3fb950" stop-opacity="0.02"/>
    </linearGradient>
    <linearGradient id="grad-danger-${mode}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#f85149" stop-opacity="0.38"/>
      <stop offset="100%" stop-color="#f85149" stop-opacity="0.03"/>
    </linearGradient>
    <clipPath id="clip-above-${mode}">
      <rect x="${padL}" y="${padT}" width="${cW}" height="${toY(0.5) - padT}"/>
    </clipPath>
    <clipPath id="clip-below-${mode}">
      <rect x="${padL}" y="${toY(0.5)}" width="${cW}" height="${cH - (toY(0.5) - padT)}"/>
    </clipPath>
  </defs>`;

  // Grid lines
  [0, 0.25, 0.5, 0.75, 1.0].forEach(v => {
    const y = toY(v);
    const color = v === 0.5 ? 'rgba(248,81,73,0.35)' : 'rgba(139,148,158,0.08)';
    const w = v === 0.5 ? '1.5' : '1';
    html += `<line x1="${padL}" y1="${y}" x2="${padL + cW}" y2="${y}" stroke="${color}" stroke-width="${w}" stroke-dasharray="${v === 0.5 ? '4,3' : '0'}"/>`;
    html += `<text x="${padL - 4}" y="${y + 4}" text-anchor="end" fill="rgba(139,148,158,0.5)" font-size="9" font-family="'JetBrains Mono',monospace">${v.toFixed(2)}</text>`;
  });

  // Build path points
  const pts = preds.map(pr => ({ x: toX(pr.t), y: toY(pr.p) }));
  const lineD  = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const areaD  = lineD + ` L${pts[pts.length - 1].x.toFixed(1)},${toY(0)} L${padL},${toY(0)} Z`;

  // Area fill — safe zone (below 0.5)
  html += `<path d="${areaD}" fill="url(#grad-safe-${mode})" clip-path="url(#clip-below-${mode})"/>`;
  // Area fill — danger zone (above 0.5)
  html += `<path d="${areaD}" fill="url(#grad-danger-${mode})" clip-path="url(#clip-above-${mode})"/>`;
  // Line
  html += `<path d="${lineD}" fill="none" stroke="#58a6ff" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;

  // Dots at each prediction
  preds.forEach(pr => {
    const x = toX(pr.t);
    const y = toY(pr.p);
    const c = pr.p >= 0.5 ? '#f87171' : '#34d399';
    html += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5" fill="${c}" stroke="rgba(7,12,22,0.6)" stroke-width="1.5"/>`;
  });

  // Incident markers
  if (mode === 'fall') {
    FIXTURES.fall.incidents.forEach(inc => {
      const x = toX(inc.detected_at_seconds);
      html += `<line x1="${x}" y1="${padT}" x2="${x}" y2="${padT + cH}" stroke="rgba(248,113,113,0.5)" stroke-width="1.5" stroke-dasharray="4,3"/>`;
      html += `<polygon points="${x},${padT} ${x - 5},${padT + 10} ${x + 5},${padT + 10}" fill="#f87171"/>`;
      html += `<text x="${x + 5}" y="${padT + 10}" fill="#f87171" font-size="9" font-family="'JetBrains Mono',monospace">FALL</text>`;
    });
  }

  // Threshold label
  const thY = toY(0.5);
  html += `<text x="${padL + cW - 2}" y="${thY - 4}" text-anchor="end" fill="rgba(248,113,113,0.6)" font-size="9" font-family="'JetBrains Mono',monospace">threshold 0.50</text>`;

  // Playhead (starts hidden at t=0)
  html += `<line id="${mode}-playhead" x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + cH}" stroke="rgba(34,211,238,0.6)" stroke-width="1.5" display="none"/>`;

  svg.innerHTML = html;
}

function updateChartPlayhead(mode, t) {
  const playhead = document.getElementById(`${mode}-playhead`);
  if (!playhead) return;
  const dur  = FIXTURES[mode === 'fall' ? 'fall' : 'normal'].duration;
  const padL = 28, padR = 12, W = 600;
  const cW = W - padL - padR;
  const x = (padL + (t / dur) * cW).toFixed(1);
  playhead.setAttribute('x1', x);
  playhead.setAttribute('x2', x);
  playhead.setAttribute('display', 'block');
}

// =============================================================================
// DEMO CONTROLLERS — Tab switching, playback, seek
// =============================================================================
const renderers = {};
let activeTab = 'fall';

function initDemos() {
  renderers['fall']   = new DemoRenderer('fall');
  renderers['normal'] = new DemoRenderer('normal');
  drawChart('fall');
  drawChart('normal');
}

function switchTab(mode) {
  // Pause all
  Object.values(renderers).forEach(r => {
    r.pause();
  });
  // Update play buttons
  ['fall', 'normal'].forEach(m => {
    const icon = document.getElementById(`${m}-play-icon`);
    const text = document.getElementById(`${m}-play-text`);
    if (icon) icon.textContent = '▶';
    if (text) text.textContent = 'Play';
  });

  // Hide all panels, deactivate all tabs
  document.querySelectorAll('.demo-panel').forEach(p => p.classList.add('demo-panel--hidden'));
  document.querySelectorAll('.tab').forEach(t => {
    t.classList.remove('tab--active');
    t.setAttribute('aria-selected', 'false');
  });

  // Show selected
  const panel = document.getElementById(`panel-${mode}`);
  const tab   = document.getElementById(`tab-${mode}`);
  if (panel) { panel.classList.remove('demo-panel--hidden'); panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
  if (tab)   { tab.classList.add('tab--active'); tab.setAttribute('aria-selected', 'true'); }

  activeTab = mode;
}

function togglePlayback(mode) {
  const r = renderers[mode];
  if (!r) return;

  if (r.playing) {
    r.pause();
    document.getElementById(`${mode}-play-icon`).textContent = '▶';
    document.getElementById(`${mode}-play-text`).textContent = 'Play';
  } else {
    r.play();
    document.getElementById(`${mode}-play-icon`).textContent = '⏸';
    document.getElementById(`${mode}-play-text`).textContent = 'Pause';
  }
}

function seekDemo(mode, event) {
  const track = event.currentTarget;
  const rect = track.getBoundingClientRect();
  const pct  = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
  const dur  = FIXTURES[mode === 'fall' ? 'fall' : 'normal'].duration;
  renderers[mode].seek(pct * dur);
}

function navigateToDemo(mode) {
  const demoEl = document.getElementById('demo');
  demoEl.scrollIntoView({ behavior: 'smooth' });
  // Small delay for smooth scroll to finish
  setTimeout(() => switchTab(mode), 400);
}

// =============================================================================
// UPLOAD HANDLER — Stub that shows "backend not connected" state
// =============================================================================
function handleFileSelect(event) {
  const file = event.target.files[0];
  if (!file) return;

  // Validate file type client-side (server also validates content)
  if (!file.type.includes('mp4') && !file.name.toLowerCase().endsWith('.mp4')) {
    showUploadError('Only MP4 files are accepted.');
    return;
  }

  // Validate file size (50 MB)
  if (file.size > 50 * 1024 * 1024) {
    showUploadError(`File too large: ${(file.size / 1024 / 1024).toFixed(1)} MB. Maximum is 50 MB.`);
    return;
  }

  // Show job card in stub mode
  const statusEl = document.getElementById('upload-status');
  statusEl.style.display = 'block';
  document.getElementById('upload-filename').textContent = file.name;
  document.getElementById('upload-job-badge').textContent = 'queued';
  document.getElementById('upload-job-badge').className = 'job-badge job-badge--queued';
  document.getElementById('upload-progress-fill').style.width = '0%';
  document.getElementById('upload-pct').textContent = '0%';
  document.getElementById('upload-message').textContent = 'Connecting to backend…';

  // Animate to show "backend not connected" state
  let pct = 0;
  const badgeEl = document.getElementById('upload-job-badge');
  const msgEl   = document.getElementById('upload-message');
  const fillEl  = document.getElementById('upload-progress-fill');
  const pctEl   = document.getElementById('upload-pct');

  badgeEl.textContent = 'connecting';
  badgeEl.className = 'job-badge job-badge--running';

  const interval = setInterval(() => {
    pct += Math.random() * 8;
    if (pct >= 30) {
      clearInterval(interval);
      pct = 0;
      badgeEl.textContent = 'failed';
      badgeEl.className = 'job-badge job-badge--failed';
      msgEl.textContent = 'Error 503 — /api/v1/jobs/upload: backend not connected.';
      fillEl.style.width = '0%';
      pctEl.textContent = '';
    } else {
      fillEl.style.width = pct + '%';
      pctEl.textContent = Math.floor(pct) + '%';
    }
  }, 120);
}

function showUploadError(msg) {
  const statusEl = document.getElementById('upload-status');
  statusEl.style.display = 'block';
  document.getElementById('upload-filename').textContent = 'Error';
  document.getElementById('upload-job-badge').textContent = 'invalid';
  document.getElementById('upload-job-badge').className = 'job-badge job-badge--failed';
  document.getElementById('upload-progress-fill').style.width = '0%';
  document.getElementById('upload-pct').textContent = '';
  document.getElementById('upload-message').textContent = msg;
}

// Upload drag-and-drop
function initUploadZone() {
  const zone = document.getElementById('upload-zone');
  if (!zone) return;

  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) {
      // Simulate file input change
      const dt = new DataTransfer();
      dt.items.add(file);
      const input = document.getElementById('file-input');
      input.files = dt.files;
      handleFileSelect({ target: input });
    }
  });
}

// =============================================================================
// NAVIGATION
// =============================================================================
function initNav() {
  const hamburger = document.getElementById('nav-hamburger');
  const mobile    = document.getElementById('nav-mobile');

  hamburger.addEventListener('click', () => {
    const isOpen = mobile.classList.toggle('open');
    hamburger.setAttribute('aria-expanded', String(isOpen));
    mobile.setAttribute('aria-hidden', String(!isOpen));
  });

  // Scroll shadow
  window.addEventListener('scroll', () => {
    document.getElementById('nav').classList.toggle('scrolled', window.scrollY > 40);
  }, { passive: true });

  // Smooth anchor links
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', (e) => {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
        closeMobileMenu();
      }
    });
  });
}

function closeMobileMenu() {
  const mobile    = document.getElementById('nav-mobile');
  const hamburger = document.getElementById('nav-hamburger');
  mobile.classList.remove('open');
  mobile.setAttribute('aria-hidden', 'true');
  hamburger.setAttribute('aria-expanded', 'false');
}

// =============================================================================
// INTERSECTION OBSERVER — Scroll-in animations
// =============================================================================
function initScrollAnimations() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in-view');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  document.querySelectorAll('.metric-card, .pipeline-step, .limitation-card, .card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    observer.observe(el);
  });

  // CSS to trigger
  const style = document.createElement('style');
  style.textContent = '.in-view { opacity: 1 !important; transform: translateY(0) !important; }';
  document.head.appendChild(style);
}

// =============================================================================
// BOOT
// =============================================================================
document.addEventListener('DOMContentLoaded', () => {
  // Nav
  initNav();

  // Hero canvas
  const heroCanvas = document.getElementById('hero-canvas');
  if (heroCanvas) new HeroCanvas(heroCanvas);

  // Demo
  initDemos();
  initUploadZone();

  // Scroll animations
  initScrollAnimations();

  console.log(
    '%c ICare Frontend%c — Development Fixtures Active\n' +
    'Fixture data is mock. Connect /api/v1 for real inference.',
    'color:#22d3ee;font-weight:700;font-size:14px;',
    'color:#94a3b8;font-size:12px;',
  );
});
