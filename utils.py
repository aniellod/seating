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
        button { padding: 8px 16px; background: #ff4b4b; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
        button:hover { background: #ff3333; }
        button.start { background: #00cc66; }
        button.start:hover { background: #00bb55; }
        #status-msg { position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.7); color: white; padding: 5px 15px; border-radius: 15px; font-size: 12px; display: none; }
    </style>
</head>
<body>

<div id="game-container">
    <div id="ui-layer">
        <div class="stat-box">⏱️ Time: <span id="timer">00:00</span></div>
        <div class="stat-box">🪑 Seated: <span id="seated-count">0</span>/250</div>
        <button id="action-btn" class="start" onclick="toggleGame()">START SIMULATION</button>
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
    speeds: {
        aisle: 2.0,
        emptySeat: 1.5, // 75%
        occupiedSeat: 0.5 // 25%
    }
};

// --- Game State ---
let canvas, ctx;
let grid = [];
let students = [];
let seats = [];
let isRunning = false;
let startTime;
let animationId;
let seatedCount = 0;
let spawnTimer = 0;
let lastTime = 0;

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
        this.x = entrance.x * CONFIG.cellSize + CONFIG.cellSize/2;
        this.y = entrance.y * CONFIG.cellSize + CONFIG.cellSize/2;
        this.gridX = entrance.x;
        this.gridY = entrance.y;
        
        this.targetSeat = targetSeat;
        this.path = [];
        this.pathIndex = 0;
        this.state = 'entering'; // entering, moving, seated
        this.color = `hsl(${Math.random() * 360}, 70%, 50%)`;
        
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

        if (this.path.length === 0) return;

        const targetNode = this.path[this.pathIndex];
        const targetX = targetNode.x * CONFIG.cellSize + CONFIG.cellSize/2;
        const targetY = targetNode.y * CONFIG.cellSize + CONFIG.cellSize/2;

        const dx = targetX - this.x;
        const dy = targetY - this.y;
        const dist = Math.sqrt(dx*dx + dy*dy);

        // Determine speed based on current tile
        const currentGridX = Math.floor(this.x / CONFIG.cellSize);
        const currentGridY = Math.floor(this.y / CONFIG.cellSize);
        let speed = CONFIG.speeds.aisle;
        
        if (currentGridX >= 0 && currentGridX < CONFIG.cols && currentGridY >= 0 && currentGridY < CONFIG.rows) {
            const node = grid[currentGridY][currentGridX];
            if (node.type === 'seat') {
                speed = node.occupied ? CONFIG.speeds.occupiedSeat : CONFIG.speeds.emptySeat;
            }
        }

        // Move
        const moveStep = speed * dt * 60; // Normalize to frame rate
        
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
        } else {
            this.x += (dx / dist) * moveStep;
            this.y += (dy / dist) * moveStep;
            this.gridX = Math.floor(this.x / CONFIG.cellSize);
            this.gridY = Math.floor(this.y / CONFIG.cellSize);
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
                ctx.lineTo(
                    this.path[i].x * CONFIG.cellSize + CONFIG.cellSize/2,
                    this.path[i].y * CONFIG.cellSize + CONFIG.cellSize/2
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
            neighbors.push(grid[ny][nx]);
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
    draw();
}

// --- Main Loop ---
function gameLoop(timestamp) {
    if (!isRunning) return;
    
    let dt = (timestamp - lastTime) / 1000;
    lastTime = timestamp;
    
    // Spawn Logic
    if (students.length < seats.length) {
        spawnTimer += dt;
        if (spawnTimer > 0.5) { // Spawn every 0.5s
            spawnTimer = 0;
            // Find random empty seat that hasn't been assigned
            let availableSeats = seats.filter(s => !s.assigned);
            if (availableSeats.length > 0) {
                let target = availableSeats[Math.floor(Math.random() * availableSeats.length)];
                target.assigned = true;
                students.push(new Student(target));
            }
        }
    }

    // Update Logic
    students.forEach(s => s.update(dt));

    // Draw
    draw();

    // Timer
    let elapsed = Math.floor((Date.now() - startTime) / 1000);
    let mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
    let secs = (elapsed % 60).toString().padStart(2, '0');
    document.getElementById('timer').innerText = `${mins}:${secs}`;

    // Check End Condition
    if (seatedCount >= seats.length) {
        isRunning = false;
        document.getElementById('action-btn').innerText = "RESET (Finished!)";
        document.getElementById('action-btn').className = "start";
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
            let px = x * CONFIG.cellSize;
            let py = y * CONFIG.cellSize;
            
            if (node.type === 'seat') {
                ctx.fillStyle = node.occupied ? '#ff4b4b' : '#e0e0e0'; // Red if occupied, Grey if empty
                ctx.fillRect(px + 2, py + 2, CONFIG.cellSize - 4, CONFIG.cellSize - 4);
                // Armrests
                ctx.fillStyle = '#999';
                ctx.fillRect(px + 2, py + CONFIG.cellSize - 4, CONFIG.cellSize - 4, 2);
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
    ctx.fillRect(200, 10, 400, 20); // Blackboard
    ctx.fillStyle = '#8B4513';
    ctx.fillRect(350, 35, 100, 30); // Desk
    
    // Draw Entrances
    ctx.fillStyle = '#00cc66';
    ENTRANCES.forEach(e => {
        ctx.fillRect(e.x * CONFIG.cellSize, e.y * CONFIG.cellSize + 15, CONFIG.cellSize, 10);
    });

    // Draw Students
    students.forEach(s => s.draw(ctx));
}

function updateUI() {
    document.getElementById('seated-count').innerText = seatedCount;
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
        startTime = Date.now();
        lastTime = performance.now();
        btn.innerText = "RESET";
        btn.className = ""; // Remove start class (make it red)
        gameLoop(performance.now());
    } else {
        // Reset Game
        isRunning = false;
        cancelAnimationFrame(animationId);
        initGrid();
        students = [];
        seatedCount = 0;
        updateUI();
        draw();
        document.getElementById('timer').innerText = "00:00";
        btn.innerText = "START SIMULATION";
        btn.className = "start";
    }
};

// Initialize on load
window.onload = init;

</script>
</body>
</html>
    """
