# MP5录播器 — iOS/macOS版技术方案

**版本：** 1.0.20  
**日期：** 2026年8月10日  
**作者：** 大米斗（Aniseedaliao）

---

## 一、概述

MP5录播器 Apple 版覆盖 iPhone 和 macOS 两个平台，使用 SwiftUI 声明式 UI 框架，通过 Swift Package 共享核心逻辑，实现一套代码双平台运行。

### 1.1 设计目标

- 与 Windows 版、Android 版、Web 版功能对齐
- MP5 格式（gloc/gsyn/gpoi/gmap）跨平台完全兼容
- 录制：视频 + GPS 同步采集 → MP5 封装（仅 iOS）
- 播放：视频 + 地图双窗口联动，5种视图模式
- 导出：MP4（剥离GPS）/ GPX / GeoJSON / KML
- 原生体验：AVPlayer 视频播放、MapKit 地图渲染

### 1.2 平台差异

| 功能 | iOS (iPhone) | macOS |
|------|-------------|-------|
| 视频录制 | ✅ AVFoundation | ❌ 无摄像头（可播放） |
| GPS采集 | ✅ CoreLocation | ❌ 无GPS（可播放） |
| 视频播放 | ✅ AVPlayer | ✅ AVPlayer |
| 地图显示 | ✅ MapKit | ✅ MapKit |
| MP5解析/封装 | ✅ Swift | ✅ Swift |
| 导出 | ✅ | ✅ |
| 录制MP5 | ✅ | ❌ |
| 从MP4制作MP5 | ✅ 导入GPX | ✅ 导入GPX |

---

## 二、项目结构

```
MP5-Apple/
├── MP5Core/                    # 共享 Swift Package（跨平台核心）
│   ├── Sources/MP5Core/
│   │   ├── Format/
│   │   │   ├── Mp5Box.swift         # ISO BMFF Box 读写工具
│   │   │   ├── Mp5Parser.swift      # MP5 文件解析
│   │   │   ├── Mp5Muxer.swift       # MP5 文件封装
│   │   │   ├── GpsSample.swift      # GPS 采样点数据结构
│   │   │   ├── SyncRules.swift      # gsyn 同步规则
│   │   │   └── Poi.swift            # POI 标记数据结构
│   │   ├── Export/
│   │   │   ├── GpxExporter.swift    # GPX 导出
│   │   │   ├── GeoJsonExporter.swift # GeoJSON 导出
│   │   │   ├── KmlExporter.swift    # KML 导出
│   │   │   └── Mp4Exporter.swift    # MP4 导出（剥离GPS box）
│   │   └── Sync/
│   │       └── SyncEngine.swift     # 视频↔地图同步引擎
│   └── Package.swift
│
├── MP5iOS/                     # iOS App
│   ├── MP5iOSApp.swift            # App 入口
│   ├── Views/
│   │   ├── FileListView.swift     # 文件列表
│   │   ├── RecordView.swift       # 录制界面
│   │   ├── PlaybackView.swift     # 播放界面
│   │   ├── MapView.swift          # MapKit 地图封装
│   │   └── CreateMp5View.swift    # 从MP4制作MP5
│   ├── ViewModels/
│   │   ├── RecordViewModel.swift  # 录制逻辑
│   │   ├── PlaybackViewModel.swift # 播放逻辑
│   │   └── FileListViewModel.swift
│   ├── Services/
│   │   ├── GpsCollector.swift     # CoreLocation GPS采集
│   │   ├── VideoRecorder.swift    # AVFoundation 视频录制
│   │   └── Mp5Recorder.swift      # 录制协调器
│   └── Persistence/
│       └── Mp5Store.swift         # SwiftData 文件管理
│
├── MP5macOS/                   # macOS App
│   ├── MP5MacApp.swift           # App 入口
│   ├── Views/
│   │   ├── FileListView.swift     # 文件列表
│   │   ├── PlaybackView.swift     # 播放界面
│   │   ├── MapView.swift          # MapKit 地图封装
│   │   └── CreateMp5View.swift    # 从MP4制作MP5
│   └── ViewModels/
│       ├── PlaybackViewModel.swift
│       └── FileListViewModel.swift
│
└── MP5-Apple技术方案.md         # 本文档
```

---

## 三、技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| UI框架 | SwiftUI | iOS 16+ / macOS 13+ 最低版本 |
| 视频播放 | AVKit / AVPlayer | 原生播放器，替代 VLC/ExoPlayer |
| 视频录制 | AVFoundation | AVCaptureSession + AVCaptureMovieFileOutput |
| 地图 | MapKit + MapKitPro | MKMapView，替代 osmdroid/Leaflet |
| GPS | CoreLocation | CLLocationManager，替代 FusedLocationProvider |
| 方向 | CoreMotion | 陀螺仪+指南针 |
| 数据持久化 | SwiftData | iOS 17+ / macOS 14+，替代 Room |
| 文件管理 | FileManager + .documentDirectory | 替代 SAF |
| 云端同步 | CloudKit（可选） | iCloud 同步 |
| MP5格式 | Swift 自实现 | 与 Windows(Python)/Android(Kotlin) 格式一致 |
| 依赖管理 | Swift Package Manager | MP5Core 作为共享 Package |

---

## 四、MP5 格式实现（Swift）

### 4.1 Mp5Box.swift

与 Windows 版 `mp5_box.py` 和 Android 版 `Mp5Box.kt` 完全对齐。

```swift
// Box 类型常量
let FTYP = "ftyp"
let MOOV = "moov"
let MVHD = "mvhd"
let TRAK = "trak"
let MDAT = "mdat"
let META = "meta"
let HDLR = "hdlr"
let GLOC = "gloc"   // GPS坐标轨迹
let GMAP = "gmap"   // 嵌入地图数据
let GSYN = "gsyn"   // 同步规则
let GPOI = "gpoi"   // POI标记数据
let STCO = "stco"   // 32位 chunk offset
let CO64 = "co64"   // 64位 chunk offset

// Box 读写辅助
func buildBox(type: String, payload: [UInt8]) -> [UInt8]
func buildFullBox(type: String, version: Int, flags: Int, payload: [UInt8]) -> [UInt8]
func findBox(in data: [UInt8], type: String, startOffset: Int, endOffset: Int) -> (offset: Int, size: Int)?
func findBoxPath(in data: [UInt8], path: [String]) -> (offset: Int, size: Int)?
func readBoxPayload(in data: [UInt8], offset: Int, size: Int, isFullBox: Bool) -> [UInt8]
```

### 4.2 GpsSample.swift

```swift
struct GpsSample: Codable, Identifiable {
    let id = UUID()
    var timestampMs: Int64      // 毫秒，相对于mvhd时间起点
    var latitudeE7: Int64      // 纬度 ×10^7 (WGS84)
    var longitudeE7: Int64     // 经度 ×10^7 (WGS84)
    var altitudeDm: Int32      // 海拔 ×10 (分米)
    var accuracyM: UInt16      // 定位精度，米
    var headingDeg: UInt16     // 方向角 0-360°
    var speedKmhX10: UInt16    // 速度 km/h ×10
    var isPoi: Bool            // 是否为POI标记点
    var poiLabel: String?      // POI标签

    var latitude: Double { Double(latitudeE7) / 10_000_000 }
    var longitude: Double { Double(longitudeE7) / 10_000_000 }
    var altitudeM: Double { Double(altitudeDm) / 10 }
    var speedKmh: Double { Double(speedKmhX10) / 10 }

    static func fromDegrees(timestampMs: Int64, latitude: Double, longitude: Double,
                            altitudeM: Double, accuracyM: Int, headingDeg: Int,
                            speedKmh: Double) -> GpsSample
}
```

### 4.3 gsyn 字段顺序

与 Windows 版 `struct.pack('>BiBfBBBB', ...)` 完全一致：

```
sync_mode(1B) + sync_offset(4B) + interpolation(1B) + video_ratio(4B) +
map_style(1B) + show_trajectory(1B) + show_poi(1B) + default_view(1B)
= 14 bytes
```

### 4.4 gpoi Box 格式

与 Windows 版 `POI.encode()` 一致：

```
entry_count(4B)
for each poi:
  timestamp(8B) + latitudeE7(8B) + longitudeE7(8B) +
  label_length(2B) + label_bytes(UTF-8) + type(1B)
```

### 4.5 stco/co64 偏移修正

Mp5Muxer 在插入 meta box 后，需修正 moov 中所有 stco/co64 的绝对偏移量，逻辑与 Windows 版 `_fix_stco_offsets` 一致。

### 4.6 hdlr Box

使用 FullBox 格式（version + flags），payload 为：
```
pre_defined(4B=0) + handler_type(4B="mp5g") + reserved(12B=0) + name(1B=0)
```

---

## 五、录制功能（仅 iOS）

### 5.1 VideoRecorder

```swift
class VideoRecorder: NSObject, AVCaptureFileOutputRecordingDelegate {
    private let session = AVCaptureSession()
    private let movieOutput = AVCaptureMovieFileOutput()
    private var outputFileURL: URL?

    func configure()          // 初始化摄像头+麦克风
    func startRecording(to url: URL)  // 开始录制MP4
    func pauseRecording()     // 暂停
    func resumeRecording()    // 续录
    func stopRecording()      // 停止，输出MP4临时文件
}
```

### 5.2 GpsCollector

```swift
class GpsCollector: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var samples: [GpsSample] = []
    private var startTimeMs: Int64 = 0
    private var paused = false

    func start(sampleRateHz: Int, startTimeMs: Int64)
    func stop() -> [GpsSample]
    func pause()    // 暂停采样
    func resume()   // 恢复采样
    func addPoi(label: String?)

    // CLLocationManagerDelegate
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation])
}
```

暂停时 GPS 降频至 0.1Hz（每10秒一次），与设计文档 3.4 节一致。

### 5.3 Mp5Recorder（协调器）

```swift
class Mp5Recorder: ObservableObject {
    enum State { case idle, recording, paused, finalizing }

    @Published var state: State = .idle
    @Published var elapsedMs: Int64 = 0
    @Published var currentLocation: GpsSample?

    private let videoRecorder = VideoRecorder()
    private let gpsCollector = GpsCollector()
    private var pendingGpsSamples: [GpsSample] = []

    func start()
    func pause()   // 同时暂停视频和GPS
    func resume()  // 同时恢复视频和GPS
    func stop()    // 停止→触发finalize
    func addPoi(label: String?)

    private func finalizeMp5()  // MP5Muxer封装 + 数据库写入
}
```

### 5.4 前台录制

iOS 录制需保持 App 在前台。使用 `UIApplication.shared.beginBackgroundTask` 争取短暂后台时间。长时间后台录制需后台定位权限 + Audio 后台模式。

---

## 六、播放功能

### 6.1 PlaybackViewModel

```swift
@MainActor
class PlaybackViewModel: ObservableObject {
    @Published var currentPositionMs: Int64 = 0
    @Published var durationMs: Int64 = 0
    @Published var isPlaying = false
    @Published var currentGps: (Double, Double)?
    @Published var gpsSamples: [GpsSample] = []
    @Published var pois: [GpsSample] = []
    @Published var syncRules = SyncRules()
    @Published var isMp5 = false
    @Published var totalDistance: Double = 0
    @Published var maxSpeed: Double = 0
    @Published var viewMode: ViewMode = .splitLR

    private var player: AVPlayer?
    private var timeObserver: Any?
    private var parser: Mp5Parser?

    func loadFile(_ url: URL)
    func play()
    func pause()      // AVPlayer.pause() 保持位置，无需额外处理
    func seekTo(ms: Int64)
    func seekToGps(lat: Double, lon: Double)  // 地图→视频
    func release()
}
```

暂停/恢复：AVPlayer 的 `pause()` / `play()` 天然保持播放位置，不存在 Windows 版 VLC 那样的从头播放问题。

### 6.2 时间同步

使用 `AVPlayer.addPeriodicTimeObserver` 替代轮询线程：

```swift
timeObserver = player.addPeriodicTimeObserver(
    forInterval: CMTime(seconds: 0.05, preferredTimescale: 600),
    queue: .main
) { [weak self] time in
    self?.onTimeUpdated(time)
}
```

20fps 更新频率，与 Android 版 `delay(50)` 一致。

### 6.3 视图模式

```swift
enum ViewMode: Int, CaseIterable {
    case videoOnly = 0
    case mapOnly = 1
    case splitLR = 2      // 分屏左右
    case splitTB = 3      // 分屏上下
    case pip = 4         // 画中画
}
```

SwiftUI 实现：

```swift
@ViewBuilder
var content: some View {
    switch viewMode {
    case .videoOnly: VideoPlayerView()
    case .mapOnly: MapContainerView()
    case .splitLR: HSplitView { VideoPlayerView() } divider: { } and: { MapContainerView() }
    case .splitTB: VSplitView { VideoPlayerView() } divider: { } and: { MapContainerView() }
    case .pip: ZStack { VideoPlayerView(); MapContainerView().frame(width: 280, height: 210).alignment(.bottomTrailing) }
    }
}
```

---

## 七、地图组件

### 7.1 MapKit 封装

```swift
import MapKit

struct Mp5MapView: UIViewRepresentable {  // iOS
// macOS 版用 NSViewRepresentable
    let gpsSamples: [GpsSample]
    let currentGps: (Double, Double)?
    let onMapClick: (Double, Double) -> Void

    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.delegate = context.coordinator
        // 绑定点击手势
        let tap = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.onTap(_:)))
        mapView.addGestureRecognizer(tap)
        return mapView
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        // 更新轨迹线、当前位置标记、起点终点
    }
}
```

### 7.2 地图功能（与 Windows/Android 对齐）

- 完整轨迹线（MKPolyline）
- 已播放部分高亮（第二段 MKPolyline，白色）
- 速度热力图（分段绘制不同颜色线段）
- 当前位置脉冲标记（MKAnnotationView + 动画）
- 起点/终点标记（绿色/红色）
- POI 标记（📍 图标 + 标签）
- 点击地图跳转视频（MKMapView tap → onMapClick）
- 自动调整视野范围（MKMapRect）

### 7.3 速度热力图颜色映射

```swift
func speedColor(_ speedKmh: Double) -> Color {
    switch speedKmh {
    case ..<5:    return .blue
    case ..<20:   return .green
    case ..<60:   return .yellow
    case ..<120:  return .orange
    default:      return .red
    }
}
```

---

## 八、数据持久化

### 8.1 SwiftData Model

```swift
@Model
class Mp5FileRecord {
    var filePath: String
    var fileName: String
    var fileSize: Int64
    var durationMs: Int64
    var createdAt: Date
    var thumbnailPath: String?
    var startLat: Double
    var startLon: Double
    var endLat: Double
    var endLon: Double
    var totalDistanceKm: Double
    var maxSpeedKmh: Double
    var gpsPointCount: Int
    var hasMapData: Bool

    init(...) { ... }
}
```

对应 Android 版 `Mp5FileEntity`，字段完全一致。

---

## 九、导出功能

与 Windows/Android 版对齐：

| 格式 | 实现 | 说明 |
|------|------|------|
| MP4 | Mp4Exporter | 剥离 gloc/gsyn/gmap/gpoi box + 修正 stco |
| GPX | GpxExporter | GPX 1.1 格式，含 trkpt/ele/time/speed |
| GeoJSON | GeoJsonExporter | FeatureCollection + LineString |
| KML | KmlExporter | KML 格式，含 LineString + LookAt |

---

## 十、权限配置

### 10.1 iOS Info.plist

```xml
<key>NSCameraUsageDescription</key>
<string>录制视频需要使用摄像头</string>
<key>NSMicrophoneUsageDescription</key>
<string>录制视频需要使用麦克风</string>
<key>NSLocationWhenInUseUsageDescription</key>
<string>录制GPS轨迹需要定位权限</string>
<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>后台录制时需要持续定位</string>
<key>UIBackgroundModes</key>
<array>
    <string>location</string>
    <string>audio</string>
</array>
```

### 10.2 macOS Entitlements

```xml
<key>com.apple.security.files.user-selected.read-write</key>
<true/>
```

macOS 不需要摄像头/GPS权限（仅播放）。

---

## 十一、跨平台共享策略

### 11.1 MP5Core Package

核心格式解析/封装/导出逻辑封装为 Swift Package，iOS 和 macOS 共同依赖：

```
// Package.swift
let package = Package(
    name: "MP5Core",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "MP5Core", targets: ["MP5Core"]),
    ],
    targets: [
        .target(name: "MP5Core", path: "Sources/MP5Core"),
    ]
)
```

### 11.2 平台条件编译

```swift
#if os(iOS)
import UIKit
import AVFoundation
import CoreLocation
#elseif os(macOS)
import AppKit
import AVFoundation
#endif
```

### 11.3 共享 vs 平台独有

| 模块 | 共享 | iOS独有 | macOS独有 |
|------|------|---------|-----------|
| Mp5Box/Parser/Muxer | ✅ | | |
| GpsSample/SyncRules/Poi | ✅ | | |
| SyncEngine | ✅ | | |
| 导出器 | ✅ | | |
| 文件列表UI | 部分 | iOS样式 | macOS样式 |
| 播放界面 | 部分 | 触摸交互 | 鼠标交互 |
| 地图组件 | 部分 | UIViewRepresentable | NSViewRepresentable |
| 录制功能 | | ✅ | |
| GPS采集 | | ✅ | |
| 视频录制 | | ✅ | |

---

## 十二、与已有平台的对齐检查

| 检查项 | Windows | Android | Apple(本方案) |
|--------|---------|---------|--------------|
| gloc 34字节/条目 | ✅ | ✅ | ✅ |
| gsyn 14字节字段顺序 | ✅ BiBfBBBB | ✅ 对齐 | ✅ 对齐 |
| gpoi box | ✅ | ✅ | ✅ |
| gmap box | ✅ 定义 | ✅ 定义 | ✅ 定义 |
| hdlr FullBox | ✅ | ✅ | ✅ |
| stco/co64修正 | ✅ | ✅ | ✅ |
| ftyp mp5v | ✅ | ✅ | ✅ |
| 5种视图模式 | ✅ | ✅ | ✅ |
| 速度热力图 | ✅ | 待实现 | ✅ 规划 |
| POI标记 | ✅ | ✅ | ✅ |
| 暂停续录 | ✅ | ✅ | ✅ |
| 导出MP4/GPX/GeoJSON/KML | ✅ | ✅ | ✅ |
| 作者署名 | ✅ | ✅ | ✅ |
| 版本号 | 1.0.20 | 1.0.20 | 1.0.20 |

---

## 十三、开发路线图

### Phase 1：MP5Core + 播放（4周）

| 周 | 里程碑 | 交付物 |
|----|--------|--------|
| 1 | MP5Core格式层 | Mp5Box/Parser/Muxer/SyncEngine Swift实现 |
| 2 | 导出功能 | GPX/GeoJSON/KML/MP4 导出器 |
| 3 | 播放界面 | AVPlayer + MapKit 联动 + 5种视图 |
| 4 | macOS适配 | macOS播放器 + 文件管理 |

### Phase 2：录制（3周，仅iOS）

| 周 | 里程碑 | 交付物 |
|----|--------|--------|
| 5 | 视频录制 | AVFoundation VideoRecorder |
| 6 | GPS采集 + MP5封装 | GpsCollector + Mp5Recorder |
| 7 | 录制UI + 集成 | RecordView + 暂停续录 + POI |

### Phase 3：完善（3周）

| 周 | 里程碑 | 交付物 |
|----|--------|--------|
| 8 | 从MP4制作MP5 | 导入MP4+GPX → MP5 |
| 9 | 高级功能 | 速度热力图 + 离线地图(gmap) |
| 10 | 优化 | 性能优化 + CloudKit同步 |

总计约10周。

---

## 十四、关键注意事项

1. **AVPlayer 暂停**：AVPlayer.pause()/play() 天然保持位置，无需像 Windows VLC 那样特殊处理
2. **stco 修正必须实现**：CameraX/AVFoundation 生成的 MP4 可能是 moov-before-mdat 布局
3. **gsyn 字段顺序**：必须与 Windows 版 `>BiBfBBBB` 完全一致，否则跨平台数据错位
4. **gpoi box**：必须实现，否则 POI 标记在跨平台时丢失
5. **hdlr FullBox**：必须用 FullBox 格式，否则严格解析器会拒绝
6. **作者署名**：所有 Swift 文件 KDoc 注释包含 `@author 大米斗（Aniseedaliao）`
7. **版本号**：1.0.20，与 Windows/Android 一致

---

---

## 十五、macOS版实现说明

### 15.1 已实现的 macOS App

MP5macOS 目录包含完整的 macOS 原生应用，使用 SwiftUI + MapKit + AVPlayer。

**项目结构：**

```
MP5macOS/
├── Package.swift               # SPM 配置（依赖 MP5Core）
├── MP5MacApp.swift             # App 入口 + NavigationSplitView 主窗口
├── Info.plist                  # macOS 配置（MP5/MP4 文件类型注册）
├── MP5macOS.entitlements       # 沙盒权限（用户文件读写）
├── Views/
│   ├── FileListView.swift      # 侧边栏文件列表（macOS 样式）
│   ├── PlaybackView.swift      # 播放界面（HSplitView/VSplitView 分屏）
│   ├── Mp5MapView.swift        # MapKit 地图（NSViewRepresentable）
│   └── CreateMp5View.swift     # 从MP4制作MP5（NSOpenPanel 文件选择）
├── ViewModels/
│   ├── PlaybackViewModel.swift # 播放逻辑（与 iOS 一致 + 导出功能）
│   └── FileListViewModel.swift # 文件列表逻辑 + 目录扫描
└── Persistence/
    └── Mp5Store.swift          # SwiftData 文件管理（Application Support 目录）
```

### 15.2 与 iOS 版的关键差异

| 差异项 | iOS | macOS |
|--------|-----|-------|
| 地图封装 | UIViewRepresentable | NSViewRepresentable |
| 点击手势 | UITapGestureRecognizer | NSClickGestureRecognizer |
| 颜色类型 | UIColor | NSColor |
| 图标加载 | UIImage(systemName:) | NSImage(systemSymbolName:) |
| 文件选择 | UIDocumentPickerViewController | NSOpenPanel |
| 文件保存 | 无（自动保存到 Documents） | NSSavePanel |
| 文件存储 | Documents/mp5/ | Application Support/MP5录播器/mp5/ |
| 导航方式 | TabView + sheet | NavigationSplitView（侧边栏） |
| 分屏方式 | HStack/VStack（固定比例） | HSplitView/VSplitView（可拖拽） |
| 录制功能 | ✅ 有 | ❌ 无 |
| 键盘快捷键 | 无 | 空格=播放/暂停，←→=快退/快进 |
| 导出UI | 无 | NSSavePanel + Menu |
| 画中画尺寸 | 160×120 | 320×240（大屏适配） |

### 15.3 macOS 独有功能

1. **可拖拽分屏**：使用 HSplitView / VSplitView，用户可拖拽分隔条调整视频和地图的比例
2. **目录扫描**：启动时自动扫描 mp5 目录，将未入库的文件加入数据库
3. **Finder 集成**：右键菜单支持「在 Finder 中显示」
4. **键盘快捷键**：空格键暂停/播放，左右箭头快退/快进10秒
5. **导出功能**：播放界面内置导出菜单，支持 GPX / GeoJSON / KML / MP4 导出
6. **菜单栏集成**：菜单栏「文件 → 从MP4制作MP5」快捷入口（Cmd+N）

### 15.4 共享代码

- **MP5Core**：100% 共享（Mp5Box/Mp5Parser/Mp5Muxer/SyncEngine/GpsSample/SyncRules/Poi/导出器）
- **ViewModels**：逻辑基本一致，macOS 版增加了导出方法和目录扫描
- **Mp5Store**：字段完全一致，仅存储目录不同
- **GpxParser**：CreateMp5View 中的 GPX 解析器完全复用

### 15.5 编译方式

**Swift Package Manager：**
```bash
cd MP5Core && swift build
cd MP5macOS && swift build
```

**Xcode：**
在 Xcode 中打开 MP5macOS/Package.swift，选择 macOS 目标编译运行。

---

*大米斗（Aniseedaliao），写于2026年8月10日*
*macOS版补充：2026年8月13日*