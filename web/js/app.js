/**
 * App — MP5录播器 主应用入口
 *
 * 职责:
 * 1. 管理页面切换（文件/录制/播放/设置）
 * 2. 协调各模块（Recorder/Player/FileManager）
 * 3. 处理 UI 交互
 */

import { Recorder } from './recorder.js';
import { Player } from './player.js';
import { FileManager } from './file-manager.js';
import { MP5Muxer } from './mp5-muxer.js';
import { MP5Parser } from './mp5-parser.js';

class App {
    constructor() {
        this.recorder = null;
        this.player = null;
        this.fileManager = null;
        this.miniMap = null;
        this.currentFileId = null;
    }

    /**
     * 初始化应用
     */
    async init() {
        this.fileManager = new FileManager();
        await this.fileManager.init();

        this._bindNavigation();
        this._bindFileList();
        this._bindRecorder();
        this._bindPlayer();
        this._bindSettings();

        // 加载文件列表
        await this._refreshFileList();

        // 加载设置
        this._loadSettings();
    }

    // ============================================================
    // 导航
    // ============================================================

    _bindNavigation() {
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const target = tab.dataset.tab;
                this._switchPage(target);
            });
        });
    }

    _switchPage(pageName) {
        // 更新导航按钮
        document.querySelectorAll('.nav-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === pageName);
        });

        // 更新页面显示
        document.querySelectorAll('.page').forEach(p => {
            p.classList.remove('active');
        });

        const pageMap = {
            'files': 'page-files',
            'record': 'page-record',
            'player': 'page-player',
            'settings': 'page-settings'
        };

        const page = document.getElementById(pageMap[pageName]);
        if (page) page.classList.add('active');

        // 如果切换到文件页，刷新列表
        if (pageName === 'files') {
            this._refreshFileList();
        }
    }

    // ============================================================
    // 文件列表
    // ============================================================

    _bindFileList() {
        document.getElementById('btn-import-mp5').addEventListener('click', () => {
            document.getElementById('file-input').click();
        });

        document.getElementById('file-input').addEventListener('change', async (e) => {
            const files = e.target.files;
            for (const file of files) {
                try {
                    await this.fileManager.importFile(file);
                    this._showToast(`已导入: ${file.name}`);
                } catch (err) {
                    this._showToast(`导入失败: ${err.message}`, true);
                }
            }
            e.target.value = '';
            await this._refreshFileList();
        });
    }

    async _refreshFileList() {
        const list = document.getElementById('file-list');
        const empty = document.getElementById('empty-state');
        const files = await this.fileManager.listFiles();

        if (files.length === 0) {
            empty.style.display = 'block';
            // 清除除 empty-state 外的所有子元素
            Array.from(list.children).forEach(child => {
                if (child.id !== 'empty-state') child.remove();
            });
            return;
        }

        empty.style.display = 'none';
        // 清除现有文件卡片
        Array.from(list.children).forEach(child => {
            if (child.id !== 'empty-state') child.remove();
        });

        for (const file of files) {
            const card = this._createFileCard(file);
            list.appendChild(card);
        }
    }

    _createFileCard(file) {
        const card = document.createElement('div');
        card.className = 'file-card';

        const icon = document.createElement('div');
        icon.className = 'file-card-icon';
        icon.textContent = '🎬';

        const info = document.createElement('div');
        info.className = 'file-card-info';
        info.innerHTML = `
            <div class="file-card-name">${file.name}</div>
            <div class="file-card-meta">
                ${FileManager.formatDuration(file.duration)}
                ${file.gpsCount > 0 ? ` · ${file.gpsCount} GPS点` : ''}
                ${file.distance > 0 ? ` · ${file.distance.toFixed(1)}km` : ''}
                · ${FileManager.formatSize(file.size)}
                · ${FileManager.formatDate(file.createdAt)}
            </div>
        `;

        const actions = document.createElement('div');
        actions.className = 'file-card-actions';

        const playBtn = document.createElement('button');
        playBtn.className = 'btn btn-primary';
        playBtn.textContent = '▶ 播放';
        playBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this._playFile(file.id, file.name);
        });

        const shareBtn = document.createElement('button');
        shareBtn.className = 'btn';
        shareBtn.textContent = '↗ 分享';
        shareBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const record = await this.fileManager.getFile(file.id);
            if (record && record.blob) {
                await this.fileManager.shareFile(record.blob, file.name);
            }
        });

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn';
        deleteBtn.textContent = '🗑';
        deleteBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (confirm(`删除 ${file.name}?`)) {
                await this.fileManager.deleteFile(file.id);
                await this._refreshFileList();
                this._showToast('已删除');
            }
        });

        actions.appendChild(playBtn);
        actions.appendChild(shareBtn);
        actions.appendChild(deleteBtn);

        card.appendChild(icon);
        card.appendChild(info);
        card.appendChild(actions);

        card.addEventListener('click', () => {
            this._playFile(file.id, file.name);
        });

        return card;
    }

    async _playFile(fileId, filename) {
        const record = await this.fileManager.getFile(fileId);
        if (!record || !record.blob) return;

        this.currentFileId = fileId;
        const buffer = await record.blob.arrayBuffer();

        // 销毁旧播放器
        if (this.player) {
            this.player.destroy();
        }

        this.player = new Player();

        try {
            const info = await this.player.load(buffer, filename);
            this._switchPage('player');
            document.getElementById('player-title').textContent = filename;

            // 等待 DOM 更新后初始化播放器
            setTimeout(() => {
                this.player.initPlayer(
                    document.getElementById('player-video'),
                    document.getElementById('player-map')
                );

                // 显示统计信息
                if (info.hasGPS) {
                    const stats = this.player.getStats();
                    if (stats) {
                        this._showToast(`GPS点: ${stats.pointCount} · 距离: ${stats.distance.toFixed(2)}km · 最高速度: ${stats.maxSpeed.toFixed(1)}km/h`);
                    }
                }
            }, 100);
        } catch (err) {
            this._showToast(`播放失败: ${err.message}`, true);
        }
    }

    // ============================================================
    // 录制
    // ============================================================

    _bindRecorder() {
        this.recorder = new Recorder();

        const previewVideo = document.getElementById('record-preview-video');
        const recordBtn = document.getElementById('btn-record');
        const pauseBtn = document.getElementById('btn-pause');
        const stopBtn = document.getElementById('btn-stop');
        const poiBtn = document.getElementById('btn-poi');

        recordBtn.addEventListener('click', async () => {
            if (!this.recorder.isRecording) {
                try {
                    // 初始化摄像头预览
                    const stream = await this.recorder.initCamera();
                    previewVideo.srcObject = stream;

                    // 开始录制
                    await this.recorder.startRecording({
                        gpsSampleRate: parseInt(document.getElementById('setting-gps-rate').value),
                        headingSampleRate: parseInt(document.getElementById('setting-heading-rate').value)
                    });

                    recordBtn.textContent = '录制中';
                    recordBtn.classList.add('recording');
                    pauseBtn.disabled = false;
                    stopBtn.disabled = false;
                    poiBtn.disabled = false;

                    // 显示迷你地图
                    this._initMiniMap();

                    // 设置回调
                    this.recorder.onUpdate = (state) => {
                        this._updateRecordUI(state);
                    };

                    this.recorder.onComplete = async (result) => {
                        await this._onRecordingComplete(result);
                    };

                    this.recorder.onError = (msg) => {
                        this._showToast(msg, true);
                    };

                    this._showToast('开始录制');
                } catch (err) {
                    this._showToast(`录制启动失败: ${err.message}`, true);
                }
            }
        });

        pauseBtn.addEventListener('click', () => {
            if (!this.recorder.isPaused) {
                this.recorder.pauseRecording();
                pauseBtn.textContent = '继续';
                recordBtn.classList.remove('recording');
                this._showToast('已暂停');
            } else {
                this.recorder.resumeRecording();
                pauseBtn.textContent = '暂停';
                recordBtn.classList.add('recording');
                this._showToast('继续录制');
            }
        });

        stopBtn.addEventListener('click', () => {
            this.recorder.stopRecording();
            recordBtn.textContent = '录制';
            recordBtn.classList.remove('recording');
            pauseBtn.disabled = true;
            stopBtn.disabled = true;
            poiBtn.disabled = true;
            pauseBtn.textContent = '暂停';

            // 清除预览
            if (previewVideo.srcObject) {
                previewVideo.srcObject = null;
            }

            // 清除迷你地图
            const miniMapDiv = document.getElementById('record-mini-map');
            miniMapDiv.style.display = 'none';
            if (this.miniMap) {
                this.miniMap.remove();
                this.miniMap = null;
            }
        });

        poiBtn.addEventListener('click', () => {
            document.getElementById('poi-modal').style.display = 'flex';
            document.getElementById('poi-label').focus();
        });

        // POI 模态框
        document.getElementById('poi-confirm').addEventListener('click', () => {
            const label = document.getElementById('poi-label').value;
            this.recorder.addPOI(label);
            document.getElementById('poi-label').value = '';
            document.getElementById('poi-modal').style.display = 'none';
            this._showToast(`已添加POI: ${label || '未命名'}`);
        });

        document.getElementById('poi-cancel').addEventListener('click', () => {
            document.getElementById('poi-modal').style.display = 'none';
            document.getElementById('poi-label').value = '';
        });
    }

    _initMiniMap() {
        const container = document.getElementById('record-mini-map');
        container.style.display = 'block';

        if (this.miniMap) {
            this.miniMap.remove();
        }

        this.miniMap = L.map(container, {
            center: [39.9042, 116.4074],
            zoom: 14,
            zoomControl: false,
            attributionControl: false
        });

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(this.miniMap);
    }

    _updateRecordUI(state) {
        // 更新录制时间
        const timeEl = document.getElementById('record-time');
        const totalSec = Math.floor(state.elapsedTime / 1000);
        const h = Math.floor(totalSec / 3600);
        const m = Math.floor((totalSec % 3600) / 60);
        const s = totalSec % 60;
        timeEl.textContent = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;

        // 更新录制指示器
        document.getElementById('record-indicator').style.display = state.isRecording && !state.isPaused ? 'block' : 'none';

        // 更新 GPS 信息
        const gpsInfo = document.getElementById('record-gps-info');
        if (state.currentPosition) {
            gpsInfo.innerHTML = `
                <div>${state.currentPosition.latitude.toFixed(4)}°, ${state.currentPosition.longitude.toFixed(4)}°</div>
                <div>方向: ${state.currentHeading.toFixed(0)}° 速度: ${state.currentSpeed.toFixed(1)}km/h</div>
            `;
        }

        // 更新状态栏
        document.getElementById('gps-accuracy').textContent = `GPS精度: ${state.gpsAccuracy ? state.gpsAccuracy.toFixed(0) + 'm' : '--'}`;

        // 更新迷你地图
        if (this.miniMap && state.currentPosition) {
            this.miniMap.panTo([state.currentPosition.latitude, state.currentPosition.longitude]);
        }
    }

    async _onRecordingComplete(result) {
        // 保存到文件管理器
        const filename = `录制_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.mp5`;

        const metadata = {
            duration: result.duration,
            gpsCount: result.gpsEntries.length,
            poiCount: result.pois.length,
            distance: this._calculateDistance(result.gpsEntries),
            latitude: result.gpsEntries[0]?.latitude,
            longitude: result.gpsEntries[0]?.longitude
        };

        await this.fileManager.saveFile(result.blob, filename, metadata);
        this._showToast(`录制完成: ${filename} (${FileManager.formatSize(result.size)})`);

        // 刷新文件列表
        await this._refreshFileList();
    }

    _calculateDistance(gpsEntries) {
        let dist = 0;
        for (let i = 1; i < gpsEntries.length; i++) {
            const R = 6371000;
            const dLat = (gpsEntries[i].latitude - gpsEntries[i-1].latitude) * Math.PI / 180;
            const dLon = (gpsEntries[i].longitude - gpsEntries[i-1].longitude) * Math.PI / 180;
            const a = Math.sin(dLat/2)**2 + Math.cos(gpsEntries[i-1].latitude * Math.PI/180) * Math.cos(gpsEntries[i].latitude * Math.PI/180) * Math.sin(dLon/2)**2;
            dist += R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        }
        return dist / 1000; // km
    }

    // ============================================================
    // 播放器
    // ============================================================

    _bindPlayer() {
        document.getElementById('btn-back').addEventListener('click', () => {
            if (this.player) {
                this.player.destroy();
                this.player = null;
            }
            this._switchPage('files');
        });

        // 视图切换
        document.querySelectorAll('.btn-view').forEach(btn => {
            btn.addEventListener('click', () => {
                if (this.player) {
                    this.player.setView(btn.dataset.view);
                }
            });
        });

        // 导出按钮
        document.querySelectorAll('.btn-export').forEach(btn => {
            btn.addEventListener('click', () => {
                this._exportFile(btn.dataset.format);
            });
        });

        // 更多菜单
        document.getElementById('btn-more').addEventListener('click', () => {
            document.getElementById('more-modal').style.display = 'flex';
        });

        document.getElementById('more-close').addEventListener('click', () => {
            document.getElementById('more-modal').style.display = 'none';
        });

        document.getElementById('more-export-mp4').addEventListener('click', () => {
            this._exportFile('mp4');
            document.getElementById('more-modal').style.display = 'none';
        });

        document.getElementById('more-export-gpx').addEventListener('click', () => {
            this._exportFile('gpx');
            document.getElementById('more-modal').style.display = 'none';
        });

        document.getElementById('more-export-geojson').addEventListener('click', () => {
            this._exportFile('geojson');
            document.getElementById('more-modal').style.display = 'none';
        });

        document.getElementById('more-screenshot').addEventListener('click', async () => {
            if (this.player) {
                const blob = await this.player.screenshot();
                this.fileManager.exportFile(blob, `screenshot_${Date.now()}.png`);
                this._showToast('截图已保存');
            }
            document.getElementById('more-modal').style.display = 'none';
        });

        document.getElementById('more-share').addEventListener('click', async () => {
            if (this.player && this.currentFileId) {
                const record = await this.fileManager.getFile(this.currentFileId);
                if (record && record.blob) {
                    await this.fileManager.shareFile(record.blob, this.player.filename || 'share.mp5');
                }
            }
            document.getElementById('more-modal').style.display = 'none';
        });
    }

    _exportFile(format) {
        if (!this.player) return;

        const baseName = this.player.filename?.replace(/\.(mp5|mp4)$/i, '') || 'export';

        switch (format) {
            case 'mp4':
                {
                    const blob = this.player.exportMP4();
                    if (blob) {
                        this.fileManager.exportFile(blob, `${baseName}.mp4`);
                        this._showToast('已导出MP4');
                    }
                }
                break;

            case 'gpx':
                {
                    const gpx = this.player.exportGPX();
                    if (gpx) {
                        const blob = new Blob([gpx], { type: 'application/gpx+xml' });
                        this.fileManager.exportFile(blob, `${baseName}.gpx`);
                        this._showToast('已导出GPX');
                    }
                }
                break;

            case 'geojson':
                {
                    const geojson = this.player.exportGeoJSON();
                    if (geojson) {
                        const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: 'application/geo+json' });
                        this.fileManager.exportFile(blob, `${baseName}.geojson`);
                        this._showToast('已导出GeoJSON');
                    }
                }
                break;
        }
    }

    // ============================================================
    // 设置
    // ============================================================

    _bindSettings() {
        // 设置变更时自动保存
        document.querySelectorAll('#page-settings select, #page-settings input').forEach(el => {
            el.addEventListener('change', () => {
                this._saveSettings();
            });
        });
    }

    _saveSettings() {
        const settings = {
            resolution: document.getElementById('setting-resolution').value,
            framerate: document.getElementById('setting-framerate').value,
            codec: document.getElementById('setting-codec').value,
            gpsRate: document.getElementById('setting-gps-rate').value,
            headingRate: document.getElementById('setting-heading-rate').value,
            mapSource: document.getElementById('setting-map-source').value,
            defaultView: document.getElementById('setting-default-view').value,
            showTrajectory: document.getElementById('setting-show-trajectory').checked,
            speedHeatmap: document.getElementById('setting-speed-heatmap').checked
        };
        localStorage.setItem('mp5_settings', JSON.stringify(settings));
    }

    _loadSettings() {
        const saved = localStorage.getItem('mp5_settings');
        if (!saved) return;

        try {
            const s = JSON.parse(saved);
            if (s.resolution) document.getElementById('setting-resolution').value = s.resolution;
            if (s.framerate) document.getElementById('setting-framerate').value = s.framerate;
            if (s.codec) document.getElementById('setting-codec').value = s.codec;
            if (s.gpsRate) document.getElementById('setting-gps-rate').value = s.gpsRate;
            if (s.headingRate) document.getElementById('setting-heading-rate').value = s.headingRate;
            if (s.mapSource) document.getElementById('setting-map-source').value = s.mapSource;
            if (s.defaultView) document.getElementById('setting-default-view').value = s.defaultView;
            if (s.showTrajectory !== undefined) document.getElementById('setting-show-trajectory').checked = s.showTrajectory;
            if (s.speedHeatmap !== undefined) document.getElementById('setting-speed-heatmap').checked = s.speedHeatmap;
        } catch (e) {
            console.warn('加载设置失败:', e);
        }
    }

    // ============================================================
    // 工具方法
    // ============================================================

    _showToast(message, isError = false) {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = isError ? 'toast error' : 'toast';
        toast.style.display = 'block';

        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => {
            toast.style.display = 'none';
        }, 3000);
    }
}

// 启动应用
const app = new App();
app.init().catch(err => {
    console.error('应用初始化失败:', err);
});

// 暴露到全局用于调试
window.MP5App = app;