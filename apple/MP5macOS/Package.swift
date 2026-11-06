// swift-tools-version: 5.9
//
// MP5macOS — macOS App Package
//
// MP5录播器 macOS版 — 播放 + 从MP4制作MP5
// 不含录制功能（无摄像头/GPS），但支持完整的播放和制作体验。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.21

import PackageDescription

let package = Package(
    name: "MP5macOS",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "MP5macOS", targets: ["MP5macOS"]),
    ],
    dependencies: [
        .package(path: "../MP5Core"),
    ],
    targets: [
        .target(
            name: "MP5macOS",
            dependencies: ["MP5Core"],
            path: ".",
            exclude: ["Info.plist", "MP5macOS.entitlements"]
        ),
    ]
)