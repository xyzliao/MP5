#!/usr/bin/env python3
"""
MP5录播器 — Windows版桌面播放器
基于 tkinter 的 GUI 应用

功能:
  - 打开 MP5/MP4 文件
  - 视频播放（VLC内嵌播放 或 系统播放器回退）
  - GPS轨迹地图显示（Canvas绘制）
  - 视频↔地图双向联动
  - 速度热力图
  - POI标记显示
  - 导出 GPX / GeoJSON / KML / MP4
  - 轨迹统计信息
  - 从MP4制作MP5（导入GPX或生成模拟轨迹）

运行方式:
  python mp5_player.py

视频播放:
  - 优先使用 python-vlc 内嵌播放（需安装 pip install python-vlc 和 VLC播放器）
  - 未安装 python-vlc 时自动回退到系统默认播放器

作者: MP5录播器
"""

import sys
import os
import time
import threading
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

# 添加父目录到路径，以便导入 mp5 模块
sys.path.insert(0, str(Path(__file__).parent))

from mp5_box import (
    GPSEntry, SyncConfig, POI,
    parse_boxes, find_box, parse_gloc, parse_gsyn, parse_gpoi,
    strip_mp5_boxes, create_sample_mp5, mux_mp5, write_gloc, write_gsyn, write_ftyp
)
from mp5_parser import MP5Parser, MP5Info
from sync_engine import SyncEngine
from exporters import export_gpx, export_geojson, export_kml
from gpx_importer import parse_gpx_file, get_video_duration
from track_generator import generate_simulated_track

# 尝试导入 python-vlc (内嵌视频播放)
try:
    import vlc
    HAS_VLC = True
except ImportError:
    HAS_VLC = False

# GUI 导入
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
    HAS_TK = True
except ImportError:
    HAS_TK = False
    print("错误: 需要 tkinter 模块。请安装 python3-tk")
    sys.exit(1)

# ============================================================
# 地图画布组件
# ============================================================

class MapCanvas(ttk.Frame):
    """基于 tkinter Canvas 的简易地图显示组件"""

    def __init__(self, parent, on_click_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_click_callback = on_click_callback

        # 画布
        self.canvas = tk.Canvas(self, bg='#1a1a2e', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)

        # 状态
        self.gps_entries = []
        self.pois = []
        self.track_points = []  # 屏幕坐标
        self.bounds = None  # (min_lat, min_lon, max_lat, max_lon)
        self.current_pos_idx = 0
        self.played_polyline = None
        self.speed_segments = []

        # 绑定事件
        self.canvas.bind('<Button-1>', self._on_click)
        self.canvas.bind('<Configure>', lambda e: self._redraw())

    def set_track(self, gps_entries, pois=None):
        """设置GPS轨迹数据"""
        self.gps_entries = gps_entries
        self.pois = pois or []
        if gps_entries:
            lats = [e.latitude for e in gps_entries]
            lons = [e.longitude for e in gps_entries]
            self.bounds = (min(lats), min(lons), max(lats), max(lons))
        else:
            self.bounds = None
        self.current_pos_idx = 0
        self._redraw()
        # 确保在widget渲染完成后重绘
        self.after(100, self._redraw)

    def update_position(self, time_ms):
        """根据时间更新当前位置标记"""
        if not self.gps_entries:
            return

        # 找到最近的GPS点
        for i, entry in enumerate(self.gps_entries):
            if entry.timestamp > time_ms:
                self.current_pos_idx = max(0, i - 1)
                break
        else:
            self.current_pos_idx = len(self.gps_entries) - 1

        self._redraw()

    def _on_click(self, event):
        """地图点击事件"""
        if not self.track_points or not self.on_click_callback:
            return

        # 找到最近的轨迹点
        x, y = event.x, event.y
        min_dist = float('inf')
        nearest_idx = 0

        for i, (px, py) in enumerate(self.track_points):
            dist = (px - x) ** 2 + (py - y) ** 2
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i

        if nearest_idx < len(self.gps_entries):
            entry = self.gps_entries[nearest_idx]
            self.on_click_callback(entry.timestamp)

    def _redraw(self):
        """重绘地图"""
        self.canvas.delete('all')
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return

        if not self.gps_entries or not self.bounds:
            self.canvas.create_text(w//2, h//2, text='无GPS轨迹数据',
                                   fill='#8b949e', font=('Arial', 14))
            return

        min_lat, min_lon, max_lat, max_lon = self.bounds

        # 添加边距
        lat_range = max(max_lat - min_lat, 0.001)
        lon_range = max(max_lon - min_lon, 0.001)
        margin = 0.15
        min_lat -= lat_range * margin
        max_lat += lat_range * margin
        min_lon -= lon_range * margin
        max_lon += lon_range * margin

        def to_screen(lat, lon):
            x = (lon - min_lon) / (max_lon - min_lon) * w
            y = h - (lat - min_lat) / (max_lat - min_lat) * h
            return x, y

        # 绘制网格（经纬度参考线）
        for i in range(5):
            gx = w * i / 4
            gy = h * i / 4
            self.canvas.create_line(gx, 0, gx, h, fill='#2a2a4e', dash=(2, 4))
            self.canvas.create_line(0, gy, w, gy, fill='#2a2a4e', dash=(2, 4))

        # 计算屏幕坐标
        self.track_points = [to_screen(e.latitude, e.longitude) for e in self.gps_entries]

        # 绘制速度热力图轨迹
        for i in range(1, len(self.track_points)):
            if i - 1 >= len(self.gps_entries):
                break
            speed = self.gps_entries[i].speed
            color = SyncEngine.get_speed_color(speed)
            x1, y1 = self.track_points[i-1]
            x2, y2 = self.track_points[i]
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=3)

        # 绘制已播放部分（高亮）
        if self.current_pos_idx > 0:
            played = self.track_points[:self.current_pos_idx + 1]
            if len(played) > 1:
                self.canvas.create_line(played, fill='#ffffff', width=2, smooth=True)

        # 起点（绿色）
        if self.track_points:
            sx, sy = self.track_points[0]
            self.canvas.create_oval(sx-6, sy-6, sx+6, sy+6, fill='#22c55e', outline='#ffffff', width=2)
            self.canvas.create_text(sx, sy-12, text='起点', fill='#22c55e', font=('Arial', 8))

        # 终点（红色）
        if len(self.track_points) > 1:
            ex, ey = self.track_points[-1]
            self.canvas.create_oval(ex-6, ey-6, ex+6, ey+6, fill='#ef4444', outline='#ffffff', width=2)
            self.canvas.create_text(ex, ey-12, text='终点', fill='#ef4444', font=('Arial', 8))

        # POI标记
        for poi in self.pois:
            px, py = to_screen(poi.latitude, poi.longitude)
            self.canvas.create_text(px, py, text='📍', font=('Arial', 12))
            if poi.label:
                self.canvas.create_text(px, py+12, text=poi.label, fill='#58a6ff', font=('Arial', 8))

        # 当前位置（脉冲圆点）
        if 0 <= self.current_pos_idx < len(self.track_points):
            cx, cy = self.track_points[self.current_pos_idx]
            self.canvas.create_oval(cx-8, cy-8, cx+8, cy+8, fill='#f85149', outline='#ffffff', width=2)
            self.canvas.create_oval(cx-12, cy-12, cx+12, cy+12, outline='#f85149', width=1)

        # 坐标信息
        if 0 <= self.current_pos_idx < len(self.gps_entries):
            entry = self.gps_entries[self.current_pos_idx]
            info = f'{entry.latitude:.4f}°, {entry.longitude:.4f}°  {entry.speed:.1f}km/h  {entry.heading:.0f}°'
            self.canvas.create_text(10, h-20, text=info, fill='#d0d7de', anchor='nw', font=('Consolas', 9))

        # 速度图例
        legend_y = 10
        legend_items = [
            ('<5 km/h', '#3b82f6'),
            ('5-20', '#22c55e'),
            ('20-60', '#eab308'),
            ('60-120', '#f97316'),
            ('>120', '#ef4444'),
        ]
        for label, color in legend_items:
            self.canvas.create_rectangle(w-90, legend_y, w-85, legend_y+10, fill=color, outline='')
            self.canvas.create_text(w-82, legend_y+5, text=label, fill='#d0d7de', anchor='w', font=('Arial', 7))
            legend_y += 14


# ============================================================
# 主应用窗口
# ============================================================

class MP5PlayerApp:
    """MP5播放器主应用"""

    def __init__(self, root):
        self.root = root
        self.root.title('MP5录播器 — Windows版')
        self.root.geometry('1200x750')
        self.root.configure(bg='#0d1117')

        # 状态
        self.file_path = None
        self.file_data = None
        self.mp5_info = None
        self.sync_engine = None
        self.video_player = None
        self.is_playing = False
        self.playback_time = 0.0
        self.playback_start = 0.0
        self.playback_thread = None
        self.playback_stop = threading.Event()

        # 临时文件（用于视频播放）
        self.temp_video_file = None

        # VLC 播放器
        self.vlc_instance = None
        self.vlc_player = None
        self.vlc_widget = None  # VLC视频输出嵌入的widget

        self._setup_ui()
        self._setup_menu()

    def _setup_ui(self):
        """构建UI界面"""
        # 主题色
        BG = '#0d1117'
        PANEL = '#161b22'
        BORDER = '#30363d'
        FG = '#e6edf3'
        ACCENT = '#58a6ff'

        # 主容器
        main = ttk.Frame(self.root)
        main.pack(fill='both', expand=True, padx=8, pady=8)

        # ---- 顶部工具栏 ----
        toolbar = ttk.Frame(main)
        toolbar.pack(fill='x', pady=(0, 8))

        ttk.Button(toolbar, text='打开文件', command=self.open_file).pack(side='left', padx=4)
        ttk.Button(toolbar, text='制作MP5', command=self.create_mp5_from_mp4).pack(side='left', padx=4)
        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=8)

        self.btn_play = ttk.Button(toolbar, text='▶ 播放', command=self.toggle_play, state='disabled')
        self.btn_play.pack(side='left', padx=4)

        self.btn_stop = ttk.Button(toolbar, text='■ 停止', command=self.stop_play, state='disabled')
        self.btn_stop.pack(side='left', padx=4)

        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=8)

        # 视图切换
        ttk.Label(toolbar, text='视图:').pack(side='left', padx=4)
        self.view_var = tk.StringVar(value='分屏')
        view_combo = ttk.Combobox(toolbar, textvariable=self.view_var, width=10,
                                  values=['仅视频', '仅地图', '分屏', '画中画'], state='readonly')
        view_combo.pack(side='left', padx=4)
        view_combo.bind('<<ComboboxSelected>>', self.switch_view)

        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=8)

        # 导出按钮
        ttk.Button(toolbar, text='导出GPX', command=self.export_gpx).pack(side='left', padx=4)
        ttk.Button(toolbar, text='导出GeoJSON', command=self.export_geojson).pack(side='left', padx=4)
        ttk.Button(toolbar, text='导出KML', command=self.export_kml).pack(side='left', padx=4)
        ttk.Button(toolbar, text='导出MP4', command=self.export_mp4).pack(side='left', padx=4)

        # ---- 文件信息栏 ----
        self.info_frame = ttk.LabelFrame(main, text='文件信息', padding=8)
        self.info_frame.pack(fill='x', pady=(0, 8))

        # 5行3列网格布局，列等宽
        self.info_labels = {}
        info_fields = [
            ('file',    '文件:'),     ('size',  '大小:'),     ('format', '格式:'),
            ('duration','时长:'),     ('tracks','轨道:'),     ('gps',    'GPS点:'),
            ('start',   '起点:'),     ('end',   '终点:'),     ('sync',   '同步:'),
            ('poi',     'POI:'),     ('brand', '品牌:'),     ('stats',  '距离:'),
            ('stat2',   '最高速度:'), ('stat3', '平均速度:'), ('stat4',  '时长:'),
        ]
        for idx, (key, label_text) in enumerate(info_fields):
            row = idx // 3
            col = idx % 3
            lbl = ttk.Label(self.info_frame, text=label_text, foreground='#8b949e')
            val = ttk.Label(self.info_frame, text='--')
            lbl.grid(row=row, column=col*2, sticky='w', padx=(0, 2), pady=1)
            val.grid(row=row, column=col*2+1, sticky='w', padx=(0, 12), pady=1)
            self.info_labels[key] = val

        # 让3列等宽分配
        for i in range(3):
            self.info_frame.columnconfigure(i*2, weight=0)
            self.info_frame.columnconfigure(i*2+1, weight=1, uniform='info_col')

        # ---- 主内容区 ----
        self.content = ttk.Frame(main)
        self.content.pack(fill='both', expand=True)

        # 可拖拽分隔的 PanedWindow（用于分屏模式）
        self.paned = ttk.PanedWindow(self.content, orient='horizontal')

        # 视频面板
        self.video_frame = ttk.LabelFrame(self.content, text='视频', padding=4)

        if HAS_VLC:
            # VLC内嵌播放 — 用一个Frame作为VLC的视频输出目标
            self.vlc_widget = tk.Frame(self.video_frame, bg='#000000')
            self.vlc_widget.pack(fill='both', expand=True)

            # 初始化VLC
            self.vlc_instance = vlc.Instance('--no-xlib --quiet')
            self.vlc_player = self.vlc_instance.media_player_new()

            # 在Windows上用HWND，Linux上用XID，macOS用NSView
            # 需要等widget渲染后获取window handle
            self.vlc_widget.bind('<Configure>', self._on_vlc_widget_configure)
        else:
            # 无VLC — 显示提示文本
            self.video_text = tk.Text(self.video_frame, bg='#000000', fg='#8b949e',
                                      height=20, wrap='word', state='disabled',
                                      font=('Consolas', 10))
            self.video_text.pack(fill='both', expand=True)
            self._set_video_text('视频区域\n\n未检测到 python-vlc，点击"播放"将使用系统播放器\n\n'
                                '安装内嵌播放支持:\n  pip install python-vlc\n\n'
                                '同时需要安装 VLC 播放器: https://www.videolan.org/')

        # 地图面板
        self.map_frame = ttk.LabelFrame(self.content, text='地图', padding=4)
        self.map_canvas = MapCanvas(self.map_frame, on_click_callback=self.on_map_click)
        self.map_canvas.pack(fill='both', expand=True)

        # 默认分屏布局（视频|地图 50/50，可拖拽分隔条调整）
        self.current_view = '分屏'
        self._apply_view_layout()

        # 等窗口渲染后设置初始平分比例
        self.root.after(50, self._set_split_equal)

        # ---- 底部状态栏 ----
        self.status_var = tk.StringVar(value='就绪')
        status_bar = ttk.Label(main, textvariable=self.status_var, relief='sunken', anchor='w')
        status_bar.pack(fill='x', pady=(4, 0))

        # 进度条
        self.progress_frame = ttk.Frame(main)
        self.progress_frame.pack(fill='x', pady=(2, 0))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Scale(self.progress_frame, from_=0, to=100,
                                       variable=self.progress_var, orient='horizontal',
                                       command=self.on_progress_change)
        self.progress_bar.pack(side='left', fill='x', expand=True, padx=4)

        self.time_label = ttk.Label(self.progress_frame, text='00:00 / 00:00')
        self.time_label.pack(side='left', padx=8)

    def _apply_view_layout(self):
        """应用视图布局"""
        # 清除现有布局
        self.paned.pack_forget()
        self.video_frame.pack_forget()
        self.map_frame.pack_forget()
        # 从 PanedWindow 中移除子组件（如果之前添加过）
        try:
            self.paned.forget(self.video_frame)
        except Exception:
            pass
        try:
            self.paned.forget(self.map_frame)
        except Exception:
            pass

        view = self.current_view
        if view == '仅视频':
            self.video_frame.pack(in_=self.content, fill='both', expand=True)
        elif view == '仅地图':
            self.map_frame.pack(in_=self.content, fill='both', expand=True)
        elif view == '画中画':
            self.video_frame.pack(in_=self.content, fill='both', expand=True)
            self.map_frame.pack(in_=self.content, fill='both', expand=False, side='right',
                               padx=(4, 0), pady=(4, 0))
            # 设置地图面板为小窗口
            self.map_frame.configure(height=200)
            self.map_frame.pack_propagate(False)
        else:  # 分屏 — 使用 PanedWindow，可拖拽分隔条调整宽度
            self.paned.pack(in_=self.content, fill='both', expand=True)
            self.paned.add(self.video_frame, weight=1)
            self.paned.add(self.map_frame, weight=1)
            self.map_frame.pack_propagate(True)
            # 设置默认平分
            self.root.after(50, self._set_split_equal)

    def _set_split_equal(self):
        """将 PanedWindow 分隔条设置到正中（50/50平分）"""
        try:
            w = self.paned.winfo_width()
            if w > 10:
                self.paned.sashpos(0, w // 2)
            else:
                # 窗口还未渲染完成，稍后重试
                self.root.after(100, self._set_split_equal)
        except Exception:
            pass

    def _setup_menu(self):
        """设置菜单栏"""
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label='打开MP5/MP4文件...', command=self.open_file, accelerator='Ctrl+O')
        file_menu.add_command(label='从MP4制作MP5...', command=self.create_mp5_from_mp4)
        file_menu.add_separator()
        file_menu.add_command(label='导出GPX', command=self.export_gpx)
        file_menu.add_command(label='导出GeoJSON', command=self.export_geojson)
        file_menu.add_command(label='导出KML', command=self.export_kml)
        file_menu.add_command(label='导出MP4（去除GPS）', command=self.export_mp4)
        file_menu.add_separator()
        file_menu.add_command(label='退出', command=self.root.quit)
        menubar.add_cascade(label='文件', menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label='仅视频', command=lambda: self._set_view('仅视频'))
        view_menu.add_command(label='仅地图', command=lambda: self._set_view('仅地图'))
        view_menu.add_command(label='分屏', command=lambda: self._set_view('分屏'))
        view_menu.add_command(label='画中画', command=lambda: self._set_view('画中画'))
        menubar.add_cascade(label='视图', menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label='关于', command=self.show_about)
        menubar.add_cascade(label='帮助', menu=help_menu)

        self.root.config(menu=menubar)

        # 快捷键
        self.root.bind('<Control-o>', lambda e: self.open_file())

    # ============================================================
    # 文件操作
    # ============================================================

    def open_file(self):
        """打开MP5/MP4文件"""
        filetypes = [('MP5文件', '*.mp5'), ('MP4文件', '*.mp4'), ('所有文件', '*.*')]
        filepath = filedialog.askopenfilename(title='打开MP5/MP4文件', filetypes=filetypes)
        if not filepath:
            return

        # 先停止当前播放并重置播放/进度条到初始状态
        self.stop_play()
        self.btn_play.config(state='disabled')
        self.btn_stop.config(state='disabled')
        self.progress_var.set(0)
        self.time_label.config(text='00:00 / 00:00')
        # 清除旧的临时视频文件，下次播放时重新生成
        if self.temp_video_file:
            try:
                os.unlink(self.temp_video_file.name)
            except Exception:
                pass
            self.temp_video_file = None

        self.status_var.set(f'正在加载 {filepath}...')
        self.root.update()

        try:
            with open(filepath, 'rb') as f:
                self.file_data = f.read()
            self.file_path = filepath

            # 解析MP5
            self.mp5_info = MP5Parser.parse(self.file_data)

            # 更新UI
            self._load_track_data()
            self._update_info_display()

            self.btn_play.config(state='normal')
            self.btn_stop.config(state='normal')

            self.status_var.set(f'已加载: {os.path.basename(filepath)} '
                               f'({"MP5" if self.mp5_info.is_mp5 else "MP4"}, '
                               f'{len(self.file_data)} bytes)')

        except Exception as e:
            messagebox.showerror('错误', f'加载文件失败:\n{e}')
            self.status_var.set('加载失败')

    def create_mp5_from_mp4(self):
        """从现有MP4文件制作MP5 — 选择MP4 + 导入GPS数据"""

        dialog = tk.Toplevel(self.root)
        dialog.title('从MP4制作MP5')
        dialog.geometry('560x520')
        dialog.transient(self.root)
        dialog.grab_set()

        # 状态
        state = {
            'mp4_path': None,
            'gpx_path': None,
            'duration_ms': None,
        }

        # ---- MP4选择区 ----
        mp4_frame = ttk.LabelFrame(dialog, text='第一步：选择MP4视频文件', padding=12)
        mp4_frame.pack(fill='x', padx=12, pady=(12, 6))

        mp4_path_var = tk.StringVar(value='未选择')
        ttk.Label(mp4_frame, textvariable=mp4_path_var).pack(side='left', fill='x', expand=True)

        def choose_mp4():
            path = filedialog.askopenfilename(
                title='选择MP4视频文件',
                filetypes=[('视频文件', '*.mp4 *.mov *.avi *.mkv'), ('所有文件', '*.*')]
            )
            if not path:
                return
            state['mp4_path'] = path
            mp4_path_var.set(os.path.basename(path))

            # 获取视频时长
            duration = get_video_duration(path)
            if duration:
                state['duration_ms'] = duration
                dur_label.config(text=f'视频时长: {duration/1000:.1f}秒')
            else:
                dur_label.config(text='视频时长: 未知（无法运行ffprobe，将手动指定）')

        ttk.Button(mp4_frame, text='浏览...', command=choose_mp4).pack(side='left', padx=(8, 0))
        dur_label = ttk.Label(mp4_frame, text='视频时长: 未知')
        dur_label.pack(anchor='w', pady=(4, 0))

        # ---- GPS来源选择区 ----
        gps_frame = ttk.LabelFrame(dialog, text='第二步：选择GPS数据来源', padding=12)
        gps_frame.pack(fill='x', padx=12, pady=6)

        gps_source = tk.StringVar(value='gpx')
        ttk.Radiobutton(gps_frame, text='导入GPX文件', variable=gps_source, value='gpx',
                       command=lambda: toggle_gps_source()).pack(anchor='w')
        gpx_row = ttk.Frame(gps_frame)
        gpx_row.pack(fill='x', padx=(24, 0), pady=2)
        gpx_path_var = tk.StringVar(value='未选择')
        ttk.Label(gpx_row, textvariable=gpx_path_var).pack(side='left', fill='x', expand=True)

        def choose_gpx():
            path = filedialog.askopenfilename(
                title='选择GPX文件',
                filetypes=[('GPX文件', '*.gpx'), ('所有文件', '*.*')]
            )
            if not path:
                return
            state['gpx_path'] = path
            gpx_path_var.set(os.path.basename(path))

        ttk.Button(gpx_row, text='浏览...', command=choose_gpx).pack(side='left', padx=(8, 0))

        ttk.Radiobutton(gps_frame, text='生成模拟轨迹', variable=gps_source, value='simulate',
                       command=lambda: toggle_gps_source()).pack(anchor='w', pady=(8, 0))

        sim_frame = ttk.Frame(gps_frame)
        sim_frame.pack(fill='x', padx=(24, 0), pady=4)

        # 模拟轨迹参数
        ttk.Label(sim_frame, text='起点纬度:').grid(row=0, column=0, sticky='w')
        start_lat_var = tk.StringVar(value='39.9042')
        ttk.Entry(sim_frame, textvariable=start_lat_var, width=12).grid(row=0, column=1, padx=4)

        ttk.Label(sim_frame, text='起点经度:').grid(row=0, column=2, sticky='w')
        start_lon_var = tk.StringVar(value='116.4074')
        ttk.Entry(sim_frame, textvariable=start_lon_var, width=12).grid(row=0, column=3, padx=4)

        ttk.Label(sim_frame, text='平均速度(km/h):').grid(row=1, column=0, sticky='w')
        avg_speed_var = tk.StringVar(value='30')
        ttk.Entry(sim_frame, textvariable=avg_speed_var, width=12).grid(row=1, column=1, padx=4)

        ttk.Label(sim_frame, text='路线类型:').grid(row=1, column=2, sticky='w')
        route_var = tk.StringVar(value='linear')
        route_combo = ttk.Combobox(sim_frame, textvariable=route_var, width=10, state='readonly',
                                   values=['linear', 'loop', 'winding'])
        route_combo.grid(row=1, column=3, padx=4)

        ttk.Label(sim_frame, text='采样率(Hz):').grid(row=2, column=0, sticky='w')
        sample_rate_var = tk.StringVar(value='1')
        ttk.Entry(sim_frame, textvariable=sample_rate_var, width=12).grid(row=2, column=1, padx=4)

        def toggle_gps_source():
            is_gpx = gps_source.get() == 'gpx'
            for child in gpx_row.winfo_children():
                child.configure(state='normal' if is_gpx else 'disabled')
            for child in sim_frame.winfo_children():
                try:
                    child.configure(state='disabled' if is_gpx else 'normal')
                except:
                    pass

        toggle_gps_source()

        # ---- POI选项 ----
        poi_frame = ttk.LabelFrame(dialog, text='POI标记（可选）', padding=12)
        poi_frame.pack(fill='x', padx=12, pady=6)

        ttk.Label(poi_frame, text='POI标签（逗号分隔，每5秒一个）:').pack(anchor='w')
        poi_labels_var = tk.StringVar(value='')
        ttk.Entry(poi_frame, textvariable=poi_labels_var, width=50).pack(fill='x', pady=4)

        # ---- 进度显示 ----
        progress_frame = ttk.LabelFrame(dialog, text='进度', padding=12)
        progress_frame.pack(fill='x', padx=12, pady=6)

        progress_var = tk.StringVar(value='准备就绪')
        ttk.Label(progress_frame, textvariable=progress_var).pack(anchor='w')

        # ---- 按钮 ----
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill='x', padx=12, pady=12)

        def do_create():
            if not state['mp4_path']:
                messagebox.showwarning('提示', '请先选择MP4文件', parent=dialog)
                return

            # 获取视频时长
            duration_ms = state['duration_ms']
            if not duration_ms:
                # 手动输入时长
                result = simpledialog.askstring('视频时长', '无法自动获取视频时长，请手动输入（秒）:', parent=dialog)
                if not result:
                    return
                try:
                    duration_ms = float(result) * 1000
                except ValueError:
                    messagebox.showerror('错误', '时长输入无效', parent=dialog)
                    return

            progress_var.set('正在读取MP4文件...')
            dialog.update()

            try:
                # 读取MP4
                with open(state['mp4_path'], 'rb') as f:
                    mp4_data = f.read()

                # 获取GPS数据
                if gps_source.get() == 'gpx':
                    if not state['gpx_path']:
                        messagebox.showwarning('提示', '请选择GPX文件', parent=dialog)
                        return
                    progress_var.set('正在解析GPX文件...')
                    dialog.update()
                    gps_entries = parse_gpx_file(state['gpx_path'], duration_ms)
                    if not gps_entries:
                        messagebox.showwarning('提示', 'GPX文件中没有找到轨迹点', parent=dialog)
                        return
                else:
                    progress_var.set('正在生成模拟GPS轨迹...')
                    dialog.update()
                    gps_entries = generate_simulated_track(
                        duration_ms=duration_ms,
                        start_lat=float(start_lat_var.get()),
                        start_lon=float(start_lon_var.get()),
                        avg_speed=float(avg_speed_var.get()),
                        route_type=route_var.get(),
                        sample_rate=int(sample_rate_var.get()),
                    )

                progress_var.set(f'GPS点: {len(gps_entries)} 个，正在封装MP5...')
                dialog.update()

                # 生成POI
                pois = []
                labels = [l.strip() for l in poi_labels_var.get().split(',') if l.strip()]
                for i, label in enumerate(labels):
                    poi_time = (i + 1) * 5000  # 每5秒一个
                    idx = int(poi_time / duration_ms * len(gps_entries))
                    if 0 <= idx < len(gps_entries):
                        e = gps_entries[idx]
                        pois.append(POI(poi_time, e.latitude, e.longitude, label, 'poi'))

                # 封装MP5
                sync_config = SyncConfig(
                    interpolation=1,
                    default_view=2,
                    show_trajectory=True,
                    show_poi=True,
                )
                mp5_data = mux_mp5(mp4_data, gps_entries, sync_config, pois)

                # 保存
                default_name = os.path.splitext(os.path.basename(state['mp4_path']))[0] + '.mp5'
                save_path = filedialog.asksaveasfilename(
                    title='保存MP5文件',
                    defaultextension='.mp5',
                    filetypes=[('MP5文件', '*.mp5')],
                    initialfile=default_name,
                    parent=dialog,
                )
                if not save_path:
                    return

                with open(save_path, 'wb') as f:
                    f.write(mp5_data)

                progress_var.set(f'完成! MP5已保存: {os.path.basename(save_path)} ({len(mp5_data)} bytes)')

                # 询问是否立即打开
                if messagebox.askyesno('成功',
                    f'MP5文件已保存:\n{save_path}\n\n'
                    f'视频: {len(mp4_data)} bytes\n'
                    f'GPS点: {len(gps_entries)}\n'
                    f'POI: {len(pois)}\n'
                    f'MP5总计: {len(mp5_data)} bytes\n\n'
                    f'是否立即打开?',
                    parent=dialog):
                    dialog.destroy()
                    self.file_path = save_path
                    self.file_data = mp5_data
                    self.mp5_info = MP5Parser.parse(mp5_data)
                    self._update_info_display()
                    self._load_track_data()
                    self.btn_play.config(state='normal')
                    self.btn_stop.config(state='normal')

            except Exception as e:
                progress_var.set(f'错误: {e}')
                messagebox.showerror('错误', f'制作MP5失败:\n{e}', parent=dialog)

        ttk.Button(btn_frame, text='制作MP5', command=do_create).pack(side='left', padx=4)
        ttk.Button(btn_frame, text='关闭', command=dialog.destroy).pack(side='left', padx=4)

    def _update_info_display(self):
        """更新文件信息显示（5行3列网格）"""
        info = self.mp5_info
        L = self.info_labels

        L['file'].config(text=os.path.basename(self.file_path))
        L['size'].config(text=self._format_size(info.file_size))
        L['format'].config(text='MP5' if info.is_mp5 else 'MP4')
        L['brand'].config(text=f'{info.major_brand} ({", ".join(info.compatible_brands[:2])})')
        L['duration'].config(text=self._format_duration(info.duration_ms))

        track_strs = [f'#{t.track_id}:{t.track_type}' + (f' {t.width}x{t.height}' if t.width else '') for t in info.tracks]
        L['tracks'].config(text=f'{len(info.tracks)}条 ' + ' '.join(track_strs[:2]))

        L['gps'].config(text=str(len(info.gps_entries)))
        L['poi'].config(text=str(len(info.pois)))

        if info.sync_config:
            L['sync'].config(text=f'插值={info.sync_config.interpolation}')
        else:
            L['sync'].config(text='无')

        if info.gps_entries:
            first = info.gps_entries[0]
            last = info.gps_entries[-1]
            L['start'].config(text=f'{first.latitude:.4f}°, {first.longitude:.4f}°')
            L['end'].config(text=f'{last.latitude:.4f}°, {last.longitude:.4f}°')
        else:
            L['start'].config(text='无')
            L['end'].config(text='无')

        # 统计信息
        if self.sync_engine:
            stats = self.sync_engine.get_stats()
            L['stats'].config(text=f'{stats["distance"]:.2f}km')
            L['stat2'].config(text=f'最高:{stats["max_speed"]:.0f}km/h')
            L['stat3'].config(text=f'均速:{stats["avg_speed"]:.0f}km/h')
            L['stat4'].config(text=f'{stats["duration"]:.0f}s')
        else:
            for k in ('stats', 'stat2', 'stat3', 'stat4'):
                L[k].config(text='--')

    def _load_track_data(self):
        """加载GPS轨迹数据到地图"""
        if self.mp5_info and self.mp5_info.gps_entries:
            self.sync_engine = SyncEngine(
                self.mp5_info.gps_entries,
                self.mp5_info.sync_config
            )
            self.map_canvas.set_track(self.mp5_info.gps_entries, self.mp5_info.pois)

            # 更新进度条范围
            duration = self.mp5_info.duration_ms or (
                self.mp5_info.gps_entries[-1].timestamp if self.mp5_info.gps_entries else 0
            )
            self.progress_bar.config(to=duration)
            self.progress_var.set(0)

            # 显示统计
            stats = self.sync_engine.get_stats()
            self.status_var.set(
                f'GPS点: {stats["point_count"]} | '
                f'距离: {stats["distance"]:.2f}km | '
                f'最高速度: {stats["max_speed"]:.1f}km/h | '
                f'平均速度: {stats["avg_speed"]:.1f}km/h | '
                f'时长: {stats["duration"]:.0f}s'
            )
        else:
            self.sync_engine = None
            self.map_canvas.set_track([], [])

    # ============================================================
    # 播放控制
    # ============================================================

    def toggle_play(self):
        """播放/暂停切换"""
        if self.is_playing:
            self.pause_play()
        else:
            self.start_play()

    def _on_vlc_widget_configure(self, event):
        """VLC视频widget尺寸变化时，重新绑定window handle"""
        if not self.vlc_player or not self.vlc_widget:
            return
        # 获取平台相关的window handle
        try:
            hdl = self.vlc_widget.winfo_id()
            if sys.platform == 'win32':
                self.vlc_player.set_hwnd(hdl)
            elif sys.platform == 'darwin':
                self.vlc_player.set_nsobject(hdl)
            else:
                self.vlc_player.set_xwindow(hdl)
        except Exception as e:
            print(f'VLC绑定窗口失败: {e}')

    def start_play(self):
        """开始播放"""
        if not self.file_data:
            return

        self.is_playing = True
        self.btn_play.config(text='⏸ 暂停')
        self.playback_stop.clear()

        # 提取纯MP4数据并写入临时文件
        mp4_data = MP5Parser.get_mp4_data(self.file_data)
        if not self.temp_video_file:
            self.temp_video_file = tempfile.NamedTemporaryFile(
                suffix='.mp4', delete=False, mode='wb'
            )
            self.temp_video_file.write(mp4_data)
            self.temp_video_file.close()
        else:
            with open(self.temp_video_file.name, 'wb') as f:
                f.write(mp4_data)

        if HAS_VLC and self.vlc_player:
            # 使用VLC内嵌播放
            self._start_vlc_playback()
        else:
            # 回退到系统播放器
            self._open_system_player()

        # 启动播放时间同步线程
        self.playback_start = time.time() - (self.playback_time / 1000.0)
        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()

    def _start_vlc_playback(self):
        """使用VLC内嵌播放视频"""
        if not self.temp_video_file or not self.vlc_player:
            return

        video_path = self.temp_video_file.name

        # 创建媒体并设置给播放器
        media = self.vlc_instance.media_new(video_path)
        self.vlc_player.set_media(media)

        # 绑定视频输出到widget
        self._on_vlc_widget_configure(None)

        # 如果有当前播放位置，跳转
        if self.playback_time > 0:
            duration = self._get_duration_ms()
            if duration > 0:
                self.vlc_player.set_position(min(0.999, self.playback_time / duration))

        # 播放
        self.vlc_player.play()

    def _open_system_player(self):
        """使用系统默认播放器打开视频（VLC不可用时的回退方案）"""
        if not self.temp_video_file:
            return

        video_path = self.temp_video_file.name

        try:
            if sys.platform == 'win32':
                os.startfile(video_path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', video_path])
            else:
                subprocess.Popen(['xdg-open', video_path])
        except Exception as e:
            messagebox.showwarning('提示', f'无法打开系统播放器:\n{e}\n\n视频已保存到: {video_path}')

    def _playback_loop(self):
        """播放时间更新循环"""
        duration = self._get_duration_ms()

        while not self.playback_stop.is_set() and self.is_playing:
            if HAS_VLC and self.vlc_player:
                # 检查VLC播放状态 — 播放结束/停止时直接触发完成
                state = self.vlc_player.get_state()
                # vlc.State.Ended=6, vlc.State.Stopped=5
                if state in (6, 5):
                    self.root.after(0, self._on_playback_finished)
                    break

                # 从VLC读取真实播放时间
                vlc_time = self.vlc_player.get_time()
                if vlc_time >= 0:
                    self.playback_time = vlc_time
                else:
                    # VLC尚未就绪或刚结束，用墙钟估算
                    self.playback_time = (time.time() - self.playback_start) * 1000
            else:
                self.playback_time = (time.time() - self.playback_start) * 1000

            # 容差200ms，避免因精度差异永远差一点不到duration
            if duration > 0 and self.playback_time >= duration - 200:
                self.playback_time = duration
                self.root.after(0, self._on_playback_finished)
                break

            # 更新UI（在主线程中）
            self.root.after(0, self._update_playback_ui)
            time.sleep(0.1)

    def _update_playback_ui(self):
        """更新播放UI"""
        duration = self._get_duration_ms()

        self.progress_var.set(self.playback_time)
        self.time_label.config(text=f'{self._format_duration(self.playback_time)} / {self._format_duration(duration)}')

        # 更新地图位置
        if self.map_canvas and self.mp5_info and self.mp5_info.gps_entries:
            self.map_canvas.update_position(self.playback_time)

    def _on_playback_finished(self):
        """播放结束 — 恢复到等待播放状态"""
        self.is_playing = False
        self.playback_stop.set()
        self.playback_time = 0  # 归零，下次播放从头开始
        self.btn_play.config(text='▶ 播放')
        # 停止VLC播放器
        if HAS_VLC and self.vlc_player:
            try:
                self.vlc_player.stop()
            except Exception:
                pass
        # 进度条和时间显示归零
        self.progress_var.set(0)
        self.time_label.config(text='00:00 / 00:00')
        # 地图位置也回到起点
        if self.map_canvas:
            self.map_canvas.update_position(0)
        self.status_var.set('播放结束 — 点击"播放"可重新播放')

    def _get_duration_ms(self):
        """获取视频时长（毫秒）"""
        duration = self.mp5_info.duration_ms if self.mp5_info else 0
        if duration == 0 and self.mp5_info and self.mp5_info.gps_entries:
            duration = self.mp5_info.gps_entries[-1].timestamp
        return duration

    def pause_play(self):
        """暂停播放"""
        self.is_playing = False
        self.btn_play.config(text='▶ 播放')
        self.playback_stop.set()

        if HAS_VLC and self.vlc_player:
            self.vlc_player.set_pause(1)

    def stop_play(self):
        """停止播放"""
        self.is_playing = False
        self.btn_play.config(text='▶ 播放')
        self.playback_stop.set()
        self.playback_time = 0
        self.progress_var.set(0)
        self.time_label.config(text='00:00 / 00:00')
        if self.map_canvas:
            self.map_canvas.update_position(0)

        if HAS_VLC and self.vlc_player:
            self.vlc_player.stop()

    def on_progress_change(self, value):
        """进度条拖动"""
        self.playback_time = float(value)
        if self.is_playing:
            self.playback_start = time.time() - (self.playback_time / 1000.0)

        duration = self._get_duration_ms()

        # VLC跳转
        if HAS_VLC and self.vlc_player and duration > 0:
            pos = min(0.999, self.playback_time / duration)
            self.vlc_player.set_position(pos)

        self.time_label.config(text=f'{self._format_duration(self.playback_time)} / {self._format_duration(duration)}')

        if self.map_canvas and self.mp5_info and self.mp5_info.gps_entries:
            self.map_canvas.update_position(self.playback_time)

    def on_map_click(self, timestamp_ms):
        """地图点击回调 — 跳转视频到对应时间"""
        self.playback_time = timestamp_ms
        self.progress_var.set(timestamp_ms)
        if self.is_playing:
            self.playback_start = time.time() - (timestamp_ms / 1000.0)

        duration = self._get_duration_ms()

        # VLC跳转
        if HAS_VLC and self.vlc_player and duration > 0:
            pos = min(0.999, timestamp_ms / duration)
            self.vlc_player.set_position(pos)

        self.time_label.config(text=f'{self._format_duration(timestamp_ms)} / {self._format_duration(duration)}')
        self.status_var.set(f'跳转到: {self._format_duration(timestamp_ms)}')

    # ============================================================
    # 视图切换
    # ============================================================

    def switch_view(self, event=None):
        """切换视图"""
        self.current_view = self.view_var.get()
        self._apply_view_layout()
        self.map_canvas._redraw()

    def _set_view(self, view):
        """设置视图"""
        self.view_var.set(view)
        self.current_view = view
        self._apply_view_layout()
        self.map_canvas._redraw()

    # ============================================================
    # 导出
    # ============================================================

    def export_gpx(self):
        """导出GPX"""
        if not self.mp5_info or not self.mp5_info.gps_entries:
            messagebox.showwarning('提示', '没有GPS轨迹数据可导出')
            return

        filepath = filedialog.asksaveasfilename(
            title='导出GPX', defaultextension='.gpx',
            filetypes=[('GPX文件', '*.gpx')])
        if not filepath:
            return

        gpx = export_gpx(self.mp5_info.gps_entries, self.mp5_info.pois)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(gpx)
        self.status_var.set(f'GPX已导出: {filepath}')
        messagebox.showinfo('成功', f'GPX文件已导出:\n{filepath}')

    def export_geojson(self):
        """导出GeoJSON"""
        if not self.mp5_info or not self.mp5_info.gps_entries:
            messagebox.showwarning('提示', '没有GPS轨迹数据可导出')
            return

        filepath = filedialog.asksaveasfilename(
            title='导出GeoJSON', defaultextension='.geojson',
            filetypes=[('GeoJSON文件', '*.geojson'), ('JSON文件', '*.json')])
        if not filepath:
            return

        geojson = export_geojson(self.mp5_info.gps_entries, self.mp5_info.pois)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(geojson)
        self.status_var.set(f'GeoJSON已导出: {filepath}')
        messagebox.showinfo('成功', f'GeoJSON文件已导出:\n{filepath}')

    def export_kml(self):
        """导出KML"""
        if not self.mp5_info or not self.mp5_info.gps_entries:
            messagebox.showwarning('提示', '没有GPS轨迹数据可导出')
            return

        filepath = filedialog.asksaveasfilename(
            title='导出KML', defaultextension='.kml',
            filetypes=[('KML文件', '*.kml')])
        if not filepath:
            return

        kml = export_kml(self.mp5_info.gps_entries, self.mp5_info.pois)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(kml)
        self.status_var.set(f'KML已导出: {filepath}')
        messagebox.showinfo('成功', f'KML文件已导出:\n{filepath}')

    def export_mp4(self):
        """导出MP4（去除GPS数据）"""
        if not self.file_data:
            messagebox.showwarning('提示', '请先打开文件')
            return

        filepath = filedialog.asksaveasfilename(
            title='导出MP4', defaultextension='.mp4',
            filetypes=[('MP4文件', '*.mp4')])
        if not filepath:
            return

        mp4_data = MP5Parser.get_mp4_data(self.file_data)
        with open(filepath, 'wb') as f:
            f.write(mp4_data)
        self.status_var.set(f'MP4已导出: {filepath} ({len(mp4_data)} bytes)')
        messagebox.showinfo('成功', f'MP4文件已导出:\n{filepath}\n大小: {self._format_size(len(mp4_data))}')

    # ============================================================
    # 工具方法
    # ============================================================

    def _set_video_text(self, text):
        """设置视频区域文本"""
        self.video_text.config(state='normal')
        self.video_text.delete('1.0', 'end')
        self.video_text.insert('1.0', text)
        self.video_text.config(state='disabled')

    @staticmethod
    def _format_size(size):
        if size < 1024:
            return f'{size} B'
        elif size < 1024 * 1024:
            return f'{size / 1024:.1f} KB'
        elif size < 1024 * 1024 * 1024:
            return f'{size / (1024 * 1024):.1f} MB'
        else:
            return f'{size / (1024 * 1024 * 1024):.1f} GB'

    @staticmethod
    def _format_duration(ms):
        total_sec = int(ms / 1000)
        h = total_sec // 3600
        m = (total_sec % 3600) // 60
        s = total_sec % 60
        if h > 0:
            return f'{h}:{m:02d}:{s:02d}'
        return f'{m:02d}:{s:02d}'

    def show_about(self):
        """显示关于对话框"""
        about_text = """MP5录播器 — Windows版播放器

版本: 1.0.0
作者: MP5录播器

MP5 = MP4 + Map

功能:
  - 播放MP5/MP4文件
  - GPS轨迹地图显示
  - 视频↔地图双向联动
  - 速度热力图
  - POI标记显示
  - 导出GPX/GeoJSON/KML/MP4

技术:
  - Python + tkinter GUI
  - ISO BMFF Box解析
  - 自定义 gloc/gsyn/gpoi Box
"""
        messagebox.showinfo('关于', about_text)

    def cleanup(self):
        """清理临时文件和VLC"""
        self.playback_stop.set()
        if HAS_VLC and self.vlc_player:
            try:
                self.vlc_player.stop()
            except:
                pass
        if self.temp_video_file:
            try:
                os.unlink(self.temp_video_file.name)
            except:
                pass


# ============================================================
# 程序入口
# ============================================================

def main():
    root = tk.Tk()

    # 设置主题
    style = ttk.Style()
    try:
        style.theme_use('clam')
    except:
        pass

    # 配置颜色
    style.configure('TFrame', background='#0d1117')
    style.configure('TLabel', background='#0d1117', foreground='#e6edf3')
    style.configure('TButton', padding=6)
    style.configure('TLabelframe', background='#0d1117', foreground='#58a6ff')
    style.configure('TLabelframe.Label', background='#0d1117', foreground='#58a6ff')

    app = MP5PlayerApp(root)

    def on_closing():
        app.cleanup()
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', on_closing)
    root.mainloop()


if __name__ == '__main__':
    main()