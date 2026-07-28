"""
MP5 Box 编解码引擎
基于 ISO BMFF (ISO 14496-12) 规范，实现 Box 的二进制读写

MP5 扩展 Box 类型:
  gloc - GPS坐标轨迹
  gmap - 嵌入地图数据（可选）
  gsyn - 同步规则
  gpoi - POI标记数据

作者: MP5录播器
"""

import struct
import io
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# ============================================================
# GPS采样点数据结构
# ============================================================

@dataclass
class GPSEntry:
    """GPS采样点 (gloc box 中的单个条目)"""
    timestamp: int    # 毫秒，相对于mvhd时间起点
    latitude: float   # 纬度, WGS84
    longitude: float  # 经度, WGS84
    altitude: float   # 海拔高度(米)
    accuracy: float   # 定位精度(米)
    heading: float    # 方向角 0-360度
    speed: float      # 速度 km/h

    def encode(self) -> bytes:
        """编码为34字节二进制

        字段顺序（按MP5格式规范）:
        timestamp(8B) + latitude(8B) + longitude(8B) + altitude(4B signed)
        + accuracy(2B) + heading(2B) + speed(2B)
        """
        return struct.pack('>qqqiHHH',
            int(self.timestamp),
            int(self.latitude * 1e7),
            int(self.longitude * 1e7),
            int(self.altitude * 10),
            int(self.accuracy),
            int(self.heading * 10) & 0xFFFF,
            int(self.speed * 10) & 0xFFFF,
        )

    @classmethod
    def decode(cls, data: bytes, offset: int = 0) -> 'GPSEntry':
        """从二进制解码"""
        ts, lat, lon, alt, acc, hdg, spd = struct.unpack_from('>qqqiHHH', data, offset)
        return cls(
            timestamp=ts,
            latitude=lat / 1e7,
            longitude=lon / 1e7,
            altitude=alt / 10,
            accuracy=acc,
            heading=hdg / 10,
            speed=spd / 10,
        )

GLOC_ENTRY_SIZE = 34

# ============================================================
# 同步规则数据结构
# ============================================================

@dataclass
class SyncConfig:
    """gsyn box 同步规则"""
    sync_mode: int = 0          # 0=时间同步, 1=最近邻, 2=插值
    sync_offset: int = 0       # 同步偏移量(毫秒)
    interpolation: int = 1      # 0=最近邻, 1=线性, 2=三次样条
    default_view: int = 2      # 0=仅视频, 1=仅地图, 2=分屏左右, 3=分屏上下, 4=画中画
    video_ratio: float = 0.5   # 分屏视频占比
    map_style: int = 0         # 0=标准, 1=卫星, 2=地形, 3=暗色
    show_trajectory: bool = True
    show_poi: bool = True

    def encode(self) -> bytes:
        return struct.pack('>BiBfBBB',
            self.sync_mode,
            self.sync_offset,
            self.interpolation,
            self.video_ratio,
            self.map_style,
            1 if self.show_trajectory else 0,
            1 if self.show_poi else 0,
        )

    @classmethod
    def decode(cls, data: bytes, offset: int = 0) -> 'SyncConfig':
        sync_mode, sync_offset, interp, ratio, map_style, show_traj, show_poi = \
            struct.unpack_from('>BiBfBBB', data, offset)
        return cls(
            sync_mode=sync_mode,
            sync_offset=sync_offset,
            interpolation=interp,
            default_view=2,  # 从数据中不直接读取，用默认值
            video_ratio=ratio,
            map_style=map_style,
            show_trajectory=bool(show_traj),
            show_poi=bool(show_poi),
        )

GSYN_PAYLOAD_SIZE = 14  # 1+4+1+4+1+1+1 = 13, 加上default_view=1 → 14

# ============================================================
# POI数据结构
# ============================================================

@dataclass
class POI:
    """兴趣点标记"""
    timestamp: int
    latitude: float
    longitude: float
    label: str = ''
    type: str = 'poi'

    def encode(self) -> bytes:
        label_bytes = self.label.encode('utf-8')
        return struct.pack('>qqq', int(self.timestamp), int(self.latitude * 1e7), int(self.longitude * 1e7)) + \
               struct.pack('>H', len(label_bytes)) + label_bytes + \
               struct.pack('>B', ord(self.type[0]) if self.type else 0)

    @classmethod
    def decode(cls, data: bytes, offset: int) -> tuple:
        ts, lat, lon = struct.unpack_from('>qqq', data, offset)
        offset += 24
        label_len = struct.unpack_from('>H', data, offset)[0]
        offset += 2
        label = data[offset:offset+label_len].decode('utf-8')
        offset += label_len
        type_byte = data[offset]
        offset += 1
        return cls(ts, lat / 1e7, lon / 1e7, label, chr(type_byte) if type_byte else 'poi'), offset

# ============================================================
# ISO BMFF Box 读写
# ============================================================

@dataclass
class Box:
    """ISO BMFF Box"""
    type: str
    offset: int
    size: int
    data_offset: int
    data_size: int
    buffer: bytes
    version: Optional[int] = None
    flags: Optional[int] = None
    children: List['Box'] = field(default_factory=list)

def parse_boxes(data: bytes, start: int = 0, end: Optional[int] = None) -> List[Box]:
    """递归解析 ISO BMFF box 结构"""
    if end is None:
        end = len(data)
    boxes = []
    offset = start

    while offset + 8 <= end:
        box_start = offset
        size = struct.unpack_from('>I', data, offset)[0]
        box_type = data[offset+4:offset+8].decode('ascii', errors='replace')
        header_size = 8

        if size == 1:
            # 64-bit extended size
            size = struct.unpack_from('>Q', data, offset + 8)[0]
            header_size = 16
        elif size == 0:
            # box extends to end
            size = end - box_start

        data_offset = box_start + header_size
        data_size = size - header_size

        box = Box(
            type=box_type,
            offset=box_start,
            size=size,
            data_offset=data_offset,
            data_size=data_size,
            buffer=data[box_start:box_start + size],
        )

        # FullBox: 解析 version 和 flags
        if box_type in ('gloc', 'gmap', 'gsyn', 'gpoi', 'mvhd', 'tkhd', 'mdhd', 'hdlr'):
            if data_size >= 4:
                box.version = data[data_offset]
                box.flags = (data[data_offset+1] << 16) | (data[data_offset+2] << 8) | data[data_offset+3]

        # Container boxes: 递归解析子 box
        if box_type in ('moov', 'trak', 'mdia', 'minf', 'stbl', 'meta', 'udta', 'edts'):
            box.children = parse_boxes(data, data_offset, box_start + size)

        boxes.append(box)
        offset = box_start + size

    return boxes

def find_box(boxes: List[Box], box_type: str) -> Optional[Box]:
    """查找指定类型的 box (递归)"""
    for box in boxes:
        if box.type == box_type:
            return box
        found = find_box(box.children, box_type)
        if found:
            return found
    return None

def find_all_boxes(boxes: List[Box], box_type: str) -> List[Box]:
    """查找所有指定类型的 box (递归)"""
    results = []
    for box in boxes:
        if box.type == box_type:
            results.append(box)
        results.extend(find_all_boxes(box.children, box_type))
    return results

# ============================================================
# MP5 自定义 Box 解析
# ============================================================

def parse_gloc(box: Box) -> List[GPSEntry]:
    """解析 gloc box，返回GPS采样点列表"""
    # FullBox: 跳过 version(1) + flags(3) = 4字节
    # box.buffer is a slice starting at box.offset in the original data
    # version+flags is at offset 8 in the buffer (after 8-byte header)
    # entry_count is at offset 12, entries start at offset 16
    payload_offset = 12  # relative to box.buffer start (8 header + 4 version+flags)
    data = box.buffer

    if len(data) < payload_offset + 4:
        return []

    entry_count = struct.unpack_from('>I', data, payload_offset)[0]
    entries = []
    offset = payload_offset + 4

    for _ in range(entry_count):
        if offset + GLOC_ENTRY_SIZE > len(data):
            break
        entry = GPSEntry.decode(data, offset)
        entries.append(entry)
        offset += GLOC_ENTRY_SIZE

    return entries

def parse_gsyn(box: Box) -> SyncConfig:
    """解析 gsyn box，返回同步规则"""
    payload_offset = 12  # relative to box.buffer (8 header + 4 version+flags)
    data = box.buffer

    if len(data) < payload_offset + 14:
        return SyncConfig()

    sync_mode, sync_offset, interp, ratio, map_style, show_traj, show_poi, default_view = \
        struct.unpack_from('>BiBfBBBB', data, payload_offset)

    return SyncConfig(
        sync_mode=sync_mode,
        sync_offset=sync_offset,
        interpolation=interp,
        default_view=default_view,
        video_ratio=ratio,
        map_style=map_style,
        show_trajectory=bool(show_traj),
        show_poi=bool(show_poi),
    )

def parse_gpoi(box: Box) -> List[POI]:
    """解析 gpoi box，返回POI列表"""
    payload_offset = 12  # relative to box.buffer (8 header + 4 version+flags)
    data = box.buffer

    if len(data) < payload_offset + 4:
        return []

    poi_count = struct.unpack_from('>I', data, payload_offset)[0]
    pois = []
    offset = payload_offset + 4

    for _ in range(poi_count):
        if offset + 27 > len(data):
            break
        poi, offset = POI.decode(data, offset)
        pois.append(poi)

    return pois

def parse_gmap(box: Box) -> Optional[Dict[str, Any]]:
    """解析 gmap box，返回地图数据"""
    payload_offset = 12  # relative to box.buffer (8 header + 4 version+flags)
    data = box.buffer

    if len(data) < payload_offset + 38:
        return None

    map_type = data[payload_offset]
    crs = data[payload_offset + 1]
    south = struct.unpack_from('>q', data, payload_offset + 2)[0] / 1e7
    west = struct.unpack_from('>q', data, payload_offset + 10)[0] / 1e7
    north = struct.unpack_from('>q', data, payload_offset + 18)[0] / 1e7
    east = struct.unpack_from('>q', data, payload_offset + 26)[0] / 1e7
    map_data_size = struct.unpack_from('>I', data, payload_offset + 34)[0]
    map_data = data[payload_offset + 38:payload_offset + 38 + map_data_size]

    return {
        'map_type': map_type,
        'crs': crs,
        'bounds': {'south': south, 'west': west, 'north': north, 'east': east},
        'map_data': map_data,
    }

# ============================================================
# MP5 Box 写入
# ============================================================

def write_box(box_type: str, payload: bytes) -> bytes:
    """写入一个标准 Box"""
    size = 8 + len(payload)
    return struct.pack('>I', size) + box_type.encode('ascii')[:4].ljust(4, b'\x00') + payload

def write_fullbox(box_type: str, version: int, flags: int, payload: bytes) -> bytes:
    """写入一个 FullBox (含 version 和 flags)"""
    header = struct.pack('>I', 12 + len(payload)) + box_type.encode('ascii')[:4].ljust(4, b'\x00')
    vf = struct.pack('>I', (version << 24) | (flags & 0xFFFFFF))
    return header + vf + payload

def write_gloc(entries: List[GPSEntry]) -> bytes:
    """写入 gloc box"""
    payload = struct.pack('>I', len(entries))
    for e in entries:
        payload += e.encode()
    return write_fullbox('gloc', 0, 0, payload)

def write_gsyn(config: SyncConfig) -> bytes:
    """写入 gsyn box"""
    payload = struct.pack('>BiBfBBBB',
        config.sync_mode,
        config.sync_offset,
        config.interpolation,
        config.video_ratio,
        config.map_style,
        1 if config.show_trajectory else 0,
        1 if config.show_poi else 0,
        config.default_view,
    )
    return write_fullbox('gsyn', 0, 0, payload)

def write_gpoi(pois: List[POI]) -> bytes:
    """写入 gpoi box"""
    payload = struct.pack('>I', len(pois))
    for p in pois:
        payload += p.encode()
    return write_fullbox('gpoi', 0, 0, payload)

def write_ftyp(major_brand: str = 'mp5v', minor_version: int = 0,
               compatible_brands: List[str] = None) -> bytes:
    """写入 ftyp box"""
    if compatible_brands is None:
        compatible_brands = ['mp5v', 'mp41', 'isom']
    payload = major_brand.encode('ascii')[:4].ljust(4, b'\x00')
    payload += struct.pack('>I', minor_version)
    for brand in compatible_brands:
        payload += brand.encode('ascii')[:4].ljust(4, b'\x00')
    return write_box('ftyp', payload)

# ============================================================
# MP5 文件封装
# ============================================================

def _fix_stco_offsets(data: bytes, delta: int) -> bytes:
    """
    修正 moov 中 stco/co64 表的绝对偏移量
    当 mdat 在文件中的位置发生变化时，stco 中的偏移需要加上 delta

    @param data: 完整文件数据
    @param delta: 偏移修正量（正数表示mdat后移，负数表示前移）
    @return: 修正后的文件数据
    """
    if delta == 0:
        return data

    boxes = parse_boxes(data)
    moov = find_box(boxes, 'moov')
    if not moov:
        return data

    # 查找所有 stco 和 co64 box
    def find_stco_boxes(boxes, results):
        for box in boxes:
            if box.type in ('stco', 'co64'):
                results.append(box)
            if box.children:
                find_stco_boxes(box.children, results)

    stco_boxes = []
    find_stco_boxes(moov.children, stco_boxes)

    if not stco_boxes:
        return data

    # 在data的副本上修改
    data = bytearray(data)

    for stco in stco_boxes:
        # stco FullBox: 8-byte header + 4-byte version/flags + 4-byte entry_count + entries
        # stco entry: uint32 absolute offset
        # co64 entry: uint64 absolute offset

        payload_start = stco.offset + 12  # 8 header + 4 version/flags
        entry_count = struct.unpack_from('>I', data, payload_start)[0]

        if stco.type == 'stco':
            for i in range(entry_count):
                offset_pos = payload_start + 4 + i * 4
                old_val = struct.unpack_from('>I', data, offset_pos)[0]
                new_val = old_val + delta
                struct.pack_into('>I', data, offset_pos, new_val & 0xFFFFFFFF)
        elif stco.type == 'co64':
            for i in range(entry_count):
                offset_pos = payload_start + 4 + i * 8
                old_val = struct.unpack_from('>Q', data, offset_pos)[0]
                new_val = old_val + delta
                struct.pack_into('>Q', data, offset_pos, new_val)

    return bytes(data)


def mux_mp5(mp4_data: bytes, gps_entries: List[GPSEntry],
            sync_config: SyncConfig = None, pois: List[POI] = None) -> bytes:
    """
    将 MP4 数据 + GPS 数据封装为 MP5 文件

    策略:
    1. 写入 MP5 ftyp (major_brand = mp5v)
    2. 写入原始 moov box
    3. 写入 gloc/gpoi/gsyn box (MP5扩展)
    4. 写入 mdat box
    5. 修正 moov 中 stco 的偏移量（因为 mdat 位置后移了）
    """
    if sync_config is None:
        sync_config = SyncConfig()
    if pois is None:
        pois = []

    # 解析原始 MP4 box 结构
    boxes = parse_boxes(mp4_data)
    ftyp_box = find_box(boxes, 'ftyp')
    moov_box = find_box(boxes, 'moov')
    mdat_box = find_box(boxes, 'mdat')

    # 计算原始 mdat 的数据偏移
    orig_mdat_data_offset = mdat_box.data_offset if mdat_box else 0

    result = io.BytesIO()

    # 1. 写入 MP5 ftyp (major_brand = mp5v)
    result.write(write_ftyp('mp5v', 0, ['mp5v', 'mp41', 'isom']))

    # 2. 写入原始 moov box
    if moov_box:
        result.write(mp4_data[moov_box.offset:moov_box.offset + moov_box.size])

    # 3. 写入 gloc box (GPS轨迹)
    if gps_entries:
        result.write(write_gloc(gps_entries))

    # 4. 写入 gpoi box (POI标记)
    if pois:
        result.write(write_gpoi(pois))

    # 5. 写入 gsyn box (同步规则)
    result.write(write_gsyn(sync_config))

    # 6. 写入 mdat box (媒体数据)
    if mdat_box:
        result.write(mp4_data[mdat_box.offset:mdat_box.offset + mdat_box.size])
    else:
        result.write(mp4_data)

    mp5_data = result.getvalue()

    # 7. 修正 stco 偏移量
    # 计算新的 mdat 数据偏移
    new_boxes = parse_boxes(mp5_data)
    new_mdat = find_box(new_boxes, 'mdat')
    new_mdat_data_offset = new_mdat.data_offset if new_mdat else 0

    # delta = 新位置 - 旧位置
    delta = new_mdat_data_offset - orig_mdat_data_offset
    if delta != 0:
        mp5_data = _fix_stco_offsets(mp5_data, delta)

    return mp5_data

def strip_mp5_boxes(data: bytes) -> bytes:
    """
    去除 MP5 扩展 box (gloc/gsyn/gmap/gpoi)，返回纯 MP4 数据
    同时修正 stco 偏移量（mdat 位置前移）
    """
    boxes = parse_boxes(data)
    mp5_types = {'gloc', 'gmap', 'gsyn', 'gpoi'}

    # 收集需要移除的范围
    ranges = []
    for box in boxes:
        if box.type in mp5_types:
            ranges.append((box.offset, box.offset + box.size))

    if not ranges:
        return data

    # 计算原始 mdat 的数据偏移
    mdat = find_box(boxes, 'mdat')
    orig_mdat_offset = mdat.data_offset if mdat else 0

    # 计算移除的总大小
    total_removed = sum(end - start for start, end in ranges)

    # 构建新数据
    ranges.sort()
    result = io.BytesIO()
    prev_end = 0
    for start, end in ranges:
        result.write(data[prev_end:start])
        prev_end = end
    result.write(data[prev_end:])

    stripped_data = result.getvalue()

    # 修正 stco 偏移量（mdat 前移了 total_removed 字节）
    new_mdat = find_box(parse_boxes(stripped_data), 'mdat')
    new_mdat_offset = new_mdat.data_offset if new_mdat else 0
    delta = new_mdat_offset - orig_mdat_offset
    if delta != 0:
        stripped_data = _fix_stco_offsets(stripped_data, delta)

    return stripped_data

# ============================================================
# 示例 MP5 文件生成
# ============================================================

def create_sample_mp5(duration_sec: int = 60) -> bytes:
    """生成示例 MP5 文件（含模拟GPS轨迹，用于测试）"""
    import math

    gps_entries = []
    center_lat = 39.9912
    center_lon = 116.3974
    radius = 0.003

    for i in range(duration_sec):
        t = i
        angle = (t / duration_sec) * math.pi * 2
        r = radius * (1 + 0.1 * math.sin(t * 0.5))
        lat = center_lat + r * math.cos(angle)
        lon = center_lon + r * math.sin(angle)

        gps_entries.append(GPSEntry(
            timestamp=t * 1000,
            latitude=lat,
            longitude=lon,
            altitude=45 + 5 * math.sin(t * 0.3),
            accuracy=5,
            heading=((angle * 180 / math.pi) + 360) % 360,
            speed=15 + 5 * math.sin(t * 0.5),
        ))

    pois = [
        POI(5000, center_lat + radius, center_lon, '起点', 'poi'),
        POI(duration_sec * 500, center_lat - radius, center_lon, '对面', 'poi'),
    ]

    # 创建最小 MP4
    mp4 = io.BytesIO()
    # ftyp
    mp4.write(write_ftyp('isom', 0, ['isom', 'mp41']))
    # moov with mvhd
    mvhd_payload = struct.pack('>IIII', 0, 0, 1000, duration_sec * 1000)  # creation, modification, timescale, duration
    mvhd_payload += struct.pack('>I', 0x00010000)  # rate
    mvhd_payload += struct.pack('>H', 0x0100)  # volume
    mvhd_payload += b'\x00' * 10  # reserved
    mvhd_payload += b'\x00' * 24  # reserved (2 * uint64)
    # matrix (3x3 identity, 36 bytes)
    mvhd_payload += struct.pack('>9I', 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)
    mvhd_payload += b'\x00' * 24  # pre_defined (6 * uint32)
    mvhd_payload += struct.pack('>I', 2)  # next_track_ID
    mp4.write(write_fullbox('mvhd', 0, 0, mvhd_payload))
    # Wrap moov
    moov_data = mp4.getvalue()
    mp4 = io.BytesIO()
    mp4.write(write_ftyp('isom', 0, ['isom', 'mp41']))
    mp4.write(write_fullbox('mvhd', 0, 0, mvhd_payload))
    moov_payload = mp4.getvalue()[len(write_ftyp('isom', 0, ['isom', 'mp41'])):]
    mp4 = io.BytesIO()
    mp4.write(write_ftyp('isom', 0, ['isom', 'mp41']))
    mp4.write(write_box('moov', moov_payload))
    # mdat
    mp4.write(write_box('mdat', b'\x00' * 1024))

    return mux_mp5(mp4.getvalue(), gps_entries, SyncConfig(
        interpolation=1, default_view=2, show_trajectory=True, show_poi=True
    ), pois)