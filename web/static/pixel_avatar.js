/**
 * StableAgent OS — Pixel Agent Avatar v5
 *
 * Canvas-based pixel-art character with 2D room navigation.
 * Black-haired girl (Q版) moves between stations, performs task-animated actions.
 *
 * Architecture:
 *   Room (background) → Character (sprite) → Animation System → Event System
 */
// ============================================================================
// 像素画引擎 — 绘制 16×16 角色 Sprite 到 Canvas
// ============================================================================

const SPRITE_SIZE = 16;
const SCALE = 4;

// ---- 调色板 ----
const C = {
  SKIN:     '#fce4dc',
  SKIN_SHD: '#e8c8b8',
  SKIN_DRK: '#d4a894',
  HAIR:     '#1a1a2e',
  HAIR_LT:  '#2d2d44',
  HAIR_TIP: '#3d3d54',
  DRESS:    '#1c1c28',
  DRESS_LT: '#2a2a3c',
  SHOE:     '#0d0d18',
  WHITE:    '#ffffff',
  EYE:      '#16213e',
  EYE_LT:   '#4a6fa5',
  BLUSH:    '#f0b0b0',
  MOUTH:    '#d47878',
  PAPER:    '#fafaf0',
  BOOK:     '#8b4513',
  BOOK_PG:  '#f5deb3',
  DESK:     '#6b4226',
  SHELF:    '#8b6914',
  FLOOR:    '#d4a853',
  FLOOR2:   '#c49a43',
  WALL:     '#f5efe6',
  WALL_SHD: '#e8e0d5',
  WINDOW:   '#a8d8ea',
  WINDOW2:  '#c8e8fa',
  SPARKLE:  '#ffd700',
  RED:      '#ff3b30',
  GREEN:    '#30d158',
};

// ============================================================================
// 角色帧定义 — 每个状态有多帧动画
// 16×16 网格，每像素用 palette key 表示，'.' 表示透明
// ============================================================================

// --- IDLE (站立, 2帧呼吸) ---
const FRAMES_IDLE = [
  // 帧0: 正常站立
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS.....',
    '...SllSllS.....',
    '...SSS.SSS.....',
    '...SbbSb.S.....',
    '....S..SS......',
    '...KKKKK.......',
    '...K.K.K.......',
    '...K..K........',
    '...............',
  ],
  // 帧1: 微呼吸 (衣服略鼓)
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDDD..',
    '...SSSSSSSS....',
    '...SllSllS.....',
    '...SSSS.SS.....',
    '...SbbSS.S.....',
    '....SS.SS......',
    '...KKKKK.......',
    '...K.K.K.......',
    '...K..K........',
    '...............',
  ],
];

// --- WALK (4帧行走) ---
const FRAMES_WALK = [
  // 帧0: 迈左腿
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS.....',
    '...SllSllS.....',
    '...SSS.SSS.....',
    '...SbbSbS......',
    '....SSS........',
    '...KK..K.......',
    '...KK..K.......',
    '...K...........',
    '...............',
  ],
  // 帧1: 过渡
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS.....',
    '...SllSllS.....',
    '...SSSS.S......',
    '...SbbSb.......',
    '....S..........',
    '...KKKK........',
    '...K..K........',
    '...............',
    '...............',
  ],
  // 帧2: 迈右腿 (镜像)
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS.....',
    '...SllSllS.....',
    '....SSS.SS.....',
    '....SbbSbS.....',
    '....SSS........',
    '...K..KK.......',
    '...K..KK.......',
    '........K......',
    '...............',
  ],
  // 帧3: 过渡
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS.....',
    '.....S.SSSS....',
    '.....SbbSb.....',
    '......S........',
    '......S........',
    '...KKKK........',
    '...K..K........',
    '...............',
    '...............',
  ],
];

// --- WORK (伏案工作, 2帧) ---
const FRAMES_WORK = [
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSS......WW.',
    '...SSS.....WWW.',
    '...SllS...WWW..',
    '...SSSS..WWW...',
    '..SSbbS.WWW....',
    '..KK..K........',
    '..K...K........',
    '...............',
    '...............',
  ],
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSS......WW.',
    '...SSS.....WWW.',
    '...SllS...WWW..',
    '...SSSS..WWW...',
    '..SSbbS.WWW....',
    '..K..K.........',
    '..K...K........',
    '...............',
    '...............',
  ],
];

// --- THINK (托腮思考, 2帧) ---
const FRAMES_THINK = [
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS.....',
    '..SSllSllS.....',
    '..SSSSSSSS.....',
    '....SbbSbS.....',
    '.....SSSS......',
    '...KKKKK.......',
    '...K.K.K.......',
    '...K...........',
    '...............',
  ],
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS.....',
    '.SSSllSllS.....',
    '.SSSSSSSS......',
    '...SbbSbS......',
    '....SSSS.......',
    '...KKKKK.......',
    '...K.K.K.......',
    '...K...........',
    '...............',
  ],
];

// --- SEARCH (翻书/查找, 2帧) ---
const FRAMES_SEARCH = [
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS.....',
    '...SllSllS.....',
    '.SSSSSSS...BB..',
    '.SSbbSbS..BB...',
    '..SSSSS..BB....',
    '.KKKKK.........',
    '.K.K.K.........',
    '...............',
    '...............',
  ],
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS.....',
    '...SllSllS.....',
    '..SSSSSS..BB...',
    '..SSbbSb..BB...',
    '..SSSS...BB....',
    '.KKKK..........',
    '.K.K...........',
    '...............',
    '...............',
  ],
];

// --- CELEBRATE (庆祝跳跃, 2帧) ---
const FRAMES_CELEBRATE = [
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS..**.',
    '..SSllSllS..**.',
    '..SSSSSSS......',
    '...SbbSbS......',
    '....SSS........',
    '...KK.........',
    '...K..........',
    '...............',
    '.....K..K......',
  ],
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS..**.',
    '.SSllSllS...**.',
    '.SSSSSSS.......',
    '..SbbSbS.......',
    '...SSS.........',
    '..KK...........',
    '..K............',
    '..K..K.........',
    '...............',
  ],
];

// --- SKILL 系列 (V4) ---
const FRAMES_SKILL_LEARN = [ // 读书
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS..BB.',
    '...SllSllS..BB.',
    '...SSSSSS..BB..',
    '...SbbSSS.BB...',
    '....SSSS.......',
    '...KK.K........',
    '...K..K........',
    '...............',
    '...............',
  ],
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS..BB.',
    '...SllSllS..BB.',
    '...SSSSSS..BB..',
    '..SbbSS...BB...',
    '..SSS..........',
    '..K.K..........',
    '..K..K.........',
    '...............',
    '...............',
  ],
];

const FRAMES_SKILL_PATCH = [ // 伏案写字
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSS......PP.',
    '...SSS.....PPP.',
    '...SllS...PPP..',
    '...SSSS..PPP...',
    '..SSbbS.PPP....',
    '..KK..K........',
    '..K...K........',
    '...............',
    '...............',
  ],
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSS......PP.',
    '...SSS.....PPP.',
    '...SllS...PPP..',
    '...SSSS..PPP...',
    '..SSbbS.PPP....',
    '..K..K.........',
    '..K...K........',
    '...............',
    '...............',
  ],
];

const FRAMES_SKILL_VALID = [ // 举手验证
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS..GG.',
    '...SllSllS..GG.',
    '.SSSSSSSS......',
    '.SSbbSbS.......',
    '..SSSS.........',
    '.KKKK..........',
    '.K..K..........',
    '...............',
    '...............',
  ],
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS..GG.',
    '...SllSllS..GG.',
    '.SSSSSSS.......',
    '.SSbbSbS.......',
    '.SSSS..........',
    '.KKK...........',
    '.K..K..........',
    '...............',
    '...............',
  ],
];

const FRAMES_SKILL_REJECT = [ // 摇头
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '..dDDDDDDdD....',
    '..dDDDDDDdD....',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS..RR.',
    '...SllSllS..RR.',
    '...SSSSSS......',
    '...SbbSbS......',
    '....SSSS.......',
    '...KKKK........',
    '...K..K........',
    '...............',
    '...............',
  ],
  [
    '......DDDDDD....',
    '.....DDDDDDDD..',
    '.....DDDDDDDD..',
    '....dDDDDDDdD..',
    '....dDDDDDDdD..',
    '.....DDDDDDDDD.',
    '.....DDDDDDDDD.',
    '.....SSSSSSS.RR',
    '.....SllSllS.RR',
    '.....SSSSSS....',
    '.....SbbSbS....',
    '......SSSS.....',
    '.....KKKK......',
    '.....K..K......',
    '...............',
    '...............',
  ],
];

const FRAMES_SKILL_ACCEPT = [ // 点头+金光
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS..**.',
    '...SllSllS..**.',
    '..SSSSSS.......',
    '..SbbSbS.......',
    '...SSS.........',
    '...KKK.........',
    '...K..K........',
    '.....K.........',
    '...............',
  ],
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '...SSSSSSS..**.',
    '...SllSllS..**.',
    '.SSSSSS........',
    '.SSbbSbS.......',
    '.SSSS..........',
    '.KKK...........',
    '.K..K..........',
    '.K.............',
    '...............',
  ],
];

const FRAMES_SKILL_EXPORT = [ // 举起纸张
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '..SSSSSSSS..PP.',
    '..SllSllSS.PPP.',
    '..SSSSSSS.PPP..',
    '...SbbSbS.PP...',
    '....SSSS.......',
    '...KKKK........',
    '...K..K........',
    '...............',
    '...............',
  ],
  [
    '....DDDDDD......',
    '...DDDDDDDD....',
    '...DDDDDDDD....',
    '...dDDDDDDdD...',
    '...dDDDDDDdD...',
    '...DDDDDDDDD...',
    '...DDDDDDDDD...',
    '.SSSSSSSS..PP..',
    '.SllSllSS.PPP..',
    '.SSSSSSS.PPP...',
    '..SbbSbS.PP....',
    '...SSSS........',
    '..KKKK.........',
    '..K..K.........',
    '...............',
    '...............',
  ],
];

// ---- 帧索引 ----
const ANIMATIONS = {
  idle:      { frames: FRAMES_IDLE,      speed: 800, loop: true },
  walking:   { frames: FRAMES_WALK,      speed: 150, loop: true },
  working:   { frames: FRAMES_WORK,      speed: 400, loop: true },
  thinking:  { frames: FRAMES_THINK,     speed: 500, loop: true },
  searching: { frames: FRAMES_SEARCH,    speed: 350, loop: true },
  celebrate: { frames: FRAMES_CELEBRATE, speed: 300, loop: true },
  skill_learning: { frames: FRAMES_SKILL_LEARN, speed: 500, loop: true },
  skill_patching: { frames: FRAMES_SKILL_PATCH, speed: 350, loop: true },
  skill_validating:{ frames: FRAMES_SKILL_VALID, speed: 400, loop: true },
  skill_rejected: { frames: FRAMES_SKILL_REJECT, speed: 250, loop: true },
  skill_accepted: { frames: FRAMES_SKILL_ACCEPT, speed: 400, loop: true },
  skill_exported: { frames: FRAMES_SKILL_EXPORT, speed: 400, loop: true },
};

// ---- 房间物体绘制 ----
function drawBackground(ctx, w, h, t) {
  // 墙壁
  ctx.fillStyle = C.WALL;
  ctx.fillRect(0, 0, w, h * 0.55);
  // 墙壁纹理
  ctx.fillStyle = C.WALL_SHD;
  for (let x = 0; x < w; x += 32) {
    ctx.fillRect(x, 0, 1, h * 0.55);
  }
  for (let y = 0; y < h * 0.55; y += 32) {
    ctx.fillRect(0, y, w, 1);
  }

  // 窗户 (左上)
  const wx = 12, wy = 16, ww = 40, wh = 36;
  ctx.fillStyle = C.WINDOW;
  ctx.fillRect(wx, wy, ww, wh);
  ctx.strokeStyle = '#b8956a';
  ctx.lineWidth = 2;
  ctx.strokeRect(wx, wy, ww, wh);
  ctx.beginPath();
  ctx.moveTo(wx + ww/2, wy);
  ctx.lineTo(wx + ww/2, wy + wh);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(wx, wy + wh/2);
  ctx.lineTo(wx + ww, wy + wh/2);
  ctx.stroke();
  // 窗外光
  ctx.fillStyle = C.WINDOW2;
  ctx.fillRect(wx+1, wy+1, ww/2-1, wh/2-1);

  // 地板
  ctx.fillStyle = C.FLOOR;
  ctx.fillRect(0, h * 0.55, w, h * 0.45);
  // 地板条纹
  for (let x = 0; x < w; x += 48) {
    ctx.fillStyle = x % 96 === 0 ? C.FLOOR2 : C.FLOOR;
    ctx.fillRect(x, h * 0.55, 48, h * 0.45);
  }

  // 书架 (左侧)
  const sx = 8, sy = h * 0.35, sw = 36, sh = h * 0.35;
  ctx.fillStyle = C.SHELF;
  ctx.fillRect(sx, sy, sw, sh);
  ctx.strokeStyle = '#6b4c1e';
  ctx.lineWidth = 1;
  ctx.strokeRect(sx, sy, sw, sh);
  // 书架隔板
  for (let by = sy + sh/3; by < sy + sh; by += sh/3) {
    ctx.beginPath();
    ctx.moveTo(sx, by);
    ctx.lineTo(sx + sw, by);
    ctx.stroke();
  }
  // 书架上的书
  const bookColors = ['#e74c3c','#3498db','#2ecc71','#f39c12','#9b59b6'];
  for (let bi = 0; bi < 3; bi++) {
    for (let bj = 0; bj < 3; bj++) {
      ctx.fillStyle = bookColors[(bi*3+bj) % bookColors.length];
      ctx.fillRect(sx + 4 + bj * 10, sy + 4 + bi * (sh/3), 7, sh/3 - 8);
    }
  }

  // 书桌 (右侧)
  const dx = w * 0.48, dy = h * 0.55, dw = w * 0.5, dh = 3;
  ctx.fillStyle = C.DESK;
  ctx.fillRect(dx, dy, dw, dh);
  // 桌腿
  ctx.fillRect(dx + 4, dy + dh, 3, 16);
  ctx.fillRect(dx + dw - 7, dy + dh, 3, 16);
  // 桌上的东西
  ctx.fillStyle = '#aaa';
  ctx.fillRect(dx + 10, dy - 4, 8, 4);  // 小物件
  ctx.fillStyle = '#ddd';
  ctx.fillRect(dx + 24, dy - 6, 14, 6); // 纸张

  // 地上装饰
  ctx.fillStyle = C.WALL_SHD;
  ctx.fillRect(w * 0.6, h * 0.55 + 2, 12, 1);
  ctx.fillRect(w * 0.7, h * 0.55 + 2, 14, 1);
}

// ---- 角色绘制 ----
function drawSprite(ctx, frame, x, y, flip) {
  const sz = SPRITE_SIZE;
  const sc = SCALE;
  ctx.save();
  const cx = x - sz * sc / 2;

  if (flip) {
    ctx.translate(x + sz * sc / 2, 0);
    ctx.scale(-1, 1);
    ctx.translate(-(x + sz * sc / 2), 0);
  }

  for (let row = 0; row < sz; row++) {
    for (let col = 0; col < sz; col++) {
      const ch = frame[row][col];
      if (ch === '.') continue;
      const color = C[ch] || ch;
      ctx.fillStyle = color;
      ctx.fillRect(
        cx + col * sc,
        y - sz * sc + row * sc,
        sc, sc
      );
    }
  }

  ctx.restore();
}

// ---- 浮动粒子效果 ----
function drawParticles(ctx, x, y, t, type) {
  if (type === 'sparkle') {
    for (let i = 0; i < 3; i++) {
      const px = x - 16 + Math.sin(t/400 + i*2) * 20 + i * 16;
      const py = y - 40 + Math.cos(t/300 + i*3) * 12;
      const alpha = 0.5 + Math.sin(t/200 + i) * 0.5;
      ctx.fillStyle = `rgba(255,215,0,${alpha})`;
      ctx.beginPath();
      ctx.arc(px, py, 2, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  if (type === 'red_x') {
    for (let i = 0; i < 2; i++) {
      const px = x + (i === 0 ? -14 : 14) + Math.sin(t/200) * 3;
      const py = y - 48 + i * 8;
      ctx.strokeStyle = C.RED;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(px-3, py-3); ctx.lineTo(px+3, py+3);
      ctx.moveTo(px+3, py-3); ctx.lineTo(px-3, py+3);
      ctx.stroke();
    }
  }
  if (type === 'check') {
    const gx = x + 12, gy = y - 48;
    ctx.strokeStyle = C.GREEN;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(gx-4, gy); ctx.lineTo(gx, gy+4); ctx.lineTo(gx+6, gy-4);
    ctx.stroke();
  }
}

// ---- 影子 ----
function drawShadow(ctx, x, y) {
  ctx.fillStyle = 'rgba(0,0,0,0.12)';
  ctx.beginPath();
  ctx.ellipse(x, y + 4, 14, 4, 0, 0, Math.PI * 2);
  ctx.fill();
}

// ============================================================================
// 主引擎
// ============================================================================
const PixelAgent = {
  canvas: null,
  ctx: null,
  animFrame: 0,
  lastTime: 0,
  charX: 0,
  charY: 0,
  targetX: 0,
  targetY: 0,
  state: 'idle',
  flip: false,
  particleType: null,
  timer: 0,

  // 房间各"站点"坐标
  STATIONS: {
    center:   { x: 0.5, y: 0.65 },
    desk:     { x: 0.65, y: 0.62 },
    shelf:    { x: 0.15, y: 0.58 },
    window:   { x: 0.12, y: 0.28 },
    door:     { x: 0.9, y: 0.68 },
  },

  init() {
    this.canvas = document.getElementById('agent-canvas');
    if (!this.canvas) return;

    this.ctx = this.canvas.getContext('2d');
    this.resize();

    const st = this.STATIONS.center;
    this.charX = this.canvas.width * st.x;
    this.charY = this.canvas.height * st.y;
    this.targetX = this.charX;
    this.targetY = this.charY;

    window.addEventListener('resize', () => this.resize());
    this.lastTime = performance.now();
    this.loop(this.lastTime);
  },

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = Math.max(rect.width, 180);
    this.canvas.height = Math.max(rect.height, 200);
    // 重新校准位置
    const st = this.STATIONS[this._currentStation] || this.STATIONS.center;
    this.targetX = this.canvas.width * st.x;
    this.targetY = this.canvas.height * st.y;
  },

  goTo(station) {
    if (!this.STATIONS[station]) {
      station = 'center';
    }
    this._currentStation = station;
    const st = this.STATIONS[station];
    this.targetX = this.canvas.width * st.x;
    this.targetY = this.canvas.height * st.y;
  },

  play(state, particle) {
    if (ANIMATIONS[state]) {
      this.state = state;
      this.particleType = particle || null;
      this.timer = 0;
    }
  },

  _framesFor(state) {
    const a = ANIMATIONS[state];
    return a ? a.frames : ANIMATIONS.idle.frames;
  },

  _speedFor(state) {
    const a = ANIMATIONS[state];
    return a ? a.speed : 800;
  },

  loop(time) {
    const dt = time - this.lastTime;
    this.lastTime = time;
    this.timer += dt;
    const speed = this._speedFor(this.state);

    // 帧动画
    const frames = this._framesFor(this.state);
    if (this.timer >= speed) {
      this.timer = 0;
      this.animFrame = (this.animFrame + 1) % frames.length;
    }

    // 移动（只有 walking 状态时实际移动；其他状态切换中间态）
    const dx = this.targetX - this.charX;
    const dy = this.targetY - this.charY;
    const dist = Math.sqrt(dx*dx + dy*dy);

    if (dist > 3) {
      const step = 1.2;
      this.charX += (dx / dist) * step;
      this.charY += (dy / dist) * step;
      // 到达后切换状态
      if (Math.abs(dx) < 2 && Math.abs(dy) < 2) {
        this.charX = this.targetX;
        this.charY = this.targetY;
      }
      // 方向翻转
      if (Math.abs(dx) > 1) this.flip = dx < 0;
    }

    // 渲染
    const { ctx, canvas: c } = this;
    ctx.clearRect(0, 0, c.width, c.height);
    drawBackground(ctx, c.width, c.height, time);
    drawShadow(ctx, this.charX, this.charY);

    // 粒子
    if (this.particleType) {
      drawParticles(ctx, this.charX, this.charY, time, this.particleType);
    }

    // 角色
    const f = frames[this.animFrame];
    drawSprite(ctx, f, this.charX, this.charY, this.flip);

    requestAnimationFrame(t => this.loop(t));
  },
};

// ============================================================================
// 事件桥接 — Dashboard 调用
// ============================================================================

const EVENT_TO_ANIM = {
  // 基础
  'workflow:started':   { state: 'thinking',  station: 'center', particle: null },
  'memory:retrieval':   { state: 'searching', station: 'shelf',  particle: null },
  'memory:retrieving':  { state: 'searching', station: 'shelf',  particle: null },
  'memory:retrieved':   { state: 'working',   station: 'desk',   particle: null },
  'rag:searched':       { state: 'working',   station: 'desk',   particle: null },
  'workflow:planned':   { state: 'thinking',  station: 'window', particle: null },
  'execute:completed':  { state: 'working',   station: 'desk',   particle: null },
  'eval:completed':     { state: 'thinking',  station: 'desk',   particle: 'sparkle' },
  'workflow:completed': { state: 'celebrate', station: 'center', particle: 'sparkle' },
  'workflow:init':      { state: 'thinking',  station: 'center', particle: null },

  // V3
  'budget:allocated':    { state: 'thinking',  station: 'desk',    particle: null },
  'context:built':       { state: 'idle',      station: 'center',  particle: null },
  'approval:required':   { state: 'idle',      station: 'center',  particle: null },
  'approval:pending':    { state: 'idle',      station: 'center',  particle: null },
  'workflow:paused':     { state: 'idle',      station: 'center',  particle: null },
  'workflow:resumed':    { state: 'working',   station: 'desk',    particle: null },
  'workflow:failed':     { state: 'idle',      station: 'center',  particle: 'red_x' },
  'workflow:cancelled':  { state: 'idle',      station: 'center',  particle: null },

  // V4 SkillOpt
  'skillopt.epoch_started':         { state: 'skill_learning',  station: 'shelf',   particle: null },
  'skillopt.rollouts_collected':    { state: 'skill_learning',  station: 'desk',    particle: null },
  'skillopt.failures_analyzed':     { state: 'skill_learning',  station: 'desk',    particle: 'red_x' },
  'skillopt.successes_analyzed':    { state: 'skill_learning',  station: 'desk',    particle: 'check' },
  'skillopt.patch_merged':          { state: 'skill_patching',  station: 'desk',    particle: null },
  'skillopt.patch_ranked':          { state: 'skill_patching',  station: 'desk',    particle: null },
  'skillopt.candidate_created':     { state: 'skill_patching',  station: 'desk',    particle: null },
  'skillopt.validation_passed':     { state: 'skill_accepted',  station: 'center',  particle: 'sparkle' },
  'skillopt.validation_failed':     { state: 'skill_rejected',  station: 'center',  particle: 'red_x' },
  'skillopt.rejected_buffer_updated': { state: 'skill_rejected', station: 'center', particle: 'red_x' },
  'skillopt.slow_update_created':   { state: 'skill_learning',  station: 'shelf',   particle: null },
  'skillopt.best_skill_exported':   { state: 'skill_exported',  station: 'center',  particle: 'sparkle' },
};

const STATE_LABELS = {
  idle: '待命中...', thinking: '思考中...', searching: '搜索中...',
  working: '工作中...', celebrate: '全部完成！',
  skill_learning: '技能学习中...', skill_patching: '修改技能中...',
  skill_validating: '验证中...', skill_rejected: '未通过验证',
  skill_accepted: '验证通过！', skill_exported: '已导出！',
};

function updateAvatar(eventType) {
  const anim = EVENT_TO_ANIM[eventType];
  if (!anim) {
    PixelAgent.play('idle', null);
    PixelAgent.goTo('center');
    updateLabel('idle');
    return;
  }
  PixelAgent.goTo(anim.station);
  PixelAgent.play(anim.state, anim.particle);
  updateLabel(anim.state);
}

function updateLabel(state) {
  const label = document.getElementById('robot-status-label');
  if (label) label.textContent = STATE_LABELS[state] || '工作中...';
}

function resetAvatar() {
  PixelAgent.play('idle', null);
  PixelAgent.goTo('center');
  updateLabel('idle');
}

// ---- 初始化 ----
document.addEventListener('DOMContentLoaded', () => {
  PixelAgent.init();
});

// ============================================================================
// V5: 新的事件到状态映射（用于 /runs/{run_id} per-run 页面）
// ============================================================================

const V5_AVATAR_STATES = {
  'listening': 'thinking',
  'thinking': 'thinking',
  'calculating': 'thinking',
  'reading_notes': 'searching',
  'searching_books': 'searching',
  'safety_check': 'idle',
  'waiting_approval': 'idle',
  'working': 'working',
  'grading': 'working',
  'writing_rule': 'skill_patching',
  'examining': 'skill_validating',
  'archiving': 'skill_exported',
  'sweating': 'idle',
  'celebrating': 'celebrate',
  'idle': 'idle',
};

const V5_STATE_LABELS = {
  listening: '聆听中...',
  thinking: '思考中...',
  calculating: '算盘中...',
  reading_notes: '查阅记忆...',
  searching_books: '搜索知识库...',
  safety_check: '安全检查...',
  waiting_approval: '等待审批...',
  working: '工作中...',
  grading: '评分中...',
  writing_rule: '编写规则...',
  examining: '考试中...',
  archiving: '归档中...',
  sweating: '出错了...',
  celebrating: '庆祝中！',
  idle: '待命中...',
};

/**
 * V5: 按 avatar_state 名直接设置像素机器人状态。
 *
 * 将新的 avatar_state（如 'thinking'、'working'、'searching'）
 * 映射到 PixelAgent 已知的动画状态并播放。
 *
 * @param {string} avatarState - 头像状态名（如 'thinking'、'working'）。
 */
window.updateAvatarByState = function (avatarState) {
  const mappedState = V5_AVATAR_STATES[avatarState] || 'idle';
  const label = V5_STATE_LABELS[avatarState] || avatarState;

  // 使用已有的 PixelAgent API 播放动画
  if (typeof PixelAgent !== 'undefined' && PixelAgent.play) {
    PixelAgent.play(mappedState, null);
  }

  // 更新状态标签
  const labelEl = document.getElementById('robot-status-label');
  if (labelEl) {
    labelEl.textContent = label;
  }
};
