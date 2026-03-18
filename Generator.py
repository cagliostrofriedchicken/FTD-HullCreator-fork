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

# --- ZOOM SETTINGS ---
ZOOM_STEP = 10
ZOOM_MIN = 50
ZOOM_MAX = 2000

# --- ROTATION SETTINGS ---
ROT_BEAM      = 0
ROT_X_AXIS    = 1
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
        self.root.title("FTD Hull Designer (1.4)")
        self.root.configure(bg=THEME_PANEL_BG)

        self.points =[(0, 0)]
        self.barbettes =[] # NEW: List of compartment dictionaries
        
        self.selected_point_index = None  
        self.selected_barbette_index = None # NEW: Tracks selected compartment
        
        self.pan_start_x = 0              
        self.pan_start_y = 0              

        self._is_syncing = False

        # Base Defaults
        self.var_height = tk.IntVar(value=3)
        self.var_undercut = tk.IntVar(value=5)
        self.var_uc_bow = tk.IntVar(value=1)
        self.var_uc_stern = tk.IntVar(value=3)
        self.var_floor_thickness = tk.IntVar(value=1)
        self.var_save_path = tk.StringVar(value="")
        self.armor_layers =[]

        # Compartment Defaults
        self.var_centerline_lock = tk.BooleanVar(value=True)
        self.var_comp_mat = tk.StringVar(value="Heavy")
        
        self.var_b_body_in_d = tk.IntVar(value=7)
        self.var_b_body_thick = tk.IntVar(value=1)
        self.var_b_body_h = tk.IntVar(value=5)
        
        self.var_b_top_hole_d = tk.IntVar(value=3)
        self.var_b_top_h = tk.IntVar(value=1)
        
        self.var_b_bot_h = tk.IntVar(value=1)

        self.var_b_neck_thick = tk.IntVar(value=1)
        self.var_b_neck_h = tk.IntVar(value=2)

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

        self.controls = tk.Frame(self.main_container, bg=THEME_PANEL_BG, padx=5, pady=5, relief=tk.RAISED, bd=2)
        self.controls.pack(side=tk.RIGHT, fill=tk.Y)

        lbl_opts = {"bg": THEME_PANEL_BG, "fg": THEME_TEXT, "font": ("MS Sans Serif", 9)}
        mat_options =["Alloy", "Metal", "Wood", "Heavy", "Stone"]

        # --- TABS ---
        self.notebook = ttk.Notebook(self.controls)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.tab_hull = tk.Frame(self.notebook, bg=THEME_PANEL_BG)
        self.tab_comp = tk.Frame(self.notebook, bg=THEME_PANEL_BG)
        
        self.notebook.add(self.tab_hull, text="Hull Logic")
        self.notebook.add(self.tab_comp, text="Compartments")

        # ==========================================
        # TAB 1: HULL
        # ==========================================
        tk.Button(self.tab_hull, text="Load Preset (100m)", command=self.load_preset1, bg=THEME_PANEL_BG).pack(pady=2, fill=tk.X)
        tk.Button(self.tab_hull, text="Load Preset (200m)", command=self.load_preset2, bg=THEME_PANEL_BG).pack(pady=2, fill=tk.X)

        grp_stats = tk.LabelFrame(self.tab_hull, text="Ship Stats", bg=THEME_PANEL_BG, font=("MS Sans Serif", 9, "bold"))
        grp_stats.pack(fill=tk.X, pady=5)
        self.lbl_stats_len = tk.Label(grp_stats, text="Length: 0m", anchor="w", **lbl_opts)
        self.lbl_stats_len.pack(anchor="w", padx=5)
        self.lbl_stats_beam = tk.Label(grp_stats, text="Beam: 1m", anchor="w", **lbl_opts)
        self.lbl_stats_beam.pack(anchor="w", padx=5)

        grp_canvas = tk.LabelFrame(self.tab_hull, text="Design Limits", **lbl_opts)
        grp_canvas.pack(fill=tk.X, pady=5)
        tk.Label(grp_canvas, text="Length (m):", **lbl_opts).pack(anchor="w")
        s_l = tk.Spinbox(grp_canvas, from_=20, to=2000, textvariable=self.var_limit_length, width=10)
        s_l.pack(pady=2)
        s_l.bind("<Return>", lambda e: self.force_redraw())

        grp_dim = tk.LabelFrame(self.tab_hull, text="Generator Settings", **lbl_opts)
        grp_dim.pack(fill=tk.X, pady=5)
        
        tk.Label(grp_dim, text="Deck Height:", **lbl_opts).pack(anchor="w")
        tk.Spinbox(grp_dim, from_=1, to=50, textvariable=self.var_height, width=10).pack(pady=2)
        
        tk.Label(grp_dim, text="Undercut Layers:", **lbl_opts).pack(anchor="w")
        tk.Spinbox(grp_dim, from_=0, to=20, textvariable=self.var_undercut, width=10).pack(pady=2)

        f_uc = tk.Frame(grp_dim, bg=THEME_PANEL_BG)
        f_uc.pack(fill=tk.X, pady=2)
        tk.Label(f_uc, text="Bow Step:", **lbl_opts).pack(side=tk.LEFT)
        tk.Spinbox(f_uc, from_=1, to=10, textvariable=self.var_uc_bow, width=4).pack(side=tk.LEFT, padx=2)
        tk.Label(f_uc, text="Stern Step:", **lbl_opts).pack(side=tk.LEFT)
        tk.Spinbox(f_uc, from_=1, to=10, textvariable=self.var_uc_stern, width=4).pack(side=tk.LEFT, padx=2)
        
        
        tk.Label(grp_dim, text="Floor Thickness (0 = None):", **lbl_opts).pack(anchor="w")
        tk.Spinbox(grp_dim, from_=0, to=10, textvariable=self.var_floor_thickness, width=10).pack(pady=2)

        self.grp_armor = tk.LabelFrame(self.tab_hull, text="Armor Layout", **lbl_opts)
        self.grp_armor.pack(fill=tk.X, pady=5)

        self.armor_list_frame = tk.Frame(self.grp_armor, bg=THEME_PANEL_BG)
        self.armor_list_frame.pack(fill=tk.X, pady=2)

        tk.Button(self.grp_armor, text="Add Layer (+)", command=self.add_armor_layer, bg=THEME_PANEL_BG).pack(pady=2)
        self.add_armor_layer("Alloy", 1)

        # ==========================================
        # TAB 2: COMPARTMENTS (BARBETTES)
        # ==========================================
        def add_trace(var):
            var.trace_add("write", lambda *args: self.sync_ui_to_barbette())

        grp_c_mat = tk.Frame(self.tab_comp, bg=THEME_PANEL_BG)
        grp_c_mat.pack(fill=tk.X, pady=5)
        tk.Label(grp_c_mat, text="Material:", **lbl_opts).pack(side=tk.LEFT)
        cb = ttk.Combobox(grp_c_mat, textvariable=self.var_comp_mat, values=mat_options, state="readonly", width=12)
        cb.pack(side=tk.RIGHT)
        cb.bind("<<ComboboxSelected>>", lambda e: self.sync_ui_to_barbette())

        # Spinbox builder helper
        def make_sb(parent, label_text, var, max_v=50):
            f = tk.Frame(parent, bg=THEME_PANEL_BG)
            f.pack(fill=tk.X, pady=1)
            tk.Label(f, text=label_text, **lbl_opts).pack(side=tk.LEFT)
            tk.Spinbox(f, from_=0, to=max_v, textvariable=var, width=5, command=self.sync_ui_to_barbette).pack(side=tk.RIGHT)
            add_trace(var)

        def make_odd_sb(parent, label_text, var, max_v=51):
            f = tk.Frame(parent, bg=THEME_PANEL_BG)
            f.pack(fill=tk.X, pady=1)
            tk.Label(f, text=label_text, **lbl_opts).pack(side=tk.LEFT)
            # increment=2 forces the arrows to only jump to odd numbers
            tk.Spinbox(f, from_=1, to=max_v, increment=2, textvariable=var, width=5, command=self.sync_ui_to_barbette).pack(side=tk.RIGHT)
            add_trace(var)

        g_bot = tk.LabelFrame(self.tab_comp, text="Bottom Cap", **lbl_opts)
        g_bot.pack(fill=tk.X, pady=2)
        make_sb(g_bot, "Thickness/Height:", self.var_b_bot_h)

        g_body = tk.LabelFrame(self.tab_comp, text="Main Body", **lbl_opts)
        g_body.pack(fill=tk.X, pady=2)
        make_odd_sb(g_body, "Inner Diameter:", self.var_b_body_in_d)
        make_sb(g_body, "Wall Thickness:", self.var_b_body_thick)
        make_sb(g_body, "Height:", self.var_b_body_h)

        g_top = tk.LabelFrame(self.tab_comp, text="Top Cap", **lbl_opts)
        g_top.pack(fill=tk.X, pady=2)
        make_odd_sb(g_top, "Hole Diameter:", self.var_b_top_hole_d)
        make_sb(g_top, "Thickness/Height:", self.var_b_top_h)

        g_neck = tk.LabelFrame(self.tab_comp, text="Neck", **lbl_opts)
        g_neck.pack(fill=tk.X, pady=2)
        make_sb(g_neck, "Wall Thickness:", self.var_b_neck_thick)
        make_sb(g_neck, "Height:", self.var_b_neck_h)

        self.lbl_comp_warn = tk.Label(self.tab_comp, text="Select a Barbette to Edit.", fg="red", bg=THEME_PANEL_BG, font=("Arial", 9, "bold"))
        self.lbl_comp_warn.pack(pady=10)

        # ==========================================
        # GLOBAL CONTROLS
        # ==========================================
        self.btn_export = tk.Button(self.controls, text="EXPORT BLUEPRINT", command=self.run_generator,
                                    bg=THEME_PANEL_BG, relief=tk.RAISED, bd=3, font=("MS Sans Serif", 9, "bold"), pady=5)
        self.btn_export.pack(pady=5, fill=tk.X)

        instructions = (
            "Shift+L-Click: Add Hull Point\n"
            "L-Click: Select Point/Compartment\n"
            "Mid-Click Drag: Pan View\n"
            "Scroll: Zoom In/Out\n"
            "Right-Click: Add Compartment\n"
            "Del / Bksp: Delete Selected\n"
            "'R' Key: Undo Last Point"
        )
        self.lbl_info = tk.Label(self.controls, text=instructions, justify=tk.LEFT, bg=THEME_PANEL_BG, fg="#444")
        self.lbl_info.pack(pady=5)

        self.lbl_cursor = tk.Label(self.controls, text="Width: -\nLength: -", width=25, bg=THEME_PANEL_BG, font=("Courier New", 9))
        self.lbl_cursor.pack(side=tk.BOTTOM, pady=5)

        self.canvas_frame = tk.Frame(self.main_container, bg="black", bd=2, relief=tk.SUNKEN)
        self.canvas_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg=THEME_BG, highlightthickness=0, takefocus=True)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # --- CONTEXT MENU ---
        self.ctx_menu = tk.Menu(self.canvas, tearoff=0)
        self.ctx_menu.add_checkbutton(label="Centerline Lock", variable=self.var_centerline_lock)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="Add Barbette", command=self.add_barbette_from_menu)

        # --- BINDINGS ---
        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Shift-Button-1>", self.add_point)
        self.canvas.bind("<Button-1>", self.select_item)
        self.canvas.bind("<B1-Motion>", self.move_item)
        self.canvas.bind("<Motion>", self.cursor_update)
        
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)   
        self.canvas.bind("<Button-5>", self.on_zoom)   
        
        self.canvas.bind("<ButtonPress-2>", self.start_pan) 
        self.canvas.bind("<B2-Motion>", self.do_pan)        
        
        # New Context Menu Bind
        self.canvas.bind("<Button-3>", self.show_context_menu)
        
        # Changed Undo Bind
        self.canvas.bind("<r>", self.remove_point)
        self.canvas.bind("<R>", self.remove_point)
        
        self.canvas.bind("<Delete>", self.delete_selected_item)
        self.canvas.bind("<BackSpace>", self.delete_selected_item)

    # --- SETTINGS / PRESETS ---
    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    saved_path = data.get("save_path", "")
                    if saved_path and os.path.exists(saved_path):
                        self.var_save_path.set(saved_path)
            except Exception: pass

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump({"save_path": self.var_save_path.get()}, f)
        except Exception: pass

    def load_preset1(self):
        self.points =[(0, 0), (4, 2), (14, 4), (39, 6), (69, 6), (85, 5), (100, 3)]
        self.barbettes =[]
        self.selected_point_index = None
        self.selected_barbette_index = None
        self.var_limit_length.set(100)
        self.offset_x = 0
        self.offset_y = 20
        self.recalc_view()

    def load_preset2(self):
        self.points =[(0, 0), (4, 4), (20, 9), (50, 14), (80, 17), (140, 17), (170, 15), (190, 11), (200, 7)]
        self.barbettes =[]
        self.selected_point_index = None
        self.selected_barbette_index = None
        self.var_limit_length.set(200)
        self.offset_x = 0
        self.offset_y = 20
        self.recalc_view()

    # --- VIEWPORT MATH ---
    def on_resize(self, event):
        self.phys_w = event.width
        self.phys_h = event.height
        self.recalc_view()

    def force_redraw(self):
        self.recalc_view()

    def recalc_view(self):
        try: log_len = int(self.var_limit_length.get())
        except ValueError: return

        if self.phys_w <= 1 or self.phys_h <= 1: return
        padding_px = 40
        available_h = max(10, self.phys_h - padding_px)
        self.grid_size = available_h / log_len
        self.var_limit_width.set(int((self.phys_w / self.grid_size) / 2))

        self.clamp_view()
        self.draw_grid()
        self.redraw_shape()
        self.update_stats()

    def to_screen(self, gx, gz):
        cx = self.offset_x + (int(self.var_limit_width.get()) * self.grid_size)
        return cx + (gx * self.grid_size), self.offset_y + (gz * self.grid_size)

    def to_grid(self, sx, sy):
        cx = self.offset_x + (int(self.var_limit_width.get()) * self.grid_size)
        return (sx - cx) / self.grid_size, (sy - self.offset_y) / self.grid_size

    def _cursor_to_point(self, sx, sz):
        raw_gx, raw_gz = self.to_grid(sx, sz)
        return int(round(max(0, raw_gz))), int(round(abs(raw_gx)))

    # --- CAMERA CONTROLS ---
    def on_zoom(self, event):
        try: current_len = int(self.var_limit_length.get())
        except ValueError: return

        if hasattr(event, 'num') and event.num in (4, 5): direction = 1 if event.num == 4 else -1
        else: direction = 1 if event.delta > 0 else -1

        new_len = max(ZOOM_MIN, min(ZOOM_MAX, current_len - (direction * ZOOM_STEP)))
        self.var_limit_length.set(new_len)
        self.recalc_view()

    def start_pan(self, event):
        self.canvas.focus_set()
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def do_pan(self, event):
        self.offset_x += event.x - self.pan_start_x
        self.offset_y += event.y - self.pan_start_y
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.clamp_view()
        self.draw_grid()
        self.redraw_shape()

    def clamp_view(self):
        try: log_len = int(self.var_limit_length.get())
        except ValueError: return
        max_px = 2 * log_len * self.grid_size
        self.offset_x = max(-max_px, min(max_px, self.offset_x))
        self.offset_y = max(20 - max_px, min(20 + max_px, self.offset_y))

    # --- RENDER LOOP ---
    def draw_grid(self):
        self.canvas.delete("grid")
        log_w_half = int(self.var_limit_width.get())
        log_h = int(self.var_limit_length.get())
        center_x = self.offset_x + (log_w_half * self.grid_size)
        end_x = self.phys_w
        end_y = self.offset_y + (log_h * self.grid_size)

        for i in range(log_w_half * 2 + 1):
            xr = center_x + (i * self.grid_size)
            if xr <= end_x:
                is_major = i % 10 == 0
                c = THEME_GRID_MAJOR if is_major else THEME_GRID_MINOR
                if is_major or self.grid_size > 3: self.canvas.create_line(xr, self.offset_y, xr, end_y, fill=c, tags="grid")
            xl = center_x - (i * self.grid_size)
            if xl >= 0:
                is_major = i % 10 == 0
                c = THEME_GRID_MAJOR if is_major else THEME_GRID_MINOR
                if is_major or self.grid_size > 3: self.canvas.create_line(xl, self.offset_y, xl, end_y, fill=c, tags="grid")

        for i in range(log_h + 1):
            y = self.offset_y + (i * self.grid_size)
            c = THEME_GRID_MAJOR if i % 10 == 0 else THEME_GRID_MINOR
            if i % 10 == 0 or self.grid_size > 3: self.canvas.create_line(0, y, end_x, y, fill=c, tags="grid")

        self.canvas.create_line(center_x, self.offset_y, center_x, end_y, fill=THEME_CENTER_LINE, width=2, dash=(6, 4), tags="grid")

    def cursor_update(self, event):
        gz, gx = self._cursor_to_point(event.x, event.y)
        wm, lm = gx * 2 + 1, gz
        self.lbl_cursor.config(text=f"Width at Cursor: {wm}m\nLength at Cursor: {lm}m")

        self.canvas.delete("preview")
        if (self.selected_point_index is None or self.selected_point_index == len(self.points) - 1) and gz > self.points[-1][0]:
            rp = self.to_screen(self.points[-1][1], self.points[-1][0])
            mp = self.to_screen(-self.points[-1][1], self.points[-1][0])
            self.canvas.create_line(rp, self.to_screen(gx, gz), tags="preview", fill="light grey")
            self.canvas.create_line(mp, self.to_screen(-gx, gz), tags="preview", fill="light grey")

    def redraw_shape(self):
        self.canvas.delete("shape")
        self.canvas.delete("points")
        if not self.points: return

        poly_points = [self.to_screen(x, z) for z, x in self.points]
        poly_points.extend([self.to_screen(-x, z) for z, x in reversed(self.points)])

        if len(poly_points) > 2:
            self.canvas.create_polygon(poly_points, fill=THEME_HULL_FILL, outline=THEME_HULL_OUTLINE, width=2, tags="shape")

        # Draw Hull Points
        for i, (z, x) in enumerate(self.points):
            rx, ry = self.to_screen(x, z)
            lx, ly = self.to_screen(-x, z)
            color = "#FF3333" if i == self.selected_point_index else "#BBB"
            radius = 4 if i == self.selected_point_index else 3
            self.canvas.create_oval(rx-radius, ry-radius, rx+radius, ry+radius, fill=color, outline="black", tags="points")
            if x != 0: self.canvas.create_oval(lx-radius, ly-radius, lx+radius, ly+radius, fill=color, outline="black", tags="points")

        # Draw Barbettes
        for i, b in enumerate(self.barbettes):
            rx, ry = self.to_screen(b['x'], b['z'])
            lx, ly = self.to_screen(-b['x'], b['z'])
            
            color = "#FF8800" if i == self.selected_barbette_index else "#AA5500"

            in_r = (b['body_inner_d'] + 2) // 2
            
            r_out = (in_r + b['body_thick']) * self.grid_size
            r_in = in_r * self.grid_size
            
            # Starboard side (and centerline)
            self.canvas.create_oval(rx-r_out, ry-r_out, rx+r_out, ry+r_out, outline=color, width=2, tags="shape")
            if r_in > 0: self.canvas.create_oval(rx-r_in, ry-r_in, rx+r_in, ry+r_in, outline=color, dash=(4,4), tags="shape")
            self.canvas.create_oval(rx-3, ry-3, rx+3, ry+3, fill=color, tags="points")

            # Mirror on Port side if not centerline
            if b['x'] != 0:
                self.canvas.create_oval(lx-r_out, ly-r_out, lx+r_out, ly+r_out, outline=color, width=2, tags="shape")
                if r_in > 0: self.canvas.create_oval(lx-r_in, ly-r_in, lx+r_in, ly+r_in, outline=color, dash=(4,4), tags="shape")
                self.canvas.create_oval(lx-3, ly-3, lx+3, ly+3, fill=color, tags="points")

    def update_stats(self):
        if not self.points: return
        l = self.points[-1][0]
        b = max(x for z, x in self.points) * 2 + 1
        self.lbl_stats_len.config(text=f"Length: {l}m")
        self.lbl_stats_beam.config(text=f"Beam: {b}m")

    # --- ITEM INTERACTION ---
    def add_point(self, event):
        self.canvas.focus_set()
        point = self._cursor_to_point(event.x, event.y)
        if not self.points or point[0] > self.points[-1][0]:
            self.points.append(point)
            self.selected_point_index = len(self.points) - 1
            self.selected_barbette_index = None
            self.notebook.select(self.tab_hull)
            self.redraw_shape(); self.update_stats()

    def select_item(self, event):
        self.canvas.focus_set()
        
        # 1. Check if clicked a Barbette (prioritized)
        for i, b in enumerate(self.barbettes):
            sx, sy = self.to_screen(b['x'], b['z'])
            msx, msy = self.to_screen(-b['x'], b['z'])

            # --- FIXED: Use diameter and apply true-volume math ---
            in_r = (b['body_inner_d'] + 2) // 2 
            hit_radius = max(3, (in_r + b['body_thick']) * self.grid_size)
            # ------------------------------------------------------
            
            if (event.x - sx)**2 + (event.y - sy)**2 <= hit_radius**2 or \
               (event.x - msx)**2 + (event.y - msy)**2 <= hit_radius**2:
                self.selected_barbette_index = i
                self.selected_point_index = None
                self.sync_barbette_to_ui()
                self.notebook.select(self.tab_comp)
                self.redraw_shape()
                return

        # 2. Check if clicked a Hull Point
        for i, (z, x) in enumerate(self.points):
            sx, sy = self.to_screen(x, z)
            msx, msy = self.to_screen(-x, z)
            if (event.x - sx)**2 + (event.y - sy)**2 <= 64 or (event.x - msx)**2 + (event.y - msy)**2 <= 64:
                self.selected_point_index = i
                self.selected_barbette_index = None
                self.notebook.select(self.tab_hull)
                self.redraw_shape()
                return
                
        self.selected_point_index = None
        self.selected_barbette_index = None
        self.redraw_shape()

    def move_item(self, event):
        gz, gx = self._cursor_to_point(event.x, event.y)

        # Move Barbette
        if self.selected_barbette_index is not None:
            if self.var_centerline_lock.get(): gx = 0
            self.barbettes[self.selected_barbette_index]['x'] = gx
            self.barbettes[self.selected_barbette_index]['z'] = gz
            self.redraw_shape()
            return

        # Move Hull Point
        if self.selected_point_index is not None:
            i = self.selected_point_index
            if i == 0:
                gx = 0 
                if len(self.points) > 1: gz = min(gz, self.points[1][0] - 1)
                gz = max(0, gz)
            else:
                gz = max(gz, self.points[i-1][0] + 1)
                if i < len(self.points) - 1: gz = min(gz, self.points[i+1][0] - 1)
                    
            self.points[i] = (gz, gx)
            self.redraw_shape(); self.update_stats()

    def delete_selected_item(self, event):
        if self.selected_barbette_index is not None:
            self.barbettes.pop(self.selected_barbette_index)
            self.selected_barbette_index = None
            self.redraw_shape()
        elif self.selected_point_index is not None and self.selected_point_index > 0:
            self.points.pop(self.selected_point_index)
            self.selected_point_index = None
            self.redraw_shape(); self.update_stats()

    def remove_point(self, event):
        if len(self.points) > 1:
            self.points.pop()
            if self.selected_point_index is not None and self.selected_point_index >= len(self.points):
                self.selected_point_index = None
            self.redraw_shape(); self.update_stats()

    # --- COMPARTMENT MENU & LOGIC ---
    def show_context_menu(self, event):
        self.canvas.focus_set()
        self.ctx_x = event.x
        self.ctx_y = event.y
        
        # Floor thickness check
        try: floor_val = int(self.var_floor_thickness.get())
        except ValueError: floor_val = 0
        
        state = tk.NORMAL if floor_val > 0 else tk.DISABLED
        self.ctx_menu.entryconfig("Add Barbette", state=state)
        
        self.ctx_menu.tk_popup(event.x_root, event.y_root)

    def add_barbette_from_menu(self):
        raw_gx, raw_gz = self.to_grid(self.ctx_x, self.ctx_y)
        gz = int(round(max(0, raw_gz)))
        gx = 0 if self.var_centerline_lock.get() else int(round(abs(raw_gx)))

        new_b = {
            'x': gx, 'z': gz,
            'mat': self.var_comp_mat.get(),
            'bottom_cap_h': self.var_b_bot_h.get(),
            'body_inner_d': self.var_b_body_in_d.get() | 1,  # bitwise OR 1 forces odd
            'body_thick': self.var_b_body_thick.get(),
            'body_h': self.var_b_body_h.get(),
            'top_cap_hole_d': self.var_b_top_hole_d.get() | 1,
            'top_cap_h': self.var_b_top_h.get(),
            'neck_thick': self.var_b_neck_thick.get(),
            'neck_h': self.var_b_neck_h.get()
        }
        self.barbettes.append(new_b)
        self.selected_barbette_index = len(self.barbettes) - 1
        self.selected_point_index = None
        self.sync_barbette_to_ui()
        self.notebook.select(self.tab_comp)
        self.redraw_shape()

    def sync_ui_to_barbette(self):
        # --- Abort if updating programmatically ---
        if getattr(self, '_is_syncing', False): return 

        if self.selected_barbette_index is None:
            self.lbl_comp_warn.config(text="Select a Barbette to Edit.")
            return
            
        self.lbl_comp_warn.config(text="Editing Selected Barbette", fg="green")
        b = self.barbettes[self.selected_barbette_index]
        try:
            b['mat'] = self.var_comp_mat.get()
            b['bottom_cap_h'] = int(self.var_b_bot_h.get())
            
            # --- FORCE MANUAL INPUT TO BE ODD ---
            in_d = int(self.var_b_body_in_d.get())
            if in_d % 2 == 0: 
                in_d += 1
                self.var_b_body_in_d.set(in_d) # Instantly correct the UI box
            b['body_inner_d'] = in_d

            hole_d = int(self.var_b_top_hole_d.get())
            if hole_d % 2 == 0: 
                hole_d += 1
                self.var_b_top_hole_d.set(hole_d)
            b['top_cap_hole_d'] = hole_d
            # ------------------------------------

            b['body_thick'] = int(self.var_b_body_thick.get())
            b['body_h'] = int(self.var_b_body_h.get())
            b['top_cap_h'] = int(self.var_b_top_h.get())
            b['neck_thick'] = int(self.var_b_neck_thick.get())
            b['neck_h'] = int(self.var_b_neck_h.get())
            self.redraw_shape()
        except (ValueError, tk.TclError): pass

    def sync_barbette_to_ui(self):
        if self.selected_barbette_index is None: return
        self.lbl_comp_warn.config(text="Editing Selected Barbette", fg="green")
        b = self.barbettes[self.selected_barbette_index]
        
        self._is_syncing = True
        
        self.var_comp_mat.set(b['mat'])
        self.var_b_bot_h.set(b['bottom_cap_h'])
        self.var_b_body_in_d.set(b['body_inner_d'])
        self.var_b_body_thick.set(b['body_thick'])
        self.var_b_body_h.set(b['body_h'])
        self.var_b_top_hole_d.set(b['top_cap_hole_d'])
        self.var_b_top_h.set(b['top_cap_h'])
        self.var_b_neck_thick.set(b['neck_thick'])
        self.var_b_neck_h.set(b['neck_h'])

        self._is_syncing = False

    # --- EXPORT PIPELINE ---
    def run_generator(self):
        if len(self.points) < 2: return

        initial_dir = self.var_save_path.get() if self.var_save_path.get() else BASE_DIR
        file_path = filedialog.asksaveasfilename(
            title="Save Blueprint As",
            initialdir=initial_dir,
            defaultextension=".blueprint",
            filetypes=[("FTD Blueprint", "*.blueprint"), ("All Files", "*.*")]
        )
        if not file_path: return

        self.var_save_path.set(os.path.dirname(file_path))
        self.save_settings()

        max_z = self.points[-1][0]
        z_coords = [p[0] for p in self.points]
        x_coords = [p[1] for p in self.points]
        full_z = np.arange(max_z + 1)
        full_x = np.interp(full_z, z_coords, x_coords)
        hull_profile = np.round(full_x).astype(int)

        armor_profile = [{'mat': layer['mat'].get(), 'thick': int(layer['thick'].get())} for layer in self.armor_layers]

        gen = BlueprintGenerator(
            profile=hull_profile,
            center_offset=int(self.var_limit_width.get()),
            height=int(self.var_height.get()),
            undercut=int(self.var_undercut.get()),
            uc_bow=int(self.var_uc_bow.get()),
            uc_stern=int(self.var_uc_stern.get()), 
            floor_thickness=int(self.var_floor_thickness.get()),
            save_path=file_path,
            armor_profile=armor_profile, # <--- NEW
            barbettes=self.barbettes
        )

        gen.generate()
        messagebox.showinfo("Success", f"Generated successfully at:\n{file_path}")

    def add_armor_layer(self, default_mat="Alloy", default_thick=1):
        mat_var = tk.StringVar(value=default_mat)
        thick_var = tk.IntVar(value=default_thick)

        row = tk.Frame(self.armor_list_frame, bg=THEME_PANEL_BG)
        row.pack(fill=tk.X, pady=1)

        tk.Label(row, text="Mat:", bg=THEME_PANEL_BG, fg=THEME_TEXT, font=("MS Sans Serif", 9)).pack(side=tk.LEFT)
        cb = ttk.Combobox(row, textvariable=mat_var, values=["Alloy", "Metal", "Wood", "Heavy", "Stone"], state="readonly", width=7)
        cb.pack(side=tk.LEFT, padx=2)

        tk.Label(row, text="Width:", bg=THEME_PANEL_BG, fg=THEME_TEXT, font=("MS Sans Serif", 9)).pack(side=tk.LEFT)
        sb = tk.Spinbox(row, from_=1, to=10, textvariable=thick_var, width=3)
        sb.pack(side=tk.LEFT, padx=2)

        layer_data = {'mat': mat_var, 'thick': thick_var, 'frame': row}
        
        btn_rm = tk.Button(row, text="X", fg="red", command=lambda: self.remove_armor_layer(layer_data))
        btn_rm.pack(side=tk.RIGHT, padx=2)

        self.armor_layers.append(layer_data)

    def remove_armor_layer(self, layer_data):
        if len(self.armor_layers) <= 1:
            return # Prevent removing the very last layer
        layer_data['frame'].destroy()
        self.armor_layers.remove(layer_data)

class BlueprintGenerator:
    def __init__(self, profile, center_offset, height, undercut, uc_bow, uc_stern, floor_thickness, save_path, armor_profile, barbettes):
        self.profile = profile
        self.center_offset = center_offset
        self.height = height
        self.undercut = undercut
        self.uc_bow = uc_bow
        self.uc_stern = uc_stern
        self.floor_thickness = floor_thickness
        self.save_path = save_path
        self.armor_profile = armor_profile
        self.barbettes = barbettes
        
        self.placements =[]
        self.mats = {"alloy": {}, "metal": {}, "wood": {}, "heavy": {}, "stone": {}}
        self.load_assets()

    def load_assets(self):
        for mat in self.mats: self.mats[mat] = {"beam": {}, "slope": {}, "offset": {}}
            
        loaded_data = {}
        for fname in GUIDMAP_FILES:
            fpath = os.path.join(BASE_DIR, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, 'r') as f: loaded_data.update(json.load(f))
                except Exception: pass

        for name, guid in loaded_data.items():
            name_lower = name.lower()
            
            for mat in self.mats.keys():
                is_1m = False
                if mat == "alloy" and "light-weight alloy block" in name_lower: is_1m = True
                elif mat == "heavy" and name_lower == "heavy armour": is_1m = True
                elif f"{mat} block" in name_lower: is_1m = True

                if is_1m:
                    self.mats[mat]['beam'][1] = guid
                    continue

                check_str = "heavy armour" if mat == "heavy" else mat
                if check_str not in name_lower: continue

                length = 0
                if "4m" in name_lower: length = 4
                elif "3m" in name_lower: length = 3
                elif "2m" in name_lower: length = 2
                elif "1m" in name_lower: length = 1 
                if length == 0: continue

                if "beam" in name_lower and "slope" not in name_lower and "corner" not in name_lower:
                    self.mats[mat]['beam'][length] = guid
                elif "slope" in name_lower:
                    self.mats[mat]['slope'][length] = guid
                elif "offset" in name_lower and "inverted" not in name_lower:
                    if length not in self.mats[mat]['offset']: self.mats[mat]['offset'][length] = {"left": None, "right": None}
                    if "left" in name_lower: self.mats[mat]['offset'][length]["left"] = guid
                    elif "right" in name_lower: self.mats[mat]['offset'][length]["right"] = guid

    def get_guids(self, mat_name):
        return self.mats.get(mat_name.lower(), self.mats["alloy"])

    def generate(self):
        # The outermost layer dictates the primary structural material
        primary_mat = self.armor_profile[0]['mat']
        h_guids = self.get_guids(primary_mat)
        
        if 1 not in h_guids['beam']:
             messagebox.showerror("Error", f"Missing 1m ID for {primary_mat}")
             return

        print("Generating Hull Shell...")
        self.placements =[] 
        score, result = self.simulate_hull(0, self.profile, is_inner_layer=False, guids=h_guids)

        if result: self.placements.extend(result)
        else:
            _, fb = self.simulate_hull(1, self.profile, is_inner_layer=False, guids=h_guids)
            self.placements.extend(fb)

        self.fill_stern(h_guids)
        self.stack_layers()     
        self.generate_undercut(h_guids) 
        self.generate_floor(h_guids)
            
        if self.barbettes:
            print("Carving and inserting Compartments...")
            self.generate_barbettes()

        print("Applying composite armor thickness...")
        self.apply_armor_thickness()

        self.save_to_blueprint()

    def fill_stern(self, guids):
        if not self.profile.any(): return
        dist_from_center = self.profile[-1]
        start_x = -(dist_from_center - 1)
        end_x = (dist_from_center - 1)
        guid_1m = guids['beam'].get(1)
        if not guid_1m or start_x > end_x: return
        
        for x in range(start_x, end_x + 1):
            self.placements.append({'pos': (x, 10, 0), 'rot': ROT_BEAM, 'guid': guid_1m, 'props': {"type": "beam", "len": 1, "is_stern": False}})

    def stack_layers(self):
        if self.height <= 1: return
        base_layer = list(self.placements)
        self.placements =[]
        for h in range(self.height):
            for p in base_layer:
                new_p = copy.deepcopy(p)
                new_p['pos'] = (p['pos'][0], p['pos'][1] - h, p['pos'][2])
                self.placements.append(new_p)

    def generate_undercut(self, guids):
        if self.undercut <= 0 or not self.placements: return
        min_y = min(p['pos'][1] for p in self.placements)
        parent_layer =[p for p in self.placements if p['pos'][1] == min_y]
        ship_center_z = max((p['pos'][2] for p in parent_layer), default=0) / 2

        for u in range(1, self.undercut + 1):
            current_undercut_y = min_y - u
            new_layer =[]
            occupied_coords = set()
            placed_offsets =[]

            for parent in parent_layer:
                props = parent['props']
                if props['type'] != 'slope': continue
                
                length = props['len']
                is_stern = props['is_stern']
                rot = parent['rot']
                offset_guid = None
                
                is_left_rot = rot in[ROT_LEFT_IN, ROT_LEFT_STERN, ROT_LEFT_OUT]
                is_right_rot = rot in[ROT_RIGHT_IN, ROT_RIGHT_STERN, ROT_RIGHT_OUT]

                target_dict = guids['offset'].get(length)
                if target_dict:
                    if is_stern:
                        offset_guid = target_dict["left"] if is_left_rot else target_dict["right"]
                    else:
                        offset_guid = target_dict["right"] if is_left_rot else target_dict["left"]

                if not offset_guid: continue

                # Determine the custom step steepness
                step_size = self.uc_stern if is_stern else self.uc_bow
                z_shift = step_size if is_stern else -step_size

                x, y, z = parent['pos']
                new_pos = (x, current_undercut_y, z + z_shift)

                for i in range(length): occupied_coords.add((new_pos[0], new_pos[2] - i if is_stern else new_pos[2] + i))
                
                entry = {'pos': new_pos, 'rot': rot, 'guid': offset_guid, 'props': props}
                new_layer.append(entry)
                placed_offsets.append(entry)

            raw_beam_voxels =[]
            for parent in parent_layer:
                if parent['props']['type'] == 'beam':
                    length, px, py, pz = parent['props']['len'], *parent['pos']
                    
                    # Shrink straight beams forward/backward based on which half they are on
                    beam_z_shift = -self.uc_bow if pz > ship_center_z else self.uc_stern
                    shifted_pz = pz + beam_z_shift
                    
                    for z_offset in range(length):
                        if (px, shifted_pz + z_offset) not in occupied_coords:
                             raw_beam_voxels.append((px, shifted_pz + z_offset))
                             occupied_coords.add((px, shifted_pz + z_offset))

            for off in placed_offsets:
                x, z_anchor = off['pos'][0], off['pos'][2]
                is_stern = off['props']['is_stern']
                step_size = self.uc_stern if is_stern else self.uc_bow
                
                # Dynamically fill the entire gap between the old layer and the custom step
                for d in range(1, step_size + 1):
                    current_z = z_anchor + d if is_stern else z_anchor - d
                    if (x, current_z) not in occupied_coords:
                        raw_beam_voxels.append((x, current_z))
                        occupied_coords.add((x, current_z))

            # The 2D Greedy Mesher will automatically combine our huge gaps into 2m, 3m, or 4m beams!
            new_layer.extend(self.optimize_beams(raw_beam_voxels, current_undercut_y, guids))
            self.placements.extend(new_layer)
            parent_layer = new_layer

    def generate_floor(self, guids):
        if self.floor_thickness <= 0 or not self.placements: return
        min_y = min(p['pos'][1] for p in self.placements)

        for t in range(self.floor_thickness):
            target_y = min_y + t
            occupied = set()

            for p in self.placements:
                if p['pos'][1] == target_y:
                    length, px, _, pz = p['props']['len'], *p['pos']
                    is_stern = p['props'].get('is_stern', False)
                    for i in range(length): occupied.add((px, pz - i if is_stern else pz + i))

            if not occupied: continue

            raw_floor_voxels =[]
            for z in range(min(z for x, z in occupied), max(z for x, z in occupied) + 1):
                xs = [x for x, _z in occupied if _z == z]
                if xs:
                    for x in range(min(xs) + 1, max(xs)):
                        if (x, z) not in occupied:
                            raw_floor_voxels.append((x, z))
                            occupied.add((x, z))

            self.placements.extend(self.optimize_beams(raw_floor_voxels, target_y, guids))

    def apply_armor_thickness(self):
        # Map depth to material. E.g., Metal(2) + Alloy(1) -> ['Metal', 'Metal', 'Alloy']
        depth_materials = []
        for layer in self.armor_profile:
            depth_materials.extend([layer['mat']] * layer['thick'])

        total_thickness = len(depth_materials)
        if total_thickness <= 1: 
            return # Ship is only 1 block thick (the outer shell)

        layer_map = {}
        for p in self.placements:
            x, y, z = p['pos']
            if y not in layer_map: layer_map[y] = {}
            if z not in layer_map[y]: layer_map[y][z] = set()

            length = p['props']['len']
            is_stern = p['props'].get('is_stern', False)
            for i in range(length): layer_map[y].setdefault(z - i if is_stern else z + i, set()).add(x)

        new_armor_voxels =[]
        for y, z_row in layer_map.items():
            voxels_by_mat = {}

            for z, x_set in z_row.items():
                if not x_set: continue
                max_x, min_x = max(x_set), min(x_set)

                for depth in range(1, total_thickness):
                    mat = depth_materials[depth]
                    if mat not in voxels_by_mat: voxels_by_mat[mat] =[]

                    # Thickening Starboard
                    if max_x - depth > 0 and (max_x - depth) not in x_set:
                        voxels_by_mat[mat].append((max_x - depth, z))
                        x_set.add(max_x - depth)
                        
                    # Thickening Port
                    if min_x + depth < 0 and (min_x + depth) not in x_set:
                        voxels_by_mat[mat].append((min_x + depth, z))
                        x_set.add(min_x + depth)

            # Optimize and place each material separately for this Y level
            for mat, voxels in voxels_by_mat.items():
                if voxels:
                    mat_guids = self.get_guids(mat)
                    new_armor_voxels.extend(self.optimize_beams(voxels, y, mat_guids))

        self.placements.extend(new_armor_voxels)

    # --- COMPARTMENT GENERATOR ---
    def get_ring_voxels(self, cx, y, cz, r_in, r_out):
        voxels =[]
        for x in range(cx - r_out - 1, cx + r_out + 2):
            for z in range(cz - r_out - 1, cz + r_out + 2):
                dist = round(np.sqrt((x-cx)**2 + (z-cz)**2))
                if r_in <= dist <= r_out:
                    voxels.append((x, y, z))
        return voxels

    def generate_barbettes(self):
        # 1. Map all occupied Hull voxels for Hull Priority
        occupied = set()
        for p in self.placements:
            x, y, z = p['pos']
            length = p['props']['len']
            is_stern = p['props'].get('is_stern', False)
            for i in range(length): occupied.add((x, y, z - i if is_stern else z + i))
            
        # 2. Build Compartments
        min_y = min(p['pos'][1] for p in self.placements) if self.placements else 10
        base_y = min_y + self.floor_thickness
        
        L = len(self.profile)
        
        for b in self.barbettes:
            c_guids = self.get_guids(b['mat'])
            
            bx = b['x']
            bz = L - 1 - b['z']
            
            # --- CONVERT UI DIAMETERS TO GENERATOR RADII ---
            body_inner_r = (b['body_inner_d'] + 2) // 2
            top_cap_hole_r = (b['top_cap_hole_d'] + 2) // 2
            # -----------------------------------------------
            
            # Use symmetry to build the mirror simultaneously if not centered
            centers =[(bx, bz)]
            if bx != 0: centers.append((-bx, bz))
            
            for cx, cz in centers:
                cur_y = base_y
                raw_voxels =[]
                
                body_outer_r = body_inner_r + b['body_thick']

                # Bottom Cap
                for y in range(cur_y, cur_y + b['bottom_cap_h']):
                    raw_voxels.extend(self.get_ring_voxels(cx, y, cz, 0, body_outer_r))
                cur_y += b['bottom_cap_h']
                
                # Body
                for y in range(cur_y, cur_y + b['body_h']):
                    raw_voxels.extend(self.get_ring_voxels(cx, y, cz, body_inner_r, body_outer_r))
                cur_y += b['body_h']
                
                # Top Cap
                for y in range(cur_y, cur_y + b['top_cap_h']):
                    raw_voxels.extend(self.get_ring_voxels(cx, y, cz, top_cap_hole_r, body_outer_r))
                cur_y += b['top_cap_h']
                
                # Neck
                for y in range(cur_y, cur_y + b['neck_h']):
                    raw_voxels.extend(self.get_ring_voxels(cx, y, cz, top_cap_hole_r, top_cap_hole_r + b['neck_thick']))
                    
                # 3. Filter against Hull Priority
                filtered =[(x,y,z) for x,y,z in set(raw_voxels) if (x,y,z) not in occupied]
                
                # Optimize to Beams and place
                if filtered:
                    # Group by Y level to optimize horizontally
                    by_y = {}
                    for x,y,z in filtered:
                        by_y.setdefault(y,[]).append((x,z))
                        
                    for y, xz_list in by_y.items():
                        self.placements.extend(self.optimize_beams(xz_list, y, c_guids))

    def optimize_beams(self, voxels, y_level, guids):
        optimized =[]
        
        # 1. Split the voxels into Starboard and Centerline 
        # (We completely ignore Port, because we will perfectly mirror Starboard)
        stbd_voxels = set((x, z) for x, z in voxels if x > 0)
        center_voxels = set((x, z) for x, z in voxels if x == 0)

        # Helper function to run the greedy mesher on a specific zone
        def mesh_region(voxel_set, allow_x_axis):
            region_optimized =[]
            unprocessed = set(voxel_set)
            sorted_voxels = sorted(list(unprocessed))

            for sx, sz in sorted_voxels:
                if (sx, sz) not in unprocessed: continue

                # Check max length Forward (+Z)
                len_z = 1
                while len_z < 4 and (sx, sz + len_z) in unprocessed: len_z += 1

                # Check max length Right (+X)
                len_x = 1
                if allow_x_axis:
                    while len_x < 4 and (sx + len_x, sz) in unprocessed: len_x += 1

                if len_x > len_z:
                    chosen_len = len_x
                    while chosen_len not in guids['beam'] and chosen_len > 1: chosen_len -= 1
                    rot = ROT_X_AXIS
                    for i in range(chosen_len): unprocessed.remove((sx + i, sz))
                else:
                    chosen_len = len_z
                    while chosen_len not in guids['beam'] and chosen_len > 1: chosen_len -= 1
                    rot = ROT_BEAM
                    for i in range(chosen_len): unprocessed.remove((sx, sz + i))
                
                region_optimized.append({
                    'pos': (sx, y_level, sz), 'rot': rot,
                    'guid': guids['beam'].get(chosen_len, guids['beam'].get(1)),
                    'props': {"type": "beam", "len": chosen_len, "is_stern": False}
                })
            return region_optimized

        # 2. Process Starboard and Mirror to Port
        stbd_blocks = mesh_region(stbd_voxels, allow_x_axis=True)
        for b in stbd_blocks:
            optimized.append(b) # Add original Starboard block
            
            # Create exact Port mirror
            bx, by, bz = b['pos']
            blen = b['props']['len']
            
            if b['rot'] == ROT_X_AXIS:
                # If block is sideways, the mirror's anchor shifts left by its length
                port_x = -bx - blen + 1
            else:
                # If block is forward, the anchor is just flipped
                port_x = -bx
                
            port_b = copy.deepcopy(b)
            port_b['pos'] = (port_x, by, bz)
            optimized.append(port_b)

        # 3. Process Centerline (Forced to Z-Axis only to prevent crossing the center)
        center_blocks = mesh_region(center_voxels, allow_x_axis=False)
        optimized.extend(center_blocks)

        return optimized

    def simulate_hull(self, forced_1m_zone, target_profile, is_inner_layer, guids):
        temp_placements =[]
        L = len(target_profile)
        current_z = 0
        current_min_len = 1
        total_penalty = 0

        while current_z < L:
            dist_current = target_profile[current_z]
            best_choice, min_step_cost = None, float('inf')

            all_lengths = sorted(list(set(list(guids['slope'].keys()) + list(guids['beam'].keys()))), reverse=True)
            limit_len = 1 if current_z < forced_1m_zone else 99

            candidates =[]
            for l in all_lengths:
                if l > limit_len: continue
                if not is_inner_layer and l in guids['slope']:
                    candidates.append({"type": "slope", "len": l, "offset": -1, "is_stern": False, "guid": guids['slope'][l]})
                    candidates.append({"type": "slope", "len": l, "offset": 1, "is_stern": True, "guid": guids['slope'][l]})
                if l in guids['beam']:
                    candidates.append({"type": "beam", "len": l, "offset": 0, "is_stern": False, "guid": guids['beam'][l]})

            for cand in candidates:
                b_len = cand["len"]
                if current_z + b_len > L: continue

                target_x = target_profile[current_z + b_len] if current_z + b_len < L else target_profile[-1]
                error = abs(target_x - (dist_current - cand["offset"]))

                if error > (1.5 if is_inner_layer else 1.0): continue

                len_penalty = (current_min_len - b_len) * 10 if b_len < current_min_len else -(b_len * 2)
                total_step_cost = len_penalty + 10 + (error * 50)

                if b_len > 1 and not is_inner_layer:
                    lookahead_z = current_z + int(b_len * 1.5)
                    if lookahead_z < L and abs(target_profile[lookahead_z] - (dist_current - (cand["offset"] * ((lookahead_z - current_z) / b_len)))) > 1.0:
                        continue

                if total_step_cost < min_step_cost:
                    min_step_cost = total_step_cost
                    best_choice = cand

            if not best_choice:
                total_penalty += 200
                current_min_len = 1
                fb_cands = []
                if not is_inner_layer and 1 in guids['slope']:
                    fb_cands.extend([{"type": "slope", "len": 1, "offset": -1, "is_stern": False, "guid": guids['slope'][1]},
                                     {"type": "slope", "len": 1, "offset": 1, "is_stern": True, "guid": guids['slope'][1]}])
                if 1 in guids['beam']: fb_cands.append({"type": "beam", "len": 1, "offset": 0, "is_stern": False, "guid": guids['beam'].get(1)})

                best_err = float('inf')
                for c in fb_cands:
                    if current_z + c["len"] <= L:
                        err = abs((target_profile[current_z+1] if current_z+1 < L else target_profile[-1]) - (dist_current - c["offset"]))
                        if err < best_err: best_err, best_choice = err, c

                if not best_choice: current_z += 1; continue

            total_penalty += min_step_cost
            current_min_len = best_choice["len"]
            placement_z = L - (current_z + (1 if best_choice["is_stern"] else current_min_len))
            rot_left = rot_right = ROT_BEAM
            gx_left, gx_right = -dist_current, dist_current

            if best_choice["type"] == "slope":
                if best_choice["is_stern"]: rot_left, rot_right = ROT_LEFT_STERN, ROT_RIGHT_STERN
                else:
                    if best_choice["offset"] == -1: rot_left, rot_right, gx_left, gx_right = ROT_LEFT_OUT, ROT_RIGHT_OUT, gx_left - 1, gx_right + 1
                    else: rot_left, rot_right = ROT_LEFT_IN, ROT_RIGHT_IN

            temp_placements.append({'pos': (gx_left, 10, placement_z), 'rot': rot_left, 'guid': best_choice["guid"], 'props': best_choice})
            temp_placements.append({'pos': (gx_right, 10, placement_z), 'rot': rot_right, 'guid': best_choice["guid"], 'props': best_choice})
            current_z += current_min_len

        return total_penalty, temp_placements

    def save_to_blueprint(self):
        if not os.path.exists(DONOR_BLUEPRINT): return messagebox.showerror("Error", f"Missing {DONOR_BLUEPRINT}")
        with open(DONOR_BLUEPRINT, "r") as f: bp = json.load(f)

        bp["Blueprint"]["SCs"] = []; bp["Blueprint"]["BP1"] = None; bp["Blueprint"]["BP2"] = None
        guid_map, next_id = {}, 1000
        bp["Blueprint"]["BLP"] = []; bp["Blueprint"]["BLR"] = []; bp["Blueprint"]["BlockIds"] = []; bp["Blueprint"]["BCI"] =[]

        for p in self.placements:
            pos, rot, guid = p['pos'], p['rot'], p['guid']
            if guid not in guid_map: guid_map[guid] = next_id; next_id += 1
            bp["Blueprint"]["BLP"].append(f"{int(pos[0])},{int(pos[1])},{int(pos[2])}")
            bp["Blueprint"]["BLR"].append(int(rot))
            bp["Blueprint"]["BlockIds"].append(int(guid_map[guid]))
            bp["Blueprint"]["BCI"].append(0)

        if "ItemDictionary" not in bp: bp["ItemDictionary"] = {}
        for g, i in guid_map.items(): bp["ItemDictionary"][str(i)] = g

        count = len(self.placements)
        bp["Blueprint"]["BlockState"] = f"=0,{count}"
        bp["Blueprint"]["TotalBlockCount"] = bp["Blueprint"]["AliveCount"] = bp["SavedTotalBlockCount"] = count

        with open(self.save_path if self.save_path else os.path.join(BASE_DIR, OUTPUT_FILENAME), "w") as f: json.dump(bp, f)

if __name__ == "__main__":
    root = tk.Tk()
    app = HullDesigner(root)
    root.mainloop()
