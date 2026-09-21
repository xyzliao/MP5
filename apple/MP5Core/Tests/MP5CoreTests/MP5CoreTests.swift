//
// MP5CoreTests.swift
// MP5CoreTests
//
// MP5格式核心测试 — 验证二进制格式与Windows/Android版本兼容
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import XCTest
@testable import MP5Core

final class MP5CoreTests: XCTestCase {

    // MARK: - GpsSample 编解码测试

    func testGpsSampleEncodeDecode() {
        let sample = GpsSample(
            timestampMs: 1000,
            latitudeE7: 399_042_000,   // 39.9042°
            longitudeE7: 116_407_400,  // 116.4074°
            altitudeDm: 432,            // 43.2m
            accuracyM: 5,
            headingDeg: 1800,           // 180.0°
            speedKmhX10: 360            // 36.0 km/h
        )

        let encoded = sample.encode()
        XCTAssertEqual(encoded.count, 34, "GPS采样点编码应为34字节")

        let decoded = GpsSample.decode(data: encoded, offset: 0)
        XCTAssertNotNil(decoded)
        XCTAssertEqual(decoded?.timestampMs, 1000)
        XCTAssertEqual(decoded?.latitudeE7, 399_042_000)
        XCTAssertEqual(decoded?.longitudeE7, 116_407_400)
        XCTAssertEqual(decoded?.altitudeDm, 432)
        XCTAssertEqual(decoded?.accuracyM, 5)
        XCTAssertEqual(decoded?.headingDeg, 1800)
        XCTAssertEqual(decoded?.speedKmhX10, 360)
    }

    func testGpsSampleFromDegrees() {
        let sample = GpsSample.fromDegrees(
            timestampMs: 0,
            latitude: 39.9042,
            longitude: 116.4074,
            altitudeM: 43.2,
            accuracyM: 5,
            headingDeg: 180,
            speedKmh: 36.0
        )
        XCTAssertEqual(sample.latitude, 39.9042, accuracy: 0.0001)
        XCTAssertEqual(sample.longitude, 116.4074, accuracy: 0.0001)
        XCTAssertEqual(sample.altitudeM, 43.2, accuracy: 0.1)
        XCTAssertEqual(sample.speedKmh, 36.0, accuracy: 0.1)
    }

    // MARK: - SyncRules 编解码测试

    func testSyncRulesEncodeDecode() {
        let rules = SyncRules(
            syncMode: 0,
            syncOffsetMs: 100,
            interpolation: 1,
            defaultView: 2,
            videoRatio: 0.5,
            mapStyle: 0,
            showTrajectory: true,
            showPoi: true
        )

        let encoded = rules.encode()
        XCTAssertEqual(encoded.count, 14, "gsyn payload应为14字节")

        let decoded = SyncRules.decode(data: encoded, offset: 0)
        XCTAssertNotNil(decoded)
        XCTAssertEqual(decoded?.syncMode, 0)
        XCTAssertEqual(decoded?.syncOffsetMs, 100)
        XCTAssertEqual(decoded?.interpolation, 1)
        XCTAssertEqual(decoded?.defaultView, 2)
        XCTAssertEqual(decoded?.videoRatio, 0.5, accuracy: 0.01)
        XCTAssertEqual(decoded?.mapStyle, 0)
        XCTAssertEqual(decoded?.showTrajectory, true)
        XCTAssertEqual(decoded?.showPoi, true)
    }

    // MARK: - Poi 编解码测试

    func testPoiEncodeDecode() {
        let poi = Poi(
            timestampMs: 5000,
            latitude: 39.9042,
            longitude: 116.4074,
            label: "测试POI",
            type: "poi"
        )

        let encoded = poi.encode()
        XCTAssertGreaterThan(encoded.count, 27)

        let result = Poi.decode(data: encoded, offset: 0)
        XCTAssertNotNil(result)
        XCTAssertEqual(result?.0.timestampMs, 5000)
        XCTAssertEqual(result?.0.latitude, 39.9042, accuracy: 0.0001)
        XCTAssertEqual(result?.0.longitude, 116.4074, accuracy: 0.0001)
        XCTAssertEqual(result?.0.label, "测试POI")
    }

    // MARK: - Box 读写测试

    func testBuildBox() {
        let payload = Data([0x01, 0x02, 0x03, 0x04])
        let box = Mp5BoxIO.buildBox(type: "test", payload: payload)
        XCTAssertEqual(box.count, 12)  // 8 header + 4 payload
        XCTAssertEqual(box.readUInt32BE(at: 0), 12)  // size
        XCTAssertEqual(box.readStringASCII(at: 4, length: 4), "test")
    }

    func testBuildFullBox() {
        let payload = Data([0x01, 0x02])
        let box = Mp5BoxIO.buildFullBox(type: "gloc", version: 0, flags: 0, payload: payload)
        XCTAssertEqual(box.count, 14)  // 8 header + 4 version/flags + 2 payload
        XCTAssertEqual(box.readUInt32BE(at: 0), 14)  // size
        XCTAssertEqual(box.readStringASCII(at: 4, length: 4), "gloc")
    }

    func testBuildFtyp() {
        let ftyp = Mp5BoxIO.buildFtyp()
        XCTAssertEqual(ftyp.readStringASCII(at: 8, length: 4), "mp5v")  // major_brand
    }

    // MARK: - Muxer 测试

    func testMuxEmptyMp4() {
        // 构建一个最小的MP4 (ftyp + free)
        var mp4Data = Data()
        mp4Data.append(Mp5BoxIO.buildFtyp(majorBrand: "isom", compatibleBrands: ["isom", "mp41"]))

        let samples = [
            GpsSample.fromDegrees(
                timestampMs: 0, latitude: 39.9042, longitude: 116.4074,
                altitudeM: 50, accuracyM: 5, headingDeg: 0, speedKmh: 10
            )
        ]

        let muxer = Mp5Muxer()
        let mp5Data = muxer.mux(mp4Data: mp4Data, gpsSamples: samples, syncRules: SyncRules())

        // 验证MP5文件包含ftyp(major_brand=mp5v)和gloc
        let boxes = Mp5BoxIO.parseBoxes(mp5Data)
        let ftyp = Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.FTYP)
        XCTAssertNotNil(ftyp)
        let ftypData = mp5Data.subdata(in: ftyp!.dataOffset..<(ftyp!.dataOffset + ftyp!.dataSize))
        XCTAssertEqual(ftypData.readStringASCII(at: 0, length: 4), "mp5v")

        let gloc = Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.GLOC)
        XCTAssertNotNil(gloc, "MP5文件应包含gloc box")

        let gsyn = Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.GSYN)
        XCTAssertNotNil(gsyn, "MP5文件应包含gsyn box")
    }

    // MARK: - 解析器测试

    func testParseEmptyFile() {
        let data = Data()
        let info = Mp5Parser.parse(data)
        XCTAssertFalse(info.isMp5)
        XCTAssertTrue(info.gpsSamples.isEmpty)
    }

    // MARK: - SyncEngine 测试

    func testSyncEngineGetGpsAtTime() {
        let samples = [
            GpsSample.fromDegrees(timestampMs: 0, latitude: 39.0, longitude: 116.0,
                                   altitudeM: 0, accuracyM: 0, headingDeg: 0, speedKmh: 0),
            GpsSample.fromDegrees(timestampMs: 1000, latitude: 39.001, longitude: 116.001,
                                   altitudeM: 0, accuracyM: 0, headingDeg: 0, speedKmh: 0),
            GpsSample.fromDegrees(timestampMs: 2000, latitude: 39.002, longitude: 116.002,
                                   altitudeM: 0, accuracyM: 0, headingDeg: 0, speedKmh: 0),
        ]

        let engine = SyncEngine(gpsSamples: samples, syncRules: SyncRules(interpolation: 1))

        // 线性插值 t=0.5
        let gps = engine.getGpsAtTime(500)
        XCTAssertNotNil(gps)
        XCTAssertEqual(gps?.latitude ?? 0, 39.0005, accuracy: 0.0001)
        XCTAssertEqual(gps?.longitude ?? 0, 116.0005, accuracy: 0.0001)
    }

    func testSyncEngineNearestTimestamp() {
        let samples = [
            GpsSample.fromDegrees(timestampMs: 0, latitude: 39.0, longitude: 116.0,
                                   altitudeM: 0, accuracyM: 0, headingDeg: 0, speedKmh: 0),
            GpsSample.fromDegrees(timestampMs: 1000, latitude: 40.0, longitude: 117.0,
                                   altitudeM: 0, accuracyM: 0, headingDeg: 0, speedKmh: 0),
        ]

        let engine = SyncEngine(gpsSamples: samples, syncRules: SyncRules())

        // 查找最接近 (39.0, 116.0) 的时间戳
        let ts = engine.findNearestTimestamp(lat: 39.0, lon: 116.0)
        XCTAssertEqual(ts, 0)
    }

    func testSyncEngineStats() {
        let samples = [
            GpsSample.fromDegrees(timestampMs: 0, latitude: 39.0, longitude: 116.0,
                                   altitudeM: 0, accuracyM: 0, headingDeg: 0, speedKmh: 0),
            GpsSample.fromDegrees(timestampMs: 1000, latitude: 39.001, longitude: 116.001,
                                   altitudeM: 0, accuracyM: 0, headingDeg: 0, speedKmh: 50),
        ]

        let engine = SyncEngine(gpsSamples: samples, syncRules: SyncRules())
        let stats = engine.getStats()
        XCTAssertEqual(stats["pointCount"], 2)
        XCTAssertEqual(stats["maxSpeed"], 50)
        XCTAssertGreaterThan(stats["distance"] ?? 0, 0)
    }

    // MARK: - 导出器测试

    func testGpxExport() {
        let samples = [
            GpsSample.fromDegrees(timestampMs: 0, latitude: 39.9042, longitude: 116.4074,
                                   altitudeM: 43.2, accuracyM: 5, headingDeg: 180, speedKmh: 36.0)
        ]
        let gpx = GpxExporter.export(samples: samples)
        XCTAssertTrue(gpx.contains("<gpx"))
        XCTAssertTrue(gpx.contains("trkpt"))
        XCTAssertTrue(gpx.contains("39.9042"))
    }

    func testGeoJsonExport() {
        let samples = [
            GpsSample.fromDegrees(timestampMs: 0, latitude: 39.9042, longitude: 116.4074,
                                   altitudeM: 43.2, accuracyM: 5, headingDeg: 180, speedKmh: 36.0)
        ]
        let json = GeoJsonExporter.export(samples: samples)
        XCTAssertTrue(json.contains("FeatureCollection"))
        XCTAssertTrue(json.contains("LineString"))
    }

    func testKmlExport() {
        let samples = [
            GpsSample.fromDegrees(timestampMs: 0, latitude: 39.9042, longitude: 116.4074,
                                   altitudeM: 43.2, accuracyM: 5, headingDeg: 180, speedKmh: 36.0)
        ]
        let kml = KmlExporter.export(samples: samples)
        XCTAssertTrue(kml.contains("<kml"))
        XCTAssertTrue(kml.contains("LineString"))
    }

    // MARK: - 速度颜色测试

    func testSpeedColor() {
        let color = SyncEngine.speedColor(3.0)
        XCTAssertEqual(color.red, 0.231, accuracy: 0.01)   // 蓝色

        let color2 = SyncEngine.speedColor(10.0)
        XCTAssertEqual(color2.green, 0.773, accuracy: 0.01)  // 绿色

        let color3 = SyncEngine.speedColor(150.0)
        XCTAssertEqual(color3.red, 0.937, accuracy: 0.01)  // 红色
    }
}