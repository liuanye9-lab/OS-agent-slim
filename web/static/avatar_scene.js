// avatar_scene.js — 像素人语义场景动画（Canvas）
// 由后端 avatar_state 驱动，非前端猜测

(function () {
  const SCENE_CONFIGS = {
    desk:           { bg: "#fafafa", objects: ["📋", "🖥️"],   mood: "neutral" },
    thinking_board: { bg: "#f0f0ff", objects: ["🧠", "💡"],   mood: "focused" },
    budget_panel:   { bg: "#f5fffa", objects: ["💰", "📊"],   mood: "calculating" },
    memory_wall:    { bg: "#fff8e1", objects: ["📝", "🧩"],   mood: "studying" },
    library:        { bg: "#f3e5f5", objects: ["📚", "🔍"],   mood: "searching" },
    context_table:  { bg: "#e8f5e9", objects: ["🧩", "✂️"],   mood: "organizing" },
    map_table:      { bg: "#e3f2fd", objects: ["🗺️", "📍"],   mood: "planning" },
    tool_bench:     { bg: "#fff3e0", objects: ["🔧", "⚙️"],   mood: "working" },
    monitor:        { bg: "#fce4ec", objects: ["📺", "👁️"],   mood: "watching" },
    exam_table:     { bg: "#f1f8e9", objects: ["📝", "✅"],   mood: "grading" },
    diagnosis_board:{ bg: "#ffebee", objects: ["🔍", "⚠️"],   mood: "concerned" },
    case_desk:      { bg: "#e8eaf6", objects: ["📋", "✏️"],   mood: "writing" },
    skill_book:     { bg: "#f9fbe7", objects: ["📖", "✨"],   mood: "learning" },
    approval_gate:  { bg: "#fff8e1", objects: ["🚦", "⏳"],   mood: "waiting" },
    archive_cabinet:{ bg: "#eceff1", objects: ["📦", "🏷️"],   mood: "archiving" },
    delivery_desk:  { bg: "#e8f5e9", objects: ["🎉", "✅"],   mood: "celebrating" },
    error_board:    { bg: "#ffebee", objects: ["⚠️", "🔴"],   mood: "error" }
  };

  const DEFAULT_SCENE = SCENE_CONFIGS.desk;

  /**
   * Render semantic scene on canvas
   * @param {string} avatarState - avatar_state from backend
   * @param {string} canvasId - canvas element id
   */
  window.renderAvatarScene = function (avatarState, canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    const config = SCENE_CONFIGS[avatarState] || DEFAULT_SCENE;

    // Background
    ctx.fillStyle = config.bg;
    ctx.fillRect(0, 0, w, h);

    // Draw character
    drawCharacter(ctx, w, h, config.mood);

    // Draw objects
    if (config.objects && config.objects.length >= 2) {
      ctx.font = "32px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(config.objects[0], w * 0.3, h * 0.35);
      ctx.fillText(config.objects[1], w * 0.7, h * 0.6);
    }
  };

  function drawCharacter(ctx, w, h, mood) {
    // Simple pixel character
    const cx = w / 2;
    const cy = h / 2;
    const s = Math.min(w, h) * 0.25;

    // Head
    ctx.fillStyle = mood === "error" ? "#ef9a9a" : "#ffcc80";
    ctx.beginPath();
    ctx.arc(cx, cy - s * 0.3, s * 0.35, 0, Math.PI * 2);
    ctx.fill();

    // Eyes
    ctx.fillStyle = "#333";
    ctx.beginPath();
    ctx.arc(cx - s * 0.1, cy - s * 0.35, 3, 0, Math.PI * 2);
    ctx.arc(cx + s * 0.1, cy - s * 0.35, 3, 0, Math.PI * 2);
    ctx.fill();

    // Mouth (varies by mood)
    ctx.beginPath();
    if (mood === "celebrating" || mood === "working") {
      ctx.arc(cx, cy - s * 0.25, 5, 0, Math.PI);
    } else if (mood === "concerned" || mood === "error") {
      ctx.arc(cx, cy - s * 0.2, 5, Math.PI, 0);
    } else {
      ctx.moveTo(cx - 5, cy - s * 0.25);
      ctx.lineTo(cx + 5, cy - s * 0.25);
    }
    ctx.strokeStyle = "#333";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Body
    ctx.fillStyle = mood === "error" ? "#e57373" : "#5c6bc0";
    ctx.fillRect(cx - s * 0.2, cy - s * 0.05, s * 0.4, s * 0.5);
  }
})();
