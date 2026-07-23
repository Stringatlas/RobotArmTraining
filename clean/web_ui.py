"""
Web UI for go_to_click robot arm control.

Renders the HTML/CSS/JavaScript interface for the camera feed and arm control.
"""


def render_page():
    """Render the complete HTML page with video feed and controls."""
    html = r'''
    <html>
    <head>
        <title>Go To Click</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            input { margin: 4px; }
            button { margin: 4px; padding: 6px 12px; background: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0052a3; }
            .row { margin-top: 10px; }
            .hint { margin: 8px 0 12px 0; line-height: 1.5; }
            .video-wrap { position: relative; display: inline-block; margin-bottom: 20px; }
            #video { border: 2px solid black; cursor: crosshair; display: block; }
            #selection_box { position: absolute; border: 2px dashed #0077ff; background: rgba(0,119,255,0.08); display: none; pointer-events: none; }
            #command_input { width: 420px; padding: 8px; font-size: 15px; border: 1px solid #ccc; border-radius: 4px; }
            #command_status { margin-top: 6px; font-size: 13px; color: #555; min-height: 18px; }
            #dropoff_status { display: inline-block; margin-left: 16px; font-size: 13px; color: #c06000; font-weight: bold; }
            pre { font-size: 12px; background: #f5f5f5; padding: 10px; border-radius: 4px; max-height: 300px; overflow: auto; }
            label { margin-right: 12px; }
            .slider-container { display: flex; align-items: center; gap: 10px; margin: 10px 0; }
            .slider-container input[type="range"] { flex: 1; max-width: 300px; }
            .slider-value { min-width: 50px; font-weight: bold; }
            h1 { color: #333; }
            .control-section { background: #f9f9f9; padding: 15px; border-radius: 4px; margin-bottom: 15px; }
            .info-text { color: #666; font-size: 14px; margin-top: 5px; }
        </style>
    </head>
    <body>
        <h1>Robot Arm Control - Click Target</h1>

        <div class="control-section">
            <h3>Pick &amp; Place Command</h3>
            <div style="display: flex; gap: 8px; align-items: center;">
                <input type="text" id="command_input" placeholder='e.g. "pick up coke can and put at point 8"'>
                <button onclick="executeCommand()" style="background:#27ae60;">Execute</button>
            </div>
            <div id="command_status"></div>
        </div>

        <p>
            Click image to pick a target. &nbsp;
            <b>Shift+Drag</b> to mark the <span style="color:#c06000;font-weight:bold;">drop-off zone</span> (darkest point in region).
            <span id="dropoff_status">Drop-off: not set</span>
        </p>

        <div class="video-wrap">
            <img id="video" src="/video" width="640" height="480">
            <div id="selection_box"></div>
        </div>

        <div class="control-section">
            <h3>Motion Options</h3>
            <label><input type="checkbox" id="auto_move"> Auto move arm on click</label>
            <label><input type="checkbox" id="perform_pick"> Move from hover to pick pose</label>
        </div>

        <div class="control-section">
            <h3>Approach Angles</h3>
            <div class="slider-container">
                <label>Vertical (0=flat, 90=vertical):</label>
                <input type="range" id="approach_vertical" min="0" max="90" value="45" step="1">
                <span class="slider-value" id="vertical_display">45</span>°
            </div>
            <div class="info-text">Controls pitch: how much the gripper approaches from the side vs. straight down</div>

            <div class="slider-container">
                <label>Horizontal Offset (-90 to +90):</label>
                <input type="range" id="approach_horizontal" min="-90" max="90" value="0" step="1">
                <span class="slider-value" id="horizontal_display">0</span>°
            </div>
            <div class="info-text">Controls rotation around vertical axis: positive = right, negative = left (relative to target direction)</div>

            <div class="slider-container">
                <label>Control Point Length (×start-end distance):</label>
                <input type="range" id="control_length" min="0.3" max="4.0" value="0.67" step="0.05">
                <span class="slider-value" id="control_length_display">0.67</span>×
            </div>
            <div class="info-text">How far the Bézier control points reach from each endpoint, as a multiple of the start→end distance</div>

            <div class="slider-container">
                <label>Approach Angle Scale (0=straight, 1=full heading):</label>
                <input type="range" id="heading_angle_scale" min="0" max="1" value="1.0" step="0.05">
                <span class="slider-value" id="heading_angle_scale_display">1.00</span>×
            </div>
            <div class="info-text">Scales how much of the curve's tangent the gripper actually points along at the end. Lower = gentler approach angle while the path stays wide.</div>

            <div class="slider-container">
                <label>Heading Start (0=start of curve, 1=end):</label>
                <input type="range" id="heading_start_t" min="0" max="1" value="0.6" step="0.05">
                <span class="slider-value" id="heading_start_t_display">0.60</span>
            </div>
            <div class="info-text">Where along the curve the gripper begins tracing the heading. Higher = starts later (only near the end). Keep ≥0.5 for aggressive curves to avoid fast wrist rotation at the apex.</div>
        </div>

        <div class="control-section">
            <h3>Motion Control</h3>
            <button onclick="resetArm()">Reset Arm (Safe)</button>
            <button onclick="startMotion()">Start Motion</button>
            <button onclick="pauseMotion()">Pause</button>
            <button onclick="resumeMotion()">Resume</button>
            <button onclick="stopMotion()">Stop</button>
            <button onclick="refreshPose()">Show Current TCP</button>
        </div>

        <div class="control-section">
            <h3>Trajectory Visualization</h3>
            <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                <div>
                    <p style="font-size: 12px; color: #666;">Top-down view (xy plane) — labels show every 5th waypoint (x, y, z)</p>
                    <canvas id="trajectoryCanvas" width="620" height="360" style="border: 1px solid #ccc; background: #f9f9f9; display: block;"></canvas>
                </div>
                <div>
                    <p style="font-size: 12px; color: #666;">Side view - height profile (xz plane)</p>
                    <canvas id="trajectoryCanvasXZ" width="620" height="360" style="border: 1px solid #ccc; background: #f9f9f9; display: block;"></canvas>
                </div>
            </div>
        </div>

        <div class="control-section">
            <h3>Manual Point Input (Testing)</h3>
            <p style="font-size: 12px; color: #666;">Skip camera targeting - directly specify a 3D point to approach</p>
            <div class="slider-container">
                <label>X (m):</label>
                <input type="number" id="manual_x" value="-0.30" step="0.01" style="flex: 1; max-width: 150px;">
                <span style="min-width: 30px; text-align: right;"></span>
            </div>
            <div class="slider-container">
                <label>Y (m):</label>
                <input type="number" id="manual_y" value="0.10" step="0.01" style="flex: 1; max-width: 150px;">
                <span style="min-width: 30px; text-align: right;"></span>
            </div>
            <div class="slider-container">
                <label>Z (m):</label>
                <input type="number" id="manual_z" value="0.20" step="0.01" style="flex: 1; max-width: 150px;">
                <span style="min-width: 30px; text-align: right;"></span>
            </div>
            <div style="display: flex; gap: 10px; margin-top: 10px;">
                <button onclick="submitManualPoint()" style="flex: 1;">Compute Pose from Manual Point</button>
                <button onclick="startMotion()" style="flex: 1; background-color: #4CAF50; color: white;">Start Motion</button>
            </div>
        </div>

        <div class="row">
            <strong>Selected pixel:</strong> <span id="pixel_text">not selected</span>
        </div>

        <div class="row">
            <div id="log_pose" style="background: #f0f0f0; padding: 10px; border-radius: 4px; margin: 10px 0;">Target info will appear here</div>
        </div>

        <details>
            <summary>Debug Info (click to expand)</summary>
            <pre id="result">Click a target in the RGB image.</pre>
        </details>

        <script>
            const img = document.getElementById("video");
            const selectionBox = document.getElementById("selection_box");
            const RGB_WIDTH = 640;
            const RGB_HEIGHT = 480;
            let lastClickPayload = null;
            let isDragging = false;
            let dragStart = null;

            function screenToImage(event) {
                const rect = img.getBoundingClientRect();
                const x_display = event.clientX - rect.left;
                const y_display = event.clientY - rect.top;
                const x = Math.round(x_display * (RGB_WIDTH / rect.width));
                const y = Math.round(y_display * (RGB_HEIGHT / rect.height));
                return { x, y };
            }

            function submitTarget(u, v, options = {}) {
                isManualPointActive = false;
                const payload = {
                    u,
                    v,
                    auto_move: options.auto_move ?? document.getElementById("auto_move").checked,
                    perform_pick: options.perform_pick ?? document.getElementById("perform_pick").checked,
                    vertical_angle_deg: Number(document.getElementById("approach_vertical").value),
                    horizontal_angle_deg: Number(document.getElementById("approach_horizontal").value),
                    control_length_factor: Number(document.getElementById("control_length").value),
                    heading_angle_scale: Number(document.getElementById("heading_angle_scale").value),
                    heading_start_t: Number(document.getElementById("heading_start_t").value)
                };
                lastClickPayload = payload;

                fetch("/click", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                })
                .then(r => r.json())
                .then(data => {
                    document.getElementById("result").innerText = JSON.stringify(data, null, 2);
                    if (data.ok) {
                        document.getElementById("pixel_text").innerText = "(" + data.pixel[0] + ", " + data.pixel[1] + ")";
                        try {
                            const approach = data.approach_tip_base_m;
                            const target = data.target_pose_m;
                            const rawTarget = data.raw_target_base_m ?? target;
                            const pickup = data.pick_pose;
                            const v_angle = data.approach_vertical_deg ?? 0.0;
                            const h_angle = data.approach_horizontal_deg ?? 0.0;
                            const wrist = data.wrist_command_pose ?? data.approach_pose ?? {};
                            const targetText = `Target pre-offset:  (${rawTarget[0].toFixed(3)}, ${rawTarget[1].toFixed(3)}, ${rawTarget[2].toFixed(3)}) m\n` +
                                `Target post-offset: (${target[0].toFixed(3)}, ${target[1].toFixed(3)}, ${target[2].toFixed(3)}) m`;
                            const anglesText = `Vertical: ${v_angle.toFixed(1)}° | Horizontal: ${h_angle.toFixed(1)}°`;
                            const wristText = `Wrist: (${Number(wrist.x).toFixed(3)}, ${Number(wrist.y).toFixed(3)}, ${Number(wrist.z).toFixed(3)})`;
                            document.getElementById("log_pose").innerText = targetText + "\n" + anglesText + "\n" + wristText;
                            updateVisualization(data);
                        } catch (e) {
                            console.log(e)
                        }
                    }
                })
                .catch(err => {
                    document.getElementById("result").innerText = String(err);
                });
            }

            img.addEventListener("mousedown", function(event) {
                if (!event.shiftKey) return;
                event.preventDefault();
                isDragging = true;
                dragStart = screenToImage(event);
                selectionBox.style.display = "block";
            });

            img.addEventListener("mousemove", function(event) {
                if (!isDragging || !dragStart) return;
                const pos = screenToImage(event);
                const x1 = Math.min(dragStart.x, pos.x);
                const y1 = Math.min(dragStart.y, pos.y);
                const x2 = Math.max(dragStart.x, pos.x);
                const y2 = Math.max(dragStart.y, pos.y);
                selectionBox.style.left = x1 + "px";
                selectionBox.style.top = y1 + "px";
                selectionBox.style.width = (x2 - x1 + 1) + "px";
                selectionBox.style.height = (y2 - y1 + 1) + "px";
            });

            img.addEventListener("mouseup", async function(event) {
                if (!isDragging || !dragStart) return;
                isDragging = false;
                const pos = screenToImage(event);
                const x1 = dragStart.x, y1 = dragStart.y;
                const x2 = pos.x, y2 = pos.y;
                selectionBox.style.display = "none";
                dragStart = null;
                if (Math.abs(x2 - x1) < 2 && Math.abs(y2 - y1) < 2) return;

                try {
                    const resp = await fetch("/set_dropoff_region", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({x1: x1, y1: y1, x2: x2, y2: y2})
                    });
                    const data = await resp.json();
                    if (data.ok) {
                        const [bx, by, bz] = data.base_xyz;
                        document.getElementById("dropoff_status").innerText =
                            `Drop-off: px(${data.pixel[0]}, ${data.pixel[1]}) | base(${bx.toFixed(3)}, ${by.toFixed(3)}, ${bz.toFixed(3)}) m`;
                    } else {
                        document.getElementById("dropoff_status").innerText = "Drop-off error: " + data.error;
                    }
                } catch (e) {
                    document.getElementById("dropoff_status").innerText = "Drop-off error: " + String(e);
                }
            });

            // Update display values when sliders change
            document.getElementById("approach_vertical").addEventListener("input", function(event) {
                document.getElementById("vertical_display").innerText = event.target.value;
            });

            document.getElementById("approach_horizontal").addEventListener("input", function(event) {
                document.getElementById("horizontal_display").innerText = event.target.value;
            });

            document.getElementById("control_length").addEventListener("input", function(event) {
                document.getElementById("control_length_display").innerText = event.target.value;
            });

            document.getElementById("heading_angle_scale").addEventListener("input", function(event) {
                document.getElementById("heading_angle_scale_display").innerText = Number(event.target.value).toFixed(2);
            });

            document.getElementById("heading_start_t").addEventListener("input", function(event) {
                document.getElementById("heading_start_t_display").innerText = Number(event.target.value).toFixed(2);
            });

            img.addEventListener("click", function(event) {
                if (event.shiftKey) return;
                const coords = screenToImage(event);
                submitTarget(coords.x, coords.y);
            });

            async function executeCommand() {
                const text = document.getElementById("command_input").value.trim();
                if (!text) return;
                const status = document.getElementById("command_status");
                status.style.color = "#555";
                status.innerText = "Executing: " + text + " …";
                try {
                    const resp = await fetch("/command", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({
                            text,
                            vertical_angle_deg: Number(document.getElementById("approach_vertical").value),
                            horizontal_angle_deg: Number(document.getElementById("approach_horizontal").value),
                            control_length_factor: Number(document.getElementById("control_length").value),
                            heading_angle_scale: Number(document.getElementById("heading_angle_scale").value),
                            heading_start_t: Number(document.getElementById("heading_start_t").value),
                        })
                    });
                    const data = await resp.json();
                    document.getElementById("result").innerText = JSON.stringify(data, null, 2);
                    if (data.ok) {
                        status.style.color = "#27ae60";
                        status.innerText = `Done — picked '${data.detection.name}', placed at (${data.dropoff_base_xyz.map(v=>v.toFixed(3)).join(", ")}) m`;
                        if (data.pick_target) updateVisualization(data.pick_target);
                    } else {
                        status.style.color = "#c0392b";
                        status.innerText = "Error: " + data.error;
                    }
                } catch (e) {
                    status.style.color = "#c0392b";
                    status.innerText = "Error: " + String(e);
                }
            }

            document.getElementById("command_input").addEventListener("keydown", function(e) {
                if (e.key === "Enter") executeCommand();
            });

            function resetArm() {
                fetch("/reset_arm", { method: "POST" })
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById("result").innerText = JSON.stringify(data, null, 2);
                    })
                    .catch(err => {
                        document.getElementById("result").innerText = String(err);
                    });
            }

            function startMotion() {
                if (!lastClickPayload) {
                    document.getElementById("result").innerText = "Click a target first, then press Start Motion.";
                    return;
                }

                const payload = {
                    ...lastClickPayload,
                    auto_move: true,
                    perform_pick: document.getElementById("perform_pick").checked,
                    vertical_angle_deg: Number(document.getElementById("approach_vertical").value),
                    horizontal_angle_deg: Number(document.getElementById("approach_horizontal").value),
                    control_length_factor: Number(document.getElementById("control_length").value),
                    heading_angle_scale: Number(document.getElementById("heading_angle_scale").value),
                    heading_start_t: Number(document.getElementById("heading_start_t").value)
                };

                fetch("/click", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                })
                .then(r => r.json())
                .then(data => {
                    document.getElementById("result").innerText = JSON.stringify(data, null, 2);
                })
                .catch(err => {
                    document.getElementById("result").innerText = String(err);
                });
            }

            function pauseMotion() {
                fetch('/pause_motion', { method: 'POST' })
                    .then(r => r.json()).then(d => { document.getElementById('result').innerText = JSON.stringify(d, null, 2); })
                    .catch(e => { document.getElementById('result').innerText = String(e); });
            }

            function resumeMotion() {
                fetch('/resume_motion', { method: 'POST' })
                    .then(r => r.json()).then(d => { document.getElementById('result').innerText = JSON.stringify(d, null, 2); })
                    .catch(e => { document.getElementById('result').innerText = String(e); });
            }

            function stopMotion() {
                fetch('/stop_motion', { method: 'POST' })
                    .then(r => r.json()).then(d => { document.getElementById('result').innerText = JSON.stringify(d, null, 2); })
                    .catch(e => { document.getElementById('result').innerText = String(e); });
            }

            function refreshPose() {
                fetch("/current_pose")
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById("result").innerText = JSON.stringify(data, null, 2);
                    })
                    .catch(err => {
                        document.getElementById("result").innerText = String(err);
                    });
            }

            // Recompute target when angle sliders change (if a target exists)
            function recomputeAngles() {
                fetch("/recompute_target", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        vertical_angle_deg: Number(document.getElementById("approach_vertical").value),
                        horizontal_angle_deg: Number(document.getElementById("approach_horizontal").value),
                    control_length_factor: Number(document.getElementById("control_length").value),
                    heading_angle_scale: Number(document.getElementById("heading_angle_scale").value),
                    heading_start_t: Number(document.getElementById("heading_start_t").value)
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.ok) {
                        document.getElementById("result").innerText = JSON.stringify(data, null, 2);
                        document.getElementById("pixel_text").innerText = "(" + data.pixel[0] + ", " + data.pixel[1] + ")";
                        try {
                            const approach = data.approach_tip_base_m;
                            const v_angle = data.approach_vertical_deg ?? 0.0;
                            const h_angle = data.approach_horizontal_deg ?? 0.0;
                            const wrist = data.wrist_command_pose ?? data.approach_pose ?? {};
                            const approachText = `Approach: (${approach[0].toFixed(3)}, ${approach[1].toFixed(3)}, ${approach[2].toFixed(3)}) m`;
                            const anglesText = `V: ${v_angle.toFixed(1)}° | H: ${h_angle.toFixed(1)}°`;
                            const wristText = `Wrist: (${Number(wrist.x).toFixed(3)}, ${Number(wrist.y).toFixed(3)}, ${Number(wrist.z).toFixed(3)})`;
                            document.getElementById("log_pose").innerText = approachText + " | " + anglesText + " | " + wristText;
                            updateVisualization(data);
                        } catch (e) {
                            // ignore
                        }
                    }
                })
                .catch(err => {
                    // ignore transient errors
                });
            }

            // ===== MANUAL POINT INPUT =====

            let lastManualPoint = null;
            let isManualPointActive = false;

            function submitManualPoint() {
                const x = Number(document.getElementById("manual_x").value);
                const y = Number(document.getElementById("manual_y").value);
                const z = Number(document.getElementById("manual_z").value);

                lastManualPoint = { x, y, z };
                isManualPointActive = true;

                const payload = {
                    x: x,
                    y: y,
                    z: z,
                    auto_move: false,
                    perform_pick: false,
                    vertical_angle_deg: Number(document.getElementById("approach_vertical").value),
                    horizontal_angle_deg: Number(document.getElementById("approach_horizontal").value),
                    control_length_factor: Number(document.getElementById("control_length").value),
                    heading_angle_scale: Number(document.getElementById("heading_angle_scale").value),
                    heading_start_t: Number(document.getElementById("heading_start_t").value)
                };

                console.log("Submitting manual point:", payload);

                fetch("/manual_point", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                })
                .then(r => r.json())
                .then(data => {
                    document.getElementById("result").innerText = JSON.stringify(data, null, 2);
                    if (data.ok) {
                        document.getElementById("pixel_text").innerText = "Manual: (" + x.toFixed(3) + ", " + y.toFixed(3) + ", " + z.toFixed(3) + ")";
                        try {
                            const approach = data.approach_tip_base_m;
                            const target = data.target_pose_m;
                            const rawTarget = data.raw_target_base_m ?? target;
                            const v_angle = data.approach_vertical_deg ?? 0.0;
                            const h_angle = data.approach_horizontal_deg ?? 0.0;
                            const wrist = data.wrist_command_pose ?? data.approach_pose ?? {};
                            const targetText = `Target pre-offset:  (${rawTarget[0].toFixed(3)}, ${rawTarget[1].toFixed(3)}, ${rawTarget[2].toFixed(3)}) m\n` +
                                `Target post-offset: (${target[0].toFixed(3)}, ${target[1].toFixed(3)}, ${target[2].toFixed(3)}) m`;
                            const anglesText = `Vertical: ${v_angle.toFixed(1)}° | Horizontal: ${h_angle.toFixed(1)}°`;
                            const wristText = `Wrist: (${Number(wrist.x).toFixed(3)}, ${Number(wrist.y).toFixed(3)}, ${Number(wrist.z).toFixed(3)})`;
                            document.getElementById("log_pose").innerText = targetText + "\n" + anglesText + "\n" + wristText;
                            updateVisualization(data);
                        } catch (e) {
                            console.log(e);
                        }
                    } else {
                        document.getElementById("log_pose").innerText = "Error: " + (data.error || "Unknown error");
                    }
                })
                .catch(err => {
                    document.getElementById("result").innerText = "Error: " + String(err);
                });
            }

            function recomputeManualPoint() {
                if (!lastManualPoint) return;

                const payload = {
                    x: lastManualPoint.x,
                    y: lastManualPoint.y,
                    z: lastManualPoint.z,
                    auto_move: false,
                    perform_pick: false,
                    vertical_angle_deg: Number(document.getElementById("approach_vertical").value),
                    horizontal_angle_deg: Number(document.getElementById("approach_horizontal").value),
                    control_length_factor: Number(document.getElementById("control_length").value),
                    heading_angle_scale: Number(document.getElementById("heading_angle_scale").value),
                    heading_start_t: Number(document.getElementById("heading_start_t").value)
                };

                fetch("/manual_point", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                })
                .then(r => r.json())
                .then(data => {
                    if (data.ok) {
                        try {
                            updateVisualization(data);
                        } catch (e) {
                            console.log(e);
                        }
                    }
                })
                .catch(err => {
                    // silently ignore errors during recompute
                });
            }

            function startMotion() {
                if (isManualPointActive) {
                    if (!lastManualPoint) {
                        alert("No manual point set. Compute a pose first.");
                        return;
                    }
                    const payload = {
                        x: lastManualPoint.x,
                        y: lastManualPoint.y,
                        z: lastManualPoint.z,
                        auto_move: true,
                        perform_pick: document.getElementById("perform_pick").checked,
                        vertical_angle_deg: Number(document.getElementById("approach_vertical").value),
                        horizontal_angle_deg: Number(document.getElementById("approach_horizontal").value),
                    control_length_factor: Number(document.getElementById("control_length").value),
                    heading_angle_scale: Number(document.getElementById("heading_angle_scale").value),
                    heading_start_t: Number(document.getElementById("heading_start_t").value)
                    };
                    fetch("/manual_point", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    })
                    .then(r => r.json())
                    .catch(err => {
                        document.getElementById("result").innerText = "Motion error: " + String(err);
                    });
                } else {
                    if (!lastClickPayload) {
                        alert("No target selected. Click on the image first.");
                        return;
                    }
                    const payload = Object.assign({}, lastClickPayload, {
                        auto_move: true,
                        perform_pick: document.getElementById("perform_pick").checked,
                        vertical_angle_deg: Number(document.getElementById("approach_vertical").value),
                        horizontal_angle_deg: Number(document.getElementById("approach_horizontal").value),
                        control_length_factor: Number(document.getElementById("control_length").value),
                        heading_angle_scale: Number(document.getElementById("heading_angle_scale").value),
                        heading_start_t: Number(document.getElementById("heading_start_t").value)
                    });
                    fetch("/click", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    })
                    .then(r => r.json())
                    .catch(err => {
                        document.getElementById("result").innerText = "Motion error: " + String(err);
                    });
                }
            }

            // ===== TRAJECTORY VISUALIZATION =====

            function drawTrajectory(vizData) {
                const canvas = document.getElementById("trajectoryCanvas");
                if (!canvas || !vizData) return;

                const ctx = canvas.getContext("2d");
                const width = canvas.width;
                const height = canvas.height;

                // Clear canvas
                ctx.fillStyle = "#f9f9f9";
                ctx.fillRect(0, 0, width, height);

                const bounds = vizData.bounds;
                const xRange = bounds.max_x - bounds.min_x;
                const yRange = bounds.max_y - bounds.min_y;

                // Reserve a 200px column on the right for coordinate labels
                const labelColWidth = 200;
                const plotWidth = width - labelColWidth;

                // Equal scale on both axes so the curve isn't distorted
                const scale = Math.min(
                    (plotWidth - 40) / (xRange || 1),
                    (height - 40) / (yRange || 1)
                );

                function worldToCanvas(x, y) {
                    const cx = (x - bounds.min_x) * scale + 20;
                    const cy = height - ((y - bounds.min_y) * scale + 20);
                    return { cx, cy };
                }

                // Draw grid
                ctx.strokeStyle = "#e0e0e0";
                ctx.lineWidth = 0.5;
                for (let i = 0; i <= 10; i++) {
                    const x = bounds.min_x + (i / 10) * xRange;
                    const y = bounds.min_y + (i / 10) * yRange;
                    const p1x = worldToCanvas(x, bounds.min_y);
                    const p2x = worldToCanvas(x, bounds.max_y);
                    const p1y = worldToCanvas(bounds.min_x, y);
                    const p2y = worldToCanvas(bounds.max_x, y);

                    ctx.beginPath();
                    ctx.moveTo(p1x.cx, p1x.cy);
                    ctx.lineTo(p2x.cx, p2x.cy);
                    ctx.stroke();

                    ctx.beginPath();
                    ctx.moveTo(p1y.cx, p1y.cy);
                    ctx.lineTo(p2y.cx, p2y.cy);
                    ctx.stroke();
                }

                // Draw spline curve (green line)
                ctx.strokeStyle = "#00cc00";
                ctx.lineWidth = 2;
                ctx.beginPath();
                let firstPoint = true;
                for (const point of vizData.spline_points) {
                    const p = worldToCanvas(point[0], point[1]);
                    if (firstPoint) {
                        ctx.moveTo(p.cx, p.cy);
                        firstPoint = false;
                    } else {
                        ctx.lineTo(p.cx, p.cy);
                    }
                }
                ctx.stroke();

                // Draw start point (large circle)
                const start = worldToCanvas(vizData.start[0], vizData.start[1]);
                ctx.fillStyle = "#ff6600";
                ctx.beginPath();
                ctx.arc(start.cx, start.cy, 8, 0, 2 * Math.PI);
                ctx.fill();
                ctx.strokeStyle = "#cc5500";
                ctx.lineWidth = 2;
                ctx.stroke();

                // Draw end point (large circle)
                const end = worldToCanvas(vizData.end[0], vizData.end[1]);
                ctx.fillStyle = "#0066ff";
                ctx.beginPath();
                ctx.arc(end.cx, end.cy, 8, 0, 2 * Math.PI);
                ctx.fill();
                ctx.strokeStyle = "#0044cc";
                ctx.lineWidth = 2;
                ctx.stroke();

                // Draw sample points (blue boxes) - these lie on the green Bézier curve
                ctx.fillStyle = "#3399ff";
                ctx.strokeStyle = "#0066ff";
                ctx.lineWidth = 1.5;
                const boxSize = 6;
                for (let i = 0; i < vizData.sample_points.length; i++) {
                    const point = vizData.sample_points[i];
                    const p = worldToCanvas(point[0], point[1]);
                    ctx.fillRect(p.cx - boxSize/2, p.cy - boxSize/2, boxSize, boxSize);
                    ctx.strokeRect(p.cx - boxSize/2, p.cy - boxSize/2, boxSize, boxSize);
                }

                // Draw coordinate labels for every 5th point with leader lines (avoid overlap)
                ctx.font = "10px monospace";
                for (let i = 0; i < vizData.sample_points.length; i += 5) {
                    const point = vizData.sample_points[i];
                    const p = worldToCanvas(point[0], point[1]);
                    const point3d = vizData.sample_points_3d && vizData.sample_points_3d[i];
                    if (!point3d) continue;

                    // Stagger labels vertically; two lines per waypoint (pos + rpy)
                    const labelY = 14 + (i / 5) * 26;
                    const posLabel = `${i}: (${point3d.x.toFixed(3)}, ${point3d.y.toFixed(3)}, ${point3d.z.toFixed(3)})`;
                    const rpyLabel = (point3d.rx !== undefined)
                        ? `   rpy(${point3d.rx.toFixed(1)}, ${point3d.ry.toFixed(1)}, ${point3d.rz.toFixed(1)})°`
                        : "";

                    // Leader line from point to label row
                    ctx.strokeStyle = "#cccccc";
                    ctx.lineWidth = 0.5;
                    ctx.beginPath();
                    ctx.moveTo(p.cx, p.cy);
                    ctx.lineTo(width - 195, labelY - 3);
                    ctx.stroke();

                    ctx.fillStyle = "#444";
                    ctx.fillText(posLabel, width - 190, labelY);
                    if (rpyLabel) {
                        ctx.fillStyle = "#a05000";
                        ctx.fillText(rpyLabel, width - 190, labelY + 11);
                    }
                }

                // Draw control points (red)
                if (vizData.control_p1 && vizData.control_p2) {
                    const cp1 = worldToCanvas(vizData.control_p1[0], vizData.control_p1[1]);
                    const cp2 = worldToCanvas(vizData.control_p2[0], vizData.control_p2[1]);

                    // Draw control point circles
                    ctx.fillStyle = "#ff0000";
                    ctx.beginPath();
                    ctx.arc(cp1.cx, cp1.cy, 5, 0, 2 * Math.PI);
                    ctx.fill();

                    ctx.beginPath();
                    ctx.arc(cp2.cx, cp2.cy, 5, 0, 2 * Math.PI);
                    ctx.fill();

                    // Draw lines from control points to start/end
                    ctx.strokeStyle = "#ff6666";
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(start.cx, start.cy);
                    ctx.lineTo(cp1.cx, cp1.cy);
                    ctx.stroke();

                    ctx.beginPath();
                    ctx.moveTo(end.cx, end.cy);
                    ctx.lineTo(cp2.cx, cp2.cy);
                    ctx.stroke();

                    // Label control points
                    ctx.fillStyle = "#ff0000";
                    ctx.font = "11px Arial";
                    ctx.fillText("p1", cp1.cx + 8, cp1.cy - 8);
                    ctx.fillText("p2", cp2.cx + 8, cp2.cy - 8);
                }

                // Draw legend
                ctx.fillStyle = "#333";
                ctx.font = "12px Arial";
                ctx.fillText("Start", start.cx + 15, start.cy);
                ctx.fillText("End", end.cx + 15, end.cy);
            }

            function drawTrajectoryXZ(vizData) {
                const canvas = document.getElementById("trajectoryCanvasXZ");
                if (!canvas || !vizData) return;

                const ctx = canvas.getContext("2d");
                const width = canvas.width;
                const height = canvas.height;

                // Clear canvas
                ctx.fillStyle = "#f9f9f9";
                ctx.fillRect(0, 0, width, height);

                const bounds = vizData.bounds;
                const xRange = bounds.max_x - bounds.min_x;
                const zRange = bounds.max_z - bounds.min_z;

                // Reserve a 200px column on the right for coordinate labels
                const labelColWidth = 200;
                const plotWidth = width - labelColWidth;

                // Equal scale on both axes so the curve isn't distorted
                const scale = Math.min(
                    (plotWidth - 40) / (xRange || 1),
                    (height - 40) / (zRange || 1)
                );

                // Map world (x, z) -> canvas. cy uses z (height).
                function worldToCanvas(x, z) {
                    const cx = (x - bounds.min_x) * scale + 20;
                    const cy = height - ((z - bounds.min_z) * scale + 20);
                    return { cx, cy };
                }

                // Draw grid
                ctx.strokeStyle = "#e0e0e0";
                ctx.lineWidth = 0.5;
                for (let i = 0; i <= 10; i++) {
                    const x = bounds.min_x + (i / 10) * xRange;
                    const z = bounds.min_z + (i / 10) * zRange;
                    const gx1 = worldToCanvas(x, bounds.min_z);
                    const gx2 = worldToCanvas(x, bounds.max_z);
                    const gz1 = worldToCanvas(bounds.min_x, z);
                    const gz2 = worldToCanvas(bounds.max_x, z);

                    ctx.beginPath();
                    ctx.moveTo(gx1.cx, gx1.cy);
                    ctx.lineTo(gx2.cx, gx2.cy);
                    ctx.stroke();

                    ctx.beginPath();
                    ctx.moveTo(gz1.cx, gz1.cy);
                    ctx.lineTo(gz2.cx, gz2.cy);
                    ctx.stroke();
                }

                // Draw spline curve (green line) using x and z
                ctx.strokeStyle = "#00cc00";
                ctx.lineWidth = 2;
                ctx.beginPath();
                let firstPoint = true;
                for (const point of vizData.spline_points) {
                    const p = worldToCanvas(point[0], point[2]);
                    if (firstPoint) {
                        ctx.moveTo(p.cx, p.cy);
                        firstPoint = false;
                    } else {
                        ctx.lineTo(p.cx, p.cy);
                    }
                }
                ctx.stroke();

                // Start point (orange circle)
                const start = worldToCanvas(vizData.start[0], vizData.start[2]);
                ctx.fillStyle = "#ff6600";
                ctx.beginPath();
                ctx.arc(start.cx, start.cy, 8, 0, 2 * Math.PI);
                ctx.fill();
                ctx.strokeStyle = "#cc5500";
                ctx.lineWidth = 2;
                ctx.stroke();

                // End point (blue circle)
                const end = worldToCanvas(vizData.end[0], vizData.end[2]);
                ctx.fillStyle = "#0066ff";
                ctx.beginPath();
                ctx.arc(end.cx, end.cy, 8, 0, 2 * Math.PI);
                ctx.fill();
                ctx.strokeStyle = "#0044cc";
                ctx.lineWidth = 2;
                ctx.stroke();

                // Draw sample points (blue boxes) on the curve
                ctx.fillStyle = "#3399ff";
                ctx.strokeStyle = "#0066ff";
                ctx.lineWidth = 1.5;
                const boxSize = 6;
                for (let i = 0; i < vizData.sample_points.length; i++) {
                    const point = vizData.sample_points[i];
                    const p = worldToCanvas(point[0], point[2]);
                    ctx.fillRect(p.cx - boxSize/2, p.cy - boxSize/2, boxSize, boxSize);
                    ctx.strokeRect(p.cx - boxSize/2, p.cy - boxSize/2, boxSize, boxSize);
                }

                // Coordinate labels for every 5th point (staggered column with leader lines)
                ctx.font = "10px monospace";
                for (let i = 0; i < vizData.sample_points.length; i += 5) {
                    const point = vizData.sample_points[i];
                    const p = worldToCanvas(point[0], point[2]);
                    const point3d = vizData.sample_points_3d && vizData.sample_points_3d[i];
                    if (!point3d) continue;

                    const labelY = 14 + (i / 5) * 26;
                    const posLabel = `${i}: (${point3d.x.toFixed(3)}, ${point3d.y.toFixed(3)}, ${point3d.z.toFixed(3)})`;
                    const rpyLabel = (point3d.rx !== undefined)
                        ? `   rpy(${point3d.rx.toFixed(1)}, ${point3d.ry.toFixed(1)}, ${point3d.rz.toFixed(1)})°`
                        : "";

                    ctx.strokeStyle = "#cccccc";
                    ctx.lineWidth = 0.5;
                    ctx.beginPath();
                    ctx.moveTo(p.cx, p.cy);
                    ctx.lineTo(width - 195, labelY - 3);
                    ctx.stroke();

                    ctx.fillStyle = "#444";
                    ctx.fillText(posLabel, width - 190, labelY);
                    if (rpyLabel) {
                        ctx.fillStyle = "#a05000";
                        ctx.fillText(rpyLabel, width - 190, labelY + 11);
                    }
                }

                // Draw control points (red) with connector lines and labels
                if (vizData.control_p1 && vizData.control_p2) {
                    const cp1 = worldToCanvas(vizData.control_p1[0], vizData.control_p1[2]);
                    const cp2 = worldToCanvas(vizData.control_p2[0], vizData.control_p2[2]);

                    ctx.fillStyle = "#ff0000";
                    ctx.beginPath();
                    ctx.arc(cp1.cx, cp1.cy, 5, 0, 2 * Math.PI);
                    ctx.fill();
                    ctx.beginPath();
                    ctx.arc(cp2.cx, cp2.cy, 5, 0, 2 * Math.PI);
                    ctx.fill();

                    ctx.strokeStyle = "#ff6666";
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(start.cx, start.cy);
                    ctx.lineTo(cp1.cx, cp1.cy);
                    ctx.stroke();
                    ctx.beginPath();
                    ctx.moveTo(end.cx, end.cy);
                    ctx.lineTo(cp2.cx, cp2.cy);
                    ctx.stroke();

                    ctx.fillStyle = "#ff0000";
                    ctx.font = "11px Arial";
                    ctx.fillText("p1", cp1.cx + 8, cp1.cy - 8);
                    ctx.fillText("p2", cp2.cx + 8, cp2.cy - 8);
                }

                // Draw legend
                ctx.fillStyle = "#333";
                ctx.font = "12px Arial";
                ctx.fillText("Start", start.cx + 15, start.cy);
                ctx.fillText("End", end.cx + 15, end.cy);
            }

            // Store last visualization for updates
            let lastVizData = null;

            function updateVisualization(data) {
                // Extract trajectory visualization from response
                if (data.visualization) {
                    lastVizData = data.visualization;
                    drawTrajectory(lastVizData);
                    drawTrajectoryXZ(lastVizData);
                }
            }

            function onAngleChange() {
                if (isManualPointActive) {
                    recomputeManualPoint();
                } else {
                    recomputeAngles();
                }
            }

            document.getElementById("approach_vertical").addEventListener("input", onAngleChange);
            document.getElementById("approach_horizontal").addEventListener("input", onAngleChange);
            document.getElementById("control_length").addEventListener("input", onAngleChange);
            document.getElementById("heading_angle_scale").addEventListener("input", onAngleChange);
            document.getElementById("heading_start_t").addEventListener("input", onAngleChange);
        </script>
    </body>
    </html>
    '''

    return html
