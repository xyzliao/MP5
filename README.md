# MP5 = MP4 + Map

MP5录播器 — 轻量级MP5录制与播放应用，支持 Web / Windows / Android / iOS / macOS 五大平台

## 什么是MP5？

MP5是在MP4基础上扩展的视频容器格式，核心创新是在视频文件中嵌入GPS坐标轨迹，并支持视频与地图的双窗口联动播放。

- **录制**：按下录制键，视频+GPS一步到位，无需后期同步
- **播放**：打开MP5文件，视频和地图自动联动，点击地图跳转视频
- **分享**：一个文件包含视频+轨迹+地图，发给别人就能看
- **向后兼容**：不支持MP5的播放器可正常播放视频轨道

## MP5格式规范

MP5基于ISO BMFF (ISO 14496-12)，新增4个自定义Box：

| Box类型 | 说明 | 可选 |
|---------|------|------|
| `gloc` | GPS坐标轨迹 | 必需 |
| `gsyn` | 同步规则 | 必需 |
| `gpoi` | POI标记数据 | 可选 |
| `gmap` | 嵌入地图数据 | 可选 |

### gloc Box (GPS坐标轨迹)

每个采样点34字节：
- `timestamp` (8B) - 毫秒时间戳
- `latitude` (8B) - 纬度 ×10^7 (WGS84)
- `longitude` (8B) - 经度 ×10^7
- `altitude` (4B) - 海拔 ×10 (精确到0.1米)
- `accuracy` (2B) - 定位精度(米)
- `heading` (2B) - 方向角 ×10
- `speed` (2B) - 速度 ×10 (km/h)

### gsyn Box (同步规则)

14字节，字段顺序与 `struct.pack('>BiBfBBBB', ...)` 一致：
- 同步模式 (1B: 0=时间同步, 1=最近邻, 2=插值)
- 同步偏移 (4B: 毫秒)
- 插值算法 (1B: 0=最近邻, 1=线性, 2=三次样条)
- 视频占比 (4B: float, 分屏视频比例)
- 地图样式 (1B: 0=标准/1=卫星/2=地形/3=暗色)
- 显示轨迹 (1B: 0/1)
- 显示POI (1B: 0/1)
- 默认视图 (1B: 0-4)

### gpoi Box (POI标记)

每个POI条目变长：
- `timestamp` (8B) - 时间戳
- `latitude` (8B) - 纬度 ×10^7
- `longitude` (8B) - 经度 ×10^7
- `label_length` (2B) - 标签长度
- `label` (N B) - UTF-8 标签
- `type` (1B) - POI类型

## 平台支持

| 平台 | 录制 | 播放 | 制作MP5 | 导出 | 地图引擎 | 视频引擎 |
|------|------|------|---------|------|---------|---------|
| Web | ✅ | ✅ | — | GPX/GeoJSON/MP4 | Leaflet | MediaRecorder |
| Windows | — | ✅ | ✅ | GPX/GeoJSON/KML/MP4 | tkinter Canvas | python-vlc |
| Android | ✅ | ✅ | — | GPX/GeoJSON/KML/MP4 | osmdroid | ExoPlayer |
| iOS | ✅ | ✅ | ✅ | GPX/GeoJSON/KML/MP4 | MapKit | AVPlayer |
| macOS | — | ✅ | ✅ | GPX/GeoJSON/KML/MP4 | MapKit | AVPlayer |

### 功能详情

**录制模式** (Web / Android / iOS)
- 视频采集 + GPS同步采集
- 暂停/续录（GPS轨迹保持连续）
- POI兴趣点标记
- 实时迷你地图预览

**播放模式** (全平台)
- 视频+地图双窗口联动
- 5种视图模式：仅视频 / 仅地图 / 分屏左右 / 分屏上下 / 画中画
- 速度热力图（蓝→绿→黄→橙→红）
- 轨迹线显示（已播放部分高亮）
- 起点/终点标记
- POI标记显示
- 点击地图跳转视频

**从MP4制作MP5** (Windows / iOS / macOS)
- 选择MP4视频 + 导入GPX轨迹 → 封装为MP5
- 或生成模拟GPS轨迹

**导出** (全平台)
- GPX 1.1 标准格式
- GeoJSON FeatureCollection
- KML (Google Earth)
- MP4 (剥离GPS box)

## 项目结构

```
MP5/
├── web/                        # Web版 (原生ES6 Modules + Leaflet)
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── mp5-box.js          # MP5 Box编解码
│       ├── mp5-parser.js       # MP5文件解析器
│       ├── mp5-muxer.js        # MP5文件封装器
│       ├── sync-engine.js      # 视频↔地图同步引擎
│       ├── recorder.js         # 录制模块
│       ├── player.js           # 播放模块
│       └── file-manager.js     # 文件管理
│
├── windows/                    # Windows/Linux版 (Python + tkinter + VLC)
│   ├── mp5_player.py           # 主程序 (GUI + 播放器)
│   ├── mp5_box.py              # MP5 Box编解码引擎
│   ├── mp5_parser.py           # MP5文件解析器
│   ├── sync_engine.py          # 同步引擎
│   ├── exporters.py            # GPX/GeoJSON/KML导出
│   ├── gpx_importer.py         # GPX导入
│   ├── track_generator.py      # 模拟轨迹生成
│   ├── build.bat               # Windows打包脚本
│   ├── build.py                # 跨平台打包脚本
│   └── requirements.txt
│
├── android/                    # Android版 (Kotlin + Jetpack Compose)
│   └── app/src/main/java/com/daliao/mp5/
│       ├── format/             # Mp5Box/Parser/Muxer/GpsSample
│       ├── recording/          # GpsCollector/Mp5Recorder
│       ├── playback/           # Mp5PlayerController
│       ├── data/               # Room数据库/导出
│       └── ui/                 # Compose界面
│
├── apple/                      # Apple版 (Swift + SwiftUI)
│   ├── MP5Core/                # 跨平台共享 Swift Package
│   │   └── Sources/MP5Core/
│   │       ├── Format/          # Mp5Box/Parser/Muxer/GpsSample/SyncRules/Poi
│   │       ├── Export/          # GPX/GeoJSON/KML/MP4导出
│   │       └── Sync/            # SyncEngine
│   ├── MP5iOS/                 # iOS App (录制+播放+制作)
│   ├── MP5macOS/               # macOS App (播放+制作)
│   ├── MP5iOS.xcodeproj/
│   └── MP5-Apple技术方案.md
│
├── samples/                    # 示例MP5文件
├── test/                       # 测试
├── generate_samples.py         # 示例文件生成脚本
├── MP5格式设计规范.pdf          # 容器格式规范
└── MP5录播器设计文档.pdf        # 产品设计文档
```

## 快速开始

### Web版

```bash
cd web && python3 -m http.server 8080
# 访问 http://localhost:8080
```

无需安装，浏览器直接运行。支持录制（需 HTTPS 或 localhost 获取 GPS/摄像头权限）。

### Windows / Linux版

```bash
# 直接运行（需要 Python 3.8+ 和 tkinter）
cd windows
python mp5_player.py

# 可选：内嵌视频播放（推荐）
pip install python-vlc
# 需同时安装 VLC 播放器: https://www.videolan.org/

# 打包为可执行文件
cd windows
build.bat          # Windows
python build.py    # 任意平台
```

### Android版

```bash
cd android
./gradlew assembleDebug
# 生成 APK: app/build/outputs/apk/debug/app-debug.apk
```

需要 Android Studio 或 Android SDK，最低 Android 8.0 (API 26)。

### iOS / macOS版

```bash
# 编译共享包
cd apple/MP5Core && swift build

# iOS App: 用 Xcode 打开 apple/MP5iOS.xcodeproj
# macOS App: 用 Xcode 打开 apple/MP5macOS/Package.swift
# 或命令行编译:
cd apple/MP5macOS && swift build
```

需要 macOS + Xcode 15+，Swift 5.9+。iOS 最低 16.0，macOS 最低 13.0。

### 运行测试

```bash
# Web版格式测试
node test/mp5-format-test.js

# Apple版核心测试
cd apple/MP5Core && swift test
```

## 跨平台兼容性

MP5格式的二进制布局在所有平台完全一致：

| 检查项 | Web | Windows | Android | iOS | macOS |
|--------|-----|---------|---------|-----|-------|
| gloc 34字节/条目 | ✅ | ✅ | ✅ | ✅ | ✅ |
| gsyn 14字节字段顺序 | ✅ | ✅ | ✅ | ✅ | ✅ |
| gpoi box | ✅ | ✅ | ✅ | ✅ | ✅ |
| gmap box | ✅ | ✅ | ✅ | ✅ | ✅ |
| ftyp mp5v | ✅ | ✅ | ✅ | ✅ | ✅ |
| stco/co64修正 | ✅ | ✅ | ✅ | ✅ | ✅ |
| hdlr FullBox | ✅ | ✅ | ✅ | ✅ | ✅ |

在一个平台录制的MP5文件，可以在任意其他平台正常播放。

## 技术栈

| 平台 | 语言 | UI框架 | 视频引擎 | 地图引擎 | 数据存储 |
|------|------|--------|---------|---------|---------|
| Web | JavaScript | 原生ES6 | MediaRecorder | Leaflet.js | IndexedDB |
| Windows | Python | tkinter | python-vlc | Canvas | 文件系统 |
| Android | Kotlin | Jetpack Compose | ExoPlayer | osmdroid | Room |
| iOS | Swift | SwiftUI | AVPlayer | MapKit | SwiftData |
| macOS | Swift | SwiftUI | AVPlayer | MapKit | SwiftData |

## 设计文档

- [MP5格式设计规范](MP5格式设计规范.pdf) — 容器格式规范
- [MP5录播器设计文档](MP5录播器设计文档.pdf) — 产品设计文档
- [Apple版技术方案](apple/MP5-Apple技术方案.md) — iOS/macOS 技术方案

## 开发路线图

- [x] Phase 1: MP5 Engine核心（ISO BMFF解析、gloc/gsyn/gpoi读写）
- [x] Phase 1: Web版录制+播放
- [x] Phase 1: Windows版播放器
- [x] Phase 1: 导出MP4/GPX/GeoJSON/KML
- [x] Phase 1: Android版录制+播放
- [x] Phase 1: iOS版录制+播放
- [x] Phase 1: macOS版播放器
- [x] Phase 1: 从MP4制作MP5（导入GPX）
- [x] Phase 1: 速度热力图
- [x] Phase 1: POI标记
- [ ] Phase 2: 离线地图（gmap box）
- [ ] Phase 2: 云端同步
- [ ] Phase 3: 社交分享平台

## 作者

大米斗（Aniseedaliao）

## 许可证

MIT