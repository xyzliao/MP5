"""
MP5 文件解析器
解析 MP5 文件，提取视频轨道、GPS轨迹、同步规则等元数据

作者: 大米斗（Aniseedaliao）
"""

from mp5_box import (
    parse_boxes, find_box, find_all_boxes,
    parse_gloc, parse_gsyn, parse_gpoi, parse_gmap,
    GPSEntry, SyncConfig, POI, Box, strip_mp5_boxes
)
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import struct


@dataclass
class TrackInfo:
    """轨道信息"""
    track_id: int = 0
    track_type: str = 'unknown'  # video / audio / metadata
    duration: int = 0
    timescale: int = 0
    width: int = 0
    height: int = 0


@dataclass
class MP5Info:
    """MP5文件解析结果"""
    is_mp5: bool = False
    major_brand: str = ''
    compatible_brands: List[str] = None
    duration_ms: float = 0
    timescale: int = 0
    tracks: List[TrackInfo] = None
    gps_entries: List[GPSEntry] = None
    sync_config: Optional[SyncConfig] = None
    pois: List[POI] = None
    map_data: Optional[Dict[str, Any]] = None
    file_size: int = 0
    box_tree: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.compatible_brands is None:
            self.compatible_brands = []
        if self.tracks is None:
            self.tracks = []
        if self.gps_entries is None:
            self.gps_entries = []
        if self.pois is None:
            self.pois = []
        if self.box_tree is None:
            self.box_tree = []


class MP5Parser:
    """MP5文件解析器"""

    @staticmethod
    def parse(data: bytes) -> MP5Info:
        """解析 MP5 文件，返回 MP5Info"""
        info = MP5Info(file_size=len(data))
        boxes = parse_boxes(data)

        # 解析 ftyp
        ftyp = find_box(boxes, 'ftyp')
        if ftyp:
            ftyp_data = data[ftyp.data_offset:ftyp.data_offset + ftyp.data_size]
            if len(ftyp_data) >= 8:
                info.major_brand = ftyp_data[0:4].decode('ascii', errors='replace')
                if info.major_brand == 'mp5v':
                    info.is_mp5 = True
                # compatible_brands
                offset = 8  # skip major_brand(4) + minor_version(4)
                while offset + 4 <= len(ftyp_data):
                    brand = ftyp_data[offset:offset+4].decode('ascii', errors='replace')
                    info.compatible_brands.append(brand)
                    if brand == 'mp5v':
                        info.is_mp5 = True
                    offset += 4

        # 解析 moov
        moov = find_box(boxes, 'moov')
        if moov:
            # mvhd
            mvhd = find_box(moov.children, 'mvhd')
            if mvhd and mvhd.data_size >= 4:
                # mvhd is a FullBox: buffer has 8-byte header + 4-byte version/flags, then payload
                mvhd_data = mvhd.buffer[12:]  # skip header(8) + version+flags(4)
                version = mvhd.version or 0
                if version == 1 and len(mvhd_data) >= 28:
                    info.timescale = struct.unpack_from('>I', mvhd_data, 8)[0]
                    duration = struct.unpack_from('>Q', mvhd_data, 12)[0]
                elif len(mvhd_data) >= 20:
                    info.timescale = struct.unpack_from('>I', mvhd_data, 8)[0]
                    duration = struct.unpack_from('>I', mvhd_data, 12)[0]
                else:
                    duration = 0
                if info.timescale > 0:
                    info.duration_ms = duration / info.timescale * 1000

            # traks
            for trak in find_all_boxes(moov.children, 'trak'):
                track = MP5Parser._parse_trak(data, trak)
                if track:
                    info.tracks.append(track)

        # 解析 gloc (GPS轨迹)
        gloc = find_box(boxes, 'gloc')
        if gloc:
            info.gps_entries = parse_gloc(gloc)

        # 解析 gsyn (同步规则)
        gsyn = find_box(boxes, 'gsyn')
        if gsyn:
            info.sync_config = parse_gsyn(gsyn)

        # 解析 gpoi (POI标记)
        gpoi = find_box(boxes, 'gpoi')
        if gpoi:
            info.pois = parse_gpoi(gpoi)

        # 解析 gmap (嵌入地图)
        gmap = find_box(boxes, 'gmap')
        if gmap:
            info.map_data = parse_gmap(gmap)

        # 构建 box 树结构
        info.box_tree = MP5Parser._build_box_tree(boxes)

        return info

    @staticmethod
    def _parse_trak(data: bytes, trak: Box) -> Optional[TrackInfo]:
        """解析单个 trak box"""
        tkhd = find_box(trak.children, 'tkhd')
        mdia = find_box(trak.children, 'mdia')
        if not tkhd or not mdia:
            return None

        track = TrackInfo()
        version = tkhd.version or 0

        # tkhd 数据 (FullBox: skip 8 header + 4 version/flags in buffer)
        tkhd_data = tkhd.buffer[12:]
        version = tkhd.version or 0

        if version == 1 and len(tkhd_data) >= 32:
            track.track_id = struct.unpack_from('>I', tkhd_data, 8)[0]
            track.duration = struct.unpack_from('>Q', tkhd_data, 16)[0]
        elif len(tkhd_data) >= 20:
            track.track_id = struct.unpack_from('>I', tkhd_data, 8)[0]
            track.duration = struct.unpack_from('>I', tkhd_data, 12)[0]

        # mdhd (timescale)
        mdhd = find_box(mdia.children, 'mdhd')
        if mdhd and mdhd.data_size >= 4:
            mdhd_data = mdhd.buffer[12:]  # FullBox: skip header(8) + version+flags(4)
            v = mdhd.version or 0
            if v == 1 and len(mdhd_data) >= 28:
                track.timescale = struct.unpack_from('>I', mdhd_data, 8)[0]
            elif len(mdhd_data) >= 20:
                track.timescale = struct.unpack_from('>I', mdhd_data, 8)[0]

        # hdlr (track type)
        hdlr = find_box(mdia.children, 'hdlr')
        if hdlr and hdlr.data_size >= 12:
            hdlr_data = hdlr.buffer[12:]  # FullBox: skip header(8) + version+flags(4)
            if len(hdlr_data) >= 8:
                handler_type = hdlr_data[4:8].decode('ascii', errors='replace')
                track.track_type = {
                    'vide': 'video',
                    'soun': 'audio',
                    'meta': 'metadata',
                }.get(handler_type, handler_type)

        # video track: width/height from tkhd
        if track.track_type == 'video':
            if version == 0 and len(tkhd_data) >= 88:
                track.width = struct.unpack_from('>I', tkhd_data, 84)[0] >> 16
                track.height = struct.unpack_from('>I', tkhd_data, 88)[0] >> 16
            elif version == 1 and len(tkhd_data) >= 104:
                track.width = struct.unpack_from('>I', tkhd_data, 100)[0] >> 16
                track.height = struct.unpack_from('>I', tkhd_data, 104)[0] >> 16

        return track

    @staticmethod
    def _build_box_tree(boxes: List[Box], depth: int = 0) -> List[Dict[str, Any]]:
        """构建 box 树结构（用于UI显示）"""
        tree = []
        for box in boxes:
            node = {
                'type': box.type,
                'size': box.size,
                'offset': box.offset,
                'depth': depth,
                'version': box.version,
                'children': MP5Parser._build_box_tree(box.children, depth + 1) if box.children else []
            }
            tree.append(node)
        return tree

    @staticmethod
    def get_mp4_data(data: bytes) -> bytes:
        """从 MP5 文件中提取纯 MP4 数据（去除 gloc/gsyn/gmap/gpoi box）"""
        return strip_mp5_boxes(data)