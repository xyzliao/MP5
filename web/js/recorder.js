/**
 * Recorder — MP5 录制模块
 *
 * 职责:
 * 1. 启动摄像头采集视频
 * 2. 启动 GPS 采样
 * 3. 启动方向传感器
 * 4. 将视频+GPS封装为 MP5 文件
 * 5. 支持暂停/续录
 * 6. 支持 POI 标记
 */

import { MP5Muxer } from './mp5-muxer.js';

export class Recorder {
    constructor() {
        this.isRecording = false;
        this.isPaused = false;
        this.startTime = 0;
        this.elapsedTime = 0;
        this.pauseStartTime = 0;
        this.totalPausedTime = 0;

        this.mediaRecorder = null;
        this.recordedChunks = [];
        this.videoStream = null;

        this.gpsEntries = [];
        this.pois = [];
        this.gpsWatchId = null;
        this.orientationListener = null;

        this.gpsSampleRate = 1;     // Hz
        this.headingSampleRate = 10; // Hz
        this.lastGpsSample = 0;
        this.lastHeadingSample = 0;

        this.gpsAccuracy = null;
        this.currentPosition = null;
        this.currentHeading = 0;
        this.currentSpeed = 0;

        this.onUpdate = null;  // 回调：状态更新
        this.onComplete = null; // 回调：录制完成
        this.onError = null;    // 回调：错误
    }

    /**
     * 初始化摄像头预览
     */
    async initCamera() {
        try {
            const constraints = {
                video: {
                    width: { ideal: 1920 },
                    height: { ideal: 1080 },
                    frameRate: { ideal: 30 }
                },
                audio: true
            };

            this.videoStream = await navigator.mediaDevices.getUserMedia(constraints);
            return this.videoStream;
        } catch (err) {
            throw new Error(`摄像头初始化失败: ${err.message}`);
        }
    }

    /**
     * 开始录制
     * @param {Object} options - 录制参数
     */
    async startRecording(options = {}) {
        this.gpsSampleRate = options.gpsSampleRate || 1;
        this.headingSampleRate = options.headingSampleRate || 10;

        // 初始化摄像头
        if (!this.videoStream) {
            await this.initCamera();
        }

        // 检查 GPS
        if (!navigator.geolocation) {
            console.warn('Geolocation API 不可用，将仅录制视频');
        }

        // 配置 MediaRecorder
        const mimeTypes = [
            'video/mp4;codecs=h264,aac',
            'video/mp4;codecs=avc1.42E01E,mp4a.40.2',
            'video/webm;codecs=vp9,opus',
            'video/webm;codecs=vp8,opus',
            'video/webm'
        ];

        let mimeType = '';
        for (const type of mimeTypes) {
            if (MediaRecorder.isTypeSupported(type)) {
                mimeType = type;
                break;
            }
        }

        this.recordedChunks = [];
        this.mediaRecorder = new MediaRecorder(this.videoStream, {
            mimeType: mimeType,
            videoBitsPerSecond: 8000000, // 8Mbps
            audioBitsPerSecond: 128000
        });

        this.mediaRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) {
                this.recordedChunks.push(e.data);
            }
        };

        this.mediaRecorder.onstop = () => {
            this._finalizeRecording();
        };

        // 开始录制
        this.mediaRecorder.start(1000); // 每秒收集一次数据
        this.isRecording = true;
        this.isPaused = false;
        this.startTime = Date.now();
        this.elapsedTime = 0;
        this.totalPausedTime = 0;
        this.gpsEntries = [];
        this.pois = [];

        // 启动 GPS 采样
        this._startGPSSampling();

        // 启动方向传感器
        this._startOrientationTracking();

        // 定时更新状态
        this._updateTimer = setInterval(() => {
            if (!this.isPaused) {
                this.elapsedTime = Date.now() - this.startTime - this.totalPausedTime;
                this._notifyUpdate();
            }
        }, 100);

        this._notifyUpdate();
    }

    /**
     * 暂停录制
     */
    pauseRecording() {
        if (!this.isRecording || this.isPaused) return;

        this.isPaused = true;
        this.pauseStartTime = Date.now();

        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.pause();
        }

        // GPS 降频至 0.1Hz
        this.gpsSampleRate = 0.1;
        this._notifyUpdate();
    }

    /**
     * 继续录制
     */
    resumeRecording() {
        if (!this.isRecording || !this.isPaused) return;

        this.isPaused = false;
        this.totalPausedTime += Date.now() - this.pauseStartTime;

        if (this.mediaRecorder && this.mediaRecorder.state === 'paused') {
            this.mediaRecorder.resume();
        }

        // GPS 恢复原始采样率
        this.gpsSampleRate = 1;
        this._notifyUpdate();
    }

    /**
     * 停止录制并生成 MP5 文件
     */
    stopRecording() {
        if (!this.isRecording) return;

        this.isRecording = false;

        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }

        // 停止 GPS
        if (this.gpsWatchId !== null) {
            navigator.geolocation.clearWatch(this.gpsWatchId);
            this.gpsWatchId = null;
        }

        // 停止方向传感器
        if (this.orientationListener) {
            window.removeEventListener('deviceorientation', this.orientationListener);
            this.orientationListener = null;
        }

        // 清理定时器
        if (this._updateTimer) {
            clearInterval(this._updateTimer);
            this._updateTimer = null;
        }

        // 停止摄像头
        if (this.videoStream) {
            this.videoStream.getTracks().forEach(t => t.stop());
            this.videoStream = null;
        }
    }

    /**
     * 添加 POI 标记
     * @param {string} label - 标记名称
     */
    addPOI(label = '') {
        if (!this.isRecording || this.isPaused) return;

        const poi = {
            timestamp: this.elapsedTime,
            latitude: this.currentPosition?.latitude || 0,
            longitude: this.currentPosition?.longitude || 0,
            label: label,
            type: 'poi'
        };

        this.pois.push(poi);
        this._notifyUpdate();
    }

    /**
     * 启动 GPS 采样
     */
    _startGPSSampling() {
        if (!navigator.geolocation) return;

        const interval = 1000 / this.gpsSampleRate;

        this.gpsWatchId = navigator.geolocation.watchPosition(
            (position) => {
                const now = Date.now();
                if (now - this.lastGpsSample < interval) return;
                this.lastGpsSample = now;

                const entry = {
                    timestamp: this.isRecording ? this.elapsedTime : 0,
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    altitude: position.coords.altitude || 0,
                    accuracy: position.coords.accuracy || 0,
                    heading: position.coords.heading || this.currentHeading,
                    speed: (position.coords.speed || 0) * 3.6 // m/s → km/h
                };

                this.gpsEntries.push(entry);
                this.currentPosition = entry;
                this.gpsAccuracy = position.coords.accuracy;
                this.currentSpeed = entry.speed;

                this._notifyUpdate();
            },
            (err) => {
                console.error('GPS 错误:', err.message);
                if (this.onError) this.onError(`GPS错误: ${err.message}`);
            },
            {
                enableHighAccuracy: true,
                maximumAge: 0,
                timeout: 10000
            }
        );
    }

    /**
     * 启动方向传感器
     */
    _startOrientationTracking() {
        if (!window.DeviceOrientationEvent) return;

        const interval = 1000 / this.headingSampleRate;

        this.orientationListener = (event) => {
            const now = Date.now();
            if (now - this.lastHeadingSample < interval) return;
            this.lastHeadingSample = now;

            // 计算方向角
            if (event.alpha !== null) {
                this.currentHeading = 360 - event.alpha;
            } else if (event.webkitCompassHeading !== undefined) {
                this.currentHeading = event.webkitCompassHeading;
            }
        };

        window.addEventListener('deviceorientation', this.orientationListener);
    }

    /**
     * 录制完成，封装 MP5 文件
     */
    async _finalizeRecording() {
        try {
            const videoBlob = new Blob(this.recordedChunks, {
                type: this.mediaRecorder.mimeType || 'video/webm'
            });

            // 封装为 MP5
            const mp5Blob = await MP5Muxer.mux(videoBlob, this.gpsEntries, {
                syncMode: 0,
                syncOffset: 0,
                interpolation: 1,
                defaultView: 2,
                videoRatio: 0.5,
                mapStyle: 0,
                showTrajectory: true,
                showPoi: true
            }, this.pois);

            if (this.onComplete) {
                this.onComplete({
                    blob: mp5Blob,
                    duration: this.elapsedTime,
                    gpsEntries: this.gpsEntries,
                    pois: this.pois,
                    size: mp5Blob.size
                });
            }
        } catch (err) {
            console.error('封装MP5失败:', err);
            if (this.onError) this.onError(`封装MP5失败: ${err.message}`);
        }
    }

    /**
     * 通知状态更新
     */
    _notifyUpdate() {
        if (this.onUpdate) {
            this.onUpdate({
                isRecording: this.isRecording,
                isPaused: this.isPaused,
                elapsedTime: this.elapsedTime,
                gpsAccuracy: this.gpsAccuracy,
                currentPosition: this.currentPosition,
                currentHeading: this.currentHeading,
                currentSpeed: this.currentSpeed,
                gpsEntryCount: this.gpsEntries.length,
                poiCount: this.pois.length
            });
        }
    }

    /**
     * 销毁录制器
     */
    destroy() {
        this.stopRecording();
    }
}