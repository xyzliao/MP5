/**
 * MP5 文件解析器
 * 解析 MP5 文件，提取视频、音频轨道和 GPS 轨迹、同步规则等元数据
 */

import { BinaryReader, parseBoxes, findBox, findAllBoxes,
         parseGlocBox, parseGsynBox, parseGmapBox } from './mp5-box.js';

export class MP5Parser {
    /**
     * 解析 MP5 文件
     * @param {ArrayBuffer} buffer - MP5 文件内容
     * @returns {Object} 解析结果
     */
    static parse(buffer) {
        const boxes = parseBoxes(buffer);
        const result = {
            isMP5: false,
            ftyp: null,
            moov: null,
            mvhd: null,
            tracks: [],
            gloc: null,    // GPS轨迹
            gmap: null,    // 嵌入地图
            gsyn: null,    // 同步规则
            gpsEntries: [],
            syncConfig: null,
            mapData: null,
            duration: 0,
            timescale: 0
        };

        // 解析 ftyp
        const ftyp = findBox(boxes, 'ftyp');
        if (ftyp) {
            const reader = new BinaryReader(ftyp.buffer, ftyp.dataOffset);
            const majorBrand = reader.readFourCC();
            const minorVersion = reader.readUint32();
            const compatibleBrands = [];
            while (reader.remaining() >= 4) {
                compatibleBrands.push(reader.readFourCC());
            }
            result.ftyp = { majorBrand, minorVersion, compatibleBrands };
            result.isMP5 = majorBrand === 'mp5v' || compatibleBrands.includes('mp5v');
        }

        // 解析 moov
        const moov = findBox(boxes, 'moov');
        if (moov) {
            result.moov = moov;

            // 解析 mvhd (电影头)
            const mvhd = findBox(moov.children, 'mvhd');
            if (mvhd) {
                const mvhdOffset = mvhd.payloadOffset !== undefined
                    ? mvhd.payloadOffset - mvhd.offset
                    : 4;
                const reader = new BinaryReader(mvhd.buffer, mvhdOffset);
                const version = mvhd.version;

                if (version === 1) {
                    reader.readUint64(); // creation_time
                    reader.readUint64(); // modification_time
                    result.timescale = reader.readUint32();
                    result.duration = reader.readUint64(); // 以 timescale 为单位
                } else {
                    reader.readUint32(); // creation_time
                    reader.readUint32(); // modification_time
                    result.timescale = reader.readUint32();
                    result.duration = reader.readUint32();
                }
                result.durationMs = result.timescale > 0
                    ? (result.duration / result.timescale) * 1000
                    : 0;
            }

            // 解析 trak (轨道)
            const traks = findAllBoxes(moov.children, 'trak');
            for (const trak of traks) {
                const track = MP5Parser._parseTrak(trak);
                if (track) result.tracks.push(track);
            }
        }

        // 解析 gloc (GPS轨迹) — MP5 扩展
        const gloc = findBox(boxes, 'gloc');
        if (gloc) {
            result.gloc = gloc;
            result.gpsEntries = parseGlocBox(gloc);
        }

        // 解析 gsyn (同步规则) — MP5 扩展
        const gsyn = findBox(boxes, 'gsyn');
        if (gsyn) {
            result.gsyn = gsyn;
            result.syncConfig = parseGsynBox(gsyn);
        }

        // 解析 gmap (嵌入地图) — MP5 扩展
        const gmap = findBox(boxes, 'gmap');
        if (gmap) {
            result.gmap = gmap;
            result.mapData = parseGmapBox(gmap);
        }

        return result;
    }

    /**
     * 解析单个 trak box
     */
    static _parseTrak(trak) {
        const tkhd = findBox(trak.children, 'tkhd');
        const mdia = findBox(trak.children, 'mdia');

        if (!tkhd || !mdia) return null;

        const track = {
            id: 0,
            type: 'unknown',
            duration: 0,
            timescale: 0,
            width: 0,
            height: 0
        };

        // 解析 tkhd
        const tkhdOffsetInSlice = tkhd.payloadOffset !== undefined
            ? tkhd.payloadOffset - tkhd.offset
            : 4;
        const reader = new BinaryReader(tkhd.buffer, tkhdOffsetInSlice);
        const version = tkhd.version;

        if (version === 1) {
            reader.readUint64(); // creation_time
            reader.readUint64(); // modification_time
            track.id = reader.readUint32();
            reader.readUint32(); // reserved
            track.duration = reader.readUint64();
        } else {
            reader.readUint32(); // creation_time
            reader.readUint32(); // modification_time
            track.id = reader.readUint32();
            reader.readUint32(); // reserved
            track.duration = reader.readUint32();
        }

        // 解析 mdia -> mdhd (获取 timescale)
        const mdhd = findBox(mdia.children, 'mdhd');
        if (mdhd) {
            const mdhdOffset = mdhd.payloadOffset !== undefined
                ? mdhd.payloadOffset - mdhd.offset
                : 4;
            const r = new BinaryReader(mdhd.buffer, mdhdOffset);
            const v = mdhd.version;
            if (v === 1) {
                r.readUint64(); r.readUint64();
                track.timescale = r.readUint32();
                track.duration = r.readUint64();
            } else {
                r.readUint32(); r.readUint32();
                track.timescale = r.readUint32();
                track.duration = r.readUint32();
            }
        }

        // 解析 mdia -> hdlr (获取轨道类型)
        const hdlr = findBox(mdia.children, 'hdlr');
        if (hdlr) {
            const r = new BinaryReader(hdlr.buffer, hdlr.dataOffset);
            r.readUint8(); // version
            r.readUint8(); r.readUint8(); r.readUint8(); // flags
            r.readUint32(); // pre_defined
            const handlerType = r.readFourCC();
            track.type = handlerType === 'vide' ? 'video'
                       : handlerType === 'soun' ? 'audio'
                       : handlerType === 'meta' ? 'metadata'
                       : handlerType;
        }

        // 解析视频轨道的尺寸
        if (track.type === 'video') {
            // 从 tkhd 中读取 width/height
            const tkhdReader = new BinaryReader(tkhd.buffer, tkhdOffsetInSlice);
            if (version === 0) {
                tkhdReader.skip(80); // 跳到 width 字段
            } else {
                tkhdReader.skip(96);
            }
            // width 和 height 是 16.16 定点数
            track.width = tkhdReader.readUint32() / 65536;
            track.height = tkhdReader.readUint32() / 65536;
        }

        return track;
    }

    /**
     * 从 MP5 文件中提取纯 MP4 数据（去除 gloc/gmap/gsyn box）
     * @param {ArrayBuffer} buffer - MP5 文件内容
     * @returns {ArrayBuffer} 纯 MP4 文件
     */
    static stripMP5Boxes(buffer) {
        const boxes = parseBoxes(buffer);
        const mp5BoxTypes = ['gloc', 'gmap', 'gsyn', 'gpoi'];

        // 记录原始 mdat 数据偏移
        const origMdat = findBox(boxes, 'mdat');
        const origMdatDataOffset = origMdat ? origMdat.dataOffset : 0;

        // 收集需要移除的 box 的字节范围
        const rangesToRemove = [];
        for (const box of boxes) {
            if (mp5BoxTypes.includes(box.type)) {
                rangesToRemove.push({ start: box.offset, end: box.offset + box.size });
            }
        }

        if (rangesToRemove.length === 0) {
            return buffer; // 没有 MP5 box，已经是纯 MP4
        }

        // 构建新的 buffer，跳过 MP5 box
        const result = new Uint8Array(buffer.byteLength - rangesToRemove.reduce((s, r) => s + (r.end - r.start), 0));
        let readOffset = 0;
        let writeOffset = 0;

        for (const range of rangesToRemove.sort((a, b) => a.start - b.start)) {
            // 复制 range 之前的数据
            const chunk = new Uint8Array(buffer, readOffset, range.start - readOffset);
            result.set(chunk, writeOffset);
            writeOffset += chunk.length;
            readOffset = range.end;
        }

        // 复制最后一部分
        if (readOffset < buffer.byteLength) {
            const chunk = new Uint8Array(buffer, readOffset, buffer.byteLength - readOffset);
            result.set(chunk, writeOffset);
        }

        const strippedBuffer = result.buffer;

        // 修正 stco/co64 偏移量（mdat 位置前移了）
        const newBoxes = parseBoxes(strippedBuffer);
        const newMdat = findBox(newBoxes, 'mdat');
        const newMdatDataOffset = newMdat ? newMdat.dataOffset : 0;
        const delta = newMdatDataOffset - origMdatDataOffset;
        if (delta !== 0) {
            MP5Parser._fixStcoOffsets(strippedBuffer, delta);
        }

        return strippedBuffer;
    }

    /**
     * 修正 moov 中 stco/co64 表的绝对偏移量
     */
    static _fixStcoOffsets(buffer, delta) {
        if (delta === 0) return;

        const boxes = parseBoxes(buffer);
        const moov = findBox(boxes, 'moov');
        if (!moov) return;

        const stcoBoxes = [];
        function findStcoBoxes(boxes) {
            for (const box of boxes) {
                if (box.type === 'stco' || box.type === 'co64') stcoBoxes.push(box);
                if (box.children) findStcoBoxes(box.children);
            }
        }
        findStcoBoxes(moov.children);

        if (stcoBoxes.length === 0) return;

        const view = new DataView(buffer);

        for (const stco of stcoBoxes) {
            const payloadStart = stco.offset + 12;
            const entryCount = view.getUint32(payloadStart);

            if (stco.type === 'stco') {
                for (let i = 0; i < entryCount; i++) {
                    const pos = payloadStart + 4 + i * 4;
                    view.setUint32(pos, (view.getUint32(pos) + delta) >>> 0);
                }
            } else if (stco.type === 'co64') {
                for (let i = 0; i < entryCount; i++) {
                    const pos = payloadStart + 4 + i * 8;
                    const hi = view.getUint32(pos);
                    const lo = view.getUint32(pos + 4);
                    const oldVal = hi * 0x100000000 + lo;
                    const newVal = oldVal + delta;
                    view.setUint32(pos, Math.floor(newVal / 0x100000000) >>> 0);
                    view.setUint32(pos + 4, newVal & 0xFFFFFFFF);
                }
            }
        }
    }

    /**
     * 提取 GPS 轨迹为 GPX 格式
     * @param {Object} parsed - parse() 的结果
     * @returns {string} GPX XML
     */
    static toGPX(parsed) {
        const entries = parsed.gpsEntries || [];
        let gpx = '<?xml version="1.0" encoding="UTF-8"?>\n';
        gpx += '<gpx version="1.1" creator="MP5录播器" xmlns="http://www.topografix.com/GPX/1/1">\n';
        gpx += '  <metadata>\n';
        gpx += '    <name>MP5 GPS Track</name>\n';
        gpx += `    <time>${new Date().toISOString()}</time>\n`;
        gpx += '  </metadata>\n';
        gpx += '  <trk>\n';
        gpx += '    <name>MP5 Track</name>\n';
        gpx += '    <trkseg>\n';

        for (const e of entries) {
            const time = new Date(e.timestamp).toISOString();
            gpx += `      <trkpt lat="${e.latitude.toFixed(7)}" lon="${e.longitude.toFixed(7)}">\n`;
            gpx += `        <ele>${e.altitude.toFixed(1)}</ele>\n`;
            gpx += `        <time>${time}</time>\n`;
            if (e.speed > 0) {
                gpx += `        <extensions><speed>${(e.speed / 3.6).toFixed(2)}</speed></extensions>\n`;
            }
            gpx += `      </trkpt>\n`;
        }

        gpx += '    </trkseg>\n';
        gpx += '  </trk>\n';
        gpx += '</gpx>\n';

        return gpx;
    }

    /**
     * 提取 GPS 轨迹为 GeoJSON 格式
     * @param {Object} parsed - parse() 的结果
     * @returns {Object} GeoJSON 对象
     */
    static toGeoJSON(parsed) {
        const entries = parsed.gpsEntries || [];
        const coordinates = entries.map(e => [e.longitude, e.altitude, e.altitude]);

        return {
            type: 'FeatureCollection',
            features: [{
                type: 'Feature',
                properties: {
                    name: 'MP5 Track',
                    creator: 'MP5录播器',
                    pointCount: entries.length
                },
                geometry: {
                    type: 'LineString',
                    coordinates: entries.map(e => [e.longitude, e.latitude, e.altitude])
                }
            }]
        };
    }
}