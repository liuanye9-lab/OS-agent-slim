/**
 * StableAgent OS V5.6 — Canvas 语义角色动画
 * 13 语义场景 + idle，每个 300x400 像素。
 */

/** @type {string} */
let currentScene = 'idle';

/** @type {boolean} */
let isAnimating = false;

/** @type {number | null} */
let animFrameId = null;

/** @type {number} */
let animTick = 0;

/**
 * 场景 → canvas 尺寸映射
 * 每个场景都是 300x400
 */
const SCENE_SIZE = { w: 300, h: 400 };

// ---------------------------------------------------------------------------
// 13 语义场景映射 —— 头像状态 → 场景/道具/标签
// 每个场景包含：scene 场景名、prop 道具标识、label_zh/label_en 双语标签
// 风格：克制、低饱和、玻璃拟态
// ---------------------------------------------------------------------------

/** @type {Object<string, {scene: string, prop: string, label_zh: string, label_en: string}>} */
const AVATAR_SCENE_MAP = {
    /** desk — 接收任务卡片 */
    listening:      { scene: 'desk',             prop: 'task_card',       label_zh: '正在接收任务',               label_en: 'Receiving task' },
    /** thinking_board — 放大镜审视需求 */
    thinking:       { scene: 'thinking_board',   prop: 'magnifier',       label_zh: '正在理解你的需求',           label_en: 'Understanding your intent' },
    /** memory_wall — 翻阅记忆卡片 */
    reading_notes:  { scene: 'memory_wall',      prop: 'memory_cards',    label_zh: '正在找以前的经验',           label_en: 'Retrieving prior memory' },
    /** library — 书架资料检索 */
    searching_books:{ scene: 'library',          prop: 'bookshelf',       label_zh: '正在查找项目资料',           label_en: 'Searching project knowledge' },
    /** budget_panel — 算盘计算成本 */
    calculating:    { scene: 'budget_panel',     prop: 'abacus',          label_zh: '正在计算 token 成本',        label_en: 'Estimating token budget' },
    /** map_table — 路线图规划 */
    planning:       { scene: 'map_table',         prop: 'route_map',       label_zh: '正在规划执行步骤',           label_en: 'Planning execution steps' },
    /** tool_bench — 扳手调用工具 */
    tooling:        { scene: 'tool_bench',       prop: 'wrench',           label_zh: '正在调用工具',               label_en: 'Calling a tool' },
    /** checkpoint — 安全头盔检查 */
    safety_check:   { scene: 'checkpoint',       prop: 'helmet',           label_zh: '正在做安全检查',             label_en: 'Running safety check' },
    /** approval_gate — 红牌等待确认 */
    waiting_approval:{ scene: 'approval_gate',    prop: 'red_card',         label_zh: '等待你确认',                 label_en: 'Waiting for approval' },
    /** exam_table — 评分表评估结果 */
    grading:        { scene: 'exam_table',       prop: 'score_sheet',      label_zh: '正在评估结果',               label_en: 'Evaluating output' },
    /** skill_book — 笔记本总结经验 */
    learning:       { scene: 'skill_book',       prop: 'notebook',         label_zh: '正在总结经验',               label_en: 'Learning from this run' },
    /** archive_cabinet — 归档 best_skill.md */
    archiving:      { scene: 'archive_cabinet',  prop: 'best_skill_file',  label_zh: '正在更新 best_skill.md',     label_en: 'Updating best_skill.md' },
    /** delivery_desk — 完成盖章 */
    done:           { scene: 'delivery_desk',    prop: 'done_stamp',       label_zh: '任务完成',                   label_en: 'Task completed' },
    /** error_board — 警告标识失败记录 */
    failed:         { scene: 'error_board',      prop: 'warning_sign',     label_zh: '任务失败，正在记录原因',     label_en: 'Task failed, recording reason' },
};

/**
 * 7 个场景的绘制函数
 * 每个函数接收 (ctx, w, h, tick)
 */
const SCENE_DRAWERS = {

    /**
     * 记忆墙 — 笔记墙 + 翻卡片手势
     * 触发: memory_retrieval
     */
    memory_wall: function(ctx, w, h, tick) {
        const cx = w / 2, cy = h / 2;

        // 背景墙
        ctx.fillStyle = '#f5f0e8';
        ctx.fillRect(0, 0, w, h);

        // 软木板纹理
        ctx.fillStyle = '#e8dcc8';
        for (let i = 0; i < 100; i++) {
            const bx = (i * 73) % w;
            const by = (i * 47) % h;
            ctx.fillStyle = `rgba(200,180,150,${0.03 + (i % 3) * 0.02})`;
            ctx.fillRect(bx, by, 3, 2);
        }

        // 图钉
        const pinPositions = [
            { x: 45, y: 40 }, { x: 120, y: 35 }, { x: 200, y: 45 },
            { x: 70, y: 135 }, { x: 160, y: 130 }, { x: 240, y: 140 },
        ];
        pinPositions.forEach(p => {
            ctx.fillStyle = '#cc4444';
            ctx.beginPath();
            ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#ff6666';
            ctx.beginPath();
            ctx.arc(p.x - 1, p.y - 1, 2, 0, Math.PI * 2);
            ctx.fill();
        });

        // 卡片
        const cards = [
            { x: 30, y: 50, color: '#fffbe6', text: '记\n忆\nA', rot: -5 },
            { x: 100, y: 45, color: '#fff0f0', text: '记\n忆\nB', rot: 3 },
            { x: 180, y: 55, color: '#f0f5ff', text: '记\n忆\nC', rot: -2 },
            { x: 45, y: 145, color: '#f5fff0', text: '记\n忆\nD', rot: 4 },
            { x: 130, y: 140, color: '#fff5f5', text: '记\n忆\nE', rot: -3 },
            { x: 215, y: 150, color: '#f0fff5', text: '记\n忆\nF', rot: 1 },
        ];

        cards.forEach((card, i) => {
            ctx.save();
            ctx.translate(card.x + 30, card.y + 40);
            ctx.rotate((card.rot + (i === 2 ? Math.sin(tick * 0.05) * 3 : 0)) * Math.PI / 180);
            ctx.fillStyle = card.color;
            roundRect(ctx, -30, -40, 60, 80, 6);
            ctx.fill();
            ctx.strokeStyle = 'rgba(0,0,0,0.1)';
            ctx.lineWidth = 1;
            ctx.stroke();
            ctx.fillStyle = '#555';
            ctx.font = 'bold 13px sans-serif';
            ctx.textAlign = 'center';
            const lines = card.text.split('\n');
            lines.forEach((line, li) => {
                ctx.fillText(line, 0, -10 + li * 18);
            });
            ctx.restore();
        });

        // 翻卡片手势 — 一只手在卡片3上
        const handCard = cards[2];
        const handX = handCard.x + 30 + Math.sin(tick * 0.05) * 8;
        const handY = handCard.y + 40 - 30 + Math.sin(tick * 0.05) * 5;
        drawHand(ctx, handX, handY, tick);

        // 选中高亮 — 3 条记忆被选中
        ctx.strokeStyle = 'rgba(52,199,89,0.7)';
        ctx.lineWidth = 3;
        ctx.setLineDash([4, 4]);
        [0, 2, 4].forEach(ci => {
            const c = cards[ci];
            ctx.save();
            ctx.translate(c.x + 30, c.y + 40);
            ctx.rotate(c.rot * Math.PI / 180);
            ctx.strokeRect(-33, -43, 66, 86);
            ctx.restore();
        });
        ctx.setLineDash([]);

        // 标题
        ctx.fillStyle = '#444';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('记忆墙', cx, h - 15);
    },

    /**
     * 书架 — 书架 + 取书动作
     * 触发: rag_retrieval
     */
    bookshelf: function(ctx, w, h, tick) {
        const cx = w / 2, cy = h / 2;

        // 背景
        ctx.fillStyle = '#faf5ed';
        ctx.fillRect(0, 0, w, h);

        // 书架框架
        ctx.fillStyle = '#8B6914';
        ctx.fillRect(20, 220, w - 40, 12); // 底板
        ctx.fillRect(20, 140, w - 40, 8);  // 中层板
        ctx.fillRect(20, 60, w - 40, 8);   // 顶板

        // 侧板
        ctx.fillStyle = '#6B4914';
        ctx.fillRect(20, 50, 8, h - 100);
        ctx.fillRect(w - 28, 50, 8, h - 100);

        // 书本
        const shelfY = 72;
        const books = [
            { x: 38, color: '#e74c3c', h: 60 }, { x: 63, color: '#3498db', h: 65 },
            { x: 88, color: '#2ecc71', h: 55 }, { x: 113, color: '#f39c12', h: 62 },
            { x: 138, color: '#9b59b6', h: 58 }, { x: 163, color: '#1abc9c', h: 64 },
            { x: 188, color: '#e67e22', h: 56 }, { x: 213, color: '#2980b9', h: 61 },
        ];

        books.forEach((book, i) => {
            ctx.fillStyle = book.color;
            ctx.fillRect(book.x, shelfY, 20, book.h);

            // 书脊文字
            ctx.fillStyle = '#fff';
            ctx.font = '8px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('R' + (i + 1), book.x + 10, shelfY + book.h / 2 + 3);
        });

        // 被取出的书
        const pulledBookIdx = Math.floor((tick * 0.3) % books.length);
        const pb = books[pulledBookIdx];
        const pullX = pb.x + 30;
        const pullY = shelfY - 20 - Math.abs(Math.sin(tick * 0.08)) * 30;
        ctx.fillStyle = pb.color;
        ctx.fillRect(pullX, pullY, 20, pb.h);
        ctx.fillStyle = '#fff';
        ctx.font = '8px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('R' + (pulledBookIdx + 1), pullX + 10, pullY + pb.h / 2 + 3);

        // 取书的手
        drawHand(ctx, pullX + 10, pullY + pb.h / 2, tick);

        // 标题
        ctx.fillStyle = '#444';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('知识书架', cx, h - 15);
    },

    /**
     * 算盘/仪表盘 — 拨打算盘
     * 触发: context_budget
     */
    calculator: function(ctx, w, h, tick) {
        const cx = w / 2, cy = h / 2;

        // 背景
        ctx.fillStyle = '#f8f6f0';
        ctx.fillRect(0, 0, w, h);

        // 算盘框架
        ctx.fillStyle = '#6B4914';
        roundRect(ctx, 40, 70, w - 80, 180, 12);
        ctx.fill();

        // 算盘横梁
        ctx.fillStyle = '#8B6914';
        ctx.fillRect(40, 155, w - 80, 10);

        // 算盘档（竖杆）
        ctx.fillStyle = '#a08060';
        for (let rod = 0; rod < 5; rod++) {
            const rx = 65 + rod * 42;
            ctx.fillRect(rx - 2, 85, 4, 150);
        }

        // 算珠 — 上档（每档 2 颗）和下档（每档 5 颗）
        const beadPositions = [];
        for (let rod = 0; rod < 5; rod++) {
            const rx = 65 + rod * 42;
            // 上档 2 颗
            beadPositions.push({ x: rx, y: 100 + Math.sin(tick * 0.04 + rod) * 8, r: 9, color: '#e8d5b0' });
            beadPositions.push({ x: rx, y: 118 + Math.sin(tick * 0.04 + rod + 1) * 8, r: 9, color: '#e8d5b0' });
            // 下档 5 颗
            for (let b = 0; b < 5; b++) {
                beadPositions.push({ x: rx, y: 172 + b * 14 + Math.sin(tick * 0.04 + rod + b) * 4, r: 8, color: '#f0e8d0' });
            }
        }

        beadPositions.forEach(bp => {
            ctx.fillStyle = bp.color;
            ctx.beginPath();
            ctx.arc(bp.x, bp.y, bp.r, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = 'rgba(0,0,0,0.15)';
            ctx.lineWidth = 1;
            ctx.stroke();
        });

        // Token 仪表盘（右下角）
        const gaugeX = w - 80, gaugeY = 280, gaugeR = 40;
        ctx.beginPath();
        ctx.arc(gaugeX, gaugeY, gaugeR, Math.PI, 0);
        ctx.strokeStyle = '#ddd';
        ctx.lineWidth = 8;
        ctx.stroke();

        const pct = 0.3 + Math.sin(tick * 0.03) * 0.2;
        ctx.beginPath();
        ctx.arc(gaugeX, gaugeY, gaugeR, Math.PI, Math.PI + Math.PI * pct);
        ctx.strokeStyle = pct > 0.6 ? '#ff9f0a' : '#0071e3';
        ctx.lineWidth = 8;
        ctx.stroke();

        ctx.fillStyle = '#444';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('预算算盘', cx, h - 15);
    },

    /**
     * 地图/路线图 — 画线规划
     * 触发: planning
     */
    map_table: function(ctx, w, h, tick) {
        const cx = w / 2, cy = h / 2;

        // 背景 — 桌面
        ctx.fillStyle = '#f6f4ef';
        ctx.fillRect(0, 0, w, h);

        // 地图底图
        ctx.fillStyle = '#e8f0e8';
        roundRect(ctx, 25, 30, w - 50, 180, 10);
        ctx.fill();
        ctx.strokeStyle = 'rgba(0,0,0,0.1)';
        ctx.lineWidth = 1;
        ctx.stroke();

        // 网格
        ctx.strokeStyle = 'rgba(0,0,0,0.04)';
        ctx.lineWidth = 0.5;
        for (let gx = 35; gx < w - 25; gx += 25) {
            ctx.beginPath();
            ctx.moveTo(gx, 40);
            ctx.lineTo(gx, 200);
            ctx.stroke();
        }
        for (let gy = 40; gy < 210; gy += 20) {
            ctx.beginPath();
            ctx.moveTo(35, gy);
            ctx.lineTo(w - 25, gy);
            ctx.stroke();
        }

        // 节点
        const nodes = [
            { x: 60, y: 170, label: 'A', color: '#0071e3' },
            { x: 150, y: 100, label: 'B', color: '#0071e3' },
            { x: 180, y: 60, label: 'C', color: '#34c759' },
            { x: 240, y: 120, label: 'D', color: '#ff9f0a' },
            { x: 200, y: 170, label: 'E', color: '#34c759' },
        ];

        nodes.forEach(n => {
            ctx.fillStyle = n.color;
            ctx.beginPath();
            ctx.arc(n.x, n.y, 8, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 9px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(n.label, n.x, n.y);
        });

        // 路线 — 逐段绘制动画
        const progress = (tick * 0.5) % nodes.length;
        ctx.strokeStyle = 'rgba(0,113,227,0.6)';
        ctx.lineWidth = 3;
        ctx.setLineDash([6, 3]);
        ctx.beginPath();
        for (let i = 0; i < Math.min(nodes.length, Math.ceil(progress) + 1); i++) {
            if (i === 0) ctx.moveTo(nodes[i].x, nodes[i].y);
            else ctx.lineTo(nodes[i].x, nodes[i].y);
        }
        ctx.stroke();
        ctx.setLineDash([]);

        // 铅笔在画
        const lastNode = nodes[Math.min(Math.floor(progress), nodes.length - 1)];
        if (lastNode) {
            drawPencil(ctx, lastNode.x + 25, lastNode.y - 35, tick);
        }

        // 桌面上的便签
        ctx.fillStyle = '#fffbe6';
        ctx.fillRect(40, 240, 80, 60);
        ctx.strokeStyle = 'rgba(0,0,0,0.1)';
        ctx.strokeRect(40, 240, 80, 60);
        ctx.fillStyle = '#555';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('步骤 1→2→3', 48, 265);
        ctx.fillText('预计 800 tokens', 48, 285);

        ctx.fillStyle = '#444';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('路线规划台', cx, h - 15);
    },

    /**
     * 工具台 — 扳手连接线
     * 触发: tool_call
     */
    tool_bench: function(ctx, w, h, tick) {
        const cx = w / 2, cy = h / 2;

        // 背景 — 工作台
        ctx.fillStyle = '#f4f1eb';
        ctx.fillRect(0, 0, w, h);

        // 工具台面
        ctx.fillStyle = '#d4c5a9';
        ctx.fillRect(20, 200, w - 40, 60);
        ctx.fillStyle = '#c4b599';
        ctx.fillRect(20, 200, w - 40, 4);

        // 工具
        const tools = [
            { x: 55, y: 170, type: 'wrench' },
            { x: 130, y: 165, type: 'screwdriver' },
            { x: 205, y: 172, type: 'hammer' },
            { x: 270, y: 168, type: 'pliers' },
        ];

        tools.forEach((tool, i) => {
            ctx.fillStyle = '#555';
            ctx.font = '28px sans-serif';
            ctx.textAlign = 'center';
            const icons = { wrench: '🔧', screwdriver: '🪛', hammer: '🔨', pliers: '🔧' };
            ctx.fillText(icons[tool.type], tool.x, tool.y);

            // 连接线 — 当前激活的工具
            if (i === Math.floor(tick * 0.3) % tools.length) {
                ctx.strokeStyle = 'rgba(0,113,227,0.6)';
                ctx.lineWidth = 2;
                ctx.setLineDash([3, 2]);
                ctx.beginPath();
                ctx.moveTo(tool.x, tool.y - 15);
                ctx.lineTo(cx, 100);
                ctx.stroke();
                ctx.setLineDash([]);

                // 激活光晕
                ctx.fillStyle = 'rgba(0,113,227,0.15)';
                ctx.beginPath();
                ctx.arc(tool.x, tool.y - 5, 22, 0, Math.PI * 2);
                ctx.fill();
            }
        });

        // 中央处理节点
        ctx.fillStyle = '#0071e3';
        ctx.beginPath();
        ctx.arc(cx, 90, 20, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 18px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('⚙', cx, 90);

        const pulse = Math.sin(tick * 0.1) * 0.3 + 0.3;
        ctx.fillStyle = `rgba(0,113,227,${pulse})`;
        ctx.beginPath();
        ctx.arc(cx, 90, 30, 0, Math.PI * 2);
        ctx.fill();

        // 标题
        ctx.textBaseline = 'alphabetic';
        ctx.fillStyle = '#444';
        ctx.font = 'bold 14px sans-serif';
        ctx.fillText('工具调用台', cx, h - 15);
    },

    /**
     * 考试台 — 批改试卷
     * 触发: evaluation, skill_validation
     */
    exam_desk: function(ctx, w, h, tick) {
        const cx = w / 2, cy = h / 2;

        // 背景
        ctx.fillStyle = '#fafaf8';
        ctx.fillRect(0, 0, w, h);

        // 桌面
        ctx.fillStyle = '#e8e0d0';
        ctx.fillRect(30, 260, w - 60, 50);

        // 试卷
        ctx.fillStyle = '#fff';
        ctx.fillRect(50, 50, w - 100, 200);
        ctx.strokeStyle = '#ddd';
        ctx.lineWidth = 1;
        ctx.strokeRect(50, 50, w - 100, 200);

        // 试卷横线
        ctx.strokeStyle = '#e8e8e8';
        ctx.lineWidth = 1;
        for (let ly = 80; ly < 230; ly += 18) {
            ctx.beginPath();
            ctx.moveTo(65, ly);
            ctx.lineTo(w - 65, ly);
            ctx.stroke();
        }

        // 批改标记 — 红勾和叉
        const marks = [
            { x: 70, y: 85, type: 'check' },
            { x: 70, y: 103, type: 'check' },
            { x: 70, y: 121, type: 'cross' },
            { x: 70, y: 139, type: 'check' },
            { x: 70, y: 157, type: 'check' },
        ];

        marks.forEach((mark, i) => {
            if (i * 0.5 > tick * 0.02) return; // 逐条出现
            if (mark.type === 'check') {
                ctx.strokeStyle = '#34c759';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(mark.x, mark.y + 6);
                ctx.lineTo(mark.x + 5, mark.y + 12);
                ctx.lineTo(mark.x + 14, mark.y);
                ctx.stroke();
            } else {
                ctx.strokeStyle = '#ff3b30';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(mark.x + 1, mark.y + 1);
                ctx.lineTo(mark.x + 12, mark.y + 13);
                ctx.moveTo(mark.x + 12, mark.y + 1);
                ctx.lineTo(mark.x + 1, mark.y + 13);
                ctx.stroke();
            }
        });

        // 分数
        if (tick > 60) {
            ctx.fillStyle = '#34c759';
            ctx.font = 'bold 20px sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText('85/100', w - 70, 240);
        }

        // 红笔
        const penX = w - 100 + Math.sin(tick * 0.05) * 15;
        const penY = 120;
        ctx.strokeStyle = '#ff3b30';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(penX, penY - 20);
        ctx.lineTo(penX, penY + 15);
        ctx.stroke();
        ctx.fillStyle = '#ff3b30';
        ctx.beginPath();
        ctx.arc(penX, penY - 22, 4, 0, Math.PI * 2);
        ctx.fill();

        // 标题
        ctx.fillStyle = '#444';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('评测考试台', cx, h - 15);
    },

    /**
     * 档案柜 — 放入抽屉
     * 触发: skill_export, completed
     */
    archive_room: function(ctx, w, h, tick) {
        const cx = w / 2, cy = h / 2;

        // 背景 — 档案室
        ctx.fillStyle = '#f6f4ef';
        ctx.fillRect(0, 0, w, h);

        // 档案柜
        ctx.fillStyle = '#8B7355';
        ctx.fillRect(30, 60, w - 60, 200);
        ctx.fillStyle = '#7a6345';
        ctx.fillRect(30, 60, w - 60, 8);

        // 抽屉
        const drawerY = [80, 140, 200];
        drawerY.forEach((dy, di) => {
            ctx.fillStyle = '#a08060';
            ctx.fillRect(45, dy, w - 90, 50);
            ctx.fillStyle = '#b09070';
            ctx.fillRect(45, dy, w - 90, 5);

            // 把手
            ctx.fillStyle = '#c0a060';
            ctx.beginPath();
            ctx.arc(cx, dy + 25, 8, 0, Math.PI * 2);
            ctx.fill();

            // 标签
            ctx.fillStyle = '#fff8e8';
            ctx.fillRect(cx - 25, dy + 8, 50, 12);
            ctx.fillStyle = '#666';
            ctx.font = '8px sans-serif';
            ctx.textAlign = 'center';
            const drawers = ['技能 v1.2', '技能 v1.3', '技能 v1.4'];
            ctx.fillText(drawers[di], cx, dy + 17);
        });

        // 当前放入的抽屉 — 打开动画
        const openDrawerIdx = Math.floor((tick * 0.15) % drawerY.length);
        const ody = drawerY[openDrawerIdx];
        const offset = Math.min(30, tick * 0.6 % 30);

        ctx.fillStyle = '#c0a080';
        ctx.fillRect(45 + offset, ody, w - 90, 50);
        ctx.fillStyle = '#d0b090';
        ctx.fillRect(45 + offset, ody, w - 90, 5);
        ctx.fillStyle = '#c0a060';
        ctx.beginPath();
        ctx.arc(cx + offset, ody + 25, 8, 0, Math.PI * 2);
        ctx.fill();

        // 文档放入
        if (tick > 40) {
            const docX = cx - 30 + Math.sin(tick * 0.04) * 10;
            const docY = ody - (tick % 60 < 40 ? 30 : Math.min(30, (tick % 60 - 40) * 1.5));
            ctx.fillStyle = '#fff';
            ctx.fillRect(docX, docY, 25, 35);
            ctx.strokeStyle = '#ddd';
            ctx.strokeRect(docX, docY, 25, 35);
            ctx.fillStyle = '#999';
            ctx.font = '6px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('export', docX + 12, docY + 20);
        }

        // 标题
        ctx.fillStyle = '#444';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('技能档案柜', cx, h - 15);
    },

    /**
     * 默认 idle 场景
     */
    idle: function(ctx, w, h, tick) {
        const cx = w / 2, cy = h / 2;

        // 背景
        ctx.fillStyle = '#f8f7f4';
        ctx.fillRect(0, 0, w, h);

        // 中心圆形
        const pulse = Math.sin(tick * 0.03) * 0.15 + 0.35;
        ctx.fillStyle = `rgba(0,113,227,${pulse})`;
        ctx.beginPath();
        ctx.arc(cx, cy - 30, 50, 0, Math.PI * 2);
        ctx.fill();

        // 中央图标
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 36px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('🤖', cx, cy - 30);

        // 底部文字
        ctx.textBaseline = 'alphabetic';
        ctx.fillStyle = '#888';
        ctx.font = '14px sans-serif';
        ctx.fillText('等待任务...', cx, cy + 60);
    },
};

// ---------------------------------------------------------------------------
// 辅助绘制函数
// ---------------------------------------------------------------------------

/**
 * 绘制圆角矩形路径
 */
function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arcTo(x + w, y, x + w, y + r, r);
    ctx.lineTo(x + w, y + h - r);
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
    ctx.lineTo(x + r, y + h);
    ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
}

/**
 * 绘制手
 */
function drawHand(ctx, x, y, tick) {
    ctx.fillStyle = '#f5c6a0';
    ctx.beginPath();
    ctx.arc(x, y, 8, 0, Math.PI * 2);
    ctx.fill();
    // 手指
    for (let fi = 0; fi < 3; fi++) {
        const fx = x - 6 + fi * 6;
        const fy = y - 10 - Math.sin(tick * 0.1 + fi) * 3;
        ctx.fillStyle = '#f5c6a0';
        ctx.fillRect(fx - 2, fy - 6, 4, 10);
    }
}

/**
 * 绘制铅笔
 */
function drawPencil(ctx, x, y, tick) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(Math.sin(tick * 0.1) * 0.3);

    ctx.fillStyle = '#f5c542';
    ctx.fillRect(-2, -25, 4, 30);
    ctx.fillStyle = '#e8b820';
    ctx.fillRect(-2, -25, 4, 6);
    ctx.fillStyle = '#333';
    ctx.beginPath();
    ctx.moveTo(-2, 5);
    ctx.lineTo(0, 12);
    ctx.lineTo(2, 5);
    ctx.closePath();
    ctx.fill();

    ctx.restore();
}

// ---------------------------------------------------------------------------
// 场景切换 API
// ---------------------------------------------------------------------------

/**
 * 设置当前场景（按 Canvas 场景名或 avatar 状态名）
 * @param {string} sceneOrState - Canvas 场景名（如 memory_wall）或 avatar 状态名（如 reading_notes）
 */
function setScene(sceneOrState) {
    // 先按 Canvas 场景名查找
    if (!SCENE_DRAWERS[sceneOrState]) {
        // 如果不是有效的场景名，尝试从 AVATAR_SCENE_MAP 映射
        const sceneCfg = AVATAR_SCENE_MAP[sceneOrState];
        if (sceneCfg) {
            // 将语义场景可映射回 Canvas 场景
            const canvasScene = _semanticToCanvas(sceneCfg.scene, sceneOrState);
            sceneOrState = SCENE_DRAWERS[canvasScene] ? canvasScene : 'idle';
        } else {
            sceneOrState = 'idle';
        }
    }
    currentScene = sceneOrState;

    // 更新玻璃拟态场景标签（根据 currentScene 反查 AVATAR_SCENE_MAP）
    const labelEl = document.getElementById('avatar-scene-label');
    if (labelEl) {
        const stateForLabel = _canvasToState(sceneOrState);
        const sceneCfg = AVATAR_SCENE_MAP[stateForLabel];
        if (sceneCfg) {
            // 双语标签：克制、低饱和、玻璃拟态
            labelEl.innerHTML = [
                '<span class="avatar-label-zh">' + sceneCfg.label_zh + '</span>',
                '<span class="avatar-label-en">' + sceneCfg.label_en + '</span>',
            ].join('');
            labelEl.style.display = 'flex';
        } else if (sceneOrState === 'idle') {
            labelEl.innerHTML = [
                '<span class="avatar-label-zh">等待任务...</span>',
                '<span class="avatar-label-en">Awaiting task...</span>',
            ].join('');
            labelEl.style.display = 'flex';
        }
    }
}

/**
 * 按 avatar 状态名设置场景（直接入口）
 * @param {string} avatarState - AVATAR_SCENE_MAP 中的 key，如 "thinking"
 */
function setSceneByState(avatarState) {
    const cfg = AVATAR_SCENE_MAP[avatarState];
    if (!cfg) {
        setScene('idle');
        return;
    }
    const canvasScene = _semanticToCanvas(cfg.scene, avatarState);
    setScene(canvasScene);
}

// ---------------------------------------------------------------------------
// 语义场景 → Canvas 场景映射（内部）
// ---------------------------------------------------------------------------

/**
 * 将语义场景名映射到现有的 Canvas 场景绘制器
 * @param {string} semanticScene - 语义场景名（如 desk, thinking_board）
 * @param {string} avatarState - avatar 状态名（备用）
 * @returns {string} Canvas 场景名
 */
function _semanticToCanvas(semanticScene, avatarState) {
    const map = {
        desk:             'idle',          // 办公桌 → idle 场景
        thinking_board:   'idle',          // 思考板 → idle 场景（可扩展抽屉）
        memory_wall:      'memory_wall',   // 记忆墙
        library:           'bookshelf',      // 书架
        budget_panel:     'calculator',    // 算盘
        map_table:        'map_table',     // 路线图
        tool_bench:       'tool_bench',    // 工具台
        checkpoint:       'idle',          // 安全检查 → idle（可扩展）
        approval_gate:    'idle',          // 审批门 → idle（可扩展）
        exam_table:       'exam_desk',     // 考试台
        skill_book:       'exam_desk',     // 技能书 → 复用考试台
        archive_cabinet:  'archive_room',  // 档案柜
        delivery_desk:    'archive_room',  // 交付台 → 复用档案柜
        error_board:      'exam_desk',     // 错误板 → 复用考试台
    };
    return map[semanticScene] || 'idle';
}

/**
 * Canvas 场景名 → avatar 状态名（用于标签显示）
 * @param {string} canvasScene
 * @returns {string}
 */
function _canvasToState(canvasScene) {
    const map = {
        memory_wall:    'reading_notes',
        bookshelf:      'searching_books',
        calculator:     'calculating',
        map_table:      'planning',
        tool_bench:     'tooling',
        exam_desk:      'grading',
        archive_room:   'archiving',
        idle:           'listening',
    };
    return map[canvasScene] || 'listening';
}

/**
 * 设置动画状态
 * @param {boolean} animating
 */
function setAnimating(animating) {
    isAnimating = animating;
}

/**
 * 开始渲染循环
 */
function startAvatarLoop() {
    const canvas = document.getElementById('avatar-canvas');
    if (!canvas) {
        // 重试
        animFrameId = requestAnimationFrame(() => startAvatarLoop());
        return;
    }

    const ctx = canvas.getContext('2d');
    const w = SCENE_SIZE.w;
    const h = SCENE_SIZE.h;

    function loop() {
        animTick++;
        ctx.clearRect(0, 0, w, h);
        const drawer = SCENE_DRAWERS[currentScene] || SCENE_DRAWERS.idle;
        drawer(ctx, w, h, animTick);
        animFrameId = requestAnimationFrame(loop);
    }

    loop();
}

/**
 * 停止渲染循环
 */
function stopAvatarLoop() {
    if (animFrameId) {
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
    }
}

// ---------------------------------------------------------------------------
// 阶段 → avatar 状态映射（13 语义场景）
// ---------------------------------------------------------------------------
const STAGE_SCENE_MAP = {
    task_intake:          'listening',
    intent_parse:         'thinking',
    context_budget:       'calculating',
    memory_retrieval:     'reading_notes',
    rag_retrieval:        'searching_books',
    context_build:        'thinking',
    planning:             'planning',
    tool_call:            'tooling',
    security_check:       'safety_check',
    approval_waiting:     'waiting_approval',
    execution:            'tooling',
    evaluation:           'grading',
    badcase_record:       'failed',
    skill_learning:       'learning',
    skill_validation:     'grading',
    skill_export:         'archiving',
    completed:            'done',
    failed:               'failed',
};

/**
 * 根据决策阶段自动切换场景（使用 13 语义场景）
 * @param {string} stage - DecisionStage
 */
function setSceneByStage(stage) {
    const avatarState = STAGE_SCENE_MAP[stage] || 'listening';
    setSceneByState(avatarState);
}
