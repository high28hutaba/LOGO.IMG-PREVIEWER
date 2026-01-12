#!/usr/bin/env python3
import os, re, time
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

BOOT_INDEX = 1
CHG_FIRST_INDEX = 3
NO_BATTERY_INDEX = 4
CHG_BG_INDEX = 36
DIGIT_START = 5
PERCENT_INDEX = 15
WAVE_START = 16
WAVE_END = 25
LOW_BG_START = 26
LOW_BG_END = 35
FILL_INDEX = 37
FULL_BG_INDEX = 38
RECOVERY_INDEX = 39

DEFAULT_LOGICAL_W = 1280
DEFAULT_LOGICAL_H = 720
PREVIEW_MAX_W = 1200
PREVIEW_MAX_H = 800
MAIN_TICK_MS = 100
LOW_DEFAULT_FPS = 6.0
WAVE_DEFAULT_FPS = 4.0
LOW_THRESHOLD = 15

_idx_re = re.compile(r'(\d{1,3})')
def index_from_filename(fn):
    m = _idx_re.search(fn)
    return int(m.group(1)) if m else None

def load_images(folder):
    imgs = {}
    other = []
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith(('.png', '.bmp', '.jpg', '.jpeg', '.webp')):
            continue
        path = os.path.join(folder, fn)
        try:
            im = Image.open(path).convert('RGBA')
        except Exception as e:
            print(f"[WARN] cannot open {fn}: {e}")
            continue
        idx = index_from_filename(fn)
        if idx is not None:
            imgs[idx] = im
        else:
            other.append((fn, im))
    if other:
        imgs['_other'] = other
    return imgs

class LKEmulator:
    def __init__(self, assets):
        self.assets = assets
        self.logical_w = DEFAULT_LOGICAL_W
        self.logical_h = DEFAULT_LOGICAL_H
        for idx in (BOOT_INDEX, CHG_BG_INDEX, FULL_BG_INDEX, RECOVERY_INDEX):
            im = self.assets.get(idx)
            if im:
                self.logical_w, self.logical_h = im.size
                break
        if '_other' in self.assets and not any(isinstance(k,int) for k in self.assets.keys()):
            self.logical_w, self.logical_h = self.assets['_other'][0][1].size

        self.bat_x = 557
        self.bat_y = 470
        self.bat_w = 163
        self.bat_h = 56

        self.pct_x = 640
        self.pct_y = 95

        self.fill_v_at_16 = 36
        self.fill_v_at_99 = -180
        self.fill_v_base = 0

        self.wave_fps = WAVE_DEFAULT_FPS
        self.wave_frame = 0

        self.low_fps = LOW_DEFAULT_FPS
        self.low_frame = 0

        self.digit_spacing = 2

    def get(self, idx):
        return self.assets.get(idx)

    def find_by_keyword(self, kw):
        for fn, im in self.assets.get('_other', []):
            if kw in fn.lower():
                return im
        return None

    def set_battery_area(self, x, y, w, h):
        self.bat_x = int(x); self.bat_y = int(y); self.bat_w = max(1,int(w)); self.bat_h = max(1,int(h))

    def set_percent_pos(self, px, py):
        self.pct_x = int(px); self.pct_y = int(py)

    def set_fill_v_points(self, v16, v99):
        self.fill_v_at_16 = int(v16)
        self.fill_v_at_99 = int(v99)

    def set_wave_fps(self, v):
        try:
            f = float(v)
            if f <= 0: f = 0.1
            self.wave_fps = f
        except:
            pass

    def set_low_fps(self, v):
        try:
            f = float(v)
            if f <= 0: f = 1.0
            self.low_fps = f
        except:
            pass

    def step_wave(self):
        self.wave_frame = (self.wave_frame + 1) % max(1, (WAVE_END - WAVE_START + 1))

    def step_low(self):
        self.low_frame = (self.low_frame + 1) % max(1, (LOW_BG_END - LOW_BG_START + 1))

    def compute_fill_v_offset(self, capacity):
        if capacity <= 16:
            pv = self.fill_v_at_16
        elif capacity >= 99:
            pv = self.fill_v_at_99
        else:
            t = (capacity - 16) / (99 - 16)
            pv = int(self.fill_v_at_16 + t * (self.fill_v_at_99 - self.fill_v_at_16))
        return pv + int(self.fill_v_base)

    def draw_boot(self):
        bg = Image.new('RGBA', (self.logical_w, self.logical_h), (0,0,0,255))
        im = self.get(BOOT_INDEX) or self.find_by_keyword('boot') or self.find_by_keyword('logo')
        if im:
            x = (self.logical_w - im.width)//2; y = (self.logical_h - im.height)//2
            bg.paste(im, (x,y), im)
        return bg

    def draw_recovery(self):
        bg = self.draw_boot()
        rec = self.get(RECOVERY_INDEX) or self.find_by_keyword('recovery')
        if rec:
            x = (self.logical_w - rec.width)//2; y = (self.logical_h - rec.height)//2
            bg.paste(rec, (x,y), rec)
        return bg

    def draw_charging_initial(self):
        im = self.get(CHG_FIRST_INDEX) or self.find_by_keyword('charging')
        if im:
            bg = Image.new('RGBA', (self.logical_w, self.logical_h), (0,0,0,255))
            x = (self.logical_w - im.width)//2; y = (self.logical_h - im.height)//2
            bg.paste(im, (x,y), im)
            return bg
        return self.draw_charging_animation(0)

    def draw_charging_animation(self, capacity, low_frame=None):
        if capacity == 0:
            im = self.get(NO_BATTERY_INDEX) or self.find_by_keyword('no') or self.find_by_keyword('nobattery')
            if im:
                bg = Image.new('RGBA', (self.logical_w, self.logical_h), (0,0,0,255))
                x = (self.logical_w - im.width)//2; y = (self.logical_h - im.height)//2
                bg.paste(im, (x,y), im)
                return bg

        if capacity >= 100:
            im = self.get(FULL_BG_INDEX) or self.find_by_keyword('full')
            if im:
                bg = Image.new('RGBA', (self.logical_w, self.logical_h), (0,0,0,255))
                x = (self.logical_w - im.width)//2; y = (self.logical_h - im.height)//2
                bg.paste(im, (x,y), im)
                return bg

        if capacity <= LOW_THRESHOLD:
            frames = LOW_BG_END - LOW_BG_START + 1
            idx = LOW_BG_START + (low_frame % frames if low_frame is not None else self.low_frame)
            im = self.get(idx) or self.get(LOW_BG_START)
            if im:
                bg = Image.new('RGBA', (self.logical_w, self.logical_h), (0,0,0,255))
                x = (self.logical_w - im.width)//2; y = (self.logical_h - im.height)//2
                bg.paste(im, (x,y), im)
                self._draw_digits_fixed(bg, capacity)
                return bg

        bg = Image.new('RGBA', (self.logical_w, self.logical_h), (0,0,0,255))
        base = self.get(CHG_BG_INDEX)
        if base:
            x = (self.logical_w - base.width)//2; y = (self.logical_h - base.height)//2
            bg.paste(base, (x,y), base)

        fill_img = self.get(FILL_INDEX)
        fill_v_offset = self.compute_fill_v_offset(capacity)
        if fill_img:
            if fill_img.width != self.bat_w:
                tile = fill_img.resize((self.bat_w, fill_img.height), Image.NEAREST)
            else:
                tile = fill_img
            fill_height = max(0, int(self.bat_h * capacity / 100))
            if fill_height > 0:
                y_base = self.bat_y + (self.bat_h - fill_height) + fill_v_offset
                cur_y = y_base
                while cur_y < self.bat_y + self.bat_h:
                    bg.paste(tile, (self.bat_x, cur_y), tile)
                    cur_y += tile.height if tile.height>0 else 1

        wave_idx = WAVE_START + (self.wave_frame % max(1, (WAVE_END - WAVE_START + 1)))
        wave_img = self.get(wave_idx)
        if wave_img and fill_img:
            wx = self.bat_x + (self.bat_w - wave_img.width)//2
            fill_height = max(0, int(self.bat_h * capacity / 100))
            y_base = self.bat_y + (self.bat_h - fill_height) + fill_v_offset
            wy = y_base - wave_img.height
            if wy < 0:
                wy = 0
            bg.paste(wave_img, (wx, wy), wave_img)

        self._draw_digits_fixed(bg, capacity)
        return bg

    def _draw_digits_fixed(self, bg, capacity):
        s = str(int(capacity))
        imgs = []
        total_w = 0
        for ch in s:
            idx = DIGIT_START + int(ch)
            d = self.get(idx)
            imgs.append(d)
            if d:
                total_w += d.width + self.digit_spacing
            else:
                total_w += 12
        pct = self.get(PERCENT_INDEX)
        if pct:
            total_w += pct.width
        x0 = self.pct_x - total_w//2
        y0 = self.pct_y
        x = x0
        for d in imgs:
            if d:
                bg.paste(d, (x, y0), d)
                x += d.width + self.digit_spacing
            else:
                x += 12
        if pct:
            bg.paste(pct, (x, y0), pct)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Logo Splash Screen Emulator - V1.0 Created By.High28Hutaba")
        self.geometry("1280x920")
        self.assets = {}
        self.lk = None
        self.mode = 'boot'
        self.battery = tk.IntVar(value=50)
        self.show_scale = tk.BooleanVar(value=True)
        self.wave_fps_var = tk.StringVar(value=str(WAVE_DEFAULT_FPS))
        self.low_fps_var = tk.StringVar(value=str(LOW_DEFAULT_FPS))
        self.after_id = None
        self.low_anim_running = False
        self.low_frame = 0
        self.low_after = None
        self.chg_start = None
        self._build_ui()
        self.after(0, self._wave_scheduler)
        self.request_redraw()

    def _build_ui(self):
        top = tk.Frame(self)
        top.pack(side='top', fill='x', padx=6, pady=6)
        tk.Button(top, text="フォルダ選択", command=self.select_folder).pack(side='left')
        tk.Button(top, text="BOOT", command=lambda: self.set_mode('boot')).pack(side='left', padx=4)
        tk.Button(top, text="CHARGING", command=lambda: self.set_mode('charging')).pack(side='left', padx=4)
        tk.Button(top, text="RECOVERY", command=lambda: self.set_mode('recovery')).pack(side='left', padx=4)
        tk.Label(top, text="Battery %").pack(side='left', padx=(12,0))
        tk.Scale(top, from_=0, to=100, orient='horizontal', variable=self.battery, command=lambda e: self.request_redraw()).pack(side='left', padx=4)
        tk.Checkbutton(top, text="自動縮小表示", variable=self.show_scale, command=lambda: self.request_redraw()).pack(side='left', padx=8)
        tk.Label(top, text="Wave FPS (0.1刻み)").pack(side='left', padx=(12,2))
        self.wave_spin = tk.Spinbox(top, from_=0.1, to=60.0, increment=0.1, textvariable=self.wave_fps_var, width=6, command=self._on_wave_fps_change)
        self.wave_spin.pack(side='left')
        tk.Label(top, text="Low-Batt FPS").pack(side='left', padx=(12,2))
        self.low_spin = tk.Spinbox(top, from_=1, to=60, increment=1, textvariable=self.low_fps_var, width=5, command=self._on_low_fps_change)
        self.low_spin.pack(side='left')
        self.canvas = tk.Canvas(self, bg='black')
        self.canvas.pack(fill='both', expand=True, padx=6, pady=6)
        bottom = tk.Frame(self)
        bottom.pack(side='bottom', fill='x', padx=6, pady=6)
        tk.Label(bottom, text="Battery X").grid(row=0, column=0)
        self.bx = tk.Scale(bottom, from_=0, to=4000, orient='horizontal', command=self._on_battery_slider)
        self.bx.set(557); self.bx.grid(row=0, column=1, sticky='ew')
        tk.Label(bottom, text="Battery Y").grid(row=1, column=0)
        self.by = tk.Scale(bottom, from_=0, to=4000, orient='horizontal', command=self._on_battery_slider)
        self.by.set(470); self.by.grid(row=1, column=1, sticky='ew')
        tk.Label(bottom, text="Battery W").grid(row=2, column=0)
        self.bw = tk.Scale(bottom, from_=10, to=2000, orient='horizontal', command=self._on_battery_slider)
        self.bw.set(163); self.bw.grid(row=2, column=1, sticky='ew')
        tk.Label(bottom, text="Battery H").grid(row=3, column=0)
        self.bh = tk.Scale(bottom, from_=1, to=2000, orient='horizontal', command=self._on_battery_slider)
        self.bh.set(56); self.bh.grid(row=3, column=1, sticky='ew')
        tk.Label(bottom, text="Fill V @16% (px)").grid(row=0, column=2)
        self.fill16 = tk.Scale(bottom, from_=-300, to=300, orient='horizontal', command=self._on_fillpoints)
        self.fill16.set(36); self.fill16.grid(row=0, column=3, sticky='ew')
        tk.Label(bottom, text="Fill V @99% (px)").grid(row=1, column=2)
        self.fill99 = tk.Scale(bottom, from_=-500, to=500, orient='horizontal', command=self._on_fillpoints)
        self.fill99.set(-180); self.fill99.grid(row=1, column=3, sticky='ew')
        tk.Label(bottom, text="Fill Base Offset (px)").grid(row=2, column=2)
        self.fillbase = tk.Scale(bottom, from_=-300, to=300, orient='horizontal', command=self._on_fillpoints)
        self.fillbase.set(0); self.fillbase.grid(row=2, column=3, sticky='ew')
        tk.Label(bottom, text="Percent X (fixed)").grid(row=0, column=4)
        self.px_entry = tk.Entry(bottom, width=6); self.px_entry.grid(row=0, column=5)
        tk.Label(bottom, text="Percent Y (fixed)").grid(row=1, column=4)
        self.py_entry = tk.Entry(bottom, width=6); self.py_entry.grid(row=1, column=5)
        tk.Button(bottom, text="Apply Percent Pos", command=self._apply_percent_pos).grid(row=2, column=5)
        bottom.grid_columnconfigure(1, weight=1)
        bottom.grid_columnconfigure(3, weight=1)
        self.status = tk.Label(self, text="フォルダ選択してください", anchor='w')
        self.status.pack(side='bottom', fill='x')

    def select_folder(self):
        d = filedialog.askdirectory()
        if not d:
            return
        self.assets = load_images(d)
        if not self.assets:
            messagebox.showerror("エラー", "画像が見つかりませんでした")
            return
        self.lk = LKEmulator(self.assets)
        self.bx.set(self.lk.bat_x); self.by.set(self.lk.bat_y)
        self.bw.set(self.lk.bat_w); self.bh.set(self.lk.bat_h)
        self.fill16.set(self.lk.fill_v_at_16); self.fill99.set(self.lk.fill_v_at_99); self.fillbase.set(self.lk.fill_v_base)
        self.px_entry.delete(0,'end'); self.px_entry.insert(0,str(self.lk.pct_x))
        self.py_entry.delete(0,'end'); self.py_entry.insert(0,str(self.lk.pct_y))
        self.status.config(text=f"読み込み完了: {len(self.assets)} 画像 (keys: {sorted([k for k in self.assets.keys() if isinstance(k,int)])})")
        self.set_mode('boot')

    def _apply_percent_pos(self):
        if not self.lk: return
        try:
            px = int(self.px_entry.get()); py = int(self.py_entry.get())
        except:
            messagebox.showwarning("入力エラー", "Percent X/Y は整数で入力してください")
            return
        self.lk.set_percent_pos(px, py)
        self.request_redraw()

    def _on_battery_slider(self, v=None):
        if not self.lk: return
        self.lk.set_battery_area(int(self.bx.get()), int(self.by.get()), int(self.bw.get()), int(self.bh.get()))
        self.request_redraw()

    def _on_fillpoints(self, v=None):
        if not self.lk: return
        self.lk.fill_v_at_16 = int(self.fill16.get())
        self.lk.fill_v_at_99 = int(self.fill99.get())
        self.lk.fill_v_base = int(self.fillbase.get())
        self.request_redraw()

    def _on_wave_fps_change(self):
        if not self.lk: return
        try:
            val = float(self.wave_fps_var.get())
            if val <= 0: val = 0.1
            self.lk.set_wave_fps(val)
        except:
            pass

    def _on_low_fps_change(self):
        if not self.lk: return
        try:
            val = float(self.low_fps_var.get())
            if val <= 0: val = 1.0
            self.lk.set_low_fps(val)
        except:
            pass

    def set_mode(self, m):
        self.mode = m
        if m == 'charging':
            self.chg_start = time.time()
            if self.battery.get() <= LOW_THRESHOLD and not self.low_anim_running:
                self._start_low_anim()
        else:
            self.chg_start = None
            self._stop_low_anim()
        self.request_redraw()

    def request_redraw(self):
        if self.after_id:
            self.after_cancel(self.after_id); self.after_id=None
        self._draw_cycle()

    def _draw_cycle(self):
        self.canvas.delete('all')
        if not getattr(self, 'lk', None):
            self.status.config(text="画像を読み込んでください")
            return
        self.lk.set_battery_area(int(self.bx.get()), int(self.by.get()), int(self.bw.get()), int(self.bh.get()))
        self.lk.set_fill_v_points(int(self.fill16.get()), int(self.fill99.get()))
        self.lk.fill_v_base = int(self.fillbase.get())
        self.lk.digit_spacing = 2
        self.lk.set_wave_fps(self.wave_fps_var.get())
        self.lk.set_low_fps(self.low_fps_var.get())
        if self.mode == 'boot':
            out = self.lk.draw_boot()
        elif self.mode == 'recovery':
            out = self.lk.draw_recovery()
        elif self.mode == 'charging':
            if getattr(self, 'chg_start', None) and (time.time() - self.chg_start) < 5:
                out = self.lk.draw_charging_initial()
            else:
                if self.battery.get() <= LOW_THRESHOLD:
                    if not self.low_anim_running:
                        self._start_low_anim()
                    out = self.lk.draw_charging_animation(self.battery.get(), low_frame=self.low_frame)
                else:
                    self._stop_low_anim()
                    out = self.lk.draw_charging_animation(self.battery.get())
        else:
            out = Image.new('RGBA', (self.lk.logical_w, self.lk.logical_h), (0,0,0,255))
        canvas_w = max(100, self.canvas.winfo_width() or PREVIEW_MAX_W)
        canvas_h = max(100, self.canvas.winfo_height() or PREVIEW_MAX_H)
        if self.show_scale.get():
            fw = canvas_w / out.width; fh = canvas_h / out.height
            scale = min(fw, fh, 1.0)
            dw = max(1, int(out.width * scale)); dh = max(1, int(out.height * scale))
            disp = out.resize((dw, dh), Image.NEAREST)
            x = (canvas_w - dw)//2; y = (canvas_h - dh)//2
        else:
            disp = out; x = y = 0
        self.tkimg = ImageTk.PhotoImage(disp)
        self.canvas.create_image(x, y, anchor='nw', image=self.tkimg)
        self.status.config(text=f"Mode:{self.mode}  Battery:{self.battery.get()}%  Logical:{self.lk.logical_w}x{self.lk.logical_h}")
        self.after_id = self.after(MAIN_TICK_MS, self._draw_cycle)

    def _start_low_anim(self):
        if self.low_anim_running: return
        self.low_anim_running = True
        self.low_frame = 0
        self._schedule_low_frame()

    def _stop_low_anim(self):
        if not self.low_anim_running: return
        self.low_anim_running = False
        if self.low_after:
            self.after_cancel(self.low_after); self.low_after=None

    def _schedule_low_frame(self):
        if not self.low_anim_running: return
        try:
            fps = float(self.low_fps_var.get())
            if fps <= 0: fps = 1.0
        except:
            fps = LOW_DEFAULT_FPS
        interval = int(1000.0 / fps)
        self.low_frame = (self.low_frame + 1) % max(1, (LOW_BG_END - LOW_BG_START + 1))
        self.request_redraw()
        self.low_after = self.after(interval, self._schedule_low_frame)

    def _wave_scheduler(self):
        try:
            fps = float(self.wave_fps_var.get())
            if fps <= 0: fps = 0.1
        except:
            fps = WAVE_DEFAULT_FPS
        interval = max(20, int(1000.0 / fps))
        if getattr(self, 'lk', None) and self.mode == 'charging' and self.battery.get() > LOW_THRESHOLD:
            self.lk.step_wave()
            self.request_redraw()
        self.after(interval, self._wave_scheduler)

if __name__ == '__main__':
    app = App()
    app.after(0, app._wave_scheduler)
    app.mainloop()