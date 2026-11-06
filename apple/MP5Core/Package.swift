// swift-tools-version: 5.9
//
// MP5Core — 跨平台共享 Swift Package
// MP5格式核心逻辑：解析、封装、导出、同步引擎
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.21

import PackageDescription

let package = Package(
    name: "MP5Core",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "MP5Core", targets: ["MP5Core"]),
    ],
    targets: [
        .target(name: "MP5Core", path: "Sources/MP5Core"),
        .testTarget(name: "MP5CoreTests", dependencies: ["MP5Core"], path: "Tests/MP5CoreTests"),
    ]
)