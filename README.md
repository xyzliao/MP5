# MP5 = MP4 + Map

MP5录播器 — 轻量级MP5录制与播放应用（Web版 + Windows版）

## 什么是MP5？

MP5是在MP4基础上扩展的视频容器格式，核心创新是在视频文件中嵌入GPS坐标轨迹，并支持视频与地图的双窗口联动播放。

- **录制**：按下录制键，视频+GPS一步到位，无需后期同步
- **播放**：打开MP5文件，视频和地图自动联动，点击地图跳转视频
- **分享**：一个文件包含视频+轨迹+地图，发给别人就能看
- **向后兼容**：不支持MP5的播放器可正常播放视频轨道

## MP5格式规范

MP5基于ISO BMFF (ISO 14496-12)，新增3个自定义Box：

| Box类型 | 说明 | 可选 |
|---------|------|------|
| `gloc` | GPS坐标轨迹 | 必需 |
| `gsyn` | 同步规则 | 必需 |
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

- 同步模式 (0=时间同步, 1=最近邻, 2=插值)
- 插值算法 (0=最近邻, 1=线性, 2=三次样条)
- 默认视图 (0-4: 仅视频/仅地图/分屏左右/分屏上下/画中画)
- 地图样式、轨迹线显示、POI显示等

## 功能

### 录制模式
- 视频采集 (MediaRecorder API)
- GPS同步采集 (Geolocation API)
- 方向传感器 (DeviceOrientation API)
- 暂停/续录（GPS轨迹保持连续）
- POI兴趣点标记
- 实时迷你地图预览

### 播放模式
- 视频+地图双窗口联动
- 5种视图模式：仅视频/仅地图/分屏(左右)/分屏(上下)/画中画
- 速度热力图（蓝→绿→黄→橙→红）
- 轨迹线显示（已播放部分高亮）
- 起点/终点标记
- POI标记显示
- 点击地图跳转视频

### 文件管理
- IndexedDB本地存储
- 导入/导出MP5文件
- 导出MP4（去除GPS数据）
- 导出GPX轨迹
- 导出GeoJSON
- Web Share API分享

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | 原生ES6 Modules | 无构建工具依赖 |
| 视频录制 | MediaRecorder API | 浏览器原生 |
| GPS采集 | Geolocation API | 浏览器原生 |
| 方向传感 | DeviceOrientation API | 浏览器原生 |
| 地图渲染 | Leaflet.js + OpenStreetMap | 轻量地图库 |
| 文件存储 | IndexedDB | 浏览器本地数据库 |
| 容器格式 | ISO BMFF (MP4) | 二进制读写 |

## 项目结构

```
MP5/
├── web/                    # Web应用
│   ├── index.html          # 主应用入口
│   ├── test.html           # 格式测试工具
│   ├── css/
│   │   └── style.css       # 全局样式
│   └── js/
│       ├── mp5-box.js      # MP5 Box编解码 (ISO BMFF)
│       ├── mp5-parser.js   # MP5文件解析器
│       ├── mp5-muxer.js    # MP5文件封装器
│       ├── sync-engine.js # 视频↔地图同步引擎
│       ├── recorder.js     # 录制模块
│       ├── player.js       # 播放模块
│       ├── file-manager.js # 文件管理模块
│       └── app.js          # 主应用入口
├── windows/                # Windows桌面版
│   ├── mp5_player.py       # 主程序入口 (tkinter GUI)
│   ├── mp5_box.py          # MP5 Box编解码引擎
│   ├── mp5_parser.py       # MP5文件解析器
│   ├── sync_engine.py     # 视频↔地图同步引擎
│   ├── exporters.py        # GPX/GeoJSON/KML导出
│   ├── __init__.py         # 包初始化
│   ├── build.bat           # Windows打包脚本
│   └── requirements.txt    # 依赖说明
├── test/
│   ├── mp5-format-test.js  # Web版格式单元测试
│   ├── mp5-integration-test.js # Web版集成测试
│   └── test_mp5_windows.py # Windows版单元测试
├── MP5录播器设计文档.pdf    # 产品设计文档
└── MP5格式设计规范.pdf      # 格式规范文档
```

## 快速开始

### 运行Web应用

由于使用了ES6 Modules，需要通过HTTP服务器运行（不能直接打开HTML文件）：

```bash
# 方式1: Python
cd web && python3 -m http.server 8080

# 方式2: Node.js
npx serve web

# 方式3: 任意静态文件服务器
```

然后访问 http://localhost:8080

### 运行Windows版

```bash
# 直接运行（需要 Python 3.8+ 和 tkinter）
cd windows
python mp5_player.py

# 打包为exe（需要 PyInstaller）
cd windows
build.bat
# 或手动: pyinstaller --onefile --windowed --name MP5Player mp5_player.py
# 生成的 exe 位于 dist/MP5Player.exe
```

Windows版功能：
- 打开MP5/MP4文件，自动解析GPS轨迹
- GPS轨迹地图显示（Canvas绘制，速度热力图）
- 视频↔地图双向联动（点击地图跳转视频）
- 4种视图模式（仅视频/仅地图/分屏/画中画）
- 导出GPX/GeoJSON/KML/MP4
- 生成示例MP5文件（用于测试）
- 轨迹统计（距离/速度/时长）

### 运行测试

```bash
node test/mp5-format-test.js
```

### 使用测试工具

访问 http://localhost:8080/test.html 可以：
1. 生成示例MP5文件（含模拟GPS轨迹）
2. 解析MP5/MP4文件
3. 查看GPS轨迹统计
4. 在地图上预览轨迹
5. 导出GPX/GeoJSON/MP4

## 设计文档

- [MP5格式设计规范](MP5格式设计规范.pdf) — 容器格式规范
- [MP5录播器设计文档](MP5录播器设计文档.pdf) — 产品设计文档

## 开发路线图

- [x] Phase 1: MP5 Engine核心（ISO BMFF解析、gloc/gsyn读写）
- [x] Phase 1: 录制功能（视频+GPS同步采集+MP5封装）
- [x] Phase 1: 播放功能（视频+在线地图联动+时间同步）
- [x] Phase 1: 导出MP4和GPX
- [x] Phase 1: 视图切换（分屏/全屏视频/全屏地图/画中画）
- [ ] Phase 2: 离线地图（gmap box）
- [ ] Phase 2: POI标记录制
- [ ] Phase 2: 速度热力图增强
- [ ] Phase 2: 电池优化+后台录制
- [ ] Phase 3: 社交分享平台
- [ ] Phase 3: 桌面端播放器

## 许可证

MIT