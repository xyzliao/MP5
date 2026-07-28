/**
 * File Manager — MP5 文件管理模块
 *
 * 职责:
 * 1. 管理本地 MP5 文件列表（IndexedDB 存储）
 * 2. 文件导入/导出
 * 3. 文件分享
 * 4. 批量管理
 */

const DB_NAME = 'MP5RecorderDB';
const DB_VERSION = 1;
const STORE_NAME = 'mp5files';

export class FileManager {
    constructor() {
        this.db = null;
    }

    /**
     * 初始化 IndexedDB
     */
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);

            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                resolve();
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    const store = db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
                    store.createIndex('name', 'name', { unique: false });
                    store.createIndex('createdAt', 'createdAt', { unique: false });
                }
            };
        });
    }

    /**
     * 保存 MP5 文件
     * @param {Blob} blob - MP5 文件 Blob
     * @param {string} name - 文件名
     * @param {Object} metadata - 元数据
     * @returns {Promise<number>} 文件 ID
     */
    async saveFile(blob, name, metadata = {}) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const tx = this.db.transaction([STORE_NAME], 'readwrite');
            const store = tx.objectStore(STORE_NAME);

            const record = {
                name: name,
                blob: blob,
                size: blob.size,
                createdAt: Date.now(),
                duration: metadata.duration || 0,
                gpsCount: metadata.gpsCount || 0,
                poiCount: metadata.poiCount || 0,
                latitude: metadata.latitude,
                longitude: metadata.longitude,
                distance: metadata.distance || 0
            };

            const request = store.add(record);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 获取所有文件列表
     * @returns {Promise<Array>} 文件列表
     */
    async listFiles() {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const tx = this.db.transaction([STORE_NAME], 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const request = store.getAll();

            request.onsuccess = () => {
                const files = request.result.map(f => ({
                    id: f.id,
                    name: f.name,
                    size: f.size,
                    createdAt: f.createdAt,
                    duration: f.duration,
                    gpsCount: f.gpsCount,
                    poiCount: f.poiCount,
                    latitude: f.latitude,
                    longitude: f.longitude,
                    distance: f.distance
                }));
                // 按创建时间降序
                files.sort((a, b) => b.createdAt - a.createdAt);
                resolve(files);
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 获取文件 Blob
     * @param {number} id - 文件 ID
     * @returns {Promise<Blob>} 文件 Blob
     */
    async getFile(id) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const tx = this.db.transaction([STORE_NAME], 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const request = store.get(id);

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 删除文件
     * @param {number} id - 文件 ID
     */
    async deleteFile(id) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const tx = this.db.transaction([STORE_NAME], 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            const request = store.delete(id);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 导入文件
     * @param {File} file - 用户选择的文件
     * @returns {Promise<number>} 文件 ID
     */
    async importFile(file) {
        const metadata = {};
        try {
            const buffer = await file.arrayBuffer();
            const { MP5Parser } = await import('./mp5-parser.js');
            const parsed = MP5Parser.parse(buffer);
            metadata.gpsCount = parsed.gpsEntries.length;
            metadata.duration = parsed.durationMs || 0;
            if (parsed.gpsEntries.length > 0) {
                const first = parsed.gpsEntries[0];
                metadata.latitude = first.latitude;
                metadata.longitude = first.longitude;
            }
        } catch (e) {
            console.warn('解析文件失败，按普通文件导入:', e);
        }

        return this.saveFile(file, file.name, metadata);
    }

    /**
     * 导出文件
     * @param {Blob} blob - 文件 Blob
     * @param {string} filename - 文件名
     */
    exportFile(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    /**
     * 分享文件（使用 Web Share API）
     * @param {Blob} blob - 文件 Blob
     * @param {string} filename - 文件名
     */
    async shareFile(blob, filename) {
        if (navigator.share && navigator.canShare) {
            const file = new File([blob], filename, { type: blob.type });
            if (navigator.canShare({ files: [file] })) {
                try {
                    await navigator.share({
                        files: [file],
                        title: 'MP5录播器',
                        text: `分享MP5文件: ${filename}`
                    });
                    return true;
                } catch (err) {
                    if (err.name !== 'AbortError') {
                        console.error('分享失败:', err);
                    }
                    return false;
                }
            }
        }
        // 回退到下载
        this.exportFile(blob, filename);
        return true;
    }

    /**
     * 格式化文件大小
     */
    static formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
    }

    /**
     * 格式化时长
     */
    static formatDuration(ms) {
        const totalSec = Math.floor(ms / 1000);
        const h = Math.floor(totalSec / 3600);
        const m = Math.floor((totalSec % 3600) / 60);
        const s = totalSec % 60;
        if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        return `${m}:${s.toString().padStart(2, '0')}`;
    }

    /**
     * 格式化日期
     */
    static formatDate(timestamp) {
        const d = new Date(timestamp);
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const fileDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());

        if (fileDate.getTime() === today.getTime()) {
            return '今天 ' + d.toTimeString().slice(0, 5);
        }
        if (fileDate.getTime() === today.getTime() - 86400000) {
            return '昨天 ' + d.toTimeString().slice(0, 5);
        }
        return `${d.getMonth() + 1}月${d.getDate()}日`;
    }
}