# Migration Guide: Original → Clean Version

## What Changed

### Directory Structure

**Before:**
```
robot_vision/
├── go_to_click.py           (1295 lines, monolithic)
└── other files...
```

**After:**
```
robot_vision/
├── go_to_click.py           (original, unchanged)
└── clean/
    ├── go_to_click.py       (refactored, ~700 lines)
    ├── pose_calculation.py  (pose math, ~280 lines)
    ├── web_ui.py           (web interface, ~440 lines)
    ├── __init__.py
    ├── README.md
    └── MIGRATION_GUIDE.md   (this file)
```

## New Features

### 1. Dual-Angle Approach Control

The original single "approach angle" slider (0-90°) is now split into two:

| Feature | Before | After |
|---------|--------|-------|
| **Vertical Control** | Single slider 0-90° | Dedicated slider 0-90° |
| **Horizontal Control** | None | New slider -90° to +90° |
| **Flexibility** | Limited | Full 3D approach direction control |

### 2. Code Organization

| Responsibility | Before | After |
|---|---|---|
| Pose calculations | Mixed in main file | Dedicated module |
| Web UI | 1000+ lines HTML in main | Separate module |
| Flask app | Monolithic | Clean orchestration |
| Testability | Hard to unit test | Easy to test modules independently |

### 3. Improved Logging

CSV now records both angles:
```csv
..., vertical_angle_deg, horizontal_angle_deg
..., 45.0, 0.0
..., 45.0, 15.0
```

## How to Migrate

### Option 1: Run Both Versions
Keep using the original while testing the new one:

```bash
# Original (existing workflow)
cd robot_vision
python go_to_click.py

# New version (parallel testing)
cd robot_vision/clean
python go_to_click.py  # Use different port if needed
```

### Option 2: Switch to Clean Version

1. **Update any scripts** that call go_to_click endpoints:
   - Change `approach_angle_deg` → `vertical_angle_deg` in requests
   - Add `horizontal_angle_deg` parameter (default 0)

2. **Update any automation code**:
   ```python
   # Before
   requests.post("http://localhost:5000/click", json={
       "u": 320, "v": 240,
       "approach_angle_deg": 45
   })

   # After
   requests.post("http://localhost:5000/click", json={
       "u": 320, "v": 240,
       "vertical_angle_deg": 45,
       "horizontal_angle_deg": 0
   })
   ```

3. **Update logging/analysis scripts** to handle new CSV columns

## Backward Compatibility

### API Differences

| Endpoint | Parameter | Before | After |
|---|---|---|---|
| /click | angle param | `approach_angle_deg` | `vertical_angle_deg`, `horizontal_angle_deg` |
| /recompute_target | | `approach_angle_deg` | `vertical_angle_deg`, `horizontal_angle_deg` |
| Response | angle fields | `"approach_incline_deg"` | `"approach_vertical_deg"`, `"approach_horizontal_deg"` |

### CSV Log Format

**Before:**
```csv
timestamp,...,approach_incline_deg
1234567890,...,45.0
```

**After:**
```csv
timestamp,...,vertical_angle_deg,horizontal_angle_deg
1234567890,...,45.0,0.0
```

Old logs are still readable but won't have the new columns.

## Testing the New Angles

### Vertical Angle (0-90°)

Test the vertical angle by setting horizontal to 0:

1. Click a target point
2. Set **Vertical** slider to 0° (flat approach)
3. Observe gripper approaches horizontally
4. Set to 90° (vertical)
5. Observe gripper approaches from above

### Horizontal Angle (-90° to +90°)

Test horizontal offset by varying while keeping vertical fixed:

1. Click a target point
2. Set **Vertical** to 45° (middle)
3. Vary **Horizontal** slider
4. Watch the approach direction rotate around the vertical axis

The gripper stays at the same distance from the target, but rotates around it.

### Combined Example

For a target at [0.0, 0.5, 0.2]:
- **V=0, H=0**: Approach from the side, horizontally along y-axis
- **V=45, H=0**: Approach at 45° angle along y-axis
- **V=45, H=45**: Approach at 45° angle, rotated 45° around z-axis
- **V=90, H=0**: Approach from directly above

## Performance

| Metric | Before | After |
|---|---|---|
| File size (main) | 1295 lines | 700 lines |
| Lines of code (web UI HTML) | 280 lines in Python | 400 lines (proper HTML file) |
| Module testability | Low (monolithic) | High (separate modules) |
| Startup time | Same | Same |
| Runtime performance | Same | Same |

## Known Differences

### Removed Features
- None - all original functionality preserved

### Changed Behavior
- Angle slider now has two independent controls instead of one
- Web UI visual improvements (slightly different layout)
- CSV logging includes two angle columns instead of one

### New Behavior
- Recompute target happens in real-time as you adjust sliders
- Horizontal angle lets you approach from different sides
- Better visual feedback in web UI

## Troubleshooting Migration

### Import Errors
```
ModuleNotFoundError: No module named 'pose_calculation'
```
Make sure you're running from the `clean/` directory:
```bash
cd robot_vision/clean
python go_to_click.py
```

### Angle Not Affecting Motion
- Horizontal angle only works with custom angle input
- Default surface normal estimation ignores horizontal angle
- Use the slider after clicking a target to override

### Old Scripts Fail
Scripts using the old endpoint need updates:
```python
# Replace this
data = {"approach_angle_deg": 45}

# With this
data = {"vertical_angle_deg": 45, "horizontal_angle_deg": 0}
```

## Integration with Other Code

### Using with Splines Library
```python
from splines import ArmTrajectory
# The clean version is compatible with spline trajectory execution
# No changes needed to use together
```

### Custom Motion Planning
Extract pose_calculation module:
```python
from robot_vision.clean.pose_calculation import compute_approach_direction
# Use in your own scripts
```

## Rollback

To revert to original version:
```bash
cd robot_vision
python go_to_click.py  # Use original
# The clean/ folder doesn't interfere with original
```

Both versions can coexist since they're in different directories.

## Questions?

Refer to `README.md` in the clean/ folder for complete documentation.
