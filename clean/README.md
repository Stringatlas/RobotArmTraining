# Clean Go-To-Click - Refactored Robot Arm Control

This is a refactored version of the robot arm control interface with improved architecture, cleaner separation of concerns, and enhanced approach pose calculation.

## Structure

```
clean/
├── __init__.py              # Package definition
├── pose_calculation.py      # Pose/orientation calculation utilities
├── web_ui.py               # Web UI rendering (HTML/CSS/JS)
├── go_to_click.py          # Main Flask app and orchestration
└── README.md               # This file
```

## Key Improvements

### 1. Modular Architecture
- **pose_calculation.py**: All pose/orientation math is isolated
  - `compute_approach_direction()`: Calculates direction from vertical & horizontal angles
  - `pose_from_tip_and_direction()`: Generates 6-DOF gripper poses
  - Helper functions for normalization, Euler conversions, etc.

- **web_ui.py**: Web interface is separated
  - Single `render_page()` function returns the complete HTML/CSS/JS
  - Easier to modify UI without touching business logic

- **go_to_click.py**: Clean orchestration layer
  - Imports from pose_calculation and web_ui
  - ~700 lines instead of 1300 (much more readable)
  - Clear separation: camera capture → target computation → motion execution

### 2. Dual-Angle Approach Control

Previously: Single slider (vertical angle 0-90°)
Now: Two independent sliders

#### Vertical Angle (0-90°)
- **0°** = Approach horizontally (along the base→target direction)
- **45°** = Balanced approach (default)
- **90°** = Vertical approach (straight down)

#### Horizontal Angle (-90 to +90°)
- **0°** = No lateral offset (approach along base→target direction)
- **+45°** = Rotate 45° right (perpendicular to base→target direction)
- **-45°** = Rotate 45° left (perpendicular, opposite direction)

This allows you to approach the same target from different angles without recomputing the target point.

### How It Works

1. **Compute horizontal direction** (from robot base to target, in xy plane):
   ```
   h_dir = normalize([-target_x, -target_y, 0])
   ```

2. **Create base approach vector** using vertical angle:
   ```
   base_approach = h_dir * cos(vertical_angle) + [0, 0, 1] * sin(vertical_angle)
   ```

3. **Apply horizontal rotation** around z-axis:
   ```
   [cos(h_angle)  -sin(h_angle)  0] [base_approach.x]
   [sin(h_angle)   cos(h_angle)  0] [base_approach.y]
   [0              0             1] [base_approach.z]
   ```

4. **Generate pose** from approach direction with orthonormal frame

## Usage

### Running the Server

```bash
cd robot_vision/clean
python go_to_click.py
```

Then open browser to `http://<robot_ip>:5000`

### Using the Web Interface

1. **Click on the camera feed** to select a target point
2. **Adjust vertical angle** slider:
   - Move right for steeper (more vertical) approach
   - Move left for shallower (more horizontal) approach

3. **Adjust horizontal offset** slider:
   - Positive = approach from the right
   - Negative = approach from the left
   - 0 = straight approach along base→target line

4. Click **"Start Motion"** to move the arm

The target hover and pick poses will update in real-time as you adjust the sliders.

## API Changes from Original

### compute_click_target()

**Before:**
```python
compute_click_target(u, v, approach_angle_deg=None)
```

**After:**
```python
compute_click_target(u, v, vertical_angle_deg=None, horizontal_angle_deg=None)
```

### /click endpoint

**Before:**
```json
{
  "u": 320,
  "v": 240,
  "auto_move": true,
  "perform_pick": false,
  "approach_angle_deg": 45
}
```

**After:**
```json
{
  "u": 320,
  "v": 240,
  "auto_move": true,
  "perform_pick": false,
  "vertical_angle_deg": 45,
  "horizontal_angle_deg": 0
}
```

### /recompute_target endpoint

**Before:**
```json
{
  "approach_angle_deg": 45
}
```

**After:**
```json
{
  "vertical_angle_deg": 45,
  "horizontal_angle_deg": 0
}
```

## Logging

CSV log file includes new columns:
- `vertical_angle_deg`: Vertical approach angle used
- `horizontal_angle_deg`: Horizontal offset angle used

This lets you reproduce exact approach angles from logs.

## Module Reference

### pose_calculation.py

```python
def compute_approach_direction(
    target_point,
    horizontal_direction,
    vertical_angle_deg=45.0,
    horizontal_angle_deg=0.0
) -> np.ndarray
    """Calculate approach direction from two angles."""

def pose_from_tip_and_direction(
    tip_base,
    approach_dir,
    gripper_tip_offset_m=0.1778
) -> Dict
    """Generate 6-DOF pose from tip position and direction."""

def pose_dict_to_list(pose) -> List[float]
    """Convert pose dict to [x, y, z, rz, ry, rx] list."""
```

### web_ui.py

```python
def render_page() -> str
    """Return complete HTML page with UI and JavaScript."""
```

### go_to_click.py

Main Flask application with all endpoints:
- GET `/` - Serve web UI
- GET `/video` - Streaming video feed
- GET `/current_pose` - Get current TCP pose
- POST `/click` - Compute and execute target
- POST `/recompute_target` - Recompute with different angles
- POST `/reset_arm` - Move to safe pose
- POST `/pause_motion`, `/resume_motion`, `/stop_motion` - Motion control
- POST `/select_region` - Find dark spot in region

## Configuration

Edit constants at the top of `go_to_click.py`:

```python
LEBAI_IP = "192.168.10.200"          # Robot IP
T_PATH = "T_base_camera.npy"         # Calibration file
GRIPPER_TIP_OFFSET_M = 0.1778        # Gripper length
APPROACH_CLEARANCE_M = 0.10          # Hover height
PICK_CLEARANCE_M = 0.02              # Pick depth

MOVE_SPEED = 0.5                     # Motion speed (0-1)
MOVE_ACCEL = 1.0                     # Acceleration
```

## Testing

To test pose calculations without a robot:

```python
from pose_calculation import compute_approach_direction, pose_from_tip_and_direction
import numpy as np

# Compute approach direction
target = np.array([-0.3, 0.1, 0.2])
h_dir = np.array([0.95, -0.31, 0])  # Normalized
approach = compute_approach_direction(target, h_dir, vertical_angle_deg=45, horizontal_angle_deg=0)

# Generate pose
pose = pose_from_tip_and_direction(target - approach * 0.1, approach)
print(pose)
```

## Future Enhancements

- [ ] Record and playback approach angle sequences
- [ ] Approach angle presets (flat, angled, vertical)
- [ ] Rotation speed adjustment
- [ ] Trajectory visualization
- [ ] Integration with splines library for smooth multi-point trajectories

## Troubleshooting

### "No color frame available"
- Ensure RealSense camera is connected
- Check USB power

### Poses not updating when sliders change
- Browser may be cached; try hard refresh (Ctrl+Shift+R)
- Check browser console for JavaScript errors

### Motion feels jerky
- Reduce `MOVE_SPEED` (try 0.3-0.4)
- Increase `points_per_segment` in spline trajectory execution

## See Also

- Original version: `../go_to_click.py`
- Splines library: `../../splines/` (for smooth multi-point motion)
- Camera calibration: `fit_camera_to_base.py`
