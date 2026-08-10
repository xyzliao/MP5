//
// VideoRecorder.swift
// MP5iOS
//
// 视频录制器 — 使用 AVFoundation 录制视频
//
// 对应 Android版 CameraX VideoCapture。
// 使用 AVCaptureSession + AVCaptureMovieFileOutput 录制MP4到临时文件。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.10
//

import Foundation
import AVFoundation
import UIKit

/// 视频录制器
public class VideoRecorder: NSObject, AVCaptureFileOutputRecordingDelegate {

    private let session = AVCaptureSession()
    private let movieOutput = AVCaptureMovieFileOutput()
    private var outputFileURL: URL?
    private var isSessionConfigured = false

    // 回调
    public var onRecordingStarted: (() -> Void)?
    public var onRecordingFinished: ((URL?) -> Void)?
    public var onRecordingError: ((Error) -> Void)?

    public override init() {
        super.init()
    }

    /// 配置摄像头+麦克风
    public func configure() throws {
        guard !isSessionConfigured else { return }

        session.beginConfiguration()

        // 摄像头
        guard let camera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
            throw NSError(domain: "VideoRecorder", code: 1, userInfo: [NSLocalizedDescriptionKey: "无法访问后置摄像头"])
        }
        let cameraInput = try AVCaptureDeviceInput(device: camera)
        if session.canAddInput(cameraInput) {
            session.addInput(cameraInput)
        }

        // 麦克风
        if let audioDevice = AVCaptureDevice.default(for: .audio) {
            let audioInput = try AVCaptureDeviceInput(device: audioDevice)
            if session.canAddInput(audioInput) {
                session.addInput(audioInput)
            }
        }

        // 视频输出
        if session.canAddOutput(movieOutput) {
            session.addOutput(movieOutput)
        }

        session.commitConfiguration()
        isSessionConfigured = true
    }

    /// 获取预览图层
    public func previewLayer() -> AVCaptureVideoPreviewLayer {
        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        return layer
    }

    /// 启动会话（在后台线程执行）
    public func startSession() {
        DispatchQueue.global(qos: .userInitiated).async {
            if !self.session.isRunning {
                self.session.startRunning()
            }
        }
    }

    /// 停止会话
    public func stopSession() {
        if session.isRunning {
            session.stopRunning()
        }
    }

    /// 开始录制MP4
    public func startRecording(to url: URL) {
        outputFileURL = url

        // 确保会话在运行
        if !session.isRunning {
            session.startRunning()
        }

        movieOutput.startRecording(to: url, recordingDelegate: self)
    }

    /// 暂停录制
    public func pauseRecording() {
        movieOutput.pauseRecording()
    }

    /// 续录
    public func resumeRecording() {
        movieOutput.resumeRecording()
    }

    /// 停止录制
    public func stopRecording() {
        movieOutput.stopRecording()
    }

    // MARK: - AVCaptureFileOutputRecordingDelegate

    public func fileOutput(_ output: AVCaptureFileOutput, didStartRecordingTo fileURL: URL, from connections: [AVCaptureConnection]) {
        DispatchQueue.main.async {
            self.onRecordingStarted?()
        }
    }

    public func fileOutput(_ output: AVCaptureFileOutput, didFinishRecordingTo fileURL: URL, from connections: [AVCaptureConnection], error: Error?) {
        if let error = error {
            DispatchQueue.main.async {
                self.onRecordingError?(error)
            }
        } else {
            DispatchQueue.main.async {
                self.onRecordingFinished?(fileURL)
            }
        }
    }

    public func fileOutput(_ output: AVCaptureFileOutput, didPauseRecordingTo fileURL: URL, from connections: [AVCaptureConnection]) {
        // 暂停回调
    }

    public func fileOutput(_ output: AVCaptureFileOutput, didResumeRecordingTo fileURL: URL, from connections: [AVCaptureConnection]) {
        // 续录回调
    }
}