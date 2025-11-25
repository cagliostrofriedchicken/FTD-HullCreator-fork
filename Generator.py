import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import json
import os
import glob
import numpy as np
import copy

# --- PATH SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- CONFIGURATION ---
DONOR_BLUEPRINT = os.path.join(BASE_DIR, "donor.blueprint")
GUIDMAP_FILES = ["guidmap.json"]
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

OUTPUT_FILENAME = "generated_hull.blueprint"

# --- ROTATION SETTINGS ---
ROT_BEAM      = 0
ROT_LEFT_IN   = 19
ROT_RIGHT_IN  = 17
ROT_LEFT_OUT  = 18
ROT_RIGHT_OUT = 16
ROT_LEFT_STERN  = 19
ROT_RIGHT_STERN = 17

# --- VISUAL THEME ---
THEME_BG = "#C4F4FF"
THEME_GRID_MINOR = "#BCE8F2"
THEME_GRID_MAJOR = "#94C8D6"
THEME_HULL_FILL = "#555555"
THEME_HULL_OUTLINE = "#000000"
THEME_CENTER_LINE = "#FFFFFF"
THEME_PANEL_BG = "#D4D0C8"
THEME_TEXT = "#000000"

class HullDesigner:
    def __init__(self, root):
        self.root = root
        self.root.title("FTD Hull Designer (1.3)")
        self.root.configure(bg=THEME_PANEL_BG)

        self.points = [(0, 0)]

        # Defaults
        self.var_height = tk.IntVar(value=3)
        self.var_undercut = tk.IntVar(value=5)
        self.var_floor = tk.BooleanVar(value=True)
        self.var_save_path = tk.StringVar(value="")
        self.var_material = tk.StringVar(value="Alloy")

        # Logical Dimensions
        self.var_limit_width = tk.IntVar(value=40)
        self.var_limit_length = tk.IntVar(value=100)

        # View State
        self.grid_size = 10.0
        self.offset_x = 0
        self.offset_y = 20
        self.phys_w = 800
        self.phys_h = 600

        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        self.main_container = tk.Frame(self.root, bg=THEME_PANEL_BG)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self.controls = tk.Frame(self.main_container, bg=THEME_PANEL_BG, padx=10, pady=10, relief=tk.RAISED, bd=2)
        self.controls.pack(side=tk.RIGHT, fill=tk.Y)

        lbl_opts = {"bg": THEME_PANEL_BG, "fg": THEME_TEXT, "font": ("MS Sans Serif", 10)}

        # --- PRESET BUTTON ---
        tk.Button(self.controls, text="Load Preset (100m)", command=self.load_preset1,
                  bg=THEME_PANEL_BG, relief=tk.RAISED, bd=2).pack(pady=5, fill=tk.X)

        tk.Button(self.controls, text="Load Preset (200m)", command=self.load_preset2,
                  bg=THEME_PANEL_BG, relief=tk.RAISED, bd=2).pack(pady=5, fill=tk.X)

        # --- STATS ---
        grp_stats = tk.LabelFrame(self.controls, text="Ship Stats", bg=THEME_PANEL_BG, font=("MS Sans Serif", 9, "bold"))
        grp_stats.pack(fill=tk.X, pady=5, padx=5)

        self.lbl_stats_len = tk.Label(grp_stats, text="Length: 0m", width=15, anchor="w", **lbl_opts)
        self.lbl_stats_len.pack(anchor="w")
        self.lbl_stats_beam = tk.Label(grp_stats, text="Beam: 1m", width=15, anchor="w", **lbl_opts)
        self.lbl_stats_beam.pack(anchor="w")

        # --- DESIGN LIMITS ---
        grp_canvas = tk.LabelFrame(self.controls, text="Design Limits", bg=THEME_PANEL_BG, font=("MS Sans Serif", 9))
        grp_canvas.pack(fill=tk.X, pady=5, padx=5)

        tk.Label(grp_canvas, text="Length (m):", **lbl_opts).pack(anchor="w")
        s_l = tk.Spinbox(grp_canvas, from_=20, to=2000, textvariable=self.var_limit_length, width=10)
        s_l.pack(pady=2)
        s_l.bind("<Return>", lambda e: self.force_redraw())
        tk.Button(grp_canvas, text="Resize View", command=self.force_redraw, bg=THEME_PANEL_BG, relief=tk.RAISED, bd=2).pack(pady=5, fill=tk.X)

        # --- GENERATOR SETTINGS ---
        grp_dim = tk.LabelFrame(self.controls, text="Generator Settings", bg=THEME_PANEL_BG, font=("MS Sans Serif", 9))
        grp_dim.pack(fill=tk.X, pady=5, padx=5)

        tk.Label(grp_dim, text="Material:", **lbl_opts).pack(anchor="w")
        # Restricted material options per user request
        mat_options = ["Alloy", "Metal", "Wood", "Heavy", "Stone"]
        self.cbo_mat = ttk.Combobox(grp_dim, textvariable=self.var_material, values=mat_options, state="readonly", width=12)
        self.cbo_mat.pack(pady=2)

        tk.Label(grp_dim, text="Deck Height:", **lbl_opts).pack(anchor="w")
        tk.Spinbox(grp_dim, from_=1, to=50, textvariable=self.var_height, width=10).pack(pady=2)

        tk.Label(grp_dim, text="Undercut Layers:", **lbl_opts).pack(anchor="w")
        tk.Spinbox(grp_dim, from_=0, to=20, textvariable=self.var_undercut, width=10).pack(pady=2)

        # --- ARMOR THICKNESS ---
        self.var_thickness = tk.IntVar(value=2)
        tk.Label(grp_dim, text="Armor Thickness:", **lbl_opts).pack(anchor="w")
        tk.Spinbox(grp_dim, from_=1, to=5, textvariable=self.var_thickness, width=10).pack(pady=2)
        # ----------------------------

        # --- OUTPUT PATH ---
        grp_path = tk.LabelFrame(self.controls, text="Output Location", bg=THEME_PANEL_BG, font=("MS Sans Serif", 9))
        grp_path.pack(fill=tk.X, pady=5, padx=5)

        self.ent_path = tk.Entry(grp_path, textvariable=self.var_save_path, bg="white", width=15)
        self.ent_path.pack(fill=tk.X, padx=5, pady=2)

        tk.Button(grp_path, text="Select Folder...", command=self.select_output_folder,
        bg=THEME_PANEL_BG, relief=tk.RAISED, bd=2).pack(fill=tk.X, padx=5, pady=5)

        tk.Checkbutton(grp_dim, text="Generate Floor", variable=self.var_floor, bg=THEME_PANEL_BG).pack(anchor="w", pady=5)

        # --- EXPORT ---
        self.btn_export = tk.Button(self.controls, text="EXPORT", command=self.run_generator,
                                    bg=THEME_PANEL_BG, relief=tk.RAISED, bd=3, font=("MS Sans Serif", 9, "bold"), pady=5)
        self.btn_export.pack(pady=10, fill=tk.X)

        # --- USAGE INSTRUCTIONS
        self.lbl_info = tk.Label(self.controls, text="L-Click: Add Point\nR-Click: Undo\n\nDraw on either side\nof the center line.",
                                 justify=tk.LEFT, bg=THEME_PANEL_BG, fg="#444")
        self.lbl_info.pack(pady=15)

        # --- WARNING LABEL ---
        self.lbl_warning = tk.Label(self.controls, text="", fg="red", bg=THEME_PANEL_BG, font=("Arial", 10, "bold"))
        self.lbl_warning.pack(pady=5)

        self.lbl_cursor = tk.Label(self.controls, text="Width at Cursor: -\nLength at Cursor: -", width=25, bg=THEME_PANEL_BG, font=("Courier New", 9))
        self.lbl_cursor.pack(side=tk.BOTTOM, pady=5)

        self.canvas_frame = tk.Frame(self.main_container, bg="black", bd=2, relief=tk.SUNKEN)
        self.canvas_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg=THEME_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Button-1>", self.add_point)
        self.canvas.bind("<Button-3>", self.remove_point)
        self.canvas.bind("<Motion>", self.cursor_update)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    saved_path = data.get("save_path", "")
                    if saved_path and os.path.exists(saved_path):
                        self.var_save_path.set(saved_path)
            except Exception as e:
                print(f"Failed to load settings: {e}")

    def save_settings(self):
        data = {
            "save_path": self.var_save_path.get()
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def select_output_folder(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.var_save_path.set(path)
            self.save_settings()

    def check_slope_warning(self):
        has_steep = False
        if len(self.points) > 1:
            for i in range(len(self.points) - 1):
                z1, x1 = self.points[i]
                z2, x2 = self.points[i+1]
                dz = z2 - z1
                dx = abs(x2 - x1)
                if dx > dz:
                    has_steep = True
                    break

        if has_steep:
            self.lbl_warning.config(text="⚠ Angle > 45° Detected\nShape may be erratic.")
        else:
            self.lbl_warning.config(text="")

    def load_preset1(self):
        self.points = [
            (0, 0),   # Tip (1m Beam)
            (4, 2),   # User Point 1
            (14, 4),  # User Point 2
            (39, 6),  # User Point 3
            (69, 6),  # User Point 4
            (85, 5),  # User Point 5
            (100, 3)  # User Point 6
        ]
        self.var_limit_length.set(100)
        self.recalc_view()
        self.update_stats()
        self.check_slope_warning()

    def load_preset2(self):
        self.points = [
            (0, 0),   # Tip (1m Beam)
            (4, 4),   # User Point 1
            (20, 9),  # User Point 2
            (50, 14),  # User Point 3
            (80, 17),  # User Point 4
            (140, 17),  # User Point 5
            (170, 15),  # User Point 6
            (190, 11),  # User Point 7
            (200, 7)  # User Point 8
        ]
        self.var_limit_length.set(200)
        self.recalc_view()
        self.update_stats()
        self.check_slope_warning()

    def on_resize(self, event):
        self.phys_w = event.width
        self.phys_h = event.height
        self.recalc_view()

    def force_redraw(self):
        self.recalc_view()

    def recalc_view(self):
        try:
            log_len = int(self.var_limit_length.get())
        except ValueError:
            return

        if self.phys_w <= 1 or self.phys_h <= 1: return

        padding_px = 40
        available_h = self.phys_h - padding_px
        if available_h < 10: available_h = 10

        self.grid_size = available_h / log_len

        available_w = self.phys_w
        total_width_blocks = available_w / self.grid_size
        half_width = int(total_width_blocks / 2)
        self.var_limit_width.set(half_width)

        self.offset_x = 0
        self.offset_y = 20

        self.draw_grid()
        self.redraw_shape()
        self.update_stats()

    def to_screen(self, gx, gz):
        log_w_half = int(self.var_limit_width.get())
        center_screen_x = self.offset_x + (log_w_half * self.grid_size)

        sx = center_screen_x + (gx * self.grid_size)
        sy = self.offset_y + (gz * self.grid_size)
        return sx, sy

    def to_grid(self, sx, sy):
        log_w_half = int(self.var_limit_width.get())
        center_screen_x = self.offset_x + (log_w_half * self.grid_size)

        dist_px = sx - center_screen_x
        gx = dist_px / self.grid_size
        gz = (sy - self.offset_y) / self.grid_size
        return gx, gz

    def draw_grid(self):
        self.canvas.delete("grid")

        log_w_half = int(self.var_limit_width.get())
        log_h = int(self.var_limit_length.get())
        center_x = self.offset_x + (log_w_half * self.grid_size)

        start_x = 0
        end_x = self.phys_w
        start_y = self.offset_y
        end_y = self.offset_y + (log_h * self.grid_size)

        for i in range(log_w_half * 2 + 1):
            xr = center_x + (i * self.grid_size)
            if xr <= end_x:
                is_major = i % 10 == 0
                color = THEME_GRID_MAJOR if is_major else THEME_GRID_MINOR
                if is_major or self.grid_size > 3:
                    self.canvas.create_line(xr, start_y, xr, end_y, fill=color, tags="grid")
            xl = center_x - (i * self.grid_size)
            if xl >= start_x:
                is_major = i % 10 == 0
                color = THEME_GRID_MAJOR if is_major else THEME_GRID_MINOR
                if is_major or self.grid_size > 3:
                    self.canvas.create_line(xl, start_y, xl, end_y, fill=color, tags="grid")

        for i in range(log_h + 1):
            y = start_y + (i * self.grid_size)
            is_major = i % 10 == 0
            color = THEME_GRID_MAJOR if is_major else THEME_GRID_MINOR
            if is_major or self.grid_size > 3:
                self.canvas.create_line(start_x, y, end_x, y, fill=color, tags="grid")

        self.canvas.create_line(center_x, start_y, center_x, end_y, fill=THEME_CENTER_LINE, width=2, dash=(6, 4), tags="grid")
        self.canvas.create_text(center_x, start_y - 10, text="BOW", fill="#444", font=("Arial", 10, "bold"), tags="grid")
        self.canvas.create_text(center_x, end_y + 10, text="STERN", fill="#444", font=("Arial", 10, "bold"), tags="grid")

    def _cursor_to_point(self, sx, sz):
        raw_gx, raw_gz = self.to_grid(sx, sz)
        gx = int(round(abs(raw_gx)))
        gz = int(round(raw_gz))
        if gz < 0: gz = 0
        return (gz, gx)

    def cursor_update(self, event):
        gz, gx = self._cursor_to_point(event.x, event.y)

        # Update Cursor position text
        width_m, length_m = gx * 2 + 1, gz
        max_places = max(len(str(self.var_limit_length.get())), len(str(self.offset_y)))
        self.lbl_cursor.config(text=f"Width at Cursor: {width_m:0>{max_places}}m\nLength at Cursor: {length_m:0>{max_places}}m")

        # Render line preview
        self.canvas.delete("preview")
        if gz > self.points[-1][0]:
            real_point_pos = self.to_screen(self.points[-1][1], self.points[-1][0])
            mirror_point_pos = self.to_screen(-self.points[-1][1], self.points[-1][0])

            self.canvas.create_line(real_point_pos, self.to_screen(gx, gz), tags="preview", fill="light grey")
            self.canvas.create_line(mirror_point_pos, self.to_screen(-gx, gz), tags="preview", fill="light grey")

    def update_stats(self):
        if not self.points:
            l, b = 0, 0
        else:
            l = self.points[-1][0]
            max_x = 0
            for z, x in self.points:
                if x > max_x: max_x = x
            b = max_x * 2 + 1
        self.lbl_stats_len.config(text=f"Length: {l}m")
        self.lbl_stats_beam.config(text=f"Beam: {b}m")

    def add_point(self, event):
        point = self._cursor_to_point(event.x, event.y)
        if not self.points or point[0] > self.points[-1][0]:
            self.points.append(point)
            self.redraw_shape()
            self.update_stats()
            self.check_slope_warning()

    def remove_point(self, event):
        if len(self.points) > 1:
            self.points.pop()
            self.redraw_shape()
            self.update_stats()
            self.check_slope_warning()

    def redraw_shape(self):
        self.canvas.delete("shape")
        self.canvas.delete("points")
        if not self.points: return

        poly_points = []
        for z, x in self.points:
            sx, sy = self.to_screen(x, z)
            poly_points.append((sx, sy))
        for z, x in reversed(self.points):
            sx, sy = self.to_screen(-x, z)
            poly_points.append((sx, sy))

        if len(poly_points) > 2:
            self.canvas.create_polygon(poly_points, fill=THEME_HULL_FILL, outline=THEME_HULL_OUTLINE, width=2, tags="shape")

        for z, x in self.points:
            rx, ry = self.to_screen(x, z)
            self.canvas.create_oval(rx-2, ry-2, rx+2, ry+2, fill="#BBB", outline="black", tags="points")
            lx, ly = self.to_screen(-x, z)
            self.canvas.create_oval(lx-2, ly-2, lx+2, ly+2, fill="#BBB", outline="black", tags="points")

    def run_generator(self):
        if len(self.points) < 2: return
        max_z = self.points[-1][0]
        z_coords = [p[0] for p in self.points]
        x_coords = [p[1] for p in self.points]
        full_z = np.arange(max_z + 1)
        full_x = np.interp(full_z, z_coords, x_coords)
        hull_profile = np.round(full_x).astype(int)

        height = int(self.var_height.get())
        undercut = int(self.var_undercut.get())
        do_floor = self.var_floor.get()
        center_offset = int(self.var_limit_width.get())
        save_path = self.var_save_path.get()
        material = self.var_material.get()

        # --- FIX START ---
        # 1. Get the thickness from the GUI variable
        thickness = int(self.var_thickness.get())

        # 2. Pass 'thickness' as the last argument
        generator = BlueprintGenerator(hull_profile, center_offset, height, undercut, do_floor, save_path, material, thickness)
        # --- FIX END ---

        generator.generate()

        if save_path:
            final_location = os.path.join(save_path, OUTPUT_FILENAME)
        else:
            final_location = os.path.join(BASE_DIR, OUTPUT_FILENAME)

        messagebox.showinfo("Success", f"Generated {final_location}")


class BlueprintGenerator:
    def __init__(self, profile, center_offset, height, undercut, do_floor, save_path, material, thickness):
        self.profile = profile
        self.center_offset = center_offset
        self.height = height
        self.undercut = undercut
        self.do_floor = do_floor
        self.save_path = save_path
        self.material = material
        self.thickness = thickness # <--- Armor Thickness
        self.placements = []

        # Initialize empty dictionaries (No hardcoding!)
        self.beam_guids = {}
        self.slope_guids = {}
        self.offset_guids = {}
        self.load_assets()


    def load_assets(self):
        # Reset to ensure clean state
        self.beam_guids = {}
        self.slope_guids = {}
        self.offset_guids = {}

        target_mat = self.material.lower() # alloy, metal, wood, heavy, stone

        # Load from both JSON files in the BASE_DIR
        loaded_data = {}
        for fname in GUIDMAP_FILES:
            fpath = os.path.join(BASE_DIR, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, 'r') as f:
                        data = json.load(f)
                        loaded_data.update(data)
                except Exception as e:
                    print(f"Error loading {fname}: {e}")

        for name, guid in loaded_data.items():
            name_lower = name.lower()

            # --- 1m Block Logic (from standard blocks in guidmap-blocks.json) ---
            # These usually do NOT have "1m" in the name in the json file provided
            is_1m = False

            if target_mat == "alloy":
                if "light-weight alloy block" in name_lower: is_1m = True
            elif target_mat == "heavy":
                if name_lower == "heavy armour": is_1m = True
            else:
                # Wood, Metal, Stone follow "{Material} Block" pattern
                if f"{target_mat} block" in name_lower: is_1m = True

            if is_1m:
                self.beam_guids[1] = guid
                continue

            # --- 2m, 3m, 4m and Slope/Corner Logic ---
            # Filter for material presence in name
            check_str = "heavy armour" if target_mat == "heavy" else target_mat
            if check_str not in name_lower: continue

            length = 0
            if "4m" in name_lower: length = 4
            elif "3m" in name_lower: length = 3
            elif "2m" in name_lower: length = 2
            elif "1m" in name_lower: length = 1 # Handle explicit "1m" in slopes/corners

            if length == 0: continue

            # Categorize
            # 1. Beams (Exclude slopes/corners)
            if "beam" in name_lower and "slope" not in name_lower and "corner" not in name_lower:
                self.beam_guids[length] = guid

            # 2. Slopes
            elif "slope" in name_lower:
                self.slope_guids[length] = guid

            # 3. Offsets/Corners
            elif "offset" in name_lower and "inverted" not in name_lower:
                if length not in self.offset_guids:
                    self.offset_guids[length] = {"left": None, "right": None}

                if "left" in name_lower:
                    self.offset_guids[length]["left"] = guid
                elif "right" in name_lower:
                    self.offset_guids[length]["right"] = guid

    def generate(self):
        if 1 not in self.beam_guids:
             messagebox.showerror("Error", f"Could not find 1m Block ID for '{self.material}' in JSON maps.")
             return

        print("Starting Solver...")

        # 1. Generate ONLY the Outer Shell (Layer 0)
        # We use the standard full profile.
        self.placements = [] # Clear previous
        score, result = self.simulate_hull(0, self.profile, is_inner_layer=False)

        if result:
            self.placements.extend(result)
        else:
            # Fallback
            _, fb = self.simulate_hull(1, self.profile, is_inner_layer=False)
            self.placements.extend(fb)

        # 2. Construct the full hollow shape
        self.fill_stern()
        self.stack_layers()     # Extrude vertically
        self.generate_undercut() # Create the bottom curve

        if self.do_floor:
            self.generate_floor()

        # 3. NEW: Apply thickness by filling inwards
        if self.thickness > 1:
            print(f"Applying {self.thickness}m armor thickness...")
            self.apply_armor_thickness()

        self.save_to_blueprint()

    def fill_stern(self):
        if not self.profile.any(): return
        stern_x_index = self.profile[-1]
        dist_from_center = stern_x_index
        z_pos = 0
        start_x = -(dist_from_center - 1)
        end_x = (dist_from_center - 1)
        guid_1m = self.beam_guids.get(1)
        if not guid_1m: return
        if start_x <= end_x:
            for x in range(start_x, end_x + 1):
                beam_props = {"type": "beam", "len": 1, "offset": 0, "is_stern": False}
                entry = {'pos': (x, 10, z_pos), 'rot': ROT_BEAM, 'guid': guid_1m, 'props': beam_props}
                self.placements.append(entry)

    def stack_layers(self):
        if self.height <= 1: return
        base_layer = list(self.placements)
        self.placements = []
        for h in range(self.height):
            offset_y = h
            for p in base_layer:
                new_p = copy.deepcopy(p)
                x, y, z = new_p['pos']
                new_p['pos'] = (x, y - offset_y, z)
                self.placements.append(new_p)

    def generate_undercut(self):
        if self.undercut <= 0: return

        # Find the bottom-most blocks of the current layer
        if not self.placements: return
        min_y = min(p['pos'][1] for p in self.placements)
        parent_layer = [p for p in self.placements if p['pos'][1] == min_y]

        max_z = max(p['pos'][2] for p in parent_layer) if parent_layer else 0
        ship_center_z = max_z / 2

        for u in range(1, self.undercut + 1):
            current_undercut_y = min_y - u
            new_layer = []
            occupied_coords = set()
            placed_offsets = []

            # 1. Place Slopes/Offsets (The curved part of the undercut)
            for parent in parent_layer:
                props = parent['props']
                if props['type'] == 'beam': continue

                if props['type'] == 'slope':
                    length = props['len']
                    is_stern = props['is_stern']
                    rot = parent['rot']

                    offset_guid = None
                    is_left_rot = rot in [ROT_LEFT_IN, ROT_LEFT_STERN, ROT_LEFT_OUT]
                    is_right_rot = rot in [ROT_RIGHT_IN, ROT_RIGHT_STERN, ROT_RIGHT_OUT]

                    if is_stern:
                        if is_left_rot and length in self.offset_guids: offset_guid = self.offset_guids[length]["left"]
                        elif is_right_rot and length in self.offset_guids: offset_guid = self.offset_guids[length]["right"]
                    else:
                        if is_left_rot and length in self.offset_guids: offset_guid = self.offset_guids[length]["right"]
                        elif is_right_rot and length in self.offset_guids: offset_guid = self.offset_guids[length]["left"]

                    if not offset_guid: continue

                    z_shift = 1 if is_stern else -1
                    x, y, z = parent['pos']
                    new_pos = (x, current_undercut_y, z + z_shift)

                    if is_stern:
                        for i in range(length): occupied_coords.add((new_pos[0], new_pos[2] - i))
                    else:
                        for i in range(length): occupied_coords.add((new_pos[0], new_pos[2] + i))

                    new_entry = {
                        'pos': new_pos, 'rot': rot, 'guid': offset_guid, 'props': props
                    }
                    new_layer.append(new_entry)
                    placed_offsets.append(new_entry)

            # 2. Fill Straight Sections (Beams)
            raw_beam_voxels = []

            # A. Propagate beams downwards (The vertical walls)
            for parent in parent_layer:
                if parent['props']['type'] == 'beam':
                    length = parent['props']['len']
                    px, py, pz = parent['pos']

                    # Shift based on position relative to center to align nicely
                    beam_z_shift = -1 if pz > ship_center_z else 1
                    shifted_pz = pz + beam_z_shift

                    for z_offset in range(length):
                        voxel_z = shifted_pz + z_offset
                        voxel_x = px
                        if (voxel_x, voxel_z) not in occupied_coords:
                             raw_beam_voxels.append((voxel_x, voxel_z))
                             occupied_coords.add((voxel_x, voxel_z))

            # B. Fill horizontally from offsets (The transition)
            # IMPORTANT CHANGE: We only fill 1 block inward to maintain shell thickness.
            # The inner loop will handle the rest.
            for off in placed_offsets:
                x = off['pos'][0]
                z_anchor = off['pos'][2]
                is_stern = off['props']['is_stern']

                if is_stern:
                    start_z = z_anchor + 1
                    direction = 1
                else:
                    start_z = z_anchor - 1
                    direction = -1

                current_z = start_z

                # --- LIMIT FILL TO 1 BLOCK ---
                # We check if the spot is empty. If so, fill it and stop.
                # This creates a single-layer shell for the undercut.
                if (x, current_z) not in occupied_coords:
                    raw_beam_voxels.append((x, current_z))
                    occupied_coords.add((x, current_z))
                # -----------------------------

            optimized_beams = self.optimize_beams(raw_beam_voxels, current_undercut_y)
            new_layer.extend(optimized_beams)

            self.placements.extend(new_layer)
            parent_layer = new_layer

    def generate_floor(self):
        if not self.placements: return

        min_y = min(p['pos'][1] for p in self.placements)
        occupied = set()

        for p in self.placements:
            if p['pos'][1] == min_y:
                length = p['props']['len']
                px, py, pz = p['pos']
                is_stern = p['props'].get('is_stern', False)

                if is_stern:
                    for i in range(length): occupied.add((px, pz - i))
                else:
                    for i in range(length): occupied.add((px, pz + i))

        if not occupied: return

        min_z = min(z for x, z in occupied)
        max_z = max(z for x, z in occupied)

        raw_floor_voxels = []

        for z in range(min_z, max_z + 1):
            xs_at_z = [x for x, _z in occupied if _z == z]
            if not xs_at_z: continue

            min_x = min(xs_at_z)
            max_x = max(xs_at_z)

            for x in range(min_x + 1, max_x):
                if (x, z) not in occupied:
                    raw_floor_voxels.append((x, z))
                    occupied.add((x, z))

        floor_beams = self.optimize_beams(raw_floor_voxels, min_y)
        self.placements.extend(floor_beams)

    def optimize_beams(self, voxels, y_level):
        by_x = {}
        for x, z in voxels:
            if x not in by_x: by_x[x] = []
            by_x[x].append(z)

        optimized = []
        for x, z_list in by_x.items():
            z_list = sorted(list(set(z_list)))
            if not z_list: continue

            runs = []
            if z_list:
                current_run = [z_list[0]]
                for i in range(1, len(z_list)):
                    if z_list[i] == z_list[i-1] + 1:
                        current_run.append(z_list[i])
                    else:
                        runs.append(current_run)
                        current_run = [z_list[i]]
                runs.append(current_run)

            for run in runs:
                start_z = run[0]
                total_len = len(run)
                current_fill_z = start_z

                while total_len > 0:
                    chosen = 1
                    for size in [4, 3, 2, 1]:
                        if size <= total_len and size in self.beam_guids:
                            chosen = size
                            break

                   # if chosen is None:
                    #    current_fill_z += 1
                    #    total_len -= 1
                    #    continue

                    guid = self.beam_guids[chosen]
                    props = {"type": "beam", "len": chosen, "offset": 0, "is_stern": False}

                    entry = {
                        'pos': (x, y_level, current_fill_z),
                        'rot': ROT_BEAM,
                        'guid': guid,
                        'props': props
                    }
                    optimized.append(entry)
                    current_fill_z += chosen
                    total_len -= chosen
        return optimized

    def simulate_hull(self, forced_1m_zone, target_profile, is_inner_layer=False):
        temp_placements = []
        L = len(target_profile)
        current_z = 0
        current_min_len = 1
        total_penalty = 0

        while current_z < L:
            x_current = target_profile[current_z]
            dist_current = x_current

            best_choice = None
            min_step_cost = float('inf')

            all_lengths = sorted(list(set(list(self.slope_guids.keys()) + list(self.beam_guids.keys()))), reverse=True)
            limit_len = 99
            if current_z < forced_1m_zone: limit_len = 1

            candidates = []
            for l in all_lengths:
                if l > limit_len: continue

                # If inner layer, ONLY allow Beams (No slopes/offsets)
                if not is_inner_layer:
                    if l in self.slope_guids:
                        candidates.append({"type": "slope", "len": l, "offset": -1, "is_stern": False, "guid": self.slope_guids[l]})
                        candidates.append({"type": "slope", "len": l, "offset": 1, "is_stern": True, "guid": self.slope_guids[l]})

                if l in self.beam_guids:
                    candidates.append({"type": "beam", "len": l, "offset": 0, "is_stern": False, "guid": self.beam_guids[l]})

            for cand in candidates:
                b_len = cand["len"]
                if current_z + b_len > L: continue

                target_x = target_profile[current_z + b_len - 1]
                if current_z + b_len < L: target_x = target_profile[current_z + b_len]
                else: target_x = target_profile[-1]

                dist_ideal = dist_current - cand["offset"]
                error = abs(target_x - dist_ideal)

                # Relax error slightly for beams-only (staircasing)
                threshold = 1.0
                if is_inner_layer: threshold = 1.5

                if error > threshold: continue

                fit_penalty = error * 50
                len_penalty = (current_min_len - b_len) * 10 if b_len < current_min_len else -(b_len * 2)
                efficiency_cost = 10
                total_step_cost = len_penalty + efficiency_cost + fit_penalty

                valid_lookahead = True

                # --- FIX: DISABLE LOOKAHEAD FOR INNER LAYERS ---
                # We only check lookahead for the outer shell.
                # Inner shells are allowed to be 'blocky' stairs.
                if b_len > 1 and not is_inner_layer:
                    lookahead_z = current_z + int(b_len * 1.5)
                    if lookahead_z < L:
                        future_x = target_profile[lookahead_z]
                        ratio = (lookahead_z - current_z) / b_len
                        dist_fut_ideal = dist_current - (cand["offset"] * ratio)
                        if abs(future_x - dist_fut_ideal) > threshold: valid_lookahead = False
                # -----------------------------------------------

                if not valid_lookahead: continue

                if total_step_cost < min_step_cost:
                    min_step_cost = total_step_cost
                    best_choice = cand

            if not best_choice:
                total_penalty += 200
                current_min_len = 1

                fb_cands = []
                if not is_inner_layer and 1 in self.slope_guids:
                    fb_cands.append({"type": "slope", "len": 1, "offset": -1, "is_stern": False, "guid": self.slope_guids[1]})
                    fb_cands.append({"type": "slope", "len": 1, "offset": 1, "is_stern": True, "guid": self.slope_guids[1]})

                if 1 in self.beam_guids:
                    fb_cands.append({"type": "beam", "len": 1, "offset": 0, "is_stern": False, "guid": self.beam_guids.get(1)})

                best_err = float('inf')
                for c in fb_cands:
                    if not c["guid"]: continue
                    if current_z + c["len"] > L: continue
                    tx = target_profile[current_z+1] if current_z+1 < L else target_profile[-1]
                    di = dist_current - c["offset"]
                    if abs(tx - di) < best_err: best_err = abs(tx - di); best_choice = c

                if not best_choice: current_z += 1; continue

            total_penalty += min_step_cost
            b_len = best_choice["len"]
            current_min_len = b_len

            z_shift = 1 if best_choice["is_stern"] else b_len
            placement_z = L - (current_z + z_shift)

            gx_left = -dist_current
            gx_right = dist_current
            rot_left = ROT_BEAM
            rot_right = ROT_BEAM

            if best_choice["type"] == "slope":
                if best_choice["is_stern"]:
                    rot_left = ROT_LEFT_STERN
                    rot_right = ROT_RIGHT_STERN
                else:
                    if best_choice["offset"] == -1:
                        rot_left = ROT_LEFT_OUT; rot_right = ROT_RIGHT_OUT; gx_left -= 1; gx_right += 1
                    else:
                        rot_left = ROT_LEFT_IN; rot_right = ROT_RIGHT_IN

            entry_left = {'pos': (gx_left, 10, placement_z), 'rot': rot_left, 'guid': best_choice["guid"], 'props': best_choice}
            entry_right = {'pos': (gx_right, 10, placement_z), 'rot': rot_right, 'guid': best_choice["guid"], 'props': best_choice}

            temp_placements.append(entry_left)
            temp_placements.append(entry_right)

            current_z += b_len

        return total_penalty, temp_placements

    def save_to_blueprint(self):
        if not os.path.exists(DONOR_BLUEPRINT):
            messagebox.showerror("Error", f"Missing {DONOR_BLUEPRINT}")
            return
        with open(DONOR_BLUEPRINT, "r") as f: bp = json.load(f)

        bp["Blueprint"]["SCs"] = []; bp["Blueprint"]["BP1"] = None; bp["Blueprint"]["BP2"] = None
        guid_map = {}; next_id = 1000
        bp["Blueprint"]["BLP"] = []; bp["Blueprint"]["BLR"] = []; bp["Blueprint"]["BlockIds"] = []; bp["Blueprint"]["BCI"] = []

        for p in self.placements:
            pos = p['pos']
            rot = p['rot']
            guid = p['guid']

            if guid not in guid_map: guid_map[guid] = next_id; next_id += 1
            bp["Blueprint"]["BLP"].append(f"{int(pos[0])},{int(pos[1])},{int(pos[2])}")
            bp["Blueprint"]["BLR"].append(int(rot))
            bp["Blueprint"]["BlockIds"].append(int(guid_map[guid]))
            bp["Blueprint"]["BCI"].append(0)

        if "ItemDictionary" not in bp: bp["ItemDictionary"] = {}
        for g, i in guid_map.items(): bp["ItemDictionary"][str(i)] = g

        count = len(self.placements)
        bp["Blueprint"]["BlockState"] = f"=0,{count}"
        bp["Blueprint"]["TotalBlockCount"] = count
        bp["Blueprint"]["AliveCount"] = count
        bp["SavedTotalBlockCount"] = count

        # --- OUTPUT LOGIC ---
        if self.save_path:
            out_file = os.path.join(self.save_path, OUTPUT_FILENAME)
        else:
            # Fallback to script directory if no path selected
            out_file = os.path.join(BASE_DIR, OUTPUT_FILENAME)

        with open(out_file, "w") as f: json.dump(bp, f)


    def apply_armor_thickness(self):
        # 1. Map the current ship state
        # structure: map[y][z] = set of occupied X coordinates
        layer_map = {}

        for p in self.placements:
            x, y, z = p['pos']
            if y not in layer_map: layer_map[y] = {}
            if z not in layer_map[y]: layer_map[y][z] = set()

            # Mark occupied voxels
            # Note: Beams/Slopes might have length > 1, but in this simplified map
            # we only care about the anchor position for the scan,
            # OR we need to map the full volume.
            # Let's map the FULL volume to be safe.

            length = p['props']['len']
            is_stern = p['props'].get('is_stern', False)

            # Determine Z-range of this block
            z_start = z
            z_end = z
            if is_stern:
                z_end = z # Stern builds "forward" from anchor?
                # Actually, checking simulate_hull:
                # Stern blocks (is_stern=True) build Z-1, Z-2...
                # Normal blocks build Z+1, Z+2...
                # Let's map all occupied Zs
                for i in range(length): layer_map[y].setdefault(z - i, set()).add(x)
            else:
                # Normal blocks (beam or slope)
                 for i in range(length): layer_map[y].setdefault(z + i, set()).add(x)

        new_armor_voxels = []

        # 2. Scan and Fill
        # Iterate over every Y level
        for y, z_row in layer_map.items():

            # Determine voxels to fill for this Y level
            voxels_to_fill_at_y = []

            for z, x_set in z_row.items():
                if not x_set: continue

                # Find boundaries
                max_x = max(x_set) # Starboard side outer wall
                min_x = min(x_set) # Port side outer wall

                # Fill Starboard (Positive X) -> Inwards (Negative direction)
                # We want to fill from (max_x - 1) down to (max_x - thickness + 1)
                for t in range(1, self.thickness):
                    target_x = max_x - t
                    if target_x > 0: # Don't cross center line
                        if target_x not in x_set:
                            voxels_to_fill_at_y.append((target_x, z))
                            # Temporarily mark as filled so we don't double add if logic overlaps
                            x_set.add(target_x)

                # Fill Port (Negative X) -> Inwards (Positive direction)
                for t in range(1, self.thickness):
                    target_x = min_x + t
                    if target_x < 0: # Don't cross center line
                        if target_x not in x_set:
                            voxels_to_fill_at_y.append((target_x, z))
                            x_set.add(target_x)

            # 3. Optimize these 1m voxels into beams for this Y level
            if voxels_to_fill_at_y:
                optimized = self.optimize_beams(voxels_to_fill_at_y, y)
                new_armor_voxels.extend(optimized)

        # 4. Add new blocks to main list
        self.placements.extend(new_armor_voxels)



if __name__ == "__main__":
    root = tk.Tk()
    app = HullDesigner(root)
    root.mainloop()
    ###