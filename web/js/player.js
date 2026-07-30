/**
 * Player — MP5 播放模块
 *
 * 职责:
 * 1. 解析 MP5 文件
 * 2. 播放视频
 * 3. 渲染地图和 GPS 轨迹
 * 4. 视频↔地图双向联动
 * 5. 视图切换（分屏/仅视频/仅地图/画中画）
 * 6. 速度热力图
 * 7. POI 标记显示
 */

import { MP5Parser } from './mp5-parser.js';
import { SyncEngine } from './sync-engine.js';

export class Player {
    constructor() {
        this.parsedData = null;
        this.videoBlobUrl = null;
        this.syncEngine = null;
        this.mapManager = null;
        this.videoElement = null;
        this.currentView = 'split';
        this.pois = [];
    }

    /**
     * 加载 MP5 文件
     * @param {ArrayBuffer} buffer - MP5 文件内容
     * @param {string} filename - 文件名
     */
    async load(buffer, filename = 'untitled.mp5') {
        // 解析 MP5 文件
        this.parsedData = MP5Parser.parse(buffer);
        this.filename = filename;

        if (!this.parsedData.ftyp) {
            throw new Error('无效的MP5/MP4文件');
        }

        // 提取纯视频数据（去除 MP5 box）
        const mp4Buffer = MP5Parser.stripMP5Boxes(buffer);
        const mp4Blob = new Blob([mp4Buffer], { type: 'video/mp4' });

        if (this.videoBlobUrl) {
            URL.revokeObjectURL(this.videoBlobUrl);
        }
        this.videoBlobUrl = URL.createObjectURL(mp4Blob);

        // 加载 POI 数据（如果有）
        this.pois = this.parsedData.gpsEntries ? [] : [];

        return {
            isMP5: this.parsedData.isMP5,
            hasGPS: this.parsedData.gpsEntries.length > 0,
            gpsCount: this.parsedData.gpsEntries.length,
            duration: this.parsedData.durationMs || 0,
            tracks: this.parsedData.tracks,
            syncConfig: this.parsedData.syncConfig
        };
    }

    /**
     * 初始化播放器 UI
     * @param {HTMLVideoElement} videoElement - 视频元素
     * @param {HTMLElement} mapContainer - 地图容器
     */
    initPlayer(videoElement, mapContainer) {
        this.videoElement = videoElement;
        this.videoElement.src = this.videoBlobUrl;

        // 初始化地图
        this.mapManager = new MapManager(mapContainer);

        // 如果有 GPS 数据，渲染轨迹
        if (this.parsedData.gpsEntries.length > 0) {
            this.mapManager.renderTrack(this.parsedData.gpsEntries);

            // 初始化同步引擎
            const syncConfig = this.parsedData.syncConfig || { interpolation: 1, syncOffset: 0 };
            this.syncEngine = new SyncEngine(
                this.parsedData.gpsEntries,
                syncConfig,
                this.mapManager,
                this.videoElement
            );

            // 应用默认视图
            if (syncConfig.defaultView !== undefined) {
                const viewMap = { 0: 'video', 1: 'map', 2: 'split', 3: 'split-v', 4: 'pip' };
                this.setView(viewMap[syncConfig.defaultView] || 'split');
            }
        }
    }

    /**
     * 切换视图模式
     * @param {string} view - 视图模式: video/map/split/split-v/pip
     */
    setView(view) {
        this.currentView = view;
        const main = document.getElementById('player-main');

        // 移除所有视图类
        main.className = 'player-main';

        switch (view) {
            case 'video':
                main.classList.add('view-video');
                break;
            case 'map':
                main.classList.add('view-map');
                break;
            case 'split':
                main.classList.add('view-split');
                break;
            case 'split-v':
                main.classList.add('view-split', 'view-split-vertical');
                break;
            case 'pip':
                main.classList.add('view-pip');
                this._setupPipDrag(main);
                break;
        }

        // 通知地图更新尺寸
        if (this.mapManager) {
            // 多次延迟调用，确保绝对定位容器完成渲染后地图能正确刷新
            setTimeout(() => this.mapManager.invalidateSize(), 50);
            setTimeout(() => this.mapManager.invalidateSize(), 200);
        }

        // 更新按钮状态
        document.querySelectorAll('.btn-view').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === view);
        });
    }

    /**
     * 设置画中画小窗口的可拖拽功能
     * @param {HTMLElement} main - player-main 容器
     */
    _setupPipDrag(main) {
        const mapPane = document.getElementById('map-pane');
        if (!mapPane || mapPane._pipDragSetup) return;
        mapPane._pipDragSetup = true;

        let dragging = false;
        let offsetX = 0;
        let offsetY = 0;

        // 用一个小拖拽手柄覆盖在地图右上角
        const handle = document.createElement('div');
        handle.style.cssText = 'position:absolute;top:0;right:0;width:20px;height:20px;' +
            'cursor:move;z-index:1000;background:rgba(48,54,61,0.8);border-radius:0 6px 0 6px;' +
            'display:flex;align-items:center;justify-content:center;font-size:10px;color:#8b949e;';
        handle.textContent = '⠿';
        handle.title = '拖拽移动地图小窗';
        mapPane.appendChild(handle);

        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragging = true;
            const rect = mapPane.getBoundingClientRect();
            const mainRect = main.getBoundingClientRect();
            offsetX = e.clientX - rect.left;
            offsetY = e.clientY - rect.top;
            // 切换为 left/top 定位
            const left = rect.left - mainRect.left;
            const top = rect.top - mainRect.top;
            mapPane.style.right = 'auto';
            mapPane.style.bottom = 'auto';
            mapPane.style.left = left + 'px';
            mapPane.style.top = top + 'px';
        });

        document.addEventListener('mousemove', (e) => {
            if (!dragging) return;
            const mainRect = main.getBoundingClientRect();
            let x = e.clientX - mainRect.left - offsetX;
            let y = e.clientY - mainRect.top - offsetY;
            // 限制在容器内
            x = Math.max(0, Math.min(x, mainRect.width - mapPane.offsetWidth));
            y = Math.max(0, Math.min(y, mainRect.height - mapPane.offsetHeight));
            mapPane.style.left = x + 'px';
            mapPane.style.top = y + 'px';
            if (this.mapManager) this.mapManager.invalidateSize();
        });

        document.addEventListener('mouseup', () => {
            if (dragging) {
                dragging = false;
                if (this.mapManager) this.mapManager.invalidateSize();
            }
        });
    }

    /**
     * 导出为 MP4（去除 GPS 数据）
     * @returns {Blob} 纯 MP4 Blob
     */
    exportMP4() {
        if (!this.parsedData) return null;
        const mp4Buffer = MP5Parser.stripMP5Boxes(this.parsedData.buffer || null);
        return new Blob([mp4Buffer], { type: 'video/mp4' });
    }

    /**
     * 导出为 GPX
     * @returns {string} GPX XML
     */
    exportGPX() {
        if (!this.parsedData) return '';
        return MP5Parser.toGPX(this.parsedData);
    }

    /**
     * 导出为 GeoJSON
     * @returns {Object} GeoJSON 对象
     */
    exportGeoJSON() {
        if (!this.parsedData) return null;
        return MP5Parser.toGeoJSON(this.parsedData);
    }

    /**
     * 截图（视频当前帧 + 地图）
     */
    screenshot() {
        const canvas = document.createElement('canvas');
        const video = this.videoElement;
        canvas.width = video.videoWidth || 1920;
        canvas.height = video.videoHeight || 1080;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0);

        return new Promise((resolve) => {
            canvas.toBlob((blob) => {
                resolve(blob);
            }, 'image/png');
        });
    }

    /**
     * 获取轨迹统计信息
     */
    getStats() {
        if (!this.syncEngine) return null;
        return this.syncEngine.getStats();
    }

    /**
     * 销毁播放器
     */
    destroy() {
        if (this.videoBlobUrl) {
            URL.revokeObjectURL(this.videoBlobUrl);
            this.videoBlobUrl = null;
        }
        if (this.syncEngine) {
            this.syncEngine.destroy();
            this.syncEngine = null;
        }
        if (this.mapManager) {
            this.mapManager.destroy();
            this.mapManager = null;
        }
    }
}

// ============================================================
// MapManager — 地图管理器（基于 Leaflet）
// ============================================================

export class MapManager {
    constructor(container) {
        this.container = container;
        this.map = L.map(container, {
            center: [39.9042, 116.4074],
            zoom: 13,
            zoomControl: true,
            attributionControl: true
        });

        // 默认使用 OpenStreetMap
        this.tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap',
            maxZoom: 19
        }).addTo(this.map);

        this.trackLayer = L.layerGroup().addTo(this.map);
        this.markerLayer = L.layerGroup().addTo(this.map);
        this.heatmapLayer = L.layerGroup().addTo(this.map);

        this.trackLine = null;
        this.playedTrackLine = null;
        this.currentMarker = null;
        this.startMarker = null;
        this.endMarker = null;
        this.poiMarkers = [];
        this.clickCallback = null;

        // 地图点击事件
        this.map.on('click', (e) => {
            if (this.clickCallback) {
                this.clickCallback(e.latlng.lat, e.latlng.lng);
            }
        });
    }

    /**
     * 渲染完整 GPS 轨迹
     */
    renderTrack(gpsEntries) {
        if (!gpsEntries || gpsEntries.length === 0) return;

        const latlngs = gpsEntries.map(e => [e.latitude, e.longitude]);

        // 清除旧轨迹
        this.trackLayer.clearLayers();
        this.markerLayer.clearLayers();

        // 绘制完整轨迹线
        this.trackLine = L.polyline(latlngs, {
            color: '#58a6ff',
            weight: 3,
            opacity: 0.6
        }).addTo(this.trackLayer);

        // 绘制已播放部分（高亮）
        this.playedTrackLine = L.polyline([], {
            color: '#f85149',
            weight: 4,
            opacity: 0.9
        }).addTo(this.trackLayer);

        // 速度热力图（按段着色）
        this._renderSpeedHeatmap(gpsEntries);

        // 起点/终点标记
        const start = latlngs[0];
        const end = latlngs[latlngs.length - 1];

        this.startMarker = L.marker(start, {
            icon: L.divIcon({
                className: 'start-marker',
                html: '🟢',
                iconSize: [24, 24]
            })
        }).addTo(this.markerLayer);
        this.startMarker.bindPopup('起点');

        this.endMarker = L.marker(end, {
            icon: L.divIcon({
                className: 'end-marker',
                html: '🔴',
                iconSize: [24, 24]
            })
        }).addTo(this.markerLayer);
        this.endMarker.bindPopup('终点');

        // 当前位置标记（脉冲圆点）
        this.currentMarker = L.circleMarker(start, {
            radius: 8,
            fillColor: '#f85149',
            fillOpacity: 1,
            color: '#fff',
            weight: 2
        }).addTo(this.markerLayer);

        // 自动适配视野
        this.map.fitBounds(this.trackLine.getBounds(), { padding: [40, 40] });
    }

    /**
     * 渲染速度热力图
     */
    _renderSpeedHeatmap(entries) {
        this.heatmapLayer.clearLayers();

        for (let i = 1; i < entries.length; i++) {
            const prev = entries[i - 1];
            const curr = entries[i];
            const color = SyncEngine.getSpeedColor(curr.speed);

            L.polyline(
                [[prev.latitude, prev.longitude], [curr.latitude, curr.longitude]],
                { color: color, weight: 5, opacity: 0.7 }
            ).addTo(this.heatmapLayer);
        }
    }

    /**
     * 更新当前位置标记
     */
    updateCurrentPosition(lat, lon, data) {
        if (!this.currentMarker) return;

        this.currentMarker.setLatLng([lat, lon]);

        // 平滑移动地图中心
        this.map.panTo([lat, lon], { animate: true, duration: 0.5 });

        // 更新已播放轨迹
        if (this.playedTrackLine && data) {
            const playedPoints = [];
            for (const e of this.gpsEntries || []) {
                if (e.timestamp <= data.timestamp) {
                    playedPoints.push([e.latitude, e.longitude]);
                }
            }
            this.playedTrackLine.setLatLngs(playedPoints);
        }
    }

    /**
     * 渲染 POI 标记
     */
    renderPOIs(pois) {
        for (const poi of pois) {
            const marker = L.marker([poi.latitude, poi.longitude], {
                icon: L.divIcon({
                    className: 'poi-marker',
                    html: '📍',
                    iconSize: [24, 24]
                })
            }).addTo(this.markerLayer);

            marker.bindPopup(
                `<strong>${poi.label || 'POI'}</strong><br>` +
                `时间: ${(poi.timestamp / 1000).toFixed(1)}s<br>` +
                `坐标: ${poi.latitude.toFixed(5)}, ${poi.longitude.toFixed(5)}`
            );

            this.poiMarkers.push(marker);
        }
    }

    /**
     * 设置地图样式
     */
    setMapStyle(style) {
        this.tileLayer.remove();

        switch (style) {
            case 'satellite':
                this.tileLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                    attribution: '© Esri',
                    maxZoom: 19
                });
                break;
            case 'terrain':
                this.tileLayer = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenTopoMap',
                    maxZoom: 17
                });
                break;
            case 'dark':
                this.tileLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                    attribution: '© CartoDB',
                    maxZoom: 19
                });
                break;
            default:
                this.tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap',
                    maxZoom: 19
                });
        }

        this.tileLayer.addTo(this.map);
    }

    /**
     * 注册地图点击回调
     */
    onMapClick(callback) {
        this.clickCallback = callback;
    }

    /**
     * 刷新地图尺寸
     */
    invalidateSize() {
        if (this.map) {
            this.map.invalidateSize();
        }
    }

    /**
     * 销毁地图
     */
    destroy() {
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
    }
}