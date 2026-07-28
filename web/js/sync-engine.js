/**
 * Sync Engine — 视频↔地图双向同步引擎
 *
 * 职责:
 * 1. 时间→位置：视频播放进度变化时，计算当前 GPS 坐标并更新地图
 * 2. 位置→时间：用户点击地图时，查找最近 GPS 采样点并跳转视频
 * 3. 插值：支持最近邻、线性、三次样条三种插值模式
 */

export class SyncEngine {
    /**
     * @param {Array} gpsEntries - GPS 轨迹数据（已排序，按 timestamp 升序）
     * @param {Object} syncConfig - 同步规则配置
     * @param {Object} mapManager - 地图管理器实例
     * @param {HTMLVideoElement} videoElement - 视频元素
     */
    constructor(gpsEntries, syncConfig, mapManager, videoElement) {
        this.gpsEntries = gpsEntries || [];
        this.syncConfig = syncConfig || { interpolation: 1, syncOffset: 0 };
        this.mapManager = mapManager;
        this.video = videoElement;

        this.isSyncing = false;
        this.suppressVideoSeek = false; // 防止循环触发

        // 排序 GPS 数据
        if (this.gpsEntries.length > 0) {
            this.gpsEntries.sort((a, b) => a.timestamp - b.timestamp);
        }

        this._bindEvents();
    }

    /**
     * 绑定视频和地图事件
     */
    _bindEvents() {
        if (!this.video) return;

        // 视频→地图：播放进度变化
        this.video.addEventListener('timeupdate', () => {
            if (this.suppressVideoSeek) return;
            this._onVideoTimeChanged(this.video.currentTime * 1000); // 转毫秒
        });

        // 视频→地图：拖动进度条
        this.video.addEventListener('seeked', () => {
            if (this.suppressVideoSeek) return;
            this._onVideoTimeChanged(this.video.currentTime * 1000);
        });

        // 地图→视频：点击地图
        if (this.mapManager) {
            this.mapManager.onMapClick((lat, lon) => {
                this._onMapClicked(lat, lon);
            });
        }
    }

    /**
     * 视频→地图：时间变化时更新地图位置
     * @param {number} timeMs - 当前视频时间（毫秒）
     */
    _onVideoTimeChanged(timeMs) {
        if (this.gpsEntries.length === 0) return;

        // 应用同步偏移
        const adjustedTime = timeMs + (this.syncConfig.syncOffset || 0);

        // 根据 interpolation 模式计算当前位置
        const position = this._getInterpolatedPosition(adjustedTime);
        if (!position) return;

        // 更新地图
        if (this.mapManager) {
            this.mapManager.updateCurrentPosition(position.latitude, position.longitude, position);
        }
    }

    /**
     * 地图→视频：点击地图时跳转视频
     * @param {number} lat - 纬度
     * @param {number} lon - 经度
     */
    _onMapClicked(lat, lon) {
        if (this.gpsEntries.length === 0) return;

        // 查找距离点击位置最近的 GPS 采样点
        const nearest = this._findNearestByPosition(lat, lon);
        if (!nearest) return;

        // 跳转视频到对应时间戳
        const targetTime = (nearest.timestamp - (this.syncConfig.syncOffset || 0)) / 1000; // 转秒

        this.suppressVideoSeek = true;
        this.video.currentTime = Math.max(0, targetTime);
        this.video.play().catch(() => {});

        setTimeout(() => {
            this.suppressVideoSeek = false;
        }, 300);
    }

    /**
     * 根据时间获取插值后的 GPS 位置
     * @param {number} timeMs - 时间（毫秒）
     * @returns {Object|null} 位置信息
     */
    _getInterpolatedPosition(timeMs) {
        const entries = this.gpsEntries;
        if (entries.length === 0) return null;

        // 如果时间在第一个采样点之前
        if (timeMs <= entries[0].timestamp) return entries[0];

        // 如果时间在最后一个采样点之后
        if (timeMs >= entries[entries.length - 1].timestamp) return entries[entries.length - 1];

        // 二分查找最近的两个采样点
        let lo = 0, hi = entries.length - 1;
        while (lo < hi - 1) {
            const mid = Math.floor((lo + hi) / 2);
            if (entries[mid].timestamp <= timeMs) {
                lo = mid;
            } else {
                hi = mid;
            }
        }

        const prev = entries[lo];
        const next = entries[hi];
        const t = (timeMs - prev.timestamp) / (next.timestamp - prev.timestamp);

        const mode = this.syncConfig.interpolation || 1;

        switch (mode) {
            case 0: // 最近邻
                return t < 0.5 ? prev : next;

            case 1: // 线性插值
                return {
                    timestamp: timeMs,
                    latitude: prev.latitude + (next.latitude - prev.latitude) * t,
                    longitude: prev.longitude + (next.longitude - prev.longitude) * t,
                    altitude: prev.altitude + (next.altitude - prev.altitude) * t,
                    accuracy: prev.accuracy,
                    heading: prev.heading + (next.heading - prev.heading) * t,
                    speed: prev.speed + (next.speed - prev.speed) * t
                };

            case 2: // 三次样条（简化版：使用前后4个点做 Catmull-Rom 插值）
                return this._catmullRomInterpolate(lo, timeMs);

            default:
                return this._getInterpolatedPosition(timeMs);
        }
    }

    /**
     * Catmull-Rom 样条插值
     */
    _catmullRomInterpolate(idx, timeMs) {
        const entries = this.gpsEntries;
        const p0 = entries[Math.max(0, idx - 1)];
        const p1 = entries[idx];
        const p2 = entries[idx + 1];
        const p3 = entries[Math.min(entries.length - 1, idx + 2)];

        const t = (timeMs - p1.timestamp) / (p2.timestamp - p1.timestamp);
        const t2 = t * t;
        const t3 = t2 * t;

        const catmullRom = (a, b, c, d) => {
            return 0.5 * ((2 * b) + (-a + c) * t +
                (2 * a - 5 * b + 4 * c - d) * t2 +
                (-a + 3 * b - 3 * c + d) * t3);
        };

        return {
            timestamp: timeMs,
            latitude: catmullRom(p0.latitude, p1.latitude, p2.latitude, p3.latitude),
            longitude: catmullRom(p0.longitude, p1.longitude, p2.longitude, p3.longitude),
            altitude: catmullRom(p0.altitude, p1.altitude, p2.altitude, p3.altitude),
            accuracy: p1.accuracy,
            heading: p1.heading,
            speed: p1.speed
        };
    }

    /**
     * 根据经纬度查找最近的 GPS 采样点
     * @param {number} lat - 纬度
     * @param {number} lon - 经度
     * @returns {Object|null} 最近的采样点
     */
    _findNearestByPosition(lat, lon) {
        let minDist = Infinity;
        let nearest = null;

        for (const entry of this.gpsEntries) {
            const dist = this._haversine(lat, lon, entry.latitude, entry.longitude);
            if (dist < minDist) {
                minDist = dist;
                nearest = entry;
            }
        }

        return nearest;
    }

    /**
     * Haversine 距离公式（计算两点间球面距离，单位：米）
     */
    _haversine(lat1, lon1, lat2, lon2) {
        const R = 6371000; // 地球半径(米)
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) ** 2 +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) ** 2;
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    /**
     * 获取速度热力图颜色
     * @param {number} speed - 速度(km/h)
     * @returns {string} 颜色值
     */
    static getSpeedColor(speed) {
        if (speed < 5) return '#3b82f6';       // 蓝色（步行/停留）
        if (speed < 20) return '#22c55e';      // 绿色（慢速）
        if (speed < 60) return '#eab308';      // 黄色（城市）
        if (speed < 120) return '#f97316';     // 橙色（高速）
        return '#ef4444';                       // 红色（极速）
    }

    /**
     * 计算轨迹统计信息
     * @returns {Object} 统计信息
     */
    getStats() {
        const entries = this.gpsEntries;
        if (entries.length === 0) return { distance: 0, maxSpeed: 0, avgSpeed: 0, duration: 0 };

        let totalDist = 0;
        let maxSpeed = 0;
        let totalSpeed = 0;

        for (let i = 0; i < entries.length; i++) {
            maxSpeed = Math.max(maxSpeed, entries[i].speed);
            totalSpeed += entries[i].speed;
            if (i > 0) {
                totalDist += this._haversine(
                    entries[i - 1].latitude, entries[i - 1].longitude,
                    entries[i].latitude, entries[i].longitude
                );
            }
        }

        const duration = entries.length > 1
            ? (entries[entries.length - 1].timestamp - entries[0].timestamp) / 1000
            : 0;

        return {
            distance: totalDist / 1000, // km
            maxSpeed: maxSpeed,
            avgSpeed: totalSpeed / entries.length,
            duration: duration, // 秒
            pointCount: entries.length
        };
    }

    /**
     * 销毁同步引擎
     */
    destroy() {
        this.gpsEntries = [];
        this.mapManager = null;
        this.video = null;
    }
}