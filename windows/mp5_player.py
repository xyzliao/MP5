#!/usr/bin/env python3
"""
MP5录播器 — Windows版桌面播放器
基于 tkinter 的 GUI 应用

功能:
  - 打开 MP5/MP4 文件
  - 视频播放（调用系统播放器或内嵌播放）
  - GPS轨迹地图显示（Canvas绘制）
  - 视频↔地图双向联动
  - 速度热力图
  - POI标记显示
  - 导出 GPX / GeoJSON / KML / MP4
  - 轨迹统计信息

运行方式:
  python mp5_player.py

在 Windows 上可直接运行，无需额外安装依赖。
视频播放使用系统默认播放器打开（如果需要内嵌播放，需安装 python-vlc）。

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
        ttk.Button(toolbar, text='生成示例', command=self.generate_sample).pack(side='left', padx=4)
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

        self.info_label = ttk.Label(self.info_frame, text='请打开 MP5/MP4 文件')
        self.info_label.pack(anchor='w')

        # ---- 主内容区 ----
        content = ttk.Frame(main)
        content.pack(fill='both', expand=True)

        # 视频面板
        self.video_frame = ttk.LabelFrame(content, text='视频', padding=4)
        self.video_text = tk.Text(self.video_frame, bg='#000000', fg='#8b949e',
                                  height=20, wrap='word', state='disabled',
                                  font=('Consolas', 10))
        self.video_text.pack(fill='both', expand=True)
        self._set_video_text('视频区域\n\n打开MP5文件后，点击"播放"将使用系统播放器播放视频\n\n'
                            '如需内嵌播放，请安装 python-vlc:\n  pip install python-vlc')

        # 地图面板
        self.map_frame = ttk.LabelFrame(content, text='地图', padding=4)
        self.map_canvas = MapCanvas(self.map_frame, on_click_callback=self.on_map_click)

        # 默认分屏布局
        self.current_view = '分屏'
        self._apply_view_layout()

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
        self.video_frame.pack_forget()
        self.map_frame.pack_forget()

        view = self.current_view
        if view == '仅视频':
            self.video_frame.pack(fill='both', expand=True, side='left')
        elif view == '仅地图':
            self.map_frame.pack(fill='both', expand=True, side='left')
        elif view == '画中画':
            self.video_frame.pack(fill='both', expand=True, side='left')
            self.map_frame.pack(fill='both', expand=False, side='right',
                               padx=(4, 0), pady=(4, 0))
            # 设置地图面板为小窗口
            self.map_frame.configure(height=200)
            self.map_frame.pack_propagate(False)
        else:  # 分屏
            self.video_frame.pack(fill='both', expand=True, side='left', padx=(0, 4))
            self.map_frame.pack(fill='both', expand=True, side='right')
            self.map_frame.pack_propagate(True)

    def _setup_menu(self):
        """设置菜单栏"""
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label='打开MP5/MP4文件...', command=self.open_file, accelerator='Ctrl+O')
        file_menu.add_command(label='生成示例MP5文件', command=self.generate_sample)
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

        self.status_var.set(f'正在加载 {filepath}...')
        self.root.update()

        try:
            with open(filepath, 'rb') as f:
                self.file_data = f.read()
            self.file_path = filepath

            # 解析MP5
            self.mp5_info = MP5Parser.parse(self.file_data)

            # 更新UI
            self._update_info_display()
            self._load_track_data()

            self.btn_play.config(state='normal')
            self.btn_stop.config(state='normal')

            self.status_var.set(f'已加载: {os.path.basename(filepath)} '
                               f'({"MP5" if self.mp5_info.is_mp5 else "MP4"}, '
                               f'{len(self.file_data)} bytes)')

        except Exception as e:
            messagebox.showerror('错误', f'加载文件失败:\n{e}')
            self.status_var.set('加载失败')

    def generate_sample(self):
        """生成示例MP5文件"""
        self.status_var.set('正在生成示例MP5文件...')
        self.root.update()

        try:
            data = create_sample_mp5(60)
            filepath = filedialog.asksaveasfilename(
                title='保存示例MP5文件',
                defaultextension='.mp5',
                filetypes=[('MP5文件', '*.mp5')],
                initialfile='sample.mp5'
            )
            if filepath:
                with open(filepath, 'wb') as f:
                    f.write(data)
                self.status_var.set(f'示例文件已保存: {filepath} ({len(data)} bytes)')
                messagebox.showinfo('成功', f'示例MP5文件已保存:\n{filepath}\n大小: {len(data)} bytes')
            else:
                self.status_var.set('就绪')
        except Exception as e:
            messagebox.showerror('错误', f'生成失败:\n{e}')
            self.status_var.set('生成失败')

    def _update_info_display(self):
        """更新文件信息显示"""
        info = self.mp5_info
        lines = []

        lines.append(f'文件: {os.path.basename(self.file_path)}')
        lines.append(f'大小: {self._format_size(info.file_size)}')
        lines.append(f'格式: {"MP5" if info.is_mp5 else "MP4"}')
        lines.append(f'品牌: {info.major_brand} (兼容: {", ".join(info.compatible_brands)})')
        lines.append(f'时长: {self._format_duration(info.duration_ms)}')
        lines.append(f'轨道: {len(info.tracks)}')
        for t in info.tracks:
            dim = f' {t.width}x{t.height}' if t.width else ''
            lines.append(f'  - #{t.track_id}: {t.track_type}{dim}')
        lines.append(f'GPS采样点: {len(info.gps_entries)}')
        lines.append(f'POI标记: {len(info.pois)}')
        if info.sync_config:
            lines.append(f'同步模式: {info.sync_config.sync_mode}, 插值: {info.sync_config.interpolation}')
        if info.gps_entries:
            first = info.gps_entries[0]
            last = info.gps_entries[-1]
            lines.append(f'起点: {first.latitude:.6f}°, {first.longitude:.6f}°')
            lines.append(f'终点: {last.latitude:.6f}°, {last.longitude:.6f}°')

        self.info_label.config(text='\n'.join(lines))

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

        # 使用系统默认播放器打开视频
        self._open_system_player()

        # 启动播放时间模拟线程
        self.playback_start = time.time() - (self.playback_time / 1000.0)
        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()

    def _open_system_player(self):
        """使用系统默认播放器打开视频"""
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
        duration = self.mp5_info.duration_ms if self.mp5_info else 0
        if duration == 0 and self.mp5_info and self.mp5_info.gps_entries:
            duration = self.mp5_info.gps_entries[-1].timestamp

        while not self.playback_stop.is_set() and self.is_playing:
            self.playback_time = (time.time() - self.playback_start) * 1000

            if duration > 0 and self.playback_time >= duration:
                self.playback_time = duration
                self.root.after(0, self._on_playback_finished)
                break

            # 更新UI（在主线程中）
            self.root.after(0, self._update_playback_ui)
            time.sleep(0.1)

    def _update_playback_ui(self):
        """更新播放UI"""
        duration = self.mp5_info.duration_ms if self.mp5_info else 0
        if duration == 0 and self.mp5_info and self.mp5_info.gps_entries:
            duration = self.mp5_info.gps_entries[-1].timestamp

        self.progress_var.set(self.playback_time)
        self.time_label.config(text=f'{self._format_duration(self.playback_time)} / {self._format_duration(duration)}')

        # 更新地图位置
        if self.map_canvas and self.mp5_info and self.mp5_info.gps_entries:
            self.map_canvas.update_position(self.playback_time)

    def _on_playback_finished(self):
        """播放结束"""
        self.is_playing = False
        self.btn_play.config(text='▶ 播放')
        self.status_var.set('播放结束')

    def pause_play(self):
        """暂停播放"""
        self.is_playing = False
        self.btn_play.config(text='▶ 播放')
        self.playback_stop.set()

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

    def on_progress_change(self, value):
        """进度条拖动"""
        self.playback_time = float(value)
        if self.is_playing:
            self.playback_start = time.time() - (self.playback_time / 1000.0)

        duration = self.mp5_info.duration_ms if self.mp5_info else 0
        if duration == 0 and self.mp5_info and self.mp5_info.gps_entries:
            duration = self.mp5_info.gps_entries[-1].timestamp

        self.time_label.config(text=f'{self._format_duration(self.playback_time)} / {self._format_duration(duration)}')

        if self.map_canvas and self.mp5_info and self.mp5_info.gps_entries:
            self.map_canvas.update_position(self.playback_time)

    def on_map_click(self, timestamp_ms):
        """地图点击回调 — 跳转视频到对应时间"""
        self.playback_time = timestamp_ms
        self.progress_var.set(timestamp_ms)
        if self.is_playing:
            self.playback_start = time.time() - (timestamp_ms / 1000.0)

        duration = self.mp5_info.duration_ms if self.mp5_info else 0
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
        """清理临时文件"""
        self.playback_stop.set()
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