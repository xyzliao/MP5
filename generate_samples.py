#!/usr/bin/env python3
"""
MP5示例文件生成器
用PIL生成模拟街景画面，ffmpeg编码为MP4，再附加GPS轨迹生成MP5

生成多个场景：
1. 城市驾驶 — 北京长安街
2. 山区骑行 — 旧金山弯道
3. 海岸线漫步 — 青岛海滨

运行: python3 generate_samples.py
输出: samples/*.mp5
"""

import os
import sys
import math
import struct
import subprocess
import tempfile
import json
from pathlib import Path

# 添加 windows 目录到路径
sys.path.insert(0, str(Path(__file__).parent / 'windows'))

from mp5_box import GPSEntry, SyncConfig, POI, mux_mp5, strip_mp5_boxes, write_gloc, write_gsyn, write_ftyp, write_box, write_fullbox

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random

# ============================================================
# 模拟街景画面生成
# ============================================================

class StreetViewGenerator:
    """生成模拟街景画面帧"""

    def __init__(self, width=1280, height=720):
        self.width = width
        self.height = height

    def generate_frame(self, scene, progress, speed, heading):
        """
        生成一帧模拟街景画面
        @param scene: 场景类型 (city/mountain/coast)
        @param progress: 进度 0.0-1.0
        @param speed: 速度 km/h
        @param heading: 方向角
        """
        img = Image.new('RGB', (self.width, self.height))
        draw = ImageDraw.Draw(img)

        if scene == 'city':
            self._draw_city(draw, progress, speed)
        elif scene == 'mountain':
            self._draw_mountain(draw, progress, speed)
        elif scene == 'coast':
            self._draw_coast(draw, progress, speed)

        # 叠加HUD信息
        self._draw_hud(draw, scene, progress, speed, heading)

        return img

    def _draw_city(self, draw, progress, speed):
        """城市驾驶场景"""
        w, h = self.width, self.height

        # 天空渐变
        for y in range(h // 2):
            r = int(135 - y * 0.3)
            g = int(180 - y * 0.5)
            b = int(220 - y * 0.4)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        # 远山
        mountain_y = h // 3
        draw.polygon([(0, mountain_y), (w//5, mountain_y-60), (2*w//5, mountain_y-30),
                       (3*w//5, mountain_y-80), (4*w//5, mountain_y-40), (w, mountain_y-20),
                       (w, h//2), (0, h//2)],
                      fill=(180, 185, 195))

        # 建筑物（随进度移动）
        offset = int(progress * 2000) % 300
        buildings = [
            (50, 80, 100, 200, (120, 125, 135)),
            (180, 60, 120, 220, (140, 140, 150)),
            (320, 100, 80, 180, (100, 105, 120)),
            (430, 50, 150, 240, (130, 135, 145)),
            (610, 70, 100, 210, (110, 115, 130)),
            (740, 90, 130, 190, (125, 130, 140)),
            (900, 60, 110, 230, (115, 120, 135)),
            (1040, 80, 140, 200, (135, 140, 150)),
            (1200, 50, 100, 240, (100, 105, 120)),
        ]

        for bx, by, bw, bh, color in buildings:
            x = bx - offset
            while x < -bw:
                x += 1200
            if x + bw > 0 and x < w:
                draw.rectangle([x, h//2 - bh, x + bw, h//2], fill=color)
                # 窗户
                for wy in range(h//2 - bh + 20, h//2 - 10, 30):
                    for wx in range(x + 10, x + bw - 10, 25):
                        if random.random() > 0.3:
                            draw.rectangle([wx, wy, wx + 15, wy + 18],
                                         fill=(255, 220, 100))

        # 道路
        draw.rectangle([(0, h//2), (w, h)], fill=(60, 60, 65))

        # 车道线（随速度移动）
        lane_offset = int(progress * 500 * (speed / 30)) % 80
        for i in range(-1, w // 80 + 2):
            x = i * 80 - lane_offset
            draw.rectangle([x + w//2 - 3, h//2 + 50, x + w//2 + 3, h//2 + 80],
                         fill=(255, 255, 0))
            draw.rectangle([x + w//2 - 3, h//2 + 120, x + w//2 + 3, h//2 + 150],
                         fill=(255, 255, 0))

        # 路边线
        draw.line([(w//4, h//2), (0, h)], fill=(255, 255, 255), width=3)
        draw.line([(3*w//4, h//2), (w, h)], fill=(255, 255, 255), width=3)

        # 对向来车（随进度出现）
        car_offset = int(progress * 300) % 200
        if car_offset < 100:
            car_y = h * 3 // 4
            draw.rectangle([w//4 - 40 - car_offset, car_y, w//4 - 10 - car_offset, car_y + 30],
                         fill=(200, 50, 50))

        # 前方车辆
        front_car_offset = int(progress * 200) % 100
        draw.rectangle([w//2 - 30, h//2 + 30 - front_car_offset//3,
                       w//2 + 30, h//2 + 60 - front_car_offset//3],
                      fill=(50, 50, 150))
        # 尾灯
        draw.rectangle([w//2 - 25, h//2 + 35 - front_car_offset//3,
                       w//2 - 20, h//2 + 40 - front_car_offset//3],
                      fill=(255, 50, 50))
        draw.rectangle([w//2 + 20, h//2 + 35 - front_car_offset//3,
                       w//2 + 25, h//2 + 40 - front_car_offset//3],
                      fill=(255, 50, 50))

    def _draw_mountain(self, draw, progress, speed):
        """山区骑行场景"""
        w, h = self.width, self.height

        # 天空渐变
        for y in range(h // 2):
            r = int(100 + y * 0.2)
            g = int(130 + y * 0.3)
            b = int(180 + y * 0.1)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        # 远山层1（最远）
        draw.polygon([(0, h//3), (w//4, h//4), (w//2, h//3 - 20),
                       (3*w//4, h//5), (w, h//3), (w, h//2), (0, h//2)],
                      fill=(100, 110, 130))

        # 远山层2
        offset2 = int(progress * 100) % w
        draw.polygon([(0 - offset2, h*2//5), (w//3, h//3 + 20),
                       (2*w//3, h*2//5 - 10), (w - offset2, h//3 + 30),
                       (w, h//2), (0, h//2)],
                      fill=(80, 95, 115))

        # 近山层
        draw.polygon([(0, h//2 - 30), (w//5, h//2 - 80),
                       (2*w//5, h//2 - 50), (3*w//5, h//2 - 90),
                       (4*w//5, h//2 - 40), (w, h//2 - 70),
                       (w, h//2), (0, h//2)],
                      fill=(60, 80, 60))

        # 树木
        tree_offset = int(progress * 300 * (speed / 20)) % 150
        for i in range(-1, w // 150 + 2):
            tx = i * 150 - tree_offset
            if 0 < tx < w:
                # 树干
                draw.rectangle([tx + 20, h//2 - 40, tx + 28, h//2], fill=(80, 60, 40))
                # 树冠
                draw.ellipse([tx, h//2 - 80, tx + 50, h//2 - 30], fill=(40, 100, 40))

        # 弯道道路
        draw.polygon([(0, h//2), (w, h//2),
                       (w, h), (0, h)],
                      fill=(80, 75, 70))

        # 弯曲道路标线
        curve_offset = int(progress * 200) % 100
        for i in range(20):
            t = i / 20 + progress * 0.1
            cx = int(w/2 + math.sin(t * math.pi * 2) * w/4)
            cy = int(h/2 + i * (h/2) / 20 + curve_offset)
            if cy < h:
                draw.ellipse([cx-3, cy-3, cx+3, cy+3], fill=(255, 255, 255))

        # 自行车手视角（车把）
        draw.arc([w//4, h-80, w//2 - 20, h-20], 0, 180, fill=(50, 50, 50), width=8)
        draw.arc([w//2 + 20, h-80, 3*w//4, h-20], 0, 180, fill=(50, 50, 50), width=8)
        draw.line([(w//2, h-50), (w//2, h-10)], fill=(40, 40, 40), width=5)

    def _draw_coast(self, draw, progress, speed):
        """海岸线漫步场景"""
        w, h = self.width, self.height

        # 天空渐变（日落）
        for y in range(h // 2):
            r = int(255 - y * 0.2)
            g = int(180 - y * 0.3)
            b = int(120 + y * 0.1)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        # 太阳
        sun_x = w * 3 // 4 + int(math.sin(progress * math.pi) * 50)
        sun_y = h // 4
        draw.ellipse([sun_x - 50, sun_y - 50, sun_x + 50, sun_y + 50],
                     fill=(255, 220, 150))
        # 太阳光晕
        for r in range(50, 100, 5):
            alpha_color = (255, 220, 150)
            draw.ellipse([sun_x - r, sun_y - r, sun_x + r, sun_y + r],
                        outline=(255, 200, 100))

        # 海面
        for y in range(h // 2, h * 3 // 4):
            r = int(50 + (y - h//2) * 0.5)
            g = int(80 + (y - h//2) * 0.3)
            b = int(120 + (y - h//2) * 0.2)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        # 海面反光
        wave_offset = int(progress * 300) % 60
        for i in range(w // 60 + 2):
            wx = i * 60 - wave_offset
            draw.line([(wx, h//2 + 20), (wx + 40, h//2 + 20)],
                      fill=(200, 200, 220), width=2)
            draw.line([(wx + 10, h//2 + 50), (wx + 50, h//2 + 50)],
                      fill=(180, 180, 210), width=1)

        # 沙滩
        draw.rectangle([(0, h*3//4), (w, h)], fill=(220, 200, 160))

        # 沙滩纹理
        for i in range(50):
            sx = random.randint(0, w)
            sy = random.randint(h*3//4, h)
            draw.point([sx, sy], fill=(200, 180, 140))

        # 远处的船
        boat_x = int(progress * 200) % (w + 100) - 50
        if boat_x > 0 and boat_x < w:
            draw.polygon([(boat_x, h//2 + 10), (boat_x + 30, h//2 + 10),
                          (boat_x + 25, h//2 + 25), (boat_x + 5, h//2 + 25)],
                         fill=(120, 80, 60))
            draw.line([(boat_x + 15, h//2 + 10), (boat_x + 15, h//2 - 15)],
                      fill=(80, 60, 40), width=2)
            draw.polygon([(boat_x + 15, h//2 - 15), (boat_x + 30, h//2),
                          (boat_x + 15, h//2)], fill=(255, 250, 240))

        # 椰子树
        tree_offset = int(progress * 200 * (speed / 10)) % 250
        for i in range(-1, w // 250 + 2):
            tx = i * 250 - tree_offset
            if 0 < tx < w:
                # 树干
                draw.line([(tx, h*3//4), (tx + 5, h*3//4 - 100)],
                         fill=(100, 70, 50), width=8)
                # 树叶
                for angle in range(0, 360, 45):
                    lx = tx + 5 + int(math.cos(math.radians(angle)) * 40)
                    ly = h*3//4 - 100 + int(math.sin(math.radians(angle)) * 30)
                    draw.ellipse([lx-20, ly-10, lx+20, ly+10],
                               fill=(30, 80, 30))

        # 行走的人影（视角下方）
        walk_offset = int(progress * 100) % 40
        draw.ellipse([w//2 - 30 + walk_offset//2, h - 60,
                      w//2 + 30 + walk_offset//2, h - 20],
                     fill=(60, 60, 80))

    def _draw_hud(self, draw, scene, progress, speed, heading):
        """绘制HUD信息"""
        w, h = self.width, self.height

        # 尝试加载字体
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            font = ImageFont.load_default()
            font_small = font

        # 半透明背景条
        overlay = Image.new('RGBA', (w, 50), (0, 0, 0, 160))
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        img.paste(overlay, (0, 0))

        # 场景名称
        scene_names = {'city': '城市驾驶', 'mountain': '山区骑行', 'coast': '海岸漫步'}
        draw.text((20, 15), scene_names.get(scene, scene),
                 fill=(255, 255, 255), font=font)

        # 速度
        draw.text((w - 200, 15), f'{speed:.0f} km/h',
                 fill=(100, 255, 100), font=font)

        # 方向
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        dir_idx = int(heading / 45) % 8
        draw.text((w - 300, 15), f'{heading:.0f}° {directions[dir_idx]}',
                 fill=(100, 200, 255), font=font)

        # 进度条
        bar_y = h - 10
        draw.rectangle([(0, bar_y), (w, h)], fill=(0, 0, 0, 180))
        bar_w = int(w * progress)
        draw.rectangle([(0, bar_y), (bar_w, h)], fill=(88, 166, 255))

        # 时间戳
        total_sec = int(progress * 60)
        draw.text((10, h - 30), f'{total_sec//60:02d}:{total_sec%60:02d}',
                 fill=(255, 255, 255), font=font_small)

        # MP5水印
        draw.text((w - 80, h - 30), 'MP5', fill=(88, 166, 255), font=font)


# ============================================================
# GPS轨迹生成
# ============================================================

def generate_gps_track(scene, duration_sec, fps=30):
    """根据场景生成模拟GPS轨迹"""
    entries = []
    total_frames = duration_sec * fps

    if scene == 'city':
        # 北京长安街 — 直线行驶
        start_lat, start_lon = 39.9087, 116.3974
        for i in range(total_frames):
            t = i / fps
            progress = t / duration_sec
            lat = start_lat + progress * 0.005
            lon = start_lon + progress * 0.003
            speed = 40 + 10 * math.sin(t * 0.3)
            heading = 89 + 5 * math.sin(t * 0.2)
            entries.append(GPSEntry(
                timestamp=int(t * 1000),
                latitude=lat, longitude=lon,
                altitude=45 + math.sin(progress * math.pi) * 3,
                accuracy=5, heading=heading, speed=speed
            ))

    elif scene == 'mountain':
        # 旧金山弯道 — S形山路
        start_lat, start_lon = 37.7589, -122.4484
        for i in range(total_frames):
            t = i / fps
            progress = t / duration_sec
            angle = progress * math.pi * 2
            lat = start_lat + progress * 0.003 + 0.001 * math.sin(angle * 3)
            lon = start_lon + progress * 0.003 + 0.001 * math.cos(angle * 3)
            speed = 20 + 15 * math.sin(t * 0.5)
            heading = (angle * 180 / math.pi + 360) % 360
            entries.append(GPSEntry(
                timestamp=int(t * 1000),
                latitude=lat, longitude=lon,
                altitude=100 + 50 * math.sin(progress * math.pi * 2),
                accuracy=3, heading=heading, speed=max(5, speed)
            ))

    elif scene == 'coast':
        # 青岛海滨 — 沿海岸线漫步
        start_lat, start_lon = 36.0591, 120.3817
        for i in range(total_frames):
            t = i / fps
            progress = t / duration_sec
            lat = start_lat + progress * 0.001
            lon = start_lon + progress * 0.002 + 0.0003 * math.sin(progress * math.pi * 4)
            speed = 5 + 3 * math.sin(t * 0.2)
            heading = (90 + 30 * math.sin(progress * math.pi * 3)) % 360
            entries.append(GPSEntry(
                timestamp=int(t * 1000),
                latitude=lat, longitude=lon,
                altitude=5 + 2 * math.sin(t * 0.1),
                accuracy=4, heading=heading, speed=max(0, speed)
            ))

    return entries


def generate_pois(scene, entries):
    """根据场景生成POI标记"""
    pois = []
    if not entries:
        return pois

    if scene == 'city':
        # 天安门、王府井
        pois = [
            POI(5000, entries[5].latitude, entries[5].longitude, '天安门广场', 'poi'),
            POI(25000, entries[150].latitude, entries[150].longitude, '王府井大街', 'poi'),
        ]
    elif scene == 'mountain':
        # 山顶、弯道
        pois = [
            POI(10000, entries[60].latitude, entries[60].longitude, '观景台', 'poi'),
            POI(30000, entries[180].latitude, entries[180].longitude, '发卡弯', 'poi'),
        ]
    elif scene == 'coast':
        # 码头、灯塔
        pois = [
            POI(8000, entries[48].latitude, entries[48].longitude, '栈桥', 'poi'),
            POI(40000, entries[240].latitude, entries[240].longitude, '灯塔', 'poi'),
        ]

    return pois


# ============================================================
# 视频生成
# ============================================================

def generate_video(scene, duration_sec=20, fps=30, output_path=None):
    """
    生成模拟街景视频
    1. PIL生成帧
    2. 保存为临时图片序列
    3. ffmpeg编码为MP4
    """
    gen = StreetViewGenerator(1280, 720)

    # 生成GPS轨迹
    gps_entries = generate_gps_track(scene, duration_sec, fps)
    pois = generate_pois(scene, gps_entries)

    # 输出路径
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.mp4')

    # 临时目录存放帧
    frames_dir = tempfile.mkdtemp(prefix='mp5_frames_')

    print(f'  生成 {scene} 场景帧 ({duration_sec}s @ {fps}fps = {duration_sec*fps}帧)...')

    for i in range(duration_sec * fps):
        t = i / fps
        progress = t / duration_sec
        entry = gps_entries[i]
        frame = gen.generate_frame(scene, progress, entry.speed, entry.heading)
        frame_path = os.path.join(frames_dir, f'frame_{i:05d}.png')
        frame.save(frame_path, 'PNG')

        if i % 150 == 0:
            print(f'    帧 {i}/{duration_sec*fps}')

    # 使用ffmpeg编码为MP4
    print(f'  ffmpeg编码 MP4...')
    cmd = [
        'ffmpeg', '-y',
        '-framerate', str(fps),
        '-i', os.path.join(frames_dir, 'frame_%05d.png'),
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'  ffmpeg错误: {result.stderr[:500]}')
        raise RuntimeError(f'ffmpeg编码失败: {result.returncode}')

    # 清理临时帧
    for f in os.listdir(frames_dir):
        os.remove(os.path.join(frames_dir, f))
    os.rmdir(frames_dir)

    print(f'  MP4已生成: {output_path} ({os.path.getsize(output_path)} bytes)')
    return output_path, gps_entries, pois


# ============================================================
# MP5封装
# ============================================================

def create_mp5(scene, duration_sec=20, fps=30, output_path=None):
    """生成完整的MP5文件（视频+GPS+POI）"""
    # 1. 生成视频
    mp4_path, gps_entries, pois = generate_video(scene, duration_sec, fps)

    # 2. 读取MP4数据
    with open(mp4_path, 'rb') as f:
        mp4_data = f.read()

    # 3. 封装为MP5
    sync_config = SyncConfig(
        sync_mode=0,
        sync_offset=0,
        interpolation=1,  # 线性插值
        default_view=2,   # 分屏
        video_ratio=0.5,
        map_style=0,      # 标准
        show_trajectory=True,
        show_poi=True
    )

    mp5_data = mux_mp5(mp4_data, gps_entries, sync_config, pois)

    # 4. 写入MP5文件
    if output_path is None:
        output_path = f'samples/{scene}_drive.mp5'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(mp5_data)

    # 清理临时MP4
    os.unlink(mp4_path)

    print(f'  MP5已生成: {output_path} ({len(mp5_data)} bytes)')
    print(f'  GPS采样点: {len(gps_entries)}')
    print(f'  POI标记: {len(pois)}')

    return output_path


# ============================================================
# 主程序
# ============================================================

def main():
    print('=' * 60)
    print('  MP5示例文件生成器')
    print('  用PIL模拟街景画面 + ffmpeg编码 + GPS轨迹封装')
    print('=' * 60)

    scenes = [
        ('city', '城市驾驶 — 北京长安街', 20, 30),
        ('mountain', '山区骑行 — 旧金山弯道', 20, 30),
        ('coast', '海岸漫步 — 青岛海滨', 20, 30),
    ]

    output_dir = os.path.join(os.path.dirname(__file__), 'samples')
    os.makedirs(output_dir, exist_ok=True)

    results = []

    for scene, name, duration, fps in scenes:
        print(f'\n{"=" * 60}')
        print(f'场景: {name}')
        print(f'时长: {duration}s, 帧率: {fps}fps')
        print(f'{"=" * 60}')

        output_path = os.path.join(output_dir, f'{scene}.mp5')

        try:
            create_mp5(scene, duration, fps, output_path)
            results.append((name, output_path, '成功'))
        except Exception as e:
            print(f'  生成失败: {e}')
            results.append((name, output_path, f'失败: {e}'))

    print(f'\n{"=" * 60}')
    print('生成结果汇总:')
    print(f'{"=" * 60}')
    for name, path, status in results:
        size = os.path.getsize(path) if os.path.exists(path) else 0
        print(f'  {name}: {status} ({path}, {size/1024/1024:.1f} MB)')

    print(f'\n输出目录: {output_dir}')


if __name__ == '__main__':
    main()