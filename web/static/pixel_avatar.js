/**
 * Pixel Avatar — 泰拉瑞亚风像素机器人状态管理器
 *
 * 使用 CSS box-shadow 像素画技术绘制机械数字机器人。
 * 支持多种动态状态：闲置呼吸、思考摇摆、工作中、搜索、庆祝。
 *
 * 事件 → 机器人状态映射
 *   workflow:started  → thinking (思考)
 *   memory:retrieval  → searching (搜索记忆)
 *   memory:retrieving → searching
 *   memory:retrieved  → working (筛选记忆)
 *   rag:searched      → working (查阅知识库)
 *   workflow:planned  → thinking (规划)
 *   execute:completed → working (执行)
 *   eval:completed    → working (评分)
 *   workflow:completed→ celebrating (完成庆祝)
 *   workflow:init     → thinking (准备就绪)
 *
 *   V3 新增事件映射:
 *   budget:allocated   → thinking (打算盘)
 *   context:built      → idle (上下文包就绪)
 *   approval:required  → idle (举手等待——用 idle + 特殊光环色)
 *   approval:pending   → idle
 *   workflow:paused    → idle
 *   workflow:resumed   → working
 *   workflow:failed    → idle (特殊红色光环)
 *   默认              → idle (闲置)
 */

// ============================================================================
// 粒子管理器
// ============================================================================

const ParticleManager = {
    container: null,
    active: false,

    init() {
        this.container = document.getElementById('particles-layer');
        if (!this.container) return;
        // 预创建粒子
        this.container.innerHTML = '';
        for (let i = 0; i < 6; i++) {
            const p = document.createElement('div');
            p.className = 'particle';
            p.style.left = (20 + Math.random() * 60) + '%';
            p.style.animationDelay = (Math.random() * 3) + 's';
            p.style.animationDuration = (2.5 + Math.random() * 2) + 's';
            this.container.appendChild(p);
        }
    },

    start() {
        if (!this.container || this.active) return;
        this.active = true;
        this.container.style.display = 'block';
        this.container.querySelectorAll('.particle').forEach(p => {
            p.style.animationPlayState = 'running';
        });
    },

    stop() {
        if (!this.container) return;
        this.active = false;
        this.container.querySelectorAll('.particle').forEach(p => {
            p.style.animationPlayState = 'paused';
        });
        setTimeout(() => {
            if (!this.active && this.container) {
                this.container.style.display = 'none';
            }
        }, 500);
    }
};

// ============================================================================
// 事件类型 → 机器人状态映射
// ============================================================================

const STATE_MAP = {
    // 原有映射
    'workflow:started':  { cssClass: 'robot-thinking', label: '思考中...', particles: true },
    'memory:retrieval':  { cssClass: 'robot-searching', label: '搜索记忆中...', particles: true },
    'memory:retrieving': { cssClass: 'robot-searching', label: '搜索记忆中...', particles: true },
    'memory:retrieved':  { cssClass: 'robot-working', label: '分析记忆中...', particles: true },
    'rag:searched':      { cssClass: 'robot-working', label: '查阅知识库...', particles: true },
    'workflow:planned':  { cssClass: 'robot-thinking', label: '规划执行中...', particles: true },
    'execute:completed': { cssClass: 'robot-working', label: '执行完毕！', particles: true },
    'eval:completed':    { cssClass: 'robot-working', label: '评测中...', particles: true },
    'workflow:completed':{ cssClass: 'robot-celebrating', label: '全部完成！', particles: true },
    'workflow:init':     { cssClass: 'robot-thinking', label: '准备就绪！', particles: true },

    // V3 新增事件映射
    'budget:allocated':   { cssClass: 'robot-thinking', label: '算盘中...', particles: true },
    'context:built':      { cssClass: 'robot-idle', label: '上下文就绪', particles: false },
    'approval:required':  { cssClass: 'robot-idle', label: '等待审批...', particles: false, glowClass: 'glow-approval' },
    'approval:pending':   { cssClass: 'robot-idle', label: '等待审批...', particles: false, glowClass: 'glow-approval' },
    'workflow:paused':    { cssClass: 'robot-idle', label: '已暂停', particles: false },
    'workflow:resumed':   { cssClass: 'robot-working', label: '继续执行...', particles: true },
    'workflow:failed':    { cssClass: 'robot-idle', label: '执行失败', particles: false, glowClass: 'glow-error' },
    'workflow:cancelled': { cssClass: 'robot-idle', label: '已取消', particles: false },

    // V4 新增: SkillOpt 事件映射
    'skillopt.epoch_started':        { cssClass: 'robot-skill-learning', label: '技能学习中...', particles: true },
    'skillopt.rollouts_collected':   { cssClass: 'robot-skill-learning', label: '整理对话记录...', particles: true },
    'skillopt.failures_analyzed':    { cssClass: 'robot-skill-learning', label: '复盘失败案例...', particles: true },
    'skillopt.successes_analyzed':   { cssClass: 'robot-skill-learning', label: '发现成功模式...', particles: true },
    'skillopt.patch_merged':         { cssClass: 'robot-skill-patching', label: '合并改进方案...', particles: true },
    'skillopt.patch_ranked':         { cssClass: 'robot-skill-patching', label: '排序改进建议...', particles: true },
    'skillopt.candidate_created':    { cssClass: 'robot-skill-patching', label: '生成候选技能...', particles: true },
    'skillopt.validation_passed':    { cssClass: 'robot-skill-accepted', label: '验证通过！', particles: true, glowClass: 'glow-skill-accepted' },
    'skillopt.validation_failed':    { cssClass: 'robot-skill-rejected', label: '验证未通过', particles: true, glowClass: 'glow-skill-rejected' },
    'skillopt.rejected_buffer_updated': { cssClass: 'robot-skill-rejected', label: '放入废纸篓...', particles: true, glowClass: 'glow-skill-rejected' },
    'skillopt.slow_update_created':  { cssClass: 'robot-skill-learning', label: '生成长期规律...', particles: true },
    'skillopt.best_skill_exported':  { cssClass: 'robot-skill-exported', label: '导出最优技能！', particles: true, glowClass: 'glow-skill-accepted' },
};

const IDLE_STATE = { cssClass: 'robot-idle', label: '待命中...', particles: false };

// ============================================================================
// V4 新增: SkillOpt 本地解释映射
// ============================================================================

const SKILLOPT_EXPLANATIONS = {
    'skillopt.epoch_started': '🔄 它开始了一轮技能学习：回顾最近的对话，找出哪里可以做得更好。',
    'skillopt.rollouts_collected': '📝 它整理完了最近的对话记录，准备从中学习。',
    'skillopt.failures_analyzed': '🔍 它正在复盘失败案例，找出用户反复不满意的地方。',
    'skillopt.successes_analyzed': '✨ 它发现了一些做得很好的模式，准备把它们固化下来。',
    'skillopt.patch_merged': '🧩 它正在把成功经验和失败教训合并成一份改进方案。',
    'skillopt.patch_ranked': '📊 它在给改进建议排序：先解决最影响体验的问题。',
    'skillopt.candidate_created': '📄 新的技能文档草案已生成，但它不会马上生效——要先通过验证。',
    'skillopt.validation_passed': '✅ 新技能文档通过了验证测试！确实比原来的更好，马上更新。',
    'skillopt.validation_failed': '❌ 这次改进在验证中表现不如预期，它把失败的尝试记录了下来。',
    'skillopt.rejected_buffer_updated': '🗑️ 它把无效的修改放进了废纸篓，防止以后重复尝试。',
    'skillopt.slow_update_created': '🐢 它总结了一些长期稳定的规律，写进了技能文档的深层保护区。',
    'skillopt.best_skill_exported': '📦 最优技能文档已导出，可以部署给 AI 助手使用了。',
};

// ============================================================================
// 公共 API
// ============================================================================

/**
 * 根据事件类型更新机器人状态。
 * @param {string} eventType
 */
function updateAvatar(eventType) {
    const state = STATE_MAP[eventType] || IDLE_STATE;
    const stage = document.getElementById('robot-stage');

    if (!stage) return;

    // 切换 CSS 类
    stage.className = 'robot-stage ' + state.cssClass;

    // V3: 特殊光环处理
    const glow = stage.querySelector('.robot-glow');
    if (glow) {
        // 清除旧的光环类
        glow.classList.remove('glow-approval', 'glow-error');
        // 应用新的光环类
        if (state.glowClass) {
            glow.classList.add(state.glowClass);
        }
    }

    // 更新标签
    const label = document.getElementById('robot-status-label');
    if (label) label.textContent = state.label;

    // 粒子效果
    if (state.particles) {
        ParticleManager.start();
    } else {
        ParticleManager.stop();
    }
}

/**
 * 重置到闲置状态。
 */
function resetAvatar() {
    const stage = document.getElementById('robot-stage');
    if (!stage) return;
    stage.className = 'robot-stage robot-idle';

    // 清除特殊光环
    const glow = stage.querySelector('.robot-glow');
    if (glow) {
        glow.classList.remove('glow-approval', 'glow-error');
    }

    const label = document.getElementById('robot-status-label');
    if (label) label.textContent = IDLE_STATE.label;

    ParticleManager.stop();
}

// ============================================================================
// 初始化
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    ParticleManager.init();
});
