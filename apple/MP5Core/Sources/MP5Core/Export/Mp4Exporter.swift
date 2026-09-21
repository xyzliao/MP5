//
// Mp4Exporter.swift
// MP5Core
//
// MP4 导出器 — 从MP5文件中提取纯MP4数据（去除gloc/gsyn/gmap/gpoi box）
//
// 与 Windows版 strip_mp5_boxes() 对齐。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import Foundation

/// MP4 导出器
public enum Mp4Exporter {

    /// 从 MP5 文件数据中提取纯 MP4 数据
    /// 去除 gloc/gsyn/gmap/gpoi box，保留 ftyp/moov/mdat
    public static func extractMp4(from mp5Data: Data) -> Data {
        let boxes = Mp5BoxIO.parseBoxes(mp5Data)
        var result = Data()

        for box in boxes {
            switch box.type {
            case Mp5BoxType.GLOC, Mp5BoxType.GSYN, Mp5BoxType.GMAP, Mp5BoxType.GPOI:
                // 跳过 MP5 扩展 box
                continue

            case Mp5BoxType.FTYP:
                // 替换 ftyp：major_brand 改回 isom
                result.append(Mp5BoxIO.buildFtyp(majorBrand: "isom", compatibleBrands: ["isom", "mp41"]))

            default:
                // 保留其他 box（moov, mdat 等）
                result.append(mp5Data.subdata(in: box.offset..<(box.offset + box.size)))
            }
        }

        return result
    }

    /// 从 MP5 文件提取 MP4 并保存
    public static func extractMp4File(from mp5Url: URL, to mp4Url: URL) throws {
        let mp5Data = try Data(contentsOf: mp5Url)
        let mp4Data = extractMp4(from: mp5Data)
        try mp4Data.write(to: mp4Url)
    }
}