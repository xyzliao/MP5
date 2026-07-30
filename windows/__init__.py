"""
MP5录播器 — Windows版播放器
基于 tkinter 的桌面 GUI 应用

作者: 大米斗（Aniseedaliao）
"""

from .mp5_box import (
    GPSEntry, SyncConfig, POI, Box,
    parse_boxes, find_box, find_all_boxes,
    parse_gloc, parse_gsyn, parse_gpoi, parse_gmap,
    write_gloc, write_gsyn, write_gpoi, write_ftyp,
    write_box, write_fullbox,
    mux_mp5, strip_mp5_boxes, create_sample_mp5,
    GLOC_ENTRY_SIZE
)
from .mp5_parser import MP5Parser, MP5Info, TrackInfo
from .sync_engine import SyncEngine
from .exporters import export_gpx, export_geojson, export_kml

__version__ = '1.0.0'
__author__ = '大米斗（Aniseedaliao）'