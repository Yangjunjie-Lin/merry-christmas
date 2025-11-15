#!/usr/bin/env python3
"""
GUI animated Christmas tree with decorations.

Features:
- Prompts for your name in a dialog.
- Opens a new window and animates flashing points to form a tree.
- Adds ornaments, string lights, and gifts at the base.
- Pops up a greeting with your name when the tree finishes.

Run: `python tree_gui.py`
"""
import tkinter as tk
from tkinter import simpledialog, messagebox

import random
import math
try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

class ChristmasTreeGUI:
    def __init__(self, name=None, width=800, height=600):
        self.root = tk.Tk()
        self.root.title('Merry Christmas')
        self.width = width
        self.height = height
        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height, bg='#0b1220')
        self.canvas.pack()

        # prepare PIL backing image and PhotoImage for smooth rendering
        if PIL_AVAILABLE:
            self.img = Image.new('RGBA', (self.width, self.height), '#0b1220')
            self.draw = ImageDraw.Draw(self.img)
            self.photo = ImageTk.PhotoImage(self.img)
            self.canvas_image = self.canvas.create_image(0, 0, anchor='nw', image=self.photo)
            # keep a small cache of PhotoImage objects to avoid GC issues
            self._photo_cache = [self.photo]

        self.name = name
        self.tree_top_y = 30
        # increase rows to add many more points (taller tree)
        self.tree_height_rows = 34
        # initial pixel parameters (will be adapted to window in build_positions)
        self.point_spacing = 3
        self.point_v_spacing = 3
        self.pixel_size = 3

        self.points = []  # list of (row, col, x, y)
        # particles: moving pixels that fly toward target positions
        self.particles = []  # list of dicts with start/target/progress
        self.revealed = set()
        self.ornament_ids = set()
        self.lights = []  # list of canvas ids for lights

        self.build_positions()
        self.create_gifts()
        self.create_star()

        # prepare pixel text for name and greeting
        self.name_pixel_ids = []
        self.greeting_pixel_ids = []
        self.prepare_text_pixels()
        self.animation_running = True
        self.flash_cycle = 0
        self.greet_shown = False
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)

    def build_positions(self):
        cx = self.width // 2
        top = self.tree_top_y
        rows = self.tree_height_rows
        # Compute spacing dynamically so the tree fills most of the canvas
        max_cols = 2 * (rows - 1) + 1
        # use most of canvas width for tree (close to full width)
        avail_w = int(self.width * 0.92)
        # horizontal spacing per column (at least 2 pixels)
        h_spacing = max(2, avail_w // max_cols)
        # vertical spacing: fit rows into available height under the top (leave room for text)
        # leave modest space for text/greeting below
        avail_h = max(100, self.height - top - 80)
        v_spacing = max(2, avail_h // rows)

        # store computed spacings for other code to use
        self.point_spacing = h_spacing
        self.point_v_spacing = v_spacing
        # pick pixel size relative to horizontal spacing
        self.pixel_size = max(2, h_spacing // 2)

        for r in range(rows):
            cols = 2 * r + 1
            row_y = top + r * (self.point_v_spacing + 1)
            row_width = cols * (self.point_spacing + 1)
            start_x = cx - row_width // 2
            for c in range(cols):
                x = start_x + c * (self.point_spacing + 1)
                y = row_y
                # store target position
                self.points.append((r, c, x, y))
                # create a particle that will fly from a random offscreen start to (x,y)
                angle = random.random() * 2 * math.pi
                # start radius: somewhere off-canvas
                diag = math.hypot(self.width, self.height)
                radius = random.uniform(diag * 0.5, diag * 1.2)
                sx = cx + math.cos(angle) * radius
                sy = top + math.sin(angle) * radius
                # depth factor (affects size and brightness)
                depth = random.uniform(0.6, 1.2)
                # particle parameters; rendering will be done by PIL per-frame
                steps = random.randint(18, 48)
                particle = {
                    'index': len(self.points) - 1,
                    'row': r,
                    'start_x': sx,
                    'start_y': sy,
                    'target_x': x,
                    'target_y': y,
                    'step': 0,
                    'steps': steps,
                    'depth': depth,
                    'arrived': False,
                    'size': max(1, int(self.pixel_size * 0.5 * depth)),
                    # floating phase for subtle post-arrival motion
                    'float_phase': random.random() * 2 * math.pi,
                    'float_amp': random.uniform(0.6, 2.4) * (1.4 - depth),
                    'final_color': None,
                    # velocity for fluid motion
                    'vx': (x - sx) * 0.02,
                    'vy': (y - sy) * 0.02,
                    'state': 'flying',
                    'angle': random.random() * 2 * math.pi,
                    'orbit_radius': random.uniform(0.5, 2.6) * (1.6 - depth),
                }
                self.particles.append(particle)

        # --- (Initial starts will be reassigned later) ---
        # We intentionally defer assigning a unified incoming direction here
        # so that trunk/star particles (appended below) can be handled together.

        # --- Add trunk and star target points so they are constructed from particles too ---
        # trunk grid
        trunk_w = max(10, self.pixel_size * 6)
        trunk_h = max(24, (self.tree_height_rows * (self.point_v_spacing + 1)) // 6)
        base_y = top + rows * (self.point_v_spacing + 1) + 10
        trunk_left = cx - trunk_w // 2
        trunk_top = base_y
        # grid spacing
        step_x = self.point_spacing + 1
        step_y = self.point_v_spacing + 1
        cols_t = max(2, trunk_w // step_x)
        rows_t = max(2, trunk_h // step_y)
        for rr in range(rows_t):
            for cc in range(cols_t):
                tx = trunk_left + cc * step_x + step_x // 2
                ty = trunk_top + rr * step_y + step_y // 2
                self.points.append(('trunk', rr, tx, ty))
                # create particle targeting trunk cell
                angle0 = random.random() * 2 * math.pi
                radius = random.uniform(diag * 0.6, diag * 1.0)
                sx = cx + math.cos(angle0) * radius
                sy = top + math.sin(angle0) * radius
                depth = random.uniform(0.7, 1.0)
                particle = {
                    'index': len(self.points) - 1,
                    'row': rows + rr,
                    'start_x': sx,
                    'start_y': sy,
                    'target_x': tx,
                    'target_y': ty,
                    'step': 0,
                    'steps': random.randint(20, 46),
                    'depth': depth,
                    'arrived': False,
                    'size': max(1, int(self.pixel_size * 0.6 * depth)),
                    'float_phase': random.random() * 2 * math.pi,
                    'float_amp': random.uniform(0.6, 1.6),
                    'final_color': None,
                    'vx': (tx - sx) * 0.02,
                    'vy': (ty - sy) * 0.02,
                    'state': 'flying',
                    'angle': random.random() * 2 * math.pi,
                    'orbit_radius': random.uniform(0.6, 1.6) * (1.4 - depth),
                }
                self.particles.append(particle)

        # star points (small cluster around top)
        if self.points:
            try:
                top_px = self.points[0]
                sx = top_px[2]
                sy = top_px[3] - int(self.point_v_spacing * 1.5)
            except Exception:
                sx = cx
                sy = top
            star_rad = max(6, int(self.pixel_size * 4))
            for i in range(10):
                ang = i * 2 * math.pi / 10
                tx = int(sx + math.cos(ang) * (star_rad * random.uniform(0.4, 1.0)))
                ty = int(sy + math.sin(ang) * (star_rad * random.uniform(0.4, 1.0)))
                self.points.append(('star', i, tx, ty))
                angle0 = random.random() * 2 * math.pi
                radius = random.uniform(diag * 0.5, diag * 0.9)
                sx0 = cx + math.cos(angle0) * radius
                sy0 = top + math.sin(angle0) * radius
                depth = random.uniform(0.8, 1.0)
                particle = {
                    'index': len(self.points) - 1,
                    'row': -1,
                    'start_x': sx0,
                    'start_y': sy0,
                    'target_x': tx,
                    'target_y': ty,
                    'step': 0,
                    'steps': random.randint(10, 40),
                    'depth': depth,
                    'arrived': False,
                    'size': max(1, int(self.pixel_size * 0.8 * depth)),
                    'float_phase': random.random() * 2 * math.pi,
                    'float_amp': random.uniform(0.6, 1.2),
                    'final_color': None,
                    'vx': (tx - sx0) * 0.02,
                    'vy': (ty - sy0) * 0.02,
                    'state': 'flying',
                    'angle': random.random() * 2 * math.pi,
                    'orbit_radius': random.uniform(0.6, 1.4) * (1.4 - depth),
                }
                self.particles.append(particle)

        # optionally increase particle density for a more 'fluid' look
        # multiplier controls how many moving particles per tree point
        # increase this for many-many particles (watch performance)
        configured_density = 6  # desired default density

        # safety cap: limit total particle count to avoid freezing on slow machines
        max_particles = 3500
        base_points = len(self.particles)
        if base_points == 0:
            self.particle_density = 1
        else:
            # compute density that would keep total under max_particles
            safe_density = max(1, min(configured_density, max_particles // base_points))
            self.particle_density = safe_density

        if self.particle_density > 1:
            extra = []
            for p in self.particles:
                for k in range(self.particle_density - 1):
                    q = p.copy()
                    # jitter start slightly and randomize velocity to avoid strict clones
                    q['start_x'] = p['start_x'] + random.uniform(-40, 40)
                    q['start_y'] = p['start_y'] + random.uniform(-40, 40)
                    q['vx'] = p['vx'] * random.uniform(0.6, 1.6)
                    q['vy'] = p['vy'] * random.uniform(0.6, 1.6)
                    q['float_phase'] = random.random() * 2 * math.pi
                    q['angle'] = random.random() * 2 * math.pi
                    # small variation in orbit radius
                    q['orbit_radius'] = max(0.8, q.get('orbit_radius', 1.0) * random.uniform(0.6, 1.6))
                    extra.append(q)
            self.particles.extend(extra)

        # 重新分配起始位置：所有粒子从左右两边汇集到中央
        # 根据目标x坐标决定从左边还是右边飞来
        try:
            cx = self.width // 2
            for p in self.particles:
                tx = p['target_x']
                ty = p['target_y']
                
                # 根据目标位置在中心的左边还是右边，决定从哪边飞来
                if tx < cx:
                    # 目标在左边，从左边飞来
                    sx = int(-random.uniform(self.width * 0.3, self.width * 1.0))
                else:
                    # 目标在右边，从右边飞来
                    sx = int(self.width + random.uniform(self.width * 0.3, self.width * 1.0))
                
                # y坐标在整个屏幕高度范围内随机，营造从四面八方汇集的效果
                sy = int(random.uniform(-self.height * 0.3, self.height * 1.2))
                
                # 更新粒子起始位置和速度
                p['start_x'] = sx
                p['start_y'] = sy
                p['vx'] = (tx - sx) * 0.02
                p['vy'] = (ty - sy) * 0.02
        except Exception:
            # 如果出错，保持原有起始位置
            pass

        # final particle count is intentionally silent in normal runs

        # choose ornaments and lights with more harmonious distribution
        all_idxs = list(range(len(self.points)))
        # weight ornaments by row: favor middle and lower-middle rows for visual balance
        row_weights = []
        for i in all_idxs:
            r = self.points[i][0]
            # some entries may be labeled (e.g. 'trunk' or 'star'); map them to numeric
            if isinstance(r, (int, float)):
                rnum = r
            else:
                if r == 'star':
                    # star sits at the very top
                    rnum = 0
                elif r == 'trunk':
                    # trunk is below the tree; place weight low for ornaments
                    rnum = rows + (rows // 6)
                else:
                    # fallback to middle of tree
                    try:
                        rnum = int(r)
                    except Exception:
                        rnum = rows // 2
            # weight peaks near 60% of tree height
            wt = 1.0 + max(0, (1.0 - abs((rnum / rows) - 0.6)) * 4.0)
            row_weights.append(wt)
        # sample ornaments using weighted roulette
        ornaments_count = max(12, len(all_idxs)//18)
        ornaments = set()
        while len(ornaments) < ornaments_count and len(ornaments) < len(all_idxs):
            pick = random.choices(all_idxs, weights=row_weights, k=1)[0]
            ornaments.add(pick)

        # lights: place symmetric pairs along rows so they read as strings
        lights = []
        # for each row choose a small number of paired lights
        for r in range(rows):
            # find indices in this row
            row_idxs = [i for i in all_idxs if self.points[i][0] == r]
            if not row_idxs:
                continue
            # sample up to 2 pairs per row depending on width
            pairs = min(2, max(0, len(row_idxs)//6))
            for _ in range(pairs):
                pi = random.choice(row_idxs)
                rr, cc, tx, ty = self.points[pi]
                # find mirrored column if available
                # choose a small horizontal offset for visual spacing
                offset = (self.point_spacing + 1) * random.randint(1, max(1, cc//3 + 1))
                left_x = tx - offset
                right_x = tx + offset
                lights.append((left_x, ty))
                lights.append((right_x, ty))

        self.ornament_map = set(ornaments)
        self.lights_map = set([i for i in all_idxs if i in ornaments])
        # lights: store light target positions; drawing will be handled in render
        self.lights = lights

        # create some gifts near the base, symmetric and ribboned
        self.gift_pixel_ids = []
        base_candidates = []
        for i in all_idxs:
            r = self.points[i][0]
            try:
                if isinstance(r, (int, float)) and r >= rows - 3:
                    base_candidates.append(i)
            except Exception:
                # skip non-numeric row labels (e.g. 'trunk'/'star')
                continue
        gift_spots = []
        if base_candidates:
            count = max(2, len(base_candidates)//12)
            # pick symmetric pairs across center
            center = self.width // 2
            for _ in range(count):
                spot = random.choice(base_candidates)
                r, c, x, y = self.points[spot]
                # place one on left and one mirrored on right (if room)
                gift_spots.append((x, y))
                mirrored_x = center + (center - x)
                gift_spots.append((mirrored_x, y))
        # generate clusters with ribbon color
        gift_colors = ['#c62828', '#1565c0', '#6a1b9a', '#ffd54a']
        ribbon_colors = ['#ffd54a', '#ffffff']
        for (gx, gy) in gift_spots:
            cluster = []
            for dy in (0, 1):
                for dx in (-1, 0, 1):
                    px = gx + dx * (self.point_spacing + 1)
                    py = gy + dy * (self.point_v_spacing + 1)
                    # choose ribbon pixel in center
                    if dx == 0 and dy == 0:
                        cluster.append({'x': px, 'y': py, 'ribbon': True, 'color': random.choice(ribbon_colors)})
                    else:
                        cluster.append({'x': px, 'y': py, 'ribbon': False, 'color': random.choice(gift_colors)})
            self.gift_pixel_ids.append(cluster)

    def create_star(self):
        # place a star at the top position (above first row)
        if not self.points:
            return
        _, _, x, y = self.points[0]
        # store star position for PIL rendering (do not create canvas polygon)
        self.star_pos = (x, y)

    # --- Utility: simple color helpers and 3D pixel drawing ---
    def hex_to_rgb(self, h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def rgb_to_hex(self, rgb):
        return '#%02x%02x%02x' % (max(0, min(255, int(rgb[0]))), max(0, min(255, int(rgb[1]))), max(0, min(255, int(rgb[2]))))

    def brighten(self, hexc, factor=1.3):
        r, g, b = self.hex_to_rgb(hexc)
        return self.rgb_to_hex((r * factor, g * factor, b * factor))

    def darken(self, hexc, factor=0.6):
        r, g, b = self.hex_to_rgb(hexc)
        return self.rgb_to_hex((r * factor, g * factor, b * factor))

    def create_pixel(self, x, y, color, size=None):
        # create a small 3D-looking pixel at (x,y). Returns tuple of ids (base, highlight, shadow)
        if size is None:
            size = self.pixel_size
        half = max(1, size // 2)
        base = self.canvas.create_rectangle(x-half, y-half, x+half, y+half, fill=color, outline='')
        # highlight and shadow adapted for very small pixels: draw tiny top-left and bottom-right accents
        hl_color = self.brighten(color, 1.4)
        sh_color = self.darken(color, 0.5)
        try:
            # top-left accent
            hl = self.canvas.create_rectangle(x-half, y-half, x, y, fill=hl_color, outline='')
            # bottom-right accent
            sh = self.canvas.create_rectangle(x, y, x+half, y+half, fill=sh_color, outline='')
        except Exception:
            hl = None
            sh = None
        return (base, hl, sh)

    def move_pixel(self, ids, x, y, size=None):
        # move an existing 3D pixel (ids tuple) to new center (x,y) and resize
        # legacy helper (no-op when using PIL rendering)
        return

    def create_gifts(self):
        # Instead of drawing large boxes at the base, place a trunk and
        # rely on gift pixel clusters and trunk particles attached to tree positions.
        # set gift_ids empty for compatibility; actual gifts are pixel clusters created in build_positions
        self.gift_ids = []

    def prepare_text_pixels(self):
        # render the name and a blessing message as pixel blocks
        who = self.name if self.name else 'Friend'
        greeting = 'Merry Christmas'
        # place name below the tree base
        base_y = self.tree_top_y + self.tree_height_rows * (self.point_v_spacing + 1) + 36
        # Render greeting then name (greeting above name)
        if PIL_AVAILABLE:
            # larger render scale for clarity: prepare structured pixel descriptors
            g_coords = self.render_text_pixels(greeting, base_y - 18)
            n_coords = self.render_text_pixels(who, base_y + 18)

            def make_pixel_list(coords, base_colors):
                if not coords:
                    return []
                xs = [c[0] for c in coords]
                min_x, max_x = min(xs), max(xs)
                span = max(1, max_x - min_x)
                pixels = []
                for i, (x, y) in enumerate(coords):
                    t = (x - min_x) / span
                    # pick gradient color across provided base_colors
                    ci = int(t * (len(base_colors) - 1))
                    base_color = base_colors[ci]
                    pixels.append({'x': x, 'y': y, 'phase': random.random() * 2 * math.pi, 'base_color': base_color})
                return pixels

            # choose a richer gradient for the greeting and name
            greet_base = ['#ffd54a', '#ff8a65', '#ff7043', '#f06292', '#ba68c8']
            name_base = ['#ffffff', '#e0f7fa', '#b2ebf2']
            self.greeting_pixels = make_pixel_list(g_coords, greet_base)
            self.name_pixels = make_pixel_list(n_coords, name_base)
            # keep compatibility fields empty for non-PIL paths
            self.greeting_pixel_ids = []
            self.name_pixel_ids = []
        else:
            # fallback: normal canvas text if Pillow not installed
            self.greeting_pixel_ids = [self.canvas.create_text(self.width//2, base_y - 12, text=greeting,
                                                               fill='white', font=('Helvetica', 14, 'bold'))]
            self.name_pixel_ids = [self.canvas.create_text(self.width//2, base_y + 12, text=who,
                                                            fill='white', font=('Helvetica', 14, 'bold'))]

    def animate(self):
        # animate frame
        # advance particle positions (flight progress)
        for p in self.particles:
            if p['arrived']:
                continue
            p['step'] += 1
            if p['step'] >= p['steps']:
                p['step'] = p['steps']
                p['arrived'] = True
            # interpolation (ease-out)
            t = p['step'] / p['steps']
            t = 1 - (1 - t) * (1 - t)
            p['cur_x'] = p['start_x'] + (p['target_x'] - p['start_x']) * t
            p['cur_y'] = p['start_y'] + (p['target_y'] - p['start_y']) * t
            p['cur_size'] = max(1, int(self.pixel_size * (0.4 + 0.6 * t) * p['depth']))
            if p['arrived']:
                # freeze final color for stability
                if p['index'] in self.ornament_map:
                    p['final_color'] = random.choice(['#e91e63', '#f44336', '#ffeb3b', '#03a9f4', '#9c27b0'])
                else:
                    # use a brighter green for visibility against dark background
                    p['final_color'] = self.brighten('#2e7d32', 1.6)
                self.revealed.add(p['index'])

        # render current frame into PIL image for smooth drawing using alpha fade
        if PIL_AVAILABLE:
            # fade previous frame slightly to create motion trails (motion blur)
            try:
                # ensure image is RGBA mode
                if getattr(self, 'img', None) is None:
                    self.img = Image.new('RGBA', (self.width, self.height), '#0b1220')
                if self.img.mode != 'RGBA':
                    try:
                        self.img = self.img.convert('RGBA')
                    except Exception:
                        self.img = Image.new('RGBA', (self.width, self.height), '#0b1220')
                overlay = Image.new('RGBA', (self.width, self.height), (11, 18, 32, 18))
                self.img = Image.alpha_composite(self.img, overlay)
                # recreate draw for the updated image reference
                self.draw = ImageDraw.Draw(self.img)
            except Exception:
                # fallback to hard clear
                self.draw.rectangle([(0, 0), (self.width, self.height)], fill='#0b1220')

            # Star is now composed from particles (no hard polygon draw)
            # keep `star_pos` available for reference, but rely on particles
            # to form the visible star instead of drawing a filled polygon here.

            # Trunk is now built from particles (no hard rectangle draw)
            # rely on trunk particles created in build_positions() to form it.

            # text color (compute before drawing so text uses it)
            text_on = (self.flash_cycle // 3) % 2 == 0
            text_color = '#ffd54a' if text_on else '#ffffff'

            # update and draw particles with fluid velocity-based motion
            for p in self.particles:
                idx = p['index']
                # initialize current pos if missing
                x = p.get('cur_x', p['start_x'])
                y = p.get('cur_y', p['start_y'])
                vx = p.get('vx', 0.0)
                vy = p.get('vy', 0.0)
                tx = p['target_x']
                ty = p['target_y']
                depth = p.get('depth', 1.0)

                # acceleration towards target (gentle) and damping for fluid motion
                ax = (tx - x) * 0.015 * (1.0 + (1.2 - depth))
                ay = (ty - y) * 0.015 * (1.0 + (1.2 - depth))
                vx += ax
                vy += ay
                # damping
                vx *= 0.92
                vy *= 0.92

                # integrate
                x += vx
                y += vy

                # 判断是否到达目标位置并切换到流动状态
                dist = math.hypot(tx - x, ty - y)
                if dist < max(1.5, 1.4 * p.get('size', 1)):
                    # 到达目标后切换到流动状态
                    p['state'] = 'flowing'
                    # 初始化流动角度
                    if 'flow_angle' not in p:
                        p['flow_angle'] = random.random() * 2 * math.pi
                
                if p.get('state') == 'flowing':
                    # 所有粒子都在目标位置附近做小范围的圆周流动
                    # 更新流动角度（持续旋转）
                    p['flow_angle'] = p.get('flow_angle', 0.0) + random.uniform(0.04, 0.08)
                    
                    # 流动半径（小范围）
                    flow_radius = random.uniform(1.5, 3.5)
                    
                    # 计算流动偏移
                    flow_x = math.cos(p['flow_angle']) * flow_radius
                    flow_y = math.sin(p['flow_angle']) * flow_radius
                    
                    # 在目标位置附近流动
                    x = tx + flow_x
                    y = ty + flow_y
                    
                    # 添加微小的随机抖动，增加流动感
                    x += math.cos(self.flash_cycle * 0.05 + idx) * 0.5
                    y += math.sin(self.flash_cycle * 0.05 + idx) * 0.5

                # store back
                p['cur_x'] = x
                p['cur_y'] = y
                p['vx'] = vx
                p['vy'] = vy
                p['cur_size'] = max(1, int(p.get('size', 1) * (0.8 + (1.0 - depth) * 0.6)))

                # 颜色选择：所有粒子在流动状态下保持最终颜色
                if p.get('state') == 'flowing':
                    if idx in self.ornament_map:
                        base_color = p.get('final_color') or random.choice(['#e91e63', '#f44336', '#ffeb3b', '#03a9f4', '#9c27b0'])
                    else:
                        base_color = p.get('final_color') or '#2e7d32'
                else:
                    # 飞行中的粒子使用闪烁的暖色
                    base_color = '#ffd54a' if (self.flash_cycle + idx) % 6 < 3 else '#101216'

                # 所有粒子都绘制成流动小球，但不同元素有不同特色
                # 确定粒子所属的点类型
                point_type = None
                try:
                    point_type = self.points[p['index']][0]
                except Exception:
                    point_type = None

                # 判断是否为装饰球
                is_ornament = (p['index'] in getattr(self, 'ornament_map', set()))

                # 根据类型设置不同的小球大小和颜色
                if point_type == 'star':
                    # 星星：最大最亮
                    ball_size = max(3, int(self.pixel_size * 1.2))
                    pix_color = '#ffd54a'
                elif point_type == 'trunk':
                    # 树干：较大，棕色
                    ball_size = max(3, int(self.pixel_size * 0.9))
                    pix_color = '#8d6e63'
                elif is_ornament:
                    # 装饰球：大一些，彩色
                    ball_size = max(3, int(self.pixel_size * 1.0))
                    pix_color = p.get('final_color') or random.choice(['#e91e63', '#f44336', '#ffeb3b', '#03a9f4', '#9c27b0'])
                else:
                    # 树叶：正常大小，绿色
                    ball_size = max(2, int(self.pixel_size * 0.7))
                    pix_color = base_color
                
                half = max(1, int(ball_size // 2))
                x0 = int(x - half)
                y0 = int(y - half)
                x1 = int(x + half)
                y1 = int(y + half)

                # 绘制流动的小球（所有元素统一样式）
                try:
                    # 绘制基础圆形小球
                    self.draw.ellipse([x0, y0, x1, y1], fill=pix_color)
                    
                    # 添加高光效果，让小球更有立体感
                    hlc = self.brighten(pix_color, 1.5)
                    # 高光位置（左上角小圆）
                    hl_size = max(1, half // 2)
                    try:
                        self.draw.ellipse([x0, y0, x0 + hl_size, y0 + hl_size], fill=hlc)
                    except Exception:
                        pass
                except Exception:
                    # 如果绘制失败，使用矩形作为后备
                    try:
                        self.draw.rectangle([x0, y0, x1, y1], fill=pix_color)
                    except Exception:
                        pass

            # (debug indicator removed)

            # 绘制灯光为流动的小球，带有脉动效果
            light_colors = ['#ffd54a', '#ff8a65', '#ff7043', '#f06292', '#4fc3f7']
            for j, (lx, ly) in enumerate(self.lights):
                # 灯光使用较大的小球样式，带脉动效果
                phase = (j * 0.8) + (self.flash_cycle * 0.06)
                pulse = 0.85 + 0.25 * math.sin(phase)
                lc = light_colors[j % len(light_colors)]
                
                # 灯光：较大且有脉动
                ball_size = max(3, int(self.pixel_size * 0.85 * pulse))
                half = max(1, int(ball_size // 2))
                
                # 绘制发光的小球
                try:
                    # 基础小球
                    self.draw.ellipse([lx-half, ly-half, lx+half, ly+half], fill=lc)
                    # 高光效果
                    hlc = self.brighten(lc, 1.6)
                    hl_size = max(1, half // 2)
                    self.draw.ellipse([lx-half, ly-half, lx-half+hl_size, ly-half+hl_size], fill=hlc)
                except Exception:
                    self.draw.rectangle([lx-half, ly-half, lx+half, ly+half], fill=lc)

            # 绘制礼物为流动的小球簇，带闪烁效果
            gift_colors = ['#c62828', '#1565c0', '#6a1b9a', '#ffd54a']
            for gi, cluster in enumerate(self.gift_pixel_ids):
                gc = gift_colors[(self.flash_cycle + gi) % len(gift_colors)] if (self.flash_cycle + gi) % 4 < 2 else '#0b1220'
                for k, item in enumerate(cluster):
                    if isinstance(item, dict):
                        gx = item.get('x')
                        gy = item.get('y')
                        color = item.get('color', gc)
                        if item.get('ribbon'):
                            # 丝带用特殊颜色
                            color = item.get('color', '#ffd54a')
                    else:
                        try:
                            gx, gy = item
                        except Exception:
                            continue
                        color = gc
                        if (self.flash_cycle + gi + k) % 5 == 0:
                            color = self.brighten(gc, 1.2)
                    
                    # 礼物小球：中等大小
                    ball_size = max(2, int(self.pixel_size * 0.8))
                    half = max(1, int(ball_size // 2))
                    
                    # 绘制礼物小球
                    try:
                        self.draw.ellipse([gx-half, gy-half, gx+half, gy+half], fill=color)
                        # 高光
                        hlc = self.brighten(color, 1.4)
                        hl_size = max(1, half // 2)
                        self.draw.ellipse([gx-half, gy-half, gx-half+hl_size, gy-half+hl_size], fill=hlc)
                    except Exception:
                        self.draw.rectangle([gx-half, gy-half, gx+half, gy+half], fill=color)

            # 绘制文字像素为统一的小球，带波浪和闪烁效果
            def draw_pixel_list(pixels, default_color, speed=0.12, amp=2.4):
                for i, pix in enumerate(pixels):
                    x = pix['x']
                    y = pix['y']
                    phase = pix.get('phase', 0.0)
                    base_color = pix.get('base_color', default_color)
                    # 波浪偏移
                    wy = math.sin(self.flash_cycle * speed + phase) * amp
                    # 闪烁效果
                    tw = 1.0
                    if (self.flash_cycle + i) % 12 == 0:
                        tw = 1.4
                    color = base_color if tw == 1.0 else self.brighten(base_color, tw)
                    
                    # 文字小球：稍大一些以便阅读
                    ball_size = max(3, int(self.pixel_size * 0.85))
                    half = max(1, int(ball_size // 2))
                    bx0 = int(x - half)
                    by0 = int(y + wy - half)
                    bx1 = int(x + half)
                    by1 = int(y + wy + half)
                    
                    # 绘制文字小球
                    try:
                        self.draw.ellipse([bx0, by0, bx1, by1], fill=color)
                        # 高光
                        hlc = self.brighten(color, 1.5)
                        hl_size = max(1, half // 2)
                        self.draw.ellipse([bx0, by0, bx0+hl_size, by0+hl_size], fill=hlc)
                    except Exception:
                        self.draw.rectangle([bx0, by0, bx1, by1], fill=color)

            if hasattr(self, 'greeting_pixels'):
                draw_pixel_list(self.greeting_pixels, '#ffd54a', speed=0.14, amp=2.6)
            if hasattr(self, 'name_pixels'):
                draw_pixel_list(self.name_pixels, '#ffffff', speed=0.10, amp=1.8)

            # push PIL image to PhotoImage and update canvas (recreate PhotoImage)
            try:
                self.photo = ImageTk.PhotoImage(self.img)
                # cache reference to avoid GC and keep a small history
                try:
                    self._photo_cache.append(self.photo)
                    if len(self._photo_cache) > 6:
                        self._photo_cache.pop(0)
                except Exception:
                    self._photo_cache = [self.photo]
                self.canvas.itemconfigure(self.canvas_image, image=self.photo)
                # force the canvas to update immediately
                try:
                    self.canvas.update_idletasks()
                except Exception:
                    pass
            except Exception:
                pass

        # If PIL is not available, fall back to per-item canvas animation
        if not PIL_AVAILABLE:
            # animate lights (cycle colors) -- lights stored as ids tuples for 3D pixels
            light_colors = ['#ffeb3b', '#ff7043', '#f06292', '#4fc3f7', '#aed581']
            for j, lid_ids in enumerate(self.lights):
                # lid_ids may be a tuple (base, hl, sh)
                color = light_colors[(self.flash_cycle + j) % len(light_colors)] if (self.flash_cycle + j) % 4 < 2 else '#101826'
                if isinstance(lid_ids, (list, tuple)):
                    base_id, hl_id, sh_id = lid_ids
                    self.canvas.itemconfigure(base_id, fill=color)
                    try:
                        self.canvas.itemconfigure(hl_id, fill=self.brighten(color, 1.4))
                        self.canvas.itemconfigure(sh_id, fill=self.darken(color, 0.5))
                    except Exception:
                        pass
                else:
                    try:
                        self.canvas.itemconfigure(lid_ids, fill=color)
                    except Exception:
                        pass

            # animate gifts (clusters of pixels) with flashing colors
            gift_colors = ['#c62828', '#1565c0', '#6a1b9a', '#ffd54a']
            for gi, cluster in enumerate(self.gift_pixel_ids):
                gc = gift_colors[(self.flash_cycle + gi) % len(gift_colors)] if (self.flash_cycle + gi) % 4 < 2 else '#0b1220'
                for pid in cluster:
                    # pid is an ids tuple for the 3D pixel
                    if isinstance(pid, (list, tuple)):
                        base_id, hl_id, sh_id = pid
                        self.canvas.itemconfigure(base_id, fill=gc)
                        try:
                            self.canvas.itemconfigure(hl_id, fill=self.brighten(gc, 1.4))
                            self.canvas.itemconfigure(sh_id, fill=self.darken(gc, 0.5))
                        except Exception:
                            pass
                    else:
                        try:
                            self.canvas.itemconfigure(pid, fill=gc)
                        except Exception:
                            pass

            # animate pixel-text (name and greeting) by toggling pixel colors
            text_on = (self.flash_cycle // 3) % 2 == 0
            text_color = '#ffd54a' if text_on else '#ffffff'
            for pid in self.greeting_pixel_ids:
                try:
                    if isinstance(pid, (list, tuple)):
                        base_id, hl_id, sh_id = pid
                        self.canvas.itemconfigure(base_id, fill=text_color)
                        if hl_id:
                            self.canvas.itemconfigure(hl_id, fill=self.brighten(text_color, 1.2))
                        if sh_id:
                            self.canvas.itemconfigure(sh_id, fill=self.darken(text_color, 0.8))
                    else:
                        self.canvas.itemconfigure(pid, fill=text_color)
                except Exception:
                    # fallback to text item or ignore
                    pass
            for pid in self.name_pixel_ids:
                try:
                    if isinstance(pid, (list, tuple)):
                        base_id, hl_id, sh_id = pid
                        self.canvas.itemconfigure(base_id, fill=text_color)
                        if hl_id:
                            self.canvas.itemconfigure(hl_id, fill=self.brighten(text_color, 1.2))
                        if sh_id:
                            self.canvas.itemconfigure(sh_id, fill=self.darken(text_color, 0.8))
                    else:
                        self.canvas.itemconfigure(pid, fill=text_color)
                except Exception:
                    pass

        self.flash_cycle += 1

        # continue or finish
        if len(self.revealed) < len(self.points):
            if self.animation_running:
                self.root.after(60, self.animate)
        else:
            # finished reveal: ensure all points are shown once
            if not self.greet_shown:
                # finalize colors for all particles (store on particle dict)
                for p in self.particles:
                    if 'final_color' in p:
                        continue
                    if p['index'] in self.ornament_map:
                        p['final_color'] = random.choice(['#e91e63', '#f44336', '#ffeb3b', '#03a9f4', '#9c27b0'])
                    else:
                        p['final_color'] = '#2e7d32'
                # small delay then popup greeting (only once)
                self.root.after(600, self.show_greeting)
                self.greet_shown = True
            # 继续动画，保持灯光/礼物/文字的闪烁效果
            # 确保所有粒子都切换到流动状态
            for p in self.particles:
                if p.get('state') != 'flowing':
                    p['state'] = 'flowing'
                # 初始化流动角度
                if 'flow_angle' not in p:
                    p['flow_angle'] = random.random() * 2 * math.pi
                # 确保final_color存在
                if 'final_color' not in p:
                    if p['index'] in self.ornament_map:
                        p['final_color'] = random.choice(['#e91e63', '#f44336', '#ffeb3b', '#03a9f4', '#9c27b0'])
                    else:
                        p['final_color'] = '#2e7d32'
            if self.animation_running:
                self.root.after(60, self.animate)

    def show_greeting(self):
        # show a messagebox greeting including the name
        title = 'Happy Holidays!'
        who = self.name if self.name else 'Friend'
        msg = f'Merry Christmas, {who}!\nMay your holidays be joyful.'
        # Use a non-blocking transient Toplevel instead of a blocking messagebox
        try:
            top = tk.Toplevel(self.root)
            top.title(title)
            # position near center
            top.geometry(f"+{self.root.winfo_x() + self.width//2 - 150}+{self.root.winfo_y() + 80}")
            lbl = tk.Label(top, text=msg, font=('Helvetica', 14, 'bold'), bg='#0b1220', fg='white')
            lbl.pack(padx=12, pady=12)
            top.transient(self.root)
            # auto-close after a short duration
            top.after(3600, top.destroy)
        except Exception:
            # fallback: draw text on canvas (non-blocking)
            self.canvas.create_text(self.width//2, 30, text=msg, fill='white', font=('Helvetica', 16, 'bold'))

    def render_text_pixels(self, text, top_y):
        # Render `text` to a small monochrome image then create pixel rectangles
        # Returns list of canvas ids for the pixels
        # Render text to a monochrome image and return pixel centers for PIL drawing
        font = ImageFont.load_default()
        tmp_img = Image.new('L', (1, 1), 0)
        tmp_draw = ImageDraw.Draw(tmp_img)
        try:
            bbox = tmp_draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except Exception:
            try:
                w, h = tmp_draw.textsize(text, font=font)
            except Exception:
                return []

        if w == 0 or h == 0:
            return []

        img = Image.new('L', (w, h), 0)
        draw = ImageDraw.Draw(img)
        draw.text((0, 0), text, fill=255, font=font)

        coords = []
        start_x = (self.width - (w * (self.pixel_size + 1))) // 2
        for py in range(h):
            for px in range(w):
                val = img.getpixel((px, py))
                if val > 64:
                    x = start_x + px * (self.pixel_size + 1)
                    y = top_y + py * (self.pixel_size + 1)
                    coords.append((x, y))
        return coords

    def on_close(self):
        self.animation_running = False
        self.root.destroy()

    def run(self):
        # start animation
        self.root.after(200, self.animate)
        self.root.mainloop()


def ask_name_and_run():
    # small temporary root used for dialog, then destroyed
    dialog_root = tk.Tk()
    dialog_root.withdraw()
    name = simpledialog.askstring('Your Name', 'Please type your name for the greeting:', parent=dialog_root)
    dialog_root.destroy()

    app = ChristmasTreeGUI(name=name)
    app.run()


if __name__ == '__main__':
    ask_name_and_run()
