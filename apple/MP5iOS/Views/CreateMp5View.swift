//
// CreateMp5View.swift
// MP5iOS
//
// 从MP4制作MP5 — 导入MP4 + GPX → MP5
//
// 对应 Windows版 "制作MP5" 功能和 Android版 CreateMp5View。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import SwiftUI
import UniformTypeIdentifiers
import MP5Core

struct CreateMp5View: View {
    @Environment(\.dismiss) private var dismiss
    @State private var mp4Url: URL?
    @State private var gpxUrl: URL?
    @State private var isProcessing = false
    @State private var errorMessage: String?
    @State private var showSuccess = false
    @State private var showMp4Picker = false
    @State private var showGpxPicker = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // MP4选择
                fileSelector(
                    title: "选择MP4视频",
                    icon: "video.fill",
                    url: mp4Url,
                    onTap: { showMp4Picker = true }
                )

                // GPX选择
                fileSelector(
                    title: "选择GPX轨迹文件",
                    icon: "location.fill",
                    url: gpxUrl,
                    onTap: { showGpxPicker = true }
                )

                Spacer()

                // 制作按钮
                Button {
                    makeMp5()
                } label: {
                    HStack {
                        if isProcessing {
                            ProgressView()
                                .tint(.white)
                        }
                        Text(isProcessing ? "正在制作..." : "制作MP5")
                            .font(.headline)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(canMake ? Color.red : Color.gray)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .disabled(!canMake || isProcessing)
                .padding(.horizontal)
                .padding(.bottom)
            }
            .navigationTitle("从MP4制作MP5")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("取消") { dismiss() }
                }
            }
        }
        .sheet(isPresented: $showMp4Picker) {
            DocumentPicker(types: [.mpeg4Movie], onPick: { url in
                mp4Url = url
            })
        }
        .sheet(isPresented: $showGpxPicker) {
            DocumentPicker(types: [.xml], onPick: { url in
                gpxUrl = url
            })
        }
        .alert("成功", isPresented: $showSuccess) {
            Button("确定") { dismiss() }
        } message: {
            Text("MP5文件已成功创建")
        }
        .alert("错误", isPresented: Binding(
            get: { errorMessage != nil },
            set: { if !$0 { errorMessage = nil } }
        )) {
            Button("确定") { errorMessage = nil }
        } message: {
            Text(errorMessage ?? "")
        }
    }

    private var canMake: Bool {
        mp4Url != nil && gpxUrl != nil
    }

    private func fileSelector(title: String, icon: String, url: URL?, onTap: @escaping () -> Void) -> some View {
        Button(action: onTap) {
            HStack(spacing: 16) {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundStyle(.red)
                    .frame(width: 48, height: 48)
                    .background(Color.red.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 12))

                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.body)
                        .foregroundStyle(.primary)
                    if let url = url {
                        Text(url.lastPathComponent)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    } else {
                        Text("未选择")
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                    }
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .foregroundStyle(.tertiary)
            }
            .padding(16)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .padding(.horizontal)
    }

    private func makeMp5() {
        guard let mp4Url = mp4Url, let gpxUrl = gpxUrl else { return }

        isProcessing = true

        DispatchQueue.global(qos: .userInitiated).async {
            do {
                // 读取MP4
                let mp4Data = try Data(contentsOf: mp4Url)

                // 解析GPX
                let gpxData = try Data(contentsOf: gpxUrl)
                let samples = parseGpx(data: gpxData)

                if samples.isEmpty {
                    DispatchQueue.main.async {
                        errorMessage = "GPX文件中没有有效的轨迹点"
                        isProcessing = false
                    }
                    return
                }

                // 封装MP5
                let muxer = Mp5Muxer()
                let mp5Data = muxer.mux(
                    mp4Data: mp4Data,
                    gpsSamples: samples,
                    syncRules: SyncRules()
                )

                // 保存
                let mp5Url = Mp5Store.newMp5FileUrl()
                try mp5Data.write(to: mp5Url)

                DispatchQueue.main.async {
                    isProcessing = false
                    showSuccess = true
                }
            } catch {
                DispatchQueue.main.async {
                    errorMessage = "制作失败: \(error.localizedDescription)"
                    isProcessing = false
                }
            }
        }
    }

    /// 简易GPX解析
    private func parseGpx(data: Data) -> [GpsSample] {
        guard let xml = String(data: data, encoding: .utf8) else { return [] }

        var samples: [GpsSample] = []

        // 使用XMLParser解析
        let parser = GpxParser()
        parser.parse(data: data)
        samples = parser.samples

        return samples
    }
}

// MARK: - 简易GPX解析器

class GpxParser: NSObject, XMLParserDelegate {
    var samples: [GpsSample] = []
    private var currentElement = ""
    private var currentLat: Double = 0
    private var currentLon: Double = 0
    private var currentEle: Double = 0
    private var currentTime: Int64 = 0
    private var currentSpeed: Double = 0
    private var inTrkpt = false
    private var inEle = false
    private var inTime = false
    private var inSpeed = false
    private var timestampOffset: Int64 = 0
    private var hasFirstPoint = false

    func parse(data: Data) {
        let parser = XMLParser(data: data)
        parser.delegate = self
        parser.parse()
    }

    func parser(_ parser: XMLParser, didStartElement elementName: String,
                namespaceURI: String?, qualifiedName qName: String?,
                attributes attributeDict: [String: String] = [:]) {
        currentElement = elementName

        if elementName == "trkpt" {
            if let latStr = attributeDict["lat"], let lonStr = attributeDict["lon"],
               let lat = Double(latStr), let lon = Double(lonStr) {
                currentLat = lat
                currentLon = lon
                inTrkpt = true
                currentEle = 0
                currentTime = 0
                currentSpeed = 0
            }
        } else if elementName == "ele" {
            inEle = true
        } else if elementName == "time" {
            inTime = true
        } else if elementName == "speed" {
            inSpeed = true
        }
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) {
        let trimmed = string.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return }

        if inEle {
            currentEle = Double(trimmed) ?? 0
        } else if inTime {
            // 解析ISO8601时间
            let formatter = ISO8601DateFormatter()
            if let date = formatter.date(from: trimmed) {
                let timeMs = Int64(date.timeIntervalSince1970 * 1000)
                if !hasFirstPoint {
                    timestampOffset = timeMs
                    hasFirstPoint = true
                }
                currentTime = timeMs - timestampOffset
            }
        } else if inSpeed {
            currentSpeed = (Double(trimmed) ?? 0) * 3.6  // m/s → km/h
        }
    }

    func parser(_ parser: XMLParser, didEndElement elementName: String,
                namespaceURI: String?, qualifiedName qName: String?) {
        if elementName == "trkpt" && inTrkpt {
            let sample = GpsSample.fromDegrees(
                timestampMs: currentTime,
                latitude: currentLat,
                longitude: currentLon,
                altitudeM: currentEle,
                accuracyM: 0,
                headingDeg: 0,
                speedKmh: currentSpeed
            )
            samples.append(sample)
            inTrkpt = false
        } else if elementName == "ele" {
            inEle = false
        } else if elementName == "time" {
            inTime = false
        } else if elementName == "speed" {
            inSpeed = false
        }
    }
}

// MARK: - 文件选择器

struct DocumentPicker: UIViewControllerRepresentable {
    let types: [UTType]
    let onPick: (URL) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onPick: onPick)
    }

    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: types)
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIDocumentPickerViewController, context: Context) {}

    class Coordinator: NSObject, UIDocumentPickerDelegate {
        let onPick: (URL) -> Void

        init(onPick: @escaping (URL) -> Void) {
            self.onPick = onPick
        }

        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            if let url = urls.first {
                onPick(url)
            }
        }
    }
}