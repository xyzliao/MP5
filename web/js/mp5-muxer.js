/**
 * MP5 Muxer — 将视频和 GPS 数据封装为 MP5 文件
 *
 * 策略：在已有 MP4 文件末尾追加 gloc/gsyn/gmap box
 * （MP5 向后兼容 MP4，新 box 可追加在 moov 之后、mdat 之前或文件末尾）
 *
 * 对于浏览器 MediaRecorder 生成的 webm/mp4，我们采用简化策略：
 * 1. 将视频数据作为 mdat 内容
 * 2. 构建简化的 moov（或直接使用原始 mp4）
 * 3. 追加 gloc/gsyn box
 */

import { BinaryWriter, BinaryReader,
         writeBoxHeader, patchBoxSize, writeFullBoxHeader,
         writeGlocBox, writeGsynBox, writeGmapBox,
         writePoiEntries, parseBoxes, findBox } from './mp5-box.js';

export class MP5Muxer {
    /**
     * 将 MP4 Blob + GPS 数据封装为 MP5 Blob
     * @param {Blob} mp4Blob - 原始 MP4 视频文件
     * @param {Array} gpsEntries - GPS 轨迹数据
     * @param {Object} syncConfig - 同步规则配置
     * @param {Array} pois - POI 标记数组
     * @returns {Promise<Blob>} MP5 文件 Blob
     */
    static async mux(mp4Blob, gpsEntries, syncConfig = {}, pois = []) {
        const mp4Buffer = await mp4Blob.arrayBuffer();

        // 解析原始 MP4 box 结构
        const boxes = parseBoxes(mp4Buffer);
        const ftypBox = findBox(boxes, 'ftyp');
        const moovBox = findBox(boxes, 'moov');
        const mdatBox = findBox(boxes, 'mdat');

        // 构建 MP5 box
        const writer = new BinaryWriter();

        // 1. 写入 ftyp box (mp5v 品牌)
        MP5Muxer._writeFtyp(writer, ftypBox);

        // 2. 写入原始 moov box（保留视频/音频轨道信息）
        if (moovBox) {
            writer.writeBytes(new Uint8Array(mp4Buffer, moovBox.offset, moovBox.size));
        }

        // 3. 写入 gloc box (GPS 轨迹)
        if (gpsEntries && gpsEntries.length > 0) {
            writeGlocBox(writer, gpsEntries);

            // 如果有 POI，追加到 gloc 之后（作为 gpoi box）
            if (pois.length > 0) {
                const poiSizeOffset = writeFullBoxHeader(writer, 'gpoi', 0, 0);
                writePoiEntries(writer, pois);
                patchBoxSize(writer, poiSizeOffset);
            }
        }

        // 4. 写入 gsyn box (同步规则)
        writeGsynBox(writer, {
            syncMode: syncConfig.syncMode || 0,
            syncOffset: syncConfig.syncOffset || 0,
            interpolation: syncConfig.interpolation || 1,
            defaultView: syncConfig.defaultView || 2,
            videoRatio: syncConfig.videoRatio || 0.5,
            mapStyle: syncConfig.mapStyle || 0,
            showTrajectory: syncConfig.showTrajectory !== false,
            showPoi: syncConfig.showPoi !== false
        });

        // 5. 写入 mdat box (媒体数据)
        if (mdatBox) {
            writer.writeBytes(new Uint8Array(mp4Buffer, mdatBox.offset, mdatBox.size));
        } else {
            // 如果原始文件没有 mdat box（某些 MP4 变体），直接追加全部剩余数据
            writer.writeBytes(new Uint8Array(mp4Buffer));
        }

        return new Blob([writer.getBuffer()], { type: 'video/mp5' });
    }

    /**
     * 写入 MP5 ftyp box
     * 如果原始文件有 ftyp，修改 major_brand 为 mp5v，添加 mp5v 到 compatible_brands
     * 否则创建新的 ftyp
     */
    static _writeFtyp(writer, originalFtyp) {
        const sizeOffset = writeBoxHeader(writer, 'ftyp');

        if (originalFtyp) {
            // 读取原始 ftyp 内容
            const reader = new BinaryReader(originalFtyp.buffer, originalFtyp.dataOffset);
            const origMajor = reader.readFourCC();
            const origMinor = reader.readUint32();
            const origCompat = [];
            while (reader.remaining() >= 4) {
                origCompat.push(reader.readFourCC());
            }

            // 写入 mp5v 品牌
            writer.writeFourCC('mp5v');
            writer.writeUint32(origMinor);

            // 添加兼容品牌
            const compatSet = new Set(['mp5v', 'mp41', 'isom']);
            if (origCompat.includes(origMajor)) compatSet.add(origMajor);
            for (const b of origCompat) compatSet.add(b);

            for (const b of compatSet) {
                writer.writeFourCC(b);
            }
        } else {
            // 创建新的 ftyp
            writer.writeFourCC('mp5v');
            writer.writeUint32(0);
            writer.writeFourCC('mp5v');
            writer.writeFourCC('mp41');
            writer.writeFourCC('isom');
        }

        patchBoxSize(writer, sizeOffset);
    }

    /**
     * 生成示例 MP5 文件（用于测试）
     * 创建一个包含模拟 GPS 轨迹的最小 MP5 文件
     * @param {number} durationSec - 模拟时长（秒）
     * @returns {Promise<Blob>} 示例 MP5 Blob
     */
    static async createSampleMP5(durationSec = 60) {
        // 生成模拟 GPS 轨迹（北京奥林匹克公园附近的一个环形路线）
        const gpsEntries = [];
        const sampleRate = 1; // 1Hz
        const startTime = Date.now();

        // 起点坐标
        const centerLat = 39.9912;
        const centerLon = 116.3974;
        const radius = 0.003; // 约300米

        for (let i = 0; i < durationSec * sampleRate; i++) {
            const t = i / sampleRate;
            const angle = (t / durationSec) * Math.PI * 2; // 环形

            // 加入一些随机波动
            const r = radius * (1 + 0.1 * Math.sin(t * 0.5));
            const lat = centerLat + r * Math.cos(angle);
            const lon = centerLon + r * Math.sin(angle);

            gpsEntries.push({
                timestamp: t * 1000,  // 毫秒
                latitude: lat,
                longitude: lon,
                altitude: 45 + 5 * Math.sin(t * 0.3),
                accuracy: 5,
                heading: ((angle * 180 / Math.PI) + 360) % 360,
                speed: 15 + 5 * Math.sin(t * 0.5) // 15±5 km/h
            });
        }

        // POI 标记
        const pois = [
            { timestamp: 5000, latitude: centerLat + radius, longitude: centerLon, label: '起点', type: 'poi' },
            { timestamp: durationSec * 500, latitude: centerLat - radius, longitude: centerLon, label: '对面', type: 'poi' }
        ];

        // 创建一个最小的 MP4 buffer（空的 ftyp + moov + mdat）
        const mp4Writer = new BinaryWriter();

        // ftyp
        const ftypOffset = writeBoxHeader(mp4Writer, 'ftyp');
        mp4Writer.writeFourCC('isom');
        mp4Writer.writeUint32(0);
        mp4Writer.writeFourCC('isom');
        mp4Writer.writeFourCC('mp41');
        patchBoxSize(mp4Writer, ftypOffset);

        // moov (空的最小 moov)
        const moovOffset = writeBoxHeader(mp4Writer, 'moov');
        // mvhd
        const mvhdOffset = writeFullBoxHeader(mp4Writer, 'mvhd', 0, 0);
        mp4Writer.writeUint32(0); // creation_time
        mp4Writer.writeUint32(0); // modification_time
        mp4Writer.writeUint32(1000); // timescale (ms)
        mp4Writer.writeUint32(durationSec * 1000); // duration (ms)
        mp4Writer.writeUint32(0x00010000); // rate = 1.0
        mp4Writer.writeUint16(0x0100); // volume = 1.0
        mp4Writer.writeUint16(0); // reserved
        mp4Writer.writeUint32(0); mp4Writer.writeUint32(0); // reserved
        mp4Writer.writeUint32(0); mp4Writer.writeUint32(0); // reserved
        // matrix (3x3 identity, 9 * 4 = 36 bytes)
        mp4Writer.writeUint32(0x00010000); mp4Writer.writeUint32(0); mp4Writer.writeUint32(0);
        mp4Writer.writeUint32(0); mp4Writer.writeUint32(0x00010000); mp4Writer.writeUint32(0);
        mp4Writer.writeUint32(0); mp4Writer.writeUint32(0); mp4Writer.writeUint32(0x40000000);
        // pre_defined (6 * 4 = 24 bytes)
        for (let i = 0; i < 6; i++) mp4Writer.writeUint32(0);
        mp4Writer.writeUint32(2); // next_track_ID
        patchBoxSize(mp4Writer, mvhdOffset);
        patchBoxSize(mp4Writer, moovOffset);

        // mdat (空)
        const mdatOffset = writeBoxHeader(mp4Writer, 'mdat');
        // 写入一些占位视频数据
        const dummyData = new Uint8Array(1024);
        mp4Writer.writeBytes(dummyData);
        patchBoxSize(mp4Writer, mdatOffset);

        const mp4Blob = new Blob([mp4Writer.getBuffer()], { type: 'video/mp4' });

        // 封装为 MP5
        return MP5Muxer.mux(mp4Blob, gpsEntries, {
            syncMode: 0,
            interpolation: 1,
            defaultView: 2,
            videoRatio: 0.5,
            mapStyle: 0,
            showTrajectory: true,
            showPoi: true
        }, pois);
    }
}