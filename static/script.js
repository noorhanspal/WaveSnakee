/*
 * Frontend Script for Gesture-Controlled Snake Game
 * Features:
 *   - Rich Game Board Themes (Checkered Grass Garden, Cyberpunk Circuit, Ocean Reef, Desert Dunes, Synthwave Retro)
 *   - Smooth 3D Connected Snake Rendering (3D drop shadows, radial 3D shading, scales, sculpted head, eyes & tongue)
 *   - 3D Glossy Apple & Golden Bonus Food
 */

const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");

const GRID_SIZE = 20;
const GRID_COLS = 32;
const GRID_ROWS = 30;

// UI DOM Elements
const scoreEl = document.getElementById("scoreValue");
const highScoreEl = document.getElementById("highScoreValue");
const handDot = document.getElementById("handDot");
const handStatusText = document.getElementById("handStatusText");
const webcamBox = document.getElementById("webcamBox");
const gestureBanner = document.getElementById("gestureBanner");
const gestureValue = document.getElementById("gestureValue");

// Overlays
const startOverlay = document.getElementById("startOverlay");
const calibrateOverlay = document.getElementById("calibrateOverlay");
const pauseOverlay = document.getElementById("pauseOverlay");
const gameOverOverlay = document.getElementById("gameOverOverlay");

// Dynamic text inside overlays
const calibStatusText = document.getElementById("calibStatusText");
const pauseScore = document.getElementById("pauseScore");
const deathReasonText = document.getElementById("deathReasonText");
const finalScore = document.getElementById("finalScore");
const bestScore = document.getElementById("bestScore");
const newHighScoreBadge = document.getElementById("newHighScoreBadge");

// Latest state from Python backend
let latestState = null;
let soundEnabled = true;
let audioCtx = null;

// Rich Game Board Themes
const BOARD_THEMES = {
    cyber: {
        border: "#00f5d4",
        shadow: "0 0 22px rgba(0, 245, 212, 0.22)"
    },
    grass: {
        border: "#52b788",
        shadow: "0 0 22px rgba(82, 183, 136, 0.25)"
    },
    retro: {
        border: "#f72585",
        shadow: "0 0 22px rgba(247, 37, 133, 0.28)"
    },
    ocean: {
        border: "#00b4d8",
        shadow: "0 0 22px rgba(0, 180, 216, 0.28)"
    },
    desert: {
        border: "#e9c46a",
        shadow: "0 0 22px rgba(233, 196, 106, 0.25)"
    }
};

// 3D Snake Skins
const SNAKE_SKINS = {
    cyan: {
        light: "#9bf6ff",
        mid: "#00f5d4",
        dark: "#007f73",
        stripe: "#00bbf9",
        eyeIris: "#00f5d4"
    },
    fire: {
        light: "#ffea00",
        mid: "#ff5400",
        dark: "#780000",
        stripe: "#ffbd00",
        eyeIris: "#ffbe0b"
    },
    rainbow: {
        light: "#ffffff",
        mid: "#00f5d4",
        dark: "#3a0ca3",
        stripe: "#ffffff",
        eyeIris: "#f72585",
        isRainbow: true
    },
    emerald: {
        light: "#b7efc5",
        mid: "#2dc653",
        dark: "#10451d",
        stripe: "#155d27",
        eyeIris: "#ffd166",
        hasDiamondPattern: true
    },
    gold: {
        light: "#fff9d2",
        mid: "#ffd60a",
        dark: "#99582a",
        stripe: "#ff9f1c",
        eyeIris: "#ffd60a"
    }
};

let currentTheme = localStorage.getItem("snake_board_theme") || "grass";
let currentSkin = localStorage.getItem("snake_skin_style") || "cyan";

// Offscreen canvas to cache rich static board textures for 60 FPS speed
const bgCacheCanvas = document.createElement("canvas");
bgCacheCanvas.width = 640;
bgCacheCanvas.height = 600;
const bgCtx = bgCacheCanvas.getContext("2d");

// Pre-generate decorative items (flowers, pebbles, stars, bubbles)
const ambientItems = [];
for (let i = 0; i < 36; i++) {
    ambientItems.push({
        x: Math.random() * 640,
        y: Math.random() * 600,
        size: 1.5 + Math.random() * 3.5,
        speed: 0.3 + Math.random() * 0.7,
        phase: Math.random() * Math.PI * 2
    });
}

// Render the selected theme texture onto the offscreen canvas
function rebuildBoardThemeTexture() {
    const w = bgCacheCanvas.width;
    const h = bgCacheCanvas.height;
    bgCtx.clearRect(0, 0, w, h);

    if (currentTheme === "grass") {
        // Checkered 3D Garden Grass Tiles (like Google Snake)
        for (let r = 0; r < GRID_ROWS; r++) {
            for (let c = 0; c < GRID_COLS; c++) {
                const isEven = (r + c) % 2 === 0;
                bgCtx.fillStyle = isEven ? "#2d6a4f" : "#24553f";
                bgCtx.fillRect(c * GRID_SIZE, r * GRID_SIZE, GRID_SIZE, GRID_SIZE);

                // Little grass blade details on some tiles
                if ((r * 7 + c * 13) % 11 === 0) {
                    const gx = c * GRID_SIZE + 10;
                    const gy = r * GRID_SIZE + 14;
                    bgCtx.strokeStyle = isEven ? "#40916c" : "#52b788";
                    bgCtx.lineWidth = 1.5;
                    bgCtx.beginPath();
                    bgCtx.moveTo(gx, gy);
                    bgCtx.lineTo(gx - 3, gy - 6);
                    bgCtx.moveTo(gx, gy);
                    bgCtx.lineTo(gx + 3, gy - 5);
                    bgCtx.stroke();
                }
                // Tiny wildflowers on rare tiles
                if ((r * 19 + c * 5) % 29 === 0) {
                    const fx = c * GRID_SIZE + 6;
                    const fy = r * GRID_SIZE + 6;
                    bgCtx.fillStyle = "#ffd166";
                    bgCtx.beginPath();
                    bgCtx.arc(fx, fy, 2.2, 0, Math.PI * 2);
                    bgCtx.fill();
                }
            }
        }
        // Soft vignette border shadow for 3D depth
        const vig = bgCtx.createRadialGradient(w / 2, h / 2, 180, w / 2, h / 2, 420);
        vig.addColorStop(0, "rgba(0,0,0,0)");
        vig.addColorStop(1, "rgba(5, 20, 12, 0.45)");
        bgCtx.fillStyle = vig;
        bgCtx.fillRect(0, 0, w, h);

    } else if (currentTheme === "cyber") {
        // Cyberpunk Dark Radial + Glowing Circuit Board
        const grad = bgCtx.createRadialGradient(w / 2, h / 2, 40, w / 2, h / 2, 420);
        grad.addColorStop(0, "#132238");
        grad.addColorStop(1, "#090d16");
        bgCtx.fillStyle = grad;
        bgCtx.fillRect(0, 0, w, h);

        for (let r = 0; r < GRID_ROWS; r++) {
            for (let c = 0; c < GRID_COLS; c++) {
                if ((r + c) % 2 === 0) {
                    bgCtx.fillStyle = "rgba(0, 245, 212, 0.025)";
                    bgCtx.fillRect(c * GRID_SIZE, r * GRID_SIZE, GRID_SIZE, GRID_SIZE);
                }
            }
        }

        bgCtx.strokeStyle = "rgba(0, 245, 212, 0.12)";
        bgCtx.lineWidth = 1;
        for (let c = 1; c < GRID_COLS; c++) {
            bgCtx.beginPath();
            bgCtx.moveTo(c * GRID_SIZE, 0);
            bgCtx.lineTo(c * GRID_SIZE, h);
            bgCtx.stroke();
        }
        for (let r = 1; r < GRID_ROWS; r++) {
            bgCtx.beginPath();
            bgCtx.moveTo(0, r * GRID_SIZE);
            bgCtx.lineTo(w, r * GRID_SIZE);
            bgCtx.stroke();
        }

    } else if (currentTheme === "ocean") {
        // Deep Ocean Reef Gradient + Checkered Water Tiles
        const grad = bgCtx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, "#023e8a");
        grad.addColorStop(0.5, "#0077b6");
        grad.addColorStop(1, "#03045e");
        bgCtx.fillStyle = grad;
        bgCtx.fillRect(0, 0, w, h);

        for (let r = 0; r < GRID_ROWS; r++) {
            for (let c = 0; c < GRID_COLS; c++) {
                if ((r + c) % 2 === 0) {
                    bgCtx.fillStyle = "rgba(144, 224, 239, 0.05)";
                    bgCtx.fillRect(c * GRID_SIZE, r * GRID_SIZE, GRID_SIZE, GRID_SIZE);
                }
            }
        }
        // Subtle sunlit water rays from top
        for (let i = 0; i < 5; i++) {
            bgCtx.fillStyle = "rgba(180, 240, 255, 0.04)";
            bgCtx.beginPath();
            bgCtx.moveTo(80 + i * 120, 0);
            bgCtx.lineTo(140 + i * 120, 0);
            bgCtx.lineTo(220 + i * 120, h);
            bgCtx.lineTo(20 + i * 120, h);
            bgCtx.closePath();
            bgCtx.fill();
        }

    } else if (currentTheme === "desert") {
        // Warm Sahara Sand Checkered Tiles + Dune Ripples
        for (let r = 0; r < GRID_ROWS; r++) {
            for (let c = 0; c < GRID_COLS; c++) {
                const isEven = (r + c) % 2 === 0;
                bgCtx.fillStyle = isEven ? "#c99b66" : "#b88b56";
                bgCtx.fillRect(c * GRID_SIZE, r * GRID_SIZE, GRID_SIZE, GRID_SIZE);

                // Small desert pebbles
                if ((r * 11 + c * 17) % 23 === 0) {
                    bgCtx.fillStyle = "#8a6236";
                    bgCtx.beginPath();
                    bgCtx.arc(c * GRID_SIZE + 8, r * GRID_SIZE + 12, 2, 0, Math.PI * 2);
                    bgCtx.fill();
                }
            }
        }
        const vig = bgCtx.createRadialGradient(w / 2, h / 2, 160, w / 2, h / 2, 420);
        vig.addColorStop(0, "rgba(255, 230, 160, 0.08)");
        vig.addColorStop(1, "rgba(60, 35, 10, 0.45)");
        bgCtx.fillStyle = vig;
        bgCtx.fillRect(0, 0, w, h);

    } else if (currentTheme === "retro") {
        // 80s Synthwave Horizon Grid
        const grad = bgCtx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, "#10002b");
        grad.addColorStop(0.6, "#240046");
        grad.addColorStop(1, "#3c096c");
        bgCtx.fillStyle = grad;
        bgCtx.fillRect(0, 0, w, h);

        bgCtx.strokeStyle = "rgba(247, 37, 133, 0.22)";
        bgCtx.lineWidth = 1;
        for (let c = 1; c < GRID_COLS; c++) {
            bgCtx.beginPath();
            bgCtx.moveTo(c * GRID_SIZE, 0);
            bgCtx.lineTo(c * GRID_SIZE, h);
            bgCtx.stroke();
        }
        for (let r = 1; r < GRID_ROWS; r++) {
            bgCtx.beginPath();
            bgCtx.moveTo(0, r * GRID_SIZE);
            bgCtx.lineTo(w, r * GRID_SIZE);
            bgCtx.stroke();
        }
    }
}

// Draw animated ambient background elements per theme
function drawThemeAmbientEffects(now) {
    if (currentTheme === "ocean") {
        // Rising underwater bubbles
        ctx.strokeStyle = "rgba(180, 245, 255, 0.35)";
        ctx.lineWidth = 1.2;
        ambientItems.forEach(item => {
            const y = (item.y - (now * 0.025 * item.speed)) % 600;
            const drawY = y < 0 ? y + 600 : y;
            const drawX = item.x + Math.sin(now * 0.003 + item.phase) * 6;
            ctx.beginPath();
            ctx.arc(drawX, drawY, item.size, 0, Math.PI * 2);
            ctx.stroke();
        });
    } else if (currentTheme === "retro" || currentTheme === "cyber") {
        // Twinkling neon stars / nodes
        ambientItems.forEach(item => {
            const alpha = 0.2 + 0.4 * Math.sin(now * 0.004 * item.speed + item.phase);
            ctx.fillStyle = currentTheme === "cyber"
                ? `rgba(0, 245, 212, ${alpha})`
                : `rgba(255, 180, 240, ${alpha})`;
            ctx.beginPath();
            ctx.arc(item.x, item.y, item.size * 0.55, 0, Math.PI * 2);
            ctx.fill();
        });
    }
}

// Simple Web Audio API synthesizer for arcade sound effects
function playArcadeSound(type) {
    if (!soundEnabled) return;
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === "suspended") {
            audioCtx.resume();
        }

        const notes = {
            eat: [[523, 0.06], [659, 0.06], [784, 0.08]],
            bonus: [[587, 0.05], [784, 0.05], [988, 0.05], [1175, 0.10]],
            pause: [[440, 0.06], [330, 0.08]],
            resume: [[330, 0.06], [440, 0.08]],
            game_over: [[392, 0.11], [349, 0.11], [330, 0.11], [261, 0.22]],
            select: [[660, 0.04], [880, 0.06]]
        }[type];

        if (!notes) return;

        let startTime = audioCtx.currentTime;
        notes.forEach(([freq, duration]) => {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = type === "game_over" ? "square" : "triangle";
            osc.frequency.setValueAtTime(freq, startTime);

            gain.gain.setValueAtTime(0.15, startTime);
            gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start(startTime);
            osc.stop(startTime + duration);
            startTime += duration;
        });
    } catch (e) {
        // Ignore audio errors if browser blocks autoplay
    }
}

// Send an action to the Python backend
async function sendAction(action, value = null) {
    try {
        await fetch("/api/action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: action, value: value })
        });
    } catch (err) {
        console.error("Failed to send action:", err);
    }
}

// Poll game state from the Python backend
let isFetching = false;
async function fetchGameState() {
    if (isFetching) return;
    isFetching = true;
    try {
        const res = await fetch("/api/state");
        if (res.ok) {
            const data = await res.json();
            latestState = data;
            updateUI(data);

            if (data.sound_events && data.sound_events.length > 0) {
                data.sound_events.forEach(evt => playArcadeSound(evt));
            }
        }
    } catch (err) {
        // Ignore transient network errors
    } finally {
        isFetching = false;
    }
}

// Update HTML UI overlays, score pills, and gesture status
function updateUI(data) {
    scoreEl.textContent = data.score;
    highScoreEl.textContent = data.high_score;

    document.querySelectorAll(".diff-btn").forEach(btn => {
        if (btn.dataset.diff === data.difficulty) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    const tracker = data.tracker || {};
    const handOk = Boolean(tracker.hand_detected);
    if (handOk) {
        handDot.classList.add("locked");
        webcamBox.classList.add("locked");
        handStatusText.textContent = "Hand Locked";
        handStatusText.style.color = "#2ed573";
    } else {
        handDot.classList.remove("locked");
        webcamBox.classList.remove("locked");
        handStatusText.textContent = "Show Hand";
        handStatusText.style.color = "#ffa502";
    }

    let gestureKey = tracker.gesture || "NONE";
    if (tracker.is_two_palms) {
        gestureKey = "TWO_PALMS";
    } else if ((data.state === "START" || data.state === "GAME_OVER") && tracker.is_open_palm) {
        gestureKey = "OPEN_PALM";
    }

    const gestureNames = {
        NONE: "NEUTRAL / IDLE",
        UP: "UP (Move Up)",
        DOWN: "DOWN (Move Down)",
        LEFT: "LEFT (Move Left)",
        RIGHT: "RIGHT (Move Right)",
        TWO_PALMS: "2 HANDS PALM (Pause/Resume)",
        OPEN_PALM: "OPEN PALM (Start/Restart)"
    };
    gestureValue.textContent = gestureNames[gestureKey] || gestureKey;

    let gColor = "#8b949e";
    if (["UP", "DOWN", "LEFT", "RIGHT"].includes(gestureKey)) {
        gColor = "#00f5d4";
    } else if (gestureKey === "TWO_PALMS") {
        gColor = "#ffa502";
    } else if (gestureKey === "OPEN_PALM") {
        gColor = "#2ed573";
    }
    gestureValue.style.color = gColor;
    gestureBanner.style.borderColor = gColor;

    startOverlay.classList.toggle("hidden", data.state !== "START");
    calibrateOverlay.classList.toggle("hidden", data.state !== "CALIBRATE");
    pauseOverlay.classList.toggle("hidden", data.state !== "PAUSED");
    gameOverOverlay.classList.toggle("hidden", data.state !== "GAME_OVER");

    if (data.state === "CALIBRATE") {
        if (handOk) {
            calibStatusText.textContent = `Locking Center in ${Math.max(0, data.calib_countdown).toFixed(1)}s...`;
            calibStatusText.style.color = "#2ed573";
        } else {
            calibStatusText.textContent = "Waiting for hand in webcam view...";
            calibStatusText.style.color = "#ffa502";
        }
    } else if (data.state === "PAUSED") {
        pauseScore.textContent = data.score;
    } else if (data.state === "GAME_OVER") {
        deathReasonText.textContent = data.death_reason || "Game Over!";
        finalScore.textContent = data.score;
        bestScore.textContent = data.high_score;
        newHighScoreBadge.classList.toggle("hidden", !(data.new_high_score && data.score > 0));
    }
}

// Draw a 3D Glossy Apple on Canvas
function draw3DApple(x, y, now, isGolden = false) {
    const bounce = Math.sin(now * 0.007) * 1.8;
    const ay = y + bounce;
    const radius = GRID_SIZE * 0.48;

    // 1. Soft 3D Ground Shadow
    ctx.fillStyle = "rgba(0, 0, 0, 0.38)";
    ctx.beginPath();
    ctx.ellipse(x + 2, y + radius - 1, radius * 0.85, radius * 0.45, 0, 0, Math.PI * 2);
    ctx.fill();

    // 2. Outer Glow for Golden Food
    if (isGolden) {
        ctx.fillStyle = "rgba(255, 215, 0, 0.28)";
        ctx.beginPath();
        ctx.arc(x, ay, radius * 1.45, 0, Math.PI * 2);
        ctx.fill();
    }

    // 3. 3D Spherical Apple Body using Radial Gradient
    const grad = ctx.createRadialGradient(
        x - radius * 0.35,
        ay - radius * 0.35,
        radius * 0.1,
        x,
        ay,
        radius
    );
    if (isGolden) {
        grad.addColorStop(0, "#fffac2");
        grad.addColorStop(0.45, "#ffd700");
        grad.addColorStop(1, "#b5651d");
    } else {
        grad.addColorStop(0, "#ff9ebb");
        grad.addColorStop(0.4, "#ff2a55");
        grad.addColorStop(1, "#800016");
    }

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(x, ay, radius, 0, Math.PI * 2);
    ctx.fill();

    // 4. Apple Stem
    ctx.strokeStyle = "#5c3a21";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x, ay - radius + 2);
    ctx.quadraticCurveTo(x + 2, ay - radius - 5, x + 4, ay - radius - 4);
    ctx.stroke();

    // 5. Green Leaf
    ctx.fillStyle = "#4cd137";
    ctx.beginPath();
    ctx.ellipse(x + 4, ay - radius - 2, 4.5, 2.2, -Math.PI / 6, 0, Math.PI * 2);
    ctx.fill();

    // 6. Specular 3D Gloss Highlight
    ctx.fillStyle = "rgba(255, 255, 255, 0.65)";
    ctx.beginPath();
    ctx.ellipse(x - radius * 0.32, ay - radius * 0.32, 2.8, 1.6, -Math.PI / 4, 0, Math.PI * 2);
    ctx.fill();
}

// Draw the Smooth 3D Connected Snake
function draw3DSnake(snake, direction, now) {
    if (!snake || snake.length === 0) return;

    const skin = SNAKE_SKINS[currentSkin] || SNAKE_SKINS.cyan;

    // Convert grid coordinates to pixel center points
    const pts = snake.map(seg => ({
        x: seg[0] * GRID_SIZE + GRID_SIZE / 2,
        y: seg[1] * GRID_SIZE + GRID_SIZE / 2
    }));

    // 1. Draw Continuous 3D Drop Shadow Underneath the Snake
    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "rgba(0, 0, 0, 0.42)";
    ctx.lineWidth = GRID_SIZE * 0.92;
    ctx.beginPath();
    ctx.moveTo(pts[0].x + 3, pts[0].y + 5);
    for (let i = 1; i < pts.length; i++) {
        // Skip shadow line if wrapped across screen
        if (Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y) < GRID_SIZE * 2.5) {
            ctx.lineTo(pts[i].x + 3, pts[i].y + 5);
        } else {
            ctx.moveTo(pts[i].x + 3, pts[i].y + 5);
        }
    }
    ctx.stroke();
    ctx.restore();

    // 2. Build Dense Sub-Sampled Points from Tail to Head for Butter-Smooth 3D Cylinder
    const denseSpheres = [];
    const subSteps = 3; // 3 interpolated spheres per grid segment
    for (let i = pts.length - 1; i > 0; i--) {
        const p1 = pts[i];
        const p2 = pts[i - 1];
        const dist = Math.hypot(p2.x - p1.x, p2.y - p1.y);
        if (dist > GRID_SIZE * 2.5) continue;

        for (let s = 0; s < subSteps; s++) {
            const tSub = s / subSteps;
            const x = p1.x + (p2.x - p1.x) * tSub;
            const y = p1.y + (p2.y - p1.y) * tSub;
            const progressFromHead = (i - tSub) / Math.max(pts.length - 1, 1);
            denseSpheres.push({ x, y, progressFromHead, index: i * subSteps - s });
        }
    }
    // Add Head center point
    denseSpheres.push({ x: pts[0].x, y: pts[0].y, progressFromHead: 0, index: 0 });

    // 3. Draw Overlapping 3D Shaded Spheres from Tail to Neck
    for (let k = 0; k < denseSpheres.length - 1; k++) {
        const sp = denseSpheres[k];
        // Smoothly taper radius near the tail tip
        const tailFactor = sp.progressFromHead > 0.72
            ? 1.0 - ((sp.progressFromHead - 0.72) / 0.28) * 0.48
            : 1.0;
        const radius = (GRID_SIZE * 0.48) * tailFactor;

        const grad = ctx.createRadialGradient(
            sp.x - radius * 0.32,
            sp.y - radius * 0.35,
            radius * 0.08,
            sp.x,
            sp.y,
            radius
        );

        if (skin.isRainbow) {
            const hue = (sp.index * 8 - now * 0.15) % 360;
            grad.addColorStop(0, "#ffffff");
            grad.addColorStop(0.35, `hsl(${hue}, 95%, 60%)`);
            grad.addColorStop(1, `hsl(${hue}, 90%, 25%)`);
        } else {
            grad.addColorStop(0, skin.light);
            grad.addColorStop(0.45, skin.mid);
            grad.addColorStop(1, skin.dark);
        }

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(sp.x, sp.y, radius, 0, Math.PI * 2);
        ctx.fill();

        // Subtle 3D Scale / Stripe accent on every 3rd sphere
        if (k % 3 === 0 && sp.progressFromHead < 0.85) {
            ctx.fillStyle = skin.hasDiamondPattern
                ? "rgba(16, 69, 29, 0.45)"
                : "rgba(255, 255, 255, 0.14)";
            ctx.beginPath();
            ctx.arc(sp.x - radius * 0.15, sp.y - radius * 0.15, radius * 0.42, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    // 4. Draw Sculpted 3D Snake Head, Flicking Tongue, and Glossy 3D Eyes
    const head = pts[0];
    const dir = direction || [1, 0];
    const angle = Math.atan2(dir[1], dir[0]);
    const headRadius = GRID_SIZE * 0.54;

    ctx.save();
    ctx.translate(head.x, head.y);
    ctx.rotate(angle);

    // 4a. Animated Forked Red Tongue
    const tongueCycle = Math.sin(now * 0.012);
    if (tongueCycle > -0.2) {
        const tongueLen = 7 + tongueCycle * 5;
        ctx.strokeStyle = "#ff2a55";
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.moveTo(headRadius - 2, 0);
        ctx.lineTo(headRadius + tongueLen, 0);
        // Forked tips
        ctx.lineTo(headRadius + tongueLen + 3.5, -3);
        ctx.moveTo(headRadius + tongueLen, 0);
        ctx.lineTo(headRadius + tongueLen + 3.5, 3);
        ctx.stroke();
    }

    // 4b. 3D Sculpted Oval Head with Radial Shading
    const headGrad = ctx.createRadialGradient(
        -headRadius * 0.2,
        -headRadius * 0.25,
        headRadius * 0.1,
        0,
        0,
        headRadius * 1.15
    );
    headGrad.addColorStop(0, skin.light);
    headGrad.addColorStop(0.5, skin.mid);
    headGrad.addColorStop(1, skin.dark);

    ctx.fillStyle = headGrad;
    ctx.beginPath();
    ctx.ellipse(1, 0, headRadius * 1.12, headRadius * 0.95, 0, 0, Math.PI * 2);
    ctx.fill();

    // 4c. 3D Bulging Glossy Eyes (Left & Right)
    [-1, 1].forEach(side => {
        const ex = 2.5;
        const ey = side * (headRadius * 0.56);

        // Eye socket shadow
        ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
        ctx.beginPath();
        ctx.arc(ex, ey, 4.4, 0, Math.PI * 2);
        ctx.fill();

        // White sclera
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(ex, ey, 3.8, 0, Math.PI * 2);
        ctx.fill();

        // Dark pupil looking slightly forward
        ctx.fillStyle = "#090d16";
        ctx.beginPath();
        ctx.arc(ex + 1.1, ey, 2.1, 0, Math.PI * 2);
        ctx.fill();

        // Bright 3D eye reflection dot
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(ex + 0.3, ey - 0.9, 0.9, 0, Math.PI * 2);
        ctx.fill();
    });

    // Tiny nostrils near snout tip
    ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
    ctx.beginPath();
    ctx.arc(headRadius * 0.72, -2.2, 0.9, 0, Math.PI * 2);
    ctx.arc(headRadius * 0.72, 2.2, 0.9, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
}

// Main 60 FPS Render Loop
function drawBoard() {
    const now = performance.now();

    // 1. Draw Cached Rich Theme Background + Live Ambient Effects
    ctx.drawImage(bgCacheCanvas, 0, 0);
    drawThemeAmbientEffects(now);

    if (!latestState) {
        requestAnimationFrame(drawBoard);
        return;
    }

    // 2. Draw 3D Regular Apple
    if (latestState.food) {
        const fx = latestState.food[0] * GRID_SIZE + GRID_SIZE / 2;
        const fy = latestState.food[1] * GRID_SIZE + GRID_SIZE / 2;
        draw3DApple(fx, fy, now, false);
    }

    // 3. Draw 3D Golden Bonus Apple if active
    if (latestState.bonus_food) {
        const bx = latestState.bonus_food[0] * GRID_SIZE + GRID_SIZE / 2;
        const by = latestState.bonus_food[1] * GRID_SIZE + GRID_SIZE / 2;
        draw3DApple(bx, by, now, true);
    }

    // 4. Draw Smooth 3D Connected Snake
    draw3DSnake(latestState.snake, latestState.direction, now);

    // 5. Draw Eating / Collision Particles
    if (latestState.particles) {
        latestState.particles.forEach(p => {
            const rad = Math.max(1, p.radius * p.life);
            ctx.fillStyle = `rgb(${p.color[0]}, ${p.color[1]}, ${p.color[2]})`;
            ctx.beginPath();
            ctx.arc(p.x, p.y, rad, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    requestAnimationFrame(drawBoard);
}

// Button Click Listeners
document.getElementById("startBtn").addEventListener("click", () => sendAction("start"));
document.getElementById("restartBtn").addEventListener("click", () => sendAction("restart"));
document.getElementById("resumeBtn").addEventListener("click", () => sendAction("resume"));
document.getElementById("pauseRestartBtn").addEventListener("click", () => sendAction("restart"));
document.getElementById("calibrateBtn").addEventListener("click", () => sendAction("calibrate"));
document.getElementById("lockCalibBtn").addEventListener("click", () => sendAction("lock_calibrate"));
document.getElementById("resetCalibBtn").addEventListener("click", () => sendAction("reset_calibrate"));
document.getElementById("cancelCalibBtn").addEventListener("click", () => sendAction("cancel_calibrate"));

const soundBtn = document.getElementById("soundBtn");
soundBtn.addEventListener("click", () => {
    soundEnabled = !soundEnabled;
    soundBtn.textContent = soundEnabled ? "Sound: ON" : "Sound: OFF";
    soundBtn.classList.toggle("active-green", soundEnabled);
});

document.querySelectorAll(".diff-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        sendAction("difficulty", btn.dataset.diff);
    });
});

// Board Theme & Snake Skin Selectors
const boardThemeSelect = document.getElementById("boardThemeSelect");
const snakeSkinSelect = document.getElementById("snakeSkinSelect");
const boardWrapper = document.querySelector(".board-wrapper");

function applyBoardBorder() {
    const theme = BOARD_THEMES[currentTheme] || BOARD_THEMES.grass;
    if (boardWrapper) {
        boardWrapper.style.borderColor = theme.border;
        boardWrapper.style.boxShadow = theme.shadow;
    }
    rebuildBoardThemeTexture();
}

if (boardThemeSelect) {
    boardThemeSelect.value = currentTheme;
    applyBoardBorder();
    boardThemeSelect.addEventListener("change", (e) => {
        currentTheme = e.target.value;
        localStorage.setItem("snake_board_theme", currentTheme);
        applyBoardBorder();
        playArcadeSound("select");
    });
} else {
    rebuildBoardThemeTexture();
}

if (snakeSkinSelect) {
    snakeSkinSelect.value = currentSkin;
    snakeSkinSelect.addEventListener("change", (e) => {
        currentSkin = e.target.value;
        localStorage.setItem("snake_skin_style", currentSkin);
        playArcadeSound("select");
    });
}

// Keyboard Controls Backup
window.addEventListener("keydown", (e) => {
    const key = e.key.toLowerCase();
    if (["arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(key)) {
        e.preventDefault();
    }

    if (key === "1") sendAction("difficulty", "EASY");
    else if (key === "2") sendAction("difficulty", "MEDIUM");
    else if (key === "3") sendAction("difficulty", "HARD");
    else if (key === "c") sendAction("calibrate");
    else if (key === "r") sendAction("restart");
    else if (key === "p") sendAction("toggle_pause");
    else if (key === "escape") sendAction("cancel_calibrate");
    else if (key === " " || key === "enter") sendAction("space_action");
    else if (key === "arrowup" || key === "w") sendAction("direction", "UP");
    else if (key === "arrowdown" || key === "s") sendAction("direction", "DOWN");
    else if (key === "arrowleft" || key === "a") sendAction("direction", "LEFT");
    else if (key === "arrowright" || key === "d") sendAction("direction", "RIGHT");
});

// Start polling Python backend at ~30 times per second and render Canvas at 60 FPS
setInterval(fetchGameState, 33);
requestAnimationFrame(drawBoard);
