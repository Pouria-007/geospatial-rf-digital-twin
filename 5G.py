import omni.usd
import omni.ui as ui
from pxr import Usd, UsdGeom, Gf, Vt
import math
import random

# =============================================================================
# 5G RF SIGNAL HEATMAP VISUALIZATION - UPGRADED
# Version: 2.0 (Gradient Heatmap)
# Changes: Smooth color gradients, inverse square law signal propagation
# =============================================================================

# ┌─────────────────────────────────────────────────────────────────────────┐
# │ USER CONFIGURATION - CHANGE THESE VALUES                                │
# └─────────────────────────────────────────────────────────────────────────┘

# Signal Range (in meters)
MAX_SIGNAL_RANGE = 150.0    # Maximum distance signal reaches (meters)
MIN_SIGNAL_RANGE = 5.0      # Minimum distance from tower (meters)

# Visualization Density
POINTS_PER_TOWER = 400      # Number of dots per antenna (more = denser heatmap)
                            # Recommended: 200-600
                            # Higher values = smoother but slower

# Point Appearance
POINT_SIZE = 4.0            # Size of each dot (1-10)

# ┌─────────────────────────────────────────────────────────────────────────┐
# │ END OF USER CONFIGURATION                                               │
# └─────────────────────────────────────────────────────────────────────────┘

# Create UI Window with Sliders
def create_control_window():
    """Create a floating control panel with sliders"""
    global MAX_SIGNAL_RANGE, MIN_SIGNAL_RANGE, POINTS_PER_TOWER, POINT_SIZE
    
    window = ui.Window("5G Heatmap Controls", width=400, height=300)
    
    with window.frame:
        with ui.VStack(spacing=10, style={"margin": 10}):
            ui.Label("5G RF Signal Heatmap Controls", style={"font_size": 18})
            ui.Spacer(height=5)
            
            # Max Range Slider
            with ui.HStack(spacing=5):
                ui.Label("Max Range (m):", width=150)
                max_range_slider = ui.FloatSlider(min=50, max=2000, width=150)
                max_range_slider.model.set_value(MAX_SIGNAL_RANGE)
                max_range_label = ui.Label(f"{MAX_SIGNAL_RANGE:.0f}m", width=50)
            
            def on_max_range_changed(model):
                global MAX_SIGNAL_RANGE
                MAX_SIGNAL_RANGE = model.as_float
                max_range_label.text = f"{MAX_SIGNAL_RANGE:.0f}m"
            
            max_range_slider.model.add_value_changed_fn(on_max_range_changed)
            
            # Min Range Slider
            with ui.HStack(spacing=5):
                ui.Label("Min Range (m):", width=150)
                min_range_slider = ui.FloatSlider(min=1, max=50, width=150)
                min_range_slider.model.set_value(MIN_SIGNAL_RANGE)
                min_range_label = ui.Label(f"{MIN_SIGNAL_RANGE:.0f}m", width=50)
            
            def on_min_range_changed(model):
                global MIN_SIGNAL_RANGE
                MIN_SIGNAL_RANGE = model.as_float
                min_range_label.text = f"{MIN_SIGNAL_RANGE:.0f}m"
            
            min_range_slider.model.add_value_changed_fn(on_min_range_changed)
            
            # Points Per Tower Slider
            with ui.HStack(spacing=5):
                ui.Label("Points Per Tower:", width=150)
                points_slider = ui.IntSlider(min=100, max=4000, width=150)
                points_slider.model.set_value(int(POINTS_PER_TOWER))
                points_label = ui.Label(f"{int(POINTS_PER_TOWER)}", width=50)
            
            def on_points_changed(model):
                global POINTS_PER_TOWER
                POINTS_PER_TOWER = model.as_int
                points_label.text = f"{POINTS_PER_TOWER}"
            
            points_slider.model.add_value_changed_fn(on_points_changed)
            
            # Point Size Slider
            with ui.HStack(spacing=5):
                ui.Label("Point Size:", width=150)
                size_slider = ui.FloatSlider(min=1, max=10, width=150)
                size_slider.model.set_value(POINT_SIZE)
                size_label = ui.Label(f"{POINT_SIZE:.1f}", width=50)
            
            def on_size_changed(model):
                global POINT_SIZE
                POINT_SIZE = model.as_float
                size_label.text = f"{POINT_SIZE:.1f}"
            
            size_slider.model.add_value_changed_fn(on_size_changed)
            
            ui.Spacer(height=10)
            
            # Refresh Button
            def on_refresh_clicked():
                print("\n🔄 Refreshing heatmap with new settings...")
                generate_heatmap()
            
            ui.Button("Refresh Heatmap", clicked_fn=on_refresh_clicked, height=40)
            
            ui.Spacer(height=5)
            ui.Label("Adjust sliders and click Refresh to update", 
                    style={"font_size": 12, "color": 0xFF888888})
    
    return window

# Show control window
control_window = create_control_window()

def calculate_gradient_color(signal_strength):
    """
    Calculate smooth gradient color based on signal strength
    
    Signal Strength Scale:
        100% = Pure Green (excellent signal)
        50%  = Yellow (medium signal)
        0%   = Red (weak/no signal)
    
    Color transitions:
        0-50%:   Red (1,0,0) → Yellow (1,1,0)
        50-100%: Yellow (1,1,0) → Green (0,1,0)
    
    Args:
        signal_strength: Float 0-100 representing signal quality
    
    Returns:
        Gf.Vec3f: RGB color value (0-1 range)
    """
    # Clamp to 0-100 range
    signal_strength = max(0.0, min(100.0, signal_strength))
    
    if signal_strength > 50.0:
        # Strong signal: Yellow (1,1,0) → Green (0,1,0)
        # As signal increases, reduce red component
        normalized = (signal_strength - 50.0) / 50.0  # 0.0 to 1.0
        r = 1.0 - normalized  # Fade from 1 to 0
        g = 1.0               # Always full green
        b = 0.0
    else:
        # Weak signal: Red (1,0,0) → Yellow (1,1,0)
        # As signal increases, increase green component
        normalized = signal_strength / 50.0  # 0.0 to 1.0
        r = 1.0               # Always full red
        g = normalized        # Fade from 0 to 1
        b = 0.0
    
    return Gf.Vec3f(r, g, b)


def calculate_signal_strength(distance, max_distance=150.0, min_distance=5.0):
    """
    Calculate signal strength - simple inverse relationship
    
    Args:
        distance: Distance from tower in meters
        max_distance: Maximum effective range
        min_distance: Minimum distance (where signal is strongest)
    
    Returns:
        Float 0-100: Signal strength percentage
    """
    # Clamp distance to valid range
    distance = max(min_distance, min(max_distance, distance))
    
    # Linear interpolation: at min_distance = 100%, at max_distance = 0%
    signal_strength = 100.0 * (max_distance - distance) / (max_distance - min_distance)
    
    return max(0.0, min(100.0, signal_strength))


def generate_heatmap():
    """Generate the heatmap visualization"""
    # 1. SETUP (Get or Create the Visualizer)
    stage = omni.usd.get_context().get_stage()
    vis_path = "/World/Signal_Visualizer"

    # DELETE and recreate the prim to force size update
    if stage.GetPrimAtPath(vis_path):
        stage.RemovePrim(vis_path)
    
    # Define creates it fresh
    points_prim = UsdGeom.Points.Define(stage, vis_path)

    # Make it pickable/selectable so you can see it in the stage
    imageable = UsdGeom.Imageable(points_prim)

    # 2. SCAN FOR VISIBLE TOWERS
    tower_positions = []
    print("="*60)
    print("5G RF SIGNAL HEATMAP GENERATOR v2.0")
    print("="*60)
    print("Scanning for VISIBLE Towers...")
    
    for prim in stage.Traverse():
        if "Tower" in prim.GetName() and prim.IsA(UsdGeom.Xformable):
            # Check Visibility
            prim_imageable = UsdGeom.Imageable(prim)
            visibility = prim_imageable.GetVisibilityAttr().Get()
            
            if visibility == 'invisible':
                continue 
                
            xform = UsdGeom.Xformable(prim)
            world_transform = xform.ComputeLocalToWorldTransform(0)
            trans = world_transform.ExtractTranslation()
            tower_positions.append(Gf.Vec3f(trans[0], trans[1], trans[2] + 5.0))
            print(f"  ✓ Found: {prim.GetName()} at ({trans[0]:.1f}, {trans[1]:.1f}, {trans[2]:.1f})")

    print(f"Total Active Towers: {len(tower_positions)}")
    print("-"*60)


    # 3. GENERATE HEATMAP VISUALIZATION
    final_points = []
    final_colors = []

    if not tower_positions:
        print("STATUS: No visible towers detected.")
        print("ACTION: Hiding signal visualizer.")
        
        # ACTION 1: Force Visibility to Invisible
        imageable.GetVisibilityAttr().Set('invisible')
        
        # ACTION 2: Empty the data
        points_prim.GetPointsAttr().Set([])
        points_prim.GetDisplayColorAttr().Set([])
        
        print("✓ Visualizer hidden and cleared.")

    else:
        print(f"Generating signal heatmap for {len(tower_positions)} towers...")
        
        # ACTION 1: Force Visibility to Visible
        imageable.GetVisibilityAttr().Set('inherited')
        
        # Use configuration from top of file
        points_per_tower = POINTS_PER_TOWER
        max_range = MAX_SIGNAL_RANGE
        min_range = MIN_SIGNAL_RANGE
        
        # Generate heatmap points for each tower
        for tower_idx, origin in enumerate(tower_positions):
            print(f"  Processing Tower {tower_idx+1}/{len(tower_positions)}...")
            
            # Base height for signal visualization
            base_height = origin[2] - 5.0
            
            # Create distance bands to ensure we get full gradient
            num_rings = 20  # Number of distance rings
            points_per_ring = points_per_tower // num_rings
            
            for ring_idx in range(num_rings):
                # Calculate distance for this ring (evenly distributed)
                ring_progress = ring_idx / (num_rings - 1) if num_rings > 1 else 0
                dist = min_range + (max_range - min_range) * ring_progress
                
                # Add variation to distance within ring
                for _ in range(points_per_ring):
                    # Random angle (0-360 degrees)
                    angle = random.uniform(0, 2 * math.pi)
                    
                    # Add small random variation to distance (±5m)
                    actual_dist = dist + random.uniform(-5, 5)
                    actual_dist = max(min_range, min(max_range, actual_dist))
                    
                    # Calculate point position
                    target_x = origin[0] + actual_dist * math.cos(angle)
                    target_y = origin[1] + actual_dist * math.sin(angle)
                    
                    # Calculate signal strength at this distance
                    signal_strength = calculate_signal_strength(actual_dist, max_range, min_range)
                    
                    # Get smooth gradient color based on signal strength
                    color = calculate_gradient_color(signal_strength)
                    
                    # Height varies based on signal strength for layered effect
                    # Strong signals (green) show at ground level
                    # Weak signals (red) show at higher elevation
                    if signal_strength > 50.0:
                        # Strong signal: near ground level
                        z_offset = -25.0 + random.uniform(-5, 5)
                    else:
                        # Weak signal: higher elevation with more variation
                        z_offset = -10.0 + random.uniform(-10, 10)
                    
                    target_z = base_height + z_offset
                    
                    # Add point and color to final arrays
                    final_points.append(Gf.Vec3f(target_x, target_y, target_z))
                    final_colors.append(color)
        
        # ACTION 2: Write Data - EXACTLY like v1
        points_prim.GetPointsAttr().Set(final_points)
        points_prim.GetDisplayColorAttr().Set(final_colors)
        
        # Set widths array (one per point) to match POINT_SIZE
        num_points = len(final_points)
        widths_array = [POINT_SIZE] * num_points
        points_prim.GetWidthsAttr().Set(widths_array)
        
        print("SUCCESS: Signal Map Updated with gradient colors")
        
        # Statistics - Check signal strength distribution
        all_signals = []
        for color in final_colors:
            # Reverse engineer signal strength from color
            r, g = color[0], color[1]
            if g == 1.0 and r < 1.0:
                # Green zone (50-100%)
                signal = 50.0 + (1.0 - r) * 50.0
            else:
                # Red-yellow zone (0-50%)
                signal = g * 50.0
            all_signals.append(signal)
        
        min_signal = min(all_signals)
        max_signal = max(all_signals)
        avg_signal = sum(all_signals) / len(all_signals)
        
        # Count colors
        red_count = sum(1 for s in all_signals if s < 33)
        yellow_count = sum(1 for s in all_signals if 33 <= s < 66)
        green_count = sum(1 for s in all_signals if s >= 66)
        
        total_points = len(final_points)
        print("-"*60)
        print(f"✓ Heatmap generated successfully!")
        print(f"  Total points: {total_points:,}")
        print(f"  Points per tower: {points_per_tower}")
        print(f"  Signal range: {min_range}m - {max_range}m")
        print(f"  Point size: {POINT_SIZE}")
        print(f"  Color scheme: Red (weak) → Yellow (medium) → Green (strong)")
        print()
        print(f"  Signal Strength Stats:")
        print(f"    Min: {min_signal:.1f}%  Max: {max_signal:.1f}%  Avg: {avg_signal:.1f}%")
        print(f"  Color Distribution:")
        print(f"    🔴 Red (<33%): {red_count} points ({red_count/total_points*100:.1f}%)")
        print(f"    🟡 Yellow (33-66%): {yellow_count} points ({yellow_count/total_points*100:.1f}%)")
        print(f"    🟢 Green (>66%): {green_count} points ({green_count/total_points*100:.1f}%)")
        print()
        print("To adjust settings, edit the configuration at the top of this script:")
        print("  - MAX_SIGNAL_RANGE: Change signal distance")
        print("  - POINTS_PER_TOWER: Change density (number of dots)")
        print("  - POINT_SIZE: Change dot size")
        print("="*60)

# Run initial generation
print("="*60)
print("5G RF HEATMAP - UI Controls Available")
print("="*60)
print("A control window should appear with sliders.")
print("Adjust the sliders and click 'Refresh Heatmap' to update.")
print("="*60)
print()

generate_heatmap()

