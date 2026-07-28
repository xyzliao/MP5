/**
 * MP5 Box 编解码工具
 * 基于 ISO BMFF (ISO 14496-12) 规范，实现 Box 的二进制读写
 *
 * MP5 扩展 Box 类型:
 *   gloc - GPS坐标轨迹
 *   gmap - 嵌入地图数据（可选）
 *   gsyn - 同步规则
 */

// ============================================================
// 二进制读写工具
// ============================================================

export class BinaryReader {
    constructor(buffer, offset = 0) {
        this.view = new DataView(buffer);
        this.offset = offset;
        this.length = buffer.byteLength;
    }

    readUint8() {
        const v = this.view.getUint8(this.offset);
        this.offset += 1;
        return v;
    }

    readUint16() {
        const v = this.view.getUint16(this.offset);
        this.offset += 2;
        return v;
    }

    readUint32() {
        const v = this.view.getUint32(this.offset);
        this.offset += 4;
        return v;
    }

    readUint64() {
        const hi = this.view.getUint32(this.offset);
        const lo = this.view.getUint32(this.offset + 4);
        this.offset += 8;
        return hi * 0x100000000 + lo;
    }

    readInt32() {
        const v = this.view.getInt32(this.offset);
        this.offset += 4;
        return v;
    }

    readInt64() {
        const hi = this.view.getInt32(this.offset);
        const lo = this.view.getUint32(this.offset + 4);
        this.offset += 8;
        return hi * 0x100000000 + lo;
    }

    readFloat32() {
        const v = this.view.getFloat32(this.offset);
        this.offset += 4;
        return v;
    }

    readFourCC() {
        let s = '';
        for (let i = 0; i < 4; i++) {
            s += String.fromCharCode(this.readUint8());
        }
        return s;
    }

    readBytes(n) {
        const bytes = new Uint8Array(this.view.buffer, this.view.byteOffset + this.offset, n);
        this.offset += n;
        return bytes;
    }

    readRemaining() {
        return this.readBytes(this.length - this.offset);
    }

    seek(offset) {
        this.offset = offset;
    }

    skip(n) {
        this.offset += n;
    }

    remaining() {
        return this.length - this.offset;
    }
}

export class BinaryWriter {
    constructor() {
        this.buffer = new ArrayBuffer(1024 * 1024); // 1MB initial
        this.view = new DataView(this.buffer);
        this.offset = 0;
    }

    _ensure(size) {
        if (this.offset + size > this.buffer.byteLength) {
            const newBuf = new ArrayBuffer(Math.max(this.buffer.byteLength * 2, this.offset + size));
            new Uint8Array(newBuf).set(new Uint8Array(this.buffer, 0, this.offset));
            this.buffer = newBuf;
            this.view = new DataView(this.buffer);
        }
    }

    writeUint8(v) {
        this._ensure(1);
        this.view.setUint8(this.offset, v & 0xFF);
        this.offset += 1;
    }

    writeUint16(v) {
        this._ensure(2);
        this.view.setUint16(this.offset, v & 0xFFFF);
        this.offset += 2;
    }

    writeUint32(v) {
        this._ensure(4);
        this.view.setUint32(this.offset, v >>> 0);
        this.offset += 4;
    }

    writeUint64(v) {
        this._ensure(8);
        const hi = Math.floor(v / 0x100000000);
        const lo = v & 0xFFFFFFFF;
        this.view.setUint32(this.offset, hi >>> 0);
        this.view.setUint32(this.offset + 4, lo >>> 0);
        this.offset += 8;
    }

    writeInt32(v) {
        this._ensure(4);
        this.view.setInt32(this.offset, v);
        this.offset += 4;
    }

    writeInt64(v) {
        this._ensure(8);
        const hi = Math.floor(v / 0x100000000);
        const lo = v & 0xFFFFFFFF;
        this.view.setInt32(this.offset, hi);
        this.view.setUint32(this.offset + 4, lo >>> 0);
        this.offset += 8;
    }

    writeFloat32(v) {
        this._ensure(4);
        this.view.setFloat32(this.offset, v);
        this.offset += 4;
    }

    writeFourCC(s) {
        for (let i = 0; i < 4; i++) {
            this.writeUint8(s.charCodeAt(i) || 0);
        }
    }

    writeBytes(bytes) {
        this._ensure(bytes.length);
        new Uint8Array(this.buffer, this.offset, bytes.length).set(bytes);
        this.offset += bytes.length;
    }

    writeString(s) {
        for (let i = 0; i < s.length; i++) {
            this.writeUint8(s.charCodeAt(i));
        }
    }

    getSize() {
        return this.offset;
    }

    getBuffer() {
        return this.buffer.slice(0, this.offset);
    }

    writeAt(position, value, size) {
        // 用于回写 box size
        if (size === 4) {
            this.view.setUint32(position, value >>> 0);
        } else if (size === 8) {
            const hi = Math.floor(value / 0x100000000);
            const lo = value & 0xFFFFFFFF;
            this.view.setUint32(position, hi >>> 0);
            this.view.setUint32(position + 4, lo >>> 0);
        }
    }
}

// ============================================================
// ISO BMFF Box 读写
// ============================================================

/**
 * 写入一个标准 Box 头部（size + type）
 * 返回 size 字段的偏位置，用于后续回写实际大小
 */
export function writeBoxHeader(writer, type) {
    const sizeOffset = writer.offset;
    writer.writeUint32(0); // placeholder for size
    writer.writeFourCC(type);
    return sizeOffset;
}

/**
 * 回写 Box 的实际大小
 */
export function patchBoxSize(writer, sizeOffset) {
    const totalSize = writer.offset - sizeOffset;
    writer.writeAt(sizeOffset, totalSize, 4);
}

/**
 * 写入 FullBox 头部（size + type + version + flags）
 */
export function writeFullBoxHeader(writer, type, version = 0, flags = 0) {
    const sizeOffset = writeBoxHeader(writer, type);
    writer.writeUint8(version);
    writer.writeUint24(flags);
    return sizeOffset;
}

// BinaryWriter 缺少 writeUint24
BinaryWriter.prototype.writeUint24 = function(v) {
    this.writeUint8((v >> 16) & 0xFF);
    this.writeUint8((v >> 8) & 0xFF);
    this.writeUint8(v & 0xFF);
};

/**
 * 递归解析 ISO BMFF box 结构
 */
export function parseBoxes(buffer, start = 0, end = buffer.byteLength) {
    const reader = new BinaryReader(buffer, start);
    const boxes = [];

    while (reader.remaining() >= 8 && reader.offset < end) {
        const boxStart = reader.offset;
        let size = reader.readUint32();
        const type = reader.readFourCC();

        let headerSize = 8;

        if (size === 1) {
            // 64-bit extended size
            size = reader.readUint64();
            headerSize = 16;
        } else if (size === 0) {
            // box extends to end of file
            size = end - boxStart;
        }

        const dataSize = size - headerSize;
        const dataOffset = boxStart + headerSize;

        const box = {
            type,
            offset: boxStart,
            size,
            dataOffset,
            dataSize,
            buffer: buffer.slice(boxStart, boxStart + size)
        };

        // 解析 FullBox 的 version 和 flags
        if (['gloc', 'gmap', 'gsyn', 'mvhd', 'tkhd', 'mdhd'].includes(type)) {
            const r = new BinaryReader(buffer, dataOffset);
            box.version = r.readUint8();
            box.flags = (r.readUint8() << 16) | (r.readUint8() << 8) | r.readUint8();
            box.payloadOffset = dataOffset + 4;
        }

        boxes.push(box);

        // 解析 container box 的子 box
        if (['moov', 'trak', 'mdia', 'minf', 'stbl', 'meta', 'udta'].includes(type)) {
            box.children = parseBoxes(buffer, dataOffset, boxStart + size);
        }

        reader.seek(boxStart + size);
    }

    return boxes;
}

/**
 * 查找指定类型的 box
 */
export function findBox(boxes, type) {
    for (const box of boxes) {
        if (box.type === type) return box;
        if (box.children) {
            const found = findBox(box.children, type);
            if (found) return found;
        }
    }
    return null;
}

/**
 * 查找所有指定类型的 box
 */
export function findAllBoxes(boxes, type) {
    const results = [];
    for (const box of boxes) {
        if (box.type === type) results.push(box);
        if (box.children) {
            results.push(...findAllBoxes(box.children, type));
        }
    }
    return results;
}

// ============================================================
// MP5 自定义 Box 数据结构
// ============================================================

/**
 * gloc Box (GPS坐标轨迹) 数据结构
 * 每个采样点: timestamp(8B) + lat(8B) + lon(8B) + alt(4B) + accuracy(2B) + heading(2B) + speed(2B) = 34B
 */
export const GLOC_ENTRY_SIZE = 34;

export function writeGlocBox(writer, entries) {
    const sizeOffset = writeFullBoxHeader(writer, 'gloc', 0, 0);
    writer.writeUint32(entries.length);

    for (const e of entries) {
        writer.writeUint64(Math.round(e.timestamp));      // 毫秒
        writer.writeInt64(Math.round(e.latitude * 1e7));   // 纬度 ×10^7
        writer.writeInt64(Math.round(e.longitude * 1e7)); // 经度 ×10^7
        writer.writeInt32(Math.round(e.altitude * 10));  // 海拔 ×10
        writer.writeUint16(e.accuracy || 0);              // 精度(米)
        writer.writeUint16(Math.round(e.heading * 10));   // 方向角 ×10
        writer.writeUint16(Math.round(e.speed * 10));     // 速度 ×10
    }

    patchBoxSize(writer, sizeOffset);
}

export function parseGlocBox(box) {
    // payloadOffset is relative to the original full buffer; box.buffer is a slice
    const offsetInSlice = (box.payloadOffset !== undefined)
        ? box.payloadOffset - box.offset
        : 4; // fallback: skip version+flags
    const reader = new BinaryReader(box.buffer, offsetInSlice);
    const entryCount = reader.readUint32();
    const entries = [];

    for (let i = 0; i < entryCount; i++) {
        entries.push({
            timestamp: reader.readUint64(),       // 毫秒
            latitude: reader.readInt64() / 1e7,   // 纬度
            longitude: reader.readInt64() / 1e7, // 经度
            altitude: reader.readInt32() / 10,   // 海拔(米)
            accuracy: reader.readUint16(),        // 精度(米)
            heading: reader.readUint16() / 10,    // 方向角
            speed: reader.readUint16() / 10       // 速度(km/h)
        });
    }

    return entries;
}

/**
 * gsyn Box (同步规则) 数据结构
 */
export function writeGsynBox(writer, config) {
    const sizeOffset = writeFullBoxHeader(writer, 'gsyn', 0, 0);

    writer.writeUint8(config.syncMode || 0);        // 同步模式
    writer.writeInt32(config.syncOffset || 0);       // 同步偏移量(毫秒)
    writer.writeUint8(config.interpolation || 1);    // 插值算法
    writer.writeUint8(config.defaultView || 2);     // 默认视图
    writer.writeFloat32(config.videoRatio || 0.5);  // 视频占比
    writer.writeUint8(config.mapStyle || 0);         // 地图样式
    writer.writeUint8(config.showTrajectory ? 1 : 0); // 显示轨迹
    writer.writeUint8(config.showPoi ? 1 : 0);      // 显示POI

    patchBoxSize(writer, sizeOffset);
}

export function parseGsynBox(box) {
    const offsetInSlice = (box.payloadOffset !== undefined)
        ? box.payloadOffset - box.offset
        : 4;
    const reader = new BinaryReader(box.buffer, offsetInSlice);

    return {
        syncMode: reader.readUint8(),
        syncOffset: reader.readInt32(),
        interpolation: reader.readUint8(),
        defaultView: reader.readUint8(),
        videoRatio: reader.readFloat32(),
        mapStyle: reader.readUint8(),
        showTrajectory: reader.readUint8() === 1,
        showPoi: reader.readUint8() === 1
    };
}

/**
 * gmap Box (嵌入地图数据) 数据结构
 */
export function writeGmapBox(writer, config) {
    const sizeOffset = writeFullBoxHeader(writer, 'gmap', 0, 0);

    writer.writeUint8(config.mapType || 1);     // 1=矢量, 2=栅格
    writer.writeUint8(config.crs || 1);         // 1=WGS84
    writer.writeInt64(Math.round(config.bounds.south * 1e7));
    writer.writeInt64(Math.round(config.bounds.west * 1e7));
    writer.writeInt64(Math.round(config.bounds.north * 1e7));
    writer.writeInt64(Math.round(config.bounds.east * 1e7));
    writer.writeUint32(config.mapData.length);
    writer.writeBytes(config.mapData);

    patchBoxSize(writer, sizeOffset);
}

export function parseGmapBox(box) {
    const offsetInSlice = (box.payloadOffset !== undefined)
        ? box.payloadOffset - box.offset
        : 4;
    const reader = new BinaryReader(box.buffer, offsetInSlice);

    const mapType = reader.readUint8();
    const crs = reader.readUint8();
    const south = reader.readInt64() / 1e7;
    const west = reader.readInt64() / 1e7;
    const north = reader.readInt64() / 1e7;
    const east = reader.readInt64() / 1e7;
    const mapDataSize = reader.readUint32();
    const mapData = reader.readBytes(mapDataSize);

    return {
        mapType,
        crs,
        bounds: { south, west, north, east },
        mapData
    };
}

/**
 * POI 数据结构（存储在 gloc box 的扩展区域）
 */
export function writePoiEntries(writer, pois) {
    writer.writeUint32(pois.length);
    for (const poi of pois) {
        writer.writeUint64(Math.round(poi.timestamp));
        writer.writeInt64(Math.round(poi.latitude * 1e7));
        writer.writeInt64(Math.round(poi.longitude * 1e7));
        // label: 变长字符串，先写长度再写内容
        const labelBytes = new TextEncoder().encode(poi.label || '');
        writer.writeUint16(labelBytes.length);
        writer.writeBytes(labelBytes);
        writer.writeUint8(poi.type ? poi.type.charCodeAt(0) : 0); // poi/marker/bookmark
    }
}

export function parsePoiEntries(buffer, offset) {
    const reader = new BinaryReader(buffer, offset);
    const count = reader.readUint32();
    const pois = [];

    for (let i = 0; i < count; i++) {
        const timestamp = reader.readUint64();
        const latitude = reader.readInt64() / 1e7;
        const longitude = reader.readInt64() / 1e7;
        const labelLen = reader.readUint16();
        const labelBytes = reader.readBytes(labelLen);
        const label = new TextDecoder().decode(labelBytes);
        const typeByte = reader.readUint8();
        const type = typeByte ? String.fromCharCode(typeByte) : 'poi';

        pois.push({ timestamp, latitude, longitude, label, type });
    }

    return pois;
}