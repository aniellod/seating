def get_game_html():
    return """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: sans-serif; background-color: #f0f2f6; margin: 0; display: flex; flex-direction: column; align-items: center; }
        #game-container { position: relative; margin-top: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; background: #fff; }
        canvas { display: block; }
        #ui-layer { position: absolute; top: 0; left: 0; width: 100%; padding: 10px; box-sizing: border-box; display: flex; justify-content: space-between; background: rgba(255,255,255,0.9); border-bottom: 1px solid #ddd; }
        .stat-box { font-weight: bold; font-size: 14px; color: #333; }
        .stat-sub { font-size: 12px; color: #555; font-weight: normal; }
        button { padding: 8px 16px; background: #ff4b4b; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
        button:hover { background: #ff3333; }
        button.start { background: #00cc66; }
        button.start:hover { background: #00bb55; }
        button.secondary { background: #444; margin-left: 10px; }
        button.secondary:hover { background: #222; }
        #status-msg { position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.7); color: white; padding: 5px 15px; border-radius: 15px; font-size: 12px; display: none; }
    </style>
</head>
<body>

<div id="game-container">
    <div id="ui-layer">
        <div class="stat-box">⏱️ Time: <span id="timer">00:00</span><br><span class="stat-sub">Best: <span id="high-score">--:--</span></span></div>
        <div class="stat-box">🪑 Seated: <span id="seated-count">0</span>/250<br><span class="stat-sub">Progress: <span id="progress">0</span>%</span></div>
        <div>
            <button id="action-btn" class="start" onclick="toggleGame()">START SIMULATION</button>
            <button id="pause-btn" class="secondary" onclick="togglePause()" disabled>PAUSE</button>
        </div>
    </div>
    <canvas id="simCanvas" width="800" height="600"></canvas>
    <div id="status-msg">Computing Paths...</div>
</div>

<script>
// --- Configuration ---
const CONFIG = {
    cols: 32, // Grid columns
    rows: 20, // Grid rows
    cellSize: 25,
    seatTotal: 250,
    seatYOffset: 0, // Keep seats aligned to their grid cell for accurate targeting
    speeds: {
        aisle: 2.0,
        emptySeat: 1.5, // 75%
        occupiedSeat: 0.5 // 25%
    },
    avoidanceRadius: 22, // Pixel radius for collision separation
    avoidanceWeight: 0.6,
    renderOffsetY: 30 // Shift entire seating grid downward for better centering
};

// --- Utility helpers ---
const gridCenterX = (x) => x * CONFIG.cellSize + CONFIG.cellSize / 2;
const gridCenterY = (y) => y * CONFIG.cellSize + CONFIG.cellSize / 2 + CONFIG.renderOffsetY;
const gridOriginX = (x) => x * CONFIG.cellSize;
const gridOriginY = (y) => y * CONFIG.cellSize + CONFIG.renderOffsetY;
const pixelToGridX = (x) => Math.floor(x / CONFIG.cellSize);
const pixelToGridY = (y) => Math.floor((y - CONFIG.renderOffsetY) / CONFIG.cellSize);

// --- Game State ---
let canvas, ctx;
let grid = [];
let students = [];
let seats = [];
let isRunning = false;
let isPaused = false;
let startTime;
let pausedAt = 0;
let animationId;
let seatedCount = 0;
let spawnTimer = 0;
let lastTime = 0;
let highScore = null;
let failTriggered = false;

// Entrances (Grid coordinates)
const ENTRANCES = [
    {x: 2, y: 19},  // Left Back
    {x: 16, y: 19}, // Center Back
    {x: 29, y: 19}  // Right Back
];

class Node {
    constructor(x, y, type) {
        this.x = x;
        this.y = y;
        this.type = type; // 'aisle', 'seat', 'wall', 'front'
        this.occupied = false;
        this.g = 0;
        this.h = 0;
        this.f = 0;
        this.parent = null;
    }
    
    getCost() {
        if (this.type === 'aisle' || this.type === 'front') return 1;
        if (this.type === 'seat') return this.occupied ? 4 : 1.3; // Higher cost for occupied
        return 100; // Wall
    }
}

class Student {
    constructor(targetSeat) {
        // Pick random entrance
        const entrance = ENTRANCES[Math.floor(Math.random() * ENTRANCES.length)];
        this.x = gridCenterX(entrance.x);
        this.y = gridCenterY(entrance.y);
        this.gridX = entrance.x;
        this.gridY = entrance.y;
        
        this.targetSeat = targetSeat;
        this.path = [];
        this.pathIndex = 0;
        this.state = 'entering'; // entering, moving, seated, paused
        this.color = `hsl(${Math.random() * 360}, 70%, 50%)`;
        this.entryDelay = 0.5 + Math.random() * 0.5;

        // Calculate initial path
        this.recalculatePath();
    }

    recalculatePath() {
        // A* Pathfinding
        this.path = findPath(this.gridX, this.gridY, this.targetSeat.x, this.targetSeat.y);
        this.pathIndex = 0;
    }

    update(dt) {
        if (this.state === 'seated') return;

        // Entrance delay
        if (this.state === 'entering') {
            this.entryDelay -= dt;
            if (this.entryDelay > 0) return;
            this.state = 'moving';
        }

        if (this.path.length === 0) return;

        const targetNode = this.path[this.pathIndex];
        const targetX = gridCenterX(targetNode.x);
        const targetYOffset = targetNode.type === 'seat' ? CONFIG.seatYOffset : 0;
        const targetY = gridCenterY(targetNode.y) + targetYOffset;

        const dx = targetX - this.x;
        const dy = targetY - this.y;
        const dist = Math.sqrt(dx*dx + dy*dy) || 0.0001;

        // Determine speed based on current tile
        const currentGridX = pixelToGridX(this.x);
        const currentGridY = pixelToGridY(this.y);
        let speed = CONFIG.speeds.aisle;
        
        if (currentGridX >= 0 && currentGridX < CONFIG.cols && currentGridY >= 0 && currentGridY < CONFIG.rows) {
            const node = grid[currentGridY][currentGridX];
            if (node.type === 'seat') {
                speed = node.occupied ? CONFIG.speeds.occupiedSeat : CONFIG.speeds.emptySeat;
            }
        }

        // Move
        let moveStep = Math.max(speed * dt * 60, 0.05); // Normalize to frame rate, avoid micro-steps

        // Separation-based collision avoidance to keep students flowing instead of stopping
        let avoidanceX = 0;
        let avoidanceY = 0;
        let avoidanceCount = 0;

        students.forEach(other => {
            if (other === this || other.state === 'seated') return;
            const ax = this.x - other.x;
            const ay = this.y - other.y;
            const d2 = ax*ax + ay*ay;
            const radius = CONFIG.avoidanceRadius;
            if (d2 > 0 && d2 < radius * radius) {
                const d = Math.sqrt(d2);
                const strength = (radius - d) / radius;
                avoidanceX += (ax / d) * strength;
                avoidanceY += (ay / d) * strength;
                avoidanceCount++;
            }
        });

        if (avoidanceCount > 0) {
            const weight = CONFIG.avoidanceWeight;
            const desiredX = dx / dist + (avoidanceX / avoidanceCount) * weight;
            const desiredY = dy / dist + (avoidanceY / avoidanceCount) * weight;
            const desiredLen = Math.sqrt(desiredX*desiredX + desiredY*desiredY) || 1;
            const normalizedX = desiredX / desiredLen;
            const normalizedY = desiredY / desiredLen;
            this.x += normalizedX * moveStep;
            this.y += normalizedY * moveStep;
        } else if (dist < moveStep) {
            this.x = targetX;
            this.y = targetY;
        } else {
            this.x += (dx / dist) * moveStep;
            this.y += (dy / dist) * moveStep;
        }

        this.gridX = pixelToGridX(this.x);
        this.gridY = pixelToGridY(this.y);

        if (dist < moveStep) {
            this.x = targetX;
            this.y = targetY;
            this.gridX = targetNode.x;
            this.gridY = targetNode.y;
            this.pathIndex++;

            if (this.pathIndex >= this.path.length) {
                this.state = 'seated';
                this.targetSeat.node.occupied = true;
                seatedCount++;
                updateUI();
            }
        }
    }

    draw(ctx) {
        if (this.state === 'seated') return;

        // Draw Path
        if (this.path.length > this.pathIndex) {
            ctx.beginPath();
            ctx.strokeStyle = this.color;
            ctx.setLineDash([3, 3]);
            ctx.lineWidth = 2;
            ctx.moveTo(this.x, this.y);
            for (let i = this.pathIndex; i < this.path.length; i++) {
                const node = this.path[i];
                const offsetY = node.type === 'seat' ? CONFIG.seatYOffset : 0;
                ctx.lineTo(
                    gridCenterX(node.x),
                    gridCenterY(node.y) + offsetY
                );
            }
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // Draw Student
        ctx.beginPath();
        ctx.fillStyle = this.color;
        ctx.arc(this.x, this.y, 8, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 1;
        ctx.stroke();
    }
}

// --- A* Pathfinding ---
function findPath(startX, startY, endX, endY) {
    let openSet = [];
    let closedSet = new Set();
    
    // Reset nodes for pathfinding
    for(let y=0; y<CONFIG.rows; y++) {
        for(let x=0; x<CONFIG.cols; x++) {
            grid[y][x].g = 0;
            grid[y][x].f = 0;
            grid[y][x].parent = null;
        }
    }

    let startNode = grid[startY][startX];
    let endNode = grid[endY][endX];
    
    openSet.push(startNode);

    while (openSet.length > 0) {
        // Find lowest f_score
        let winner = 0;
        for (let i = 0; i < openSet.length; i++) {
            if (openSet[i].f < openSet[winner].f) {
                winner = i;
            }
        }
        let current = openSet[winner];

        if (current === endNode) {
            let path = [];
            let temp = current;
            while (temp.parent) {
                path.push(temp);
                temp = temp.parent;
            }
            return path.reverse();
        }

        openSet.splice(winner, 1);
        closedSet.add(current);

        let neighbors = getNeighbors(current);
        for (let i = 0; i < neighbors.length; i++) {
            let neighbor = neighbors[i];

            if (closedSet.has(neighbor) || neighbor.type === 'wall') continue;

            // Calculate cost
            let tentativeG = current.g + neighbor.getCost();

            let newPath = false;
            if (openSet.includes(neighbor)) {
                if (tentativeG < neighbor.g) {
                    neighbor.g = tentativeG;
                    newPath = true;
                }
            } else {
                neighbor.g = tentativeG;
                newPath = true;
                openSet.push(neighbor);
            }

            if (newPath) {
                neighbor.h = Math.abs(neighbor.x - endX) + Math.abs(neighbor.y - endY);
                neighbor.f = neighbor.g + neighbor.h;
                neighbor.parent = current;
            }
        }
    }
    return []; // No path
}

function getNeighbors(node) {
    let neighbors = [];
    const dirs = [[0,1], [1,0], [0,-1], [-1,0]];
    for (let d of dirs) {
        let nx = node.x + d[0];
        let ny = node.y + d[1];
        if (nx >= 0 && nx < CONFIG.cols && ny >= 0 && ny < CONFIG.rows) {
            const candidate = grid[ny][nx];
            // Students cannot go vertically into seats; they must enter from sides
            if (candidate.type === 'seat' && node.x === candidate.x) continue;
            neighbors.push(candidate);
        }
    }
    return neighbors;
}

// --- Initialization ---
function initGrid() {
    grid = [];
    seats = [];
    
    // Layout definition (1 = seat, 0 = aisle, 2 = wall/front)
    // Simple layout: 3 blocks of seats
    for (let y = 0; y < CONFIG.rows; y++) {
        let row = [];
        for (let x = 0; x < CONFIG.cols; x++) {
            let type = 'aisle';
            
            // Front area (Professor)
            if (y < 2) type = 'front';
            
            // Back area (Entrance)
            else if (y > 17) type = 'aisle';
            
            // Seating blocks
            else {
                // Left Block (x: 2-8)
                if (x >= 2 && x <= 9) type = 'seat';
                // Center Block (x: 12-20)
                else if (x >= 12 && x <= 20) type = 'seat';
                // Right Block (x: 23-30)
                else if (x >= 23 && x <= 30) type = 'seat';
            }
            
            let node = new Node(x, y, type);
            row.push(node);
            
            if (type === 'seat') {
                seats.push({x: x, y: y, node: node});
            }
        }
        grid.push(row);
    }
    
    // Limit seats to 250 if we generated too many
    if (seats.length > 250) {
         // Trim extra seats back to aisle
         for(let i=250; i<seats.length; i++) {
             seats[i].node.type = 'aisle';
         }
         seats = seats.slice(0, 250);
    }
}

function init() {
    canvas = document.getElementById('simCanvas');
    ctx = canvas.getContext('2d');
    initGrid();
    loadHighScore();
    draw();
}

// --- Main Loop ---
function gameLoop(timestamp) {
    if (!isRunning) return;
    if (isPaused) return;

    let dt = (timestamp - lastTime) / 1000;
    lastTime = timestamp;
    
    // Spawn Logic
    if (students.length < seats.length) {
        spawnTimer += dt;
        if (spawnTimer > 0.5) { // Spawn every 0.5s
            spawnTimer = 0;
            // Find random empty seat that hasn't been assigned
            assignSeatToNewStudent();
        }
    }

    // Update Logic
    students.forEach(s => s.update(dt));

    // Draw
    draw();

    // Timer
    updateTimer();

    // Check End Condition
    if (!failTriggered && seatedCount === 0 && elapsedSeconds() >= 10) {
        setStatus('Failure: No seats filled after 10 seconds.', true);
        endGame(false);
        return;
    }

    if (seatedCount >= seats.length) {
        const finishedIn = elapsedSeconds();
        maybeSetHighScore(finishedIn);
        setStatus(`Success: All seats filled in ${formatTime(finishedIn)}.`, true);
        endGame(true);
        return;
    }

    animationId = requestAnimationFrame(gameLoop);
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw Grid
    for (let y = 0; y < CONFIG.rows; y++) {
        for (let x = 0; x < CONFIG.cols; x++) {
            let node = grid[y][x];
            let px = gridOriginX(x);
            let py = gridOriginY(y);

            if (node.type === 'seat') {
                const seatOffsetY = CONFIG.seatYOffset;
                ctx.fillStyle = node.occupied ? '#ff4b4b' : '#e0e0e0'; // Red if occupied, Grey if empty
                ctx.fillRect(px + 2, py + 2 + seatOffsetY, CONFIG.cellSize - 4, CONFIG.cellSize - 4);
                // Armrests
                ctx.fillStyle = '#999';
                ctx.fillRect(px + 2, py + CONFIG.cellSize - 4 + seatOffsetY, CONFIG.cellSize - 4, 2);
            } else if (node.type === 'front') {
                ctx.fillStyle = '#d1d1d1';
                ctx.fillRect(px, py, CONFIG.cellSize, CONFIG.cellSize);
            } else {
                // Aisle
                ctx.fillStyle = '#fff';
                // ctx.fillRect(px, py, CONFIG.cellSize, CONFIG.cellSize); // Keep white/clean
            }
        }
    }

    // Draw Professor Area
    ctx.fillStyle = '#333';
    ctx.fillRect(200, CONFIG.renderOffsetY + 10, 400, 20); // Blackboard
    ctx.fillStyle = '#8B4513';
    // Keep the desk within the front row so it doesn't overlap the first seating row
    ctx.fillRect(350, CONFIG.renderOffsetY + 25, 100, 18); // Desk

    // Draw Entrances
    ctx.fillStyle = '#00cc66';
    ENTRANCES.forEach(e => {
        ctx.fillRect(gridOriginX(e.x), gridOriginY(e.y) + 15, CONFIG.cellSize, 10);
    });

    // Draw Students
    students.forEach(s => s.draw(ctx));
}

function updateUI() {
    document.getElementById('seated-count').innerText = seatedCount;
    const progress = Math.floor((seatedCount / seats.length) * 100);
    document.getElementById('progress').innerText = progress;
}

// --- Controls ---
window.toggleGame = function() {
    let btn = document.getElementById('action-btn');

    if (!isRunning && btn.innerText.includes("START")) {
        // Start Game
        initGrid(); // Reset grid
        students = [];
        seatedCount = 0;
        updateUI();
        isRunning = true;
        isPaused = false;
        failTriggered = false;
        document.getElementById('status-msg').style.display = 'none';
        startTime = Date.now();
        lastTime = performance.now();
        btn.innerText = "RESET";
        btn.className = ""; // Remove start class (make it red)
        document.getElementById('pause-btn').disabled = false;
        document.getElementById('pause-btn').innerText = 'PAUSE';
        gameLoop(performance.now());
    } else {
        // Reset Game
        endGame(false, true);
    }
};

window.togglePause = function() {
    if (!isRunning) return;
    isPaused = !isPaused;
    const pauseBtn = document.getElementById('pause-btn');
    if (isPaused) {
        pauseBtn.innerText = 'RESUME';
        pausedAt = Date.now();
    } else {
        pauseBtn.innerText = 'PAUSE';
        const pauseDuration = Date.now() - pausedAt;
        startTime += pauseDuration; // Keep timer accurate
        lastTime = performance.now();
        animationId = requestAnimationFrame(gameLoop);
    }
};

function endGame(isSuccess, fromReset) {
    isRunning = false;
    isPaused = false;
    failTriggered = !isSuccess && !fromReset;
    cancelAnimationFrame(animationId);
    initGrid();
    students = [];
    seatedCount = 0;
    updateUI();
    draw();
    document.getElementById('timer').innerText = "00:00";
    document.getElementById('action-btn').innerText = isSuccess ? "RESET (Finished!)" : "START SIMULATION";
    document.getElementById('action-btn').className = "start";
    document.getElementById('pause-btn').disabled = true;
}

function updateTimer() {
    const elapsed = elapsedSeconds();
    document.getElementById('timer').innerText = formatTime(elapsed);
}

function elapsedSeconds() {
    return Math.floor((Date.now() - startTime) / 1000);
}

function formatTime(totalSeconds) {
    const mins = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const secs = (totalSeconds % 60).toString().padStart(2, '0');
    return `${mins}:${secs}`;
}

function setStatus(message, show) {
    const status = document.getElementById('status-msg');
    status.innerText = message;
    status.style.display = show ? 'block' : 'none';
}

function loadHighScore() {
    const stored = localStorage.getItem('auditorium_high_score');
    if (stored) {
        highScore = parseInt(stored, 10);
        document.getElementById('high-score').innerText = formatTime(highScore);
    }
}

function maybeSetHighScore(seconds) {
    if (highScore === null || seconds < highScore) {
        highScore = seconds;
        localStorage.setItem('auditorium_high_score', seconds.toString());
        document.getElementById('high-score').innerText = formatTime(seconds);
    }
}

function assignSeatToNewStudent() {
    let availableSeats = seats.filter(s => !s.assigned);
    if (availableSeats.length === 0) return;

    let target = availableSeats[Math.floor(Math.random() * availableSeats.length)];

    // Friend logic: 1/250 chance new student tries to sit next to previous assignment
    const recentSeat = students.length > 0 ? students[students.length - 1].targetSeat : null;
    const chance = Math.floor(Math.random() * 250) === 0;
    if (chance && recentSeat) {
        const neighborOptions = [
            {x: recentSeat.x - 1, y: recentSeat.y},
            {x: recentSeat.x + 1, y: recentSeat.y}
        ];
        const neighbor = neighborOptions.find(pos => {
            return seats.some(s => !s.assigned && s.x === pos.x && s.y === pos.y);
        });
        if (neighbor) {
            const buddySeat = seats.find(s => !s.assigned && s.x === neighbor.x && s.y === neighbor.y);
            if (buddySeat) {
                target = buddySeat;
            }
        }
    }

    target.assigned = true;
    students.push(new Student(target));
}

// Initialize on load
window.onload = init;

</script>
</body>
</html>
    """
