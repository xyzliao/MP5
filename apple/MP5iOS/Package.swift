// swift-tools-version: 5.9
//
// MP5iOS — iOS App Package
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.10

import PackageDescription

let package = Package(
    name: "MP5iOS",
    platforms: [.iOS(.v16)],
    products: [
        .library(name: "MP5iOS", targets: ["MP5iOS"]),
    ],
    dependencies: [
        .package(path: "../MP5Core"),
    ],
    targets: [
        .target(
            name: "MP5iOS",
            dependencies: ["MP5Core"],
            path: ".",
            exclude: ["Info.plist"],
            resources: [
                .process("Resources"),
            ]
        ),
    ]
)