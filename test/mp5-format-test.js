/**
 * MP5 格式验证测试 (Node.js)
 *
 * 验证 MP5 Box 的读写、解析、封装流程
 * 运行: node test/mp5-format-test.js
 */

// 由于 mp5-box.js 使用了 ES module export，我们需要简单的 polyfill
// 直接内联关键代码进行测试

import { readFileSync, writeFileSync } from 'fs';

// ============================================================
// BinaryReader/Writer (从 mp5-box.js 提取)
// ============================================================

class BinaryReader {
    constructor(buffer, offset = 0) {
        this.view = new DataView(buffer);
        this.offset = offset;
        this.length = buffer.byteLength;
    }
    readUint8() { const v = this.view.getUint8(this.offset); this.offset += 1; return v; }
    readUint16() { const v = this.view.getUint16(this.offset); this.offset += 2; return v; }
    readUint32() { const v = this.view.getUint32(this.offset); this.offset += 4; return v; }
    readUint64() { const hi = this.view.getUint32(this.offset); const lo = this.view.getUint32(this.offset + 4); this.offset += 8; return hi * 0x100000000 + lo; }
    readInt32() { const v = this.view.getInt32(this.offset); this.offset += 4; return v; }
    readInt64() { const hi = this.view.getInt32(this.offset); const lo = this.view.getUint32(this.offset + 4); this.offset += 8; return hi * 0x100000000 + lo; }
    readFloat32() { const v = this.view.getFloat32(this.offset); this.offset += 4; return v; }
    readFourCC() { let s = ''; for (let i = 0; i < 4; i++) s += String.fromCharCode(this.readUint8()); return s; }
    readBytes(n) { const bytes = new Uint8Array(this.view.buffer, this.view.byteOffset + this.offset, n); this.offset += n; return bytes; }
    seek(offset) { this.offset = offset; }
    skip(n) { this.offset += n; }
    remaining() { return this.length - this.offset; }
}

class BinaryWriter {
    constructor() { this.buffer = new ArrayBuffer(1024 * 1024); this.view = new DataView(this.buffer); this.offset = 0; }
    _ensure(size) { if (this.offset + size > this.buffer.byteLength) { const newBuf = new ArrayBuffer(Math.max(this.buffer.byteLength * 2, this.offset + size)); new Uint8Array(newBuf).set(new Uint8Array(this.buffer, 0, this.offset)); this.buffer = newBuf; this.view = new DataView(this.buffer); } }
    writeUint8(v) { this._ensure(1); this.view.setUint8(this.offset, v & 0xFF); this.offset += 1; }
    writeUint16(v) { this._ensure(2); this.view.setUint16(this.offset, v & 0xFFFF); this.offset += 2; }
    writeUint24(v) { this.writeUint8((v >> 16) & 0xFF); this.writeUint8((v >> 8) & 0xFF); this.writeUint8(v & 0xFF); }
    writeUint32(v) { this._ensure(4); this.view.setUint32(this.offset, v >>> 0); this.offset += 4; }
    writeUint64(v) { this._ensure(8); const hi = Math.floor(v / 0x100000000); const lo = v & 0xFFFFFFFF; this.view.setUint32(this.offset, hi >>> 0); this.view.setUint32(this.offset + 4, lo >>> 0); this.offset += 8; }
    writeInt32(v) { this._ensure(4); this.view.setInt32(this.offset, v); this.offset += 4; }
    writeInt64(v) { this._ensure(8); const hi = Math.floor(v / 0x100000000); const lo = v & 0xFFFFFFFF; this.view.setInt32(this.offset, hi); this.view.setUint32(this.offset + 4, lo >>> 0); this.offset += 8; }
    writeFloat32(v) { this._ensure(4); this.view.setFloat32(this.offset, v); this.offset += 4; }
    writeFourCC(s) { for (let i = 0; i < 4; i++) this.writeUint8(s.charCodeAt(i) || 0); }
    writeBytes(bytes) { this._ensure(bytes.length); new Uint8Array(this.buffer, this.offset, bytes.length).set(bytes); this.offset += bytes.length; }
    getSize() { return this.offset; }
    getBuffer() { return this.buffer.slice(0, this.offset); }
    writeAt(position, value, size) { if (size === 4) this.view.setUint32(position, value >>> 0); else if (size === 8) { const hi = Math.floor(value / 0x100000000); const lo = value & 0xFFFFFFFF; this.view.setUint32(position, hi >>> 0); this.view.setUint32(position + 4, lo >>> 0); } }
}

function writeBoxHeader(writer, type) { const sizeOffset = writer.offset; writer.writeUint32(0); writer.writeFourCC(type); return sizeOffset; }
function patchBoxSize(writer, sizeOffset) { const totalSize = writer.offset - sizeOffset; writer.writeAt(sizeOffset, totalSize, 4); }
function writeFullBoxHeader(writer, type, version = 0, flags = 0) { const sizeOffset = writeBoxHeader(writer, type); writer.writeUint8(version); writer.writeUint24(flags); return sizeOffset; }

const GLOC_ENTRY_SIZE = 34;

function writeGlocBox(writer, entries) {
    const sizeOffset = writeFullBoxHeader(writer, 'gloc', 0, 0);
    writer.writeUint32(entries.length);
    for (const e of entries) {
        writer.writeUint64(Math.round(e.timestamp));
        writer.writeInt64(Math.round(e.latitude * 1e7));
        writer.writeInt64(Math.round(e.longitude * 1e7));
        writer.writeInt32(Math.round(e.altitude * 10));
        writer.writeUint16(e.accuracy || 0);
        writer.writeUint16(Math.round(e.heading * 10));
        writer.writeUint16(Math.round(e.speed * 10));
    }
    patchBoxSize(writer, sizeOffset);
}

function writeGsynBox(writer, config) {
    const sizeOffset = writeFullBoxHeader(writer, 'gsyn', 0, 0);
    writer.writeUint8(config.syncMode || 0);
    writer.writeInt32(config.syncOffset || 0);
    writer.writeUint8(config.interpolation || 1);
    writer.writeUint8(config.defaultView || 2);
    writer.writeFloat32(config.videoRatio || 0.5);
    writer.writeUint8(config.mapStyle || 0);
    writer.writeUint8(config.showTrajectory ? 1 : 0);
    writer.writeUint8(config.showPoi ? 1 : 0);
    patchBoxSize(writer, sizeOffset);
}

function parseBoxes(buffer, start = 0, end = buffer.byteLength) {
    const reader = new BinaryReader(buffer, start);
    const boxes = [];
    while (reader.remaining() >= 8 && reader.offset < end) {
        const boxStart = reader.offset;
        let size = reader.readUint32();
        const type = reader.readFourCC();
        let headerSize = 8;
        if (size === 1) { size = reader.readUint64(); headerSize = 16; }
        else if (size === 0) { size = end - boxStart; }
        const dataSize = size - headerSize;
        const dataOffset = boxStart + headerSize;
        const box = { type, offset: boxStart, size, dataOffset, dataSize, buffer: buffer.slice(boxStart, boxStart + size) };
        if (['gloc', 'gmap', 'gsyn', 'mvhd', 'tkhd', 'mdhd'].includes(type)) {
            const r = new BinaryReader(buffer, dataOffset);
            box.version = r.readUint8();
            box.flags = (r.readUint8() << 16) | (r.readUint8() << 8) | r.readUint8();
            box.payloadOffset = dataOffset + 4;
        }
        boxes.push(box);
        if (['moov', 'trak', 'mdia', 'minf', 'stbl', 'meta', 'udta'].includes(type)) {
            box.children = parseBoxes(buffer, dataOffset, boxStart + size);
        }
        reader.seek(boxStart + size);
    }
    return boxes;
}

function findBox(boxes, type) {
    for (const box of boxes) {
        if (box.type === type) return box;
        if (box.children) { const found = findBox(box.children, type); if (found) return found; }
    }
    return null;
}

function parseGlocBox(box) {
    // payloadOffset is relative to the original full buffer; box.buffer is a slice
    // So we need to compute the offset within the slice
    const offsetInSlice = (box.payloadOffset !== undefined)
        ? box.payloadOffset - box.offset
        : 4; // fallback: skip version+flags
    const reader = new BinaryReader(box.buffer, offsetInSlice);
    const entryCount = reader.readUint32();
    const entries = [];
    for (let i = 0; i < entryCount; i++) {
        entries.push({
            timestamp: reader.readUint64(),
            latitude: reader.readInt64() / 1e7,
            longitude: reader.readInt64() / 1e7,
            altitude: reader.readInt32() / 10,
            accuracy: reader.readUint16(),
            heading: reader.readUint16() / 10,
            speed: reader.readUint16() / 10
        });
    }
    return entries;
}

function parseGsynBox(box) {
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

// ============================================================
// 测试用例
// ============================================================

let passCount = 0;
let failCount = 0;

function assert(condition, message) {
    if (condition) {
        console.log(`  ✅ ${message}`);
        passCount++;
    } else {
        console.log(`  ❌ ${message}`);
        failCount++;
    }
}

function testSection(name) {
    console.log(`\n=== ${name} ===`);
}

// 测试1: BinaryWriter/Reader 基础读写
testSection('BinaryWriter/Reader 基础读写');
{
    const writer = new BinaryWriter();
    writer.writeUint8(0x41);
    writer.writeUint16(0x1234);
    writer.writeUint32(0xDEADBEEF);
    writer.writeUint64(0x0123456789ABCDEF);
    writer.writeInt32(-123456);
    writer.writeInt64(-9999999999);
    writer.writeFloat32(3.14);
    writer.writeFourCC('mp5v');

    const buf = writer.getBuffer();
    const reader = new BinaryReader(buf);

    assert(reader.readUint8() === 0x41, 'writeUint8/readUint8');
    assert(reader.readUint16() === 0x1234, 'writeUint16/readUint16');
    assert(reader.readUint32() === 0xDEADBEEF, 'writeUint32/readUint32');
    assert(reader.readUint64() === 0x0123456789ABCDEF, 'writeUint64/readUint64');
    assert(reader.readInt32() === -123456, 'writeInt32/readInt32');
    assert(reader.readInt64() === -9999999999, 'writeInt64/readInt64');
    assert(Math.abs(reader.readFloat32() - 3.14) < 0.001, 'writeFloat32/readFloat32');
    assert(reader.readFourCC() === 'mp5v', 'writeFourCC/readFourCC');
}

// 测试2: gloc Box 读写
testSection('gloc Box (GPS轨迹) 读写');
{
    const testEntries = [
        { timestamp: 0, latitude: 39.9042, longitude: 116.4074, altitude: 45.5, accuracy: 5, heading: 245.0, speed: 12.3 },
        { timestamp: 1000, latitude: 39.9045, longitude: 116.4080, altitude: 46.0, accuracy: 4, heading: 250.0, speed: 15.0 },
        { timestamp: 2000, latitude: 39.9050, longitude: 116.4090, altitude: 47.0, accuracy: 3, heading: 255.0, speed: 18.5 }
    ];

    const writer = new BinaryWriter();
    writeGlocBox(writer, testEntries);
    const buffer = writer.getBuffer();

    // 验证 box 大小: header(8) + version+flags(4) + entry_count(4) + 3*34 = 8+4+4+102 = 118
    assert(buffer.byteLength === 118, `gloc box 大小 = 118 (实际: ${buffer.byteLength})`);

    // 解析
    const boxes = parseBoxes(buffer);
    assert(boxes.length === 1, '解析出1个box');
    assert(boxes[0].type === 'gloc', 'box类型 = gloc');

    const parsed = parseGlocBox(boxes[0]);
    assert(parsed.length === 3, `解析出3个GPS点 (实际: ${parsed.length})`);

    // 验证数据精度
    assert(parsed[0].latitude === 39.9042, `纬度精度: ${parsed[0].latitude}`);
    assert(parsed[0].longitude === 116.4074, `经度精度: ${parsed[0].longitude}`);
    assert(parsed[0].altitude === 45.5, `海拔精度: ${parsed[0].altitude}`);
    assert(parsed[0].speed === 12.3, `速度精度: ${parsed[0].speed}`);
    assert(parsed[1].timestamp === 1000, `时间戳: ${parsed[1].timestamp}`);
    assert(parsed[2].heading === 255.0, `方向角: ${parsed[2].heading}`);
}

// 测试3: gsyn Box 读写
testSection('gsyn Box (同步规则) 读写');
{
    const config = {
        syncMode: 0,
        syncOffset: 100,
        interpolation: 2,
        defaultView: 4,
        videoRatio: 0.6,
        mapStyle: 1,
        showTrajectory: true,
        showPoi: false
    };

    const writer = new BinaryWriter();
    writeGsynBox(writer, config);
    const buffer = writer.getBuffer();

    // 验证 box 大小: header(8) + version+flags(4) + payload(14) = 26
    assert(buffer.byteLength === 26, `gsyn box 大小 = 26 (实际: ${buffer.byteLength})`);

    const boxes = parseBoxes(buffer);
    assert(boxes[0].type === 'gsyn', 'box类型 = gsyn');

    const parsed = parseGsynBox(boxes[0]);
    assert(parsed.syncMode === 0, `syncMode: ${parsed.syncMode}`);
    assert(parsed.syncOffset === 100, `syncOffset: ${parsed.syncOffset}`);
    assert(parsed.interpolation === 2, `interpolation: ${parsed.interpolation}`);
    assert(parsed.defaultView === 4, `defaultView: ${parsed.defaultView}`);
    assert(Math.abs(parsed.videoRatio - 0.6) < 0.001, `videoRatio: ${parsed.videoRatio}`);
    assert(parsed.mapStyle === 1, `mapStyle: ${parsed.mapStyle}`);
    assert(parsed.showTrajectory === true, `showTrajectory: ${parsed.showTrajectory}`);
    assert(parsed.showPoi === false, `showPoi: ${parsed.showPoi}`);
}

// 测试4: ftyp Box 读写
testSection('ftyp Box (文件类型) 读写');
{
    const writer = new BinaryWriter();
    const sizeOffset = writeBoxHeader(writer, 'ftyp');
    writer.writeFourCC('mp5v');
    writer.writeUint32(0);
    writer.writeFourCC('mp5v');
    writer.writeFourCC('mp41');
    writer.writeFourCC('isom');
    patchBoxSize(writer, sizeOffset);

    const buffer = writer.getBuffer();
    const boxes = parseBoxes(buffer);
    assert(boxes[0].type === 'ftyp', 'box类型 = ftyp');
    assert(boxes[0].size === 28, `ftyp box 大小 = 28 (实际: ${boxes[0].size})`);

    const reader = new BinaryReader(buffer, boxes[0].dataOffset);
    const majorBrand = reader.readFourCC();
    assert(majorBrand === 'mp5v', `major_brand = mp5v (实际: ${majorBrand})`);
}

// 测试5: 完整 MP5 文件结构
testSection('完整 MP5 文件结构');
{
    const writer = new BinaryWriter();

    // ftyp
    const ftypOffset = writeBoxHeader(writer, 'ftyp');
    writer.writeFourCC('mp5v');
    writer.writeUint32(0);
    writer.writeFourCC('mp5v');
    writer.writeFourCC('mp41');
    writer.writeFourCC('isom');
    patchBoxSize(writer, ftypOffset);

    // moov (空)
    const moovOffset = writeBoxHeader(writer, 'moov');
    // mvhd
    const mvhdOffset = writeFullBoxHeader(writer, 'mvhd', 0, 0);
    writer.writeUint32(0); // creation_time
    writer.writeUint32(0); // modification_time
    writer.writeUint32(1000); // timescale
    writer.writeUint32(60000); // duration (60s)
    writer.writeUint32(0x00010000); // rate
    writer.writeUint16(0x0100); // volume
    writer.writeUint16(0); // reserved
    writer.writeUint32(0); writer.writeUint32(0); // reserved
    writer.writeUint32(0); writer.writeUint32(0); // reserved
    for (let i = 0; i < 9; i++) writer.writeUint32(i === 0 || i === 4 ? 0x00010000 : (i === 8 ? 0x40000000 : 0)); // matrix
    for (let i = 0; i < 6; i++) writer.writeUint32(0); // pre_defined
    writer.writeUint32(2); // next_track_ID
    patchBoxSize(writer, mvhdOffset);
    patchBoxSize(writer, moovOffset);

    // gloc
    const gpsEntries = [];
    for (let i = 0; i < 60; i++) {
        gpsEntries.push({
            timestamp: i * 1000,
            latitude: 39.9912 + 0.003 * Math.cos(i / 60 * Math.PI * 2),
            longitude: 116.3974 + 0.003 * Math.sin(i / 60 * Math.PI * 2),
            altitude: 45 + 5 * Math.sin(i * 0.1),
            accuracy: 5,
            heading: (i / 60 * 360) % 360,
            speed: 15 + 5 * Math.sin(i * 0.05)
        });
    }
    writeGlocBox(writer, gpsEntries);

    // gsyn
    writeGsynBox(writer, {
        syncMode: 0, syncOffset: 0, interpolation: 1,
        defaultView: 2, videoRatio: 0.5, mapStyle: 0,
        showTrajectory: true, showPoi: true
    });

    // mdat
    const mdatOffset = writeBoxHeader(writer, 'mdat');
    writer.writeBytes(new Uint8Array(1024));
    patchBoxSize(writer, mdatOffset);

    const buffer = writer.getBuffer();

    // 解析完整文件
    const boxes = parseBoxes(buffer);
    assert(boxes.length === 5, `解析出5个顶层box (实际: ${boxes.length})`);

    const ftyp = findBox(boxes, 'ftyp');
    assert(ftyp !== null, '找到 ftyp box');

    const moov = findBox(boxes, 'moov');
    assert(moov !== null, '找到 moov box');

    const gloc = findBox(boxes, 'gloc');
    assert(gloc !== null, '找到 gloc box');

    const gsyn = findBox(boxes, 'gsyn');
    assert(gsyn !== null, '找到 gsyn box');

    const mdat = findBox(boxes, 'mdat');
    assert(mdat !== null, '找到 mdat box');

    // 验证 GPS 数据
    const parsedGps = parseGlocBox(gloc);
    assert(parsedGps.length === 60, `GPS点数 = 60 (实际: ${parsedGps.length})`);
    assert(parsedGps[0].latitude > 39.99 && parsedGps[0].latitude < 40.00, `首点纬度范围正确: ${parsedGps[0].latitude}`);

    // 验证同步规则
    const parsedSync = parseGsynBox(gsyn);
    assert(parsedSync.interpolation === 1, `插值模式 = 1 (实际: ${parsedSync.interpolation})`);
    assert(parsedSync.defaultView === 2, `默认视图 = 2 (实际: ${parsedSync.defaultView})`);

    // 保存测试文件
    writeFileSync('test/sample.mp5', Buffer.from(buffer));
    console.log(`  📄 示例文件已保存: test/sample.mp5 (${buffer.byteLength} bytes)`);
}

// 测试6: 向后兼容性（stripMP5Boxes）
testSection('向后兼容性 (stripMP5Boxes)');
{
    const writer = new BinaryWriter();

    // ftyp
    const ftypOffset = writeBoxHeader(writer, 'ftyp');
    writer.writeFourCC('mp5v');
    writer.writeUint32(0);
    writer.writeFourCC('mp5v');
    writer.writeFourCC('mp41');
    writer.writeFourCC('isom');
    patchBoxSize(writer, ftypOffset);

    // moov (简化)
    const moovOffset = writeBoxHeader(writer, 'moov');
    const mvhdOffset = writeFullBoxHeader(writer, 'mvhd', 0, 0);
    writer.writeUint32(0); writer.writeUint32(0);
    writer.writeUint32(1000); writer.writeUint32(10000);
    writer.writeUint32(0x00010000); writer.writeUint16(0x0100); writer.writeUint16(0);
    writer.writeUint32(0); writer.writeUint32(0); writer.writeUint32(0); writer.writeUint32(0);
    for (let i = 0; i < 9; i++) writer.writeUint32(i === 0 || i === 4 ? 0x00010000 : (i === 8 ? 0x40000000 : 0));
    for (let i = 0; i < 6; i++) writer.writeUint32(0);
    writer.writeUint32(2);
    patchBoxSize(writer, mvhdOffset);
    patchBoxSize(writer, moovOffset);

    // gloc
    writeGlocBox(writer, [{ timestamp: 0, latitude: 39.9, longitude: 116.4, altitude: 50, accuracy: 5, heading: 0, speed: 10 }]);

    // gsyn
    writeGsynBox(writer, { syncMode: 0, syncOffset: 0, interpolation: 1, defaultView: 2, videoRatio: 0.5, mapStyle: 0, showTrajectory: true, showPoi: true });

    // mdat
    const mdatOffset = writeBoxHeader(writer, 'mdat');
    writer.writeBytes(new Uint8Array(512));
    patchBoxSize(writer, mdatOffset);

    const mp5Buffer = writer.getBuffer();
    const mp5Size = mp5Buffer.byteLength;

    // strip MP5 boxes
    const mp5BoxTypes = ['gloc', 'gmap', 'gsyn'];
    const boxes = parseBoxes(mp5Buffer);
    const rangesToRemove = [];
    for (const box of boxes) {
        if (mp5BoxTypes.includes(box.type)) {
            rangesToRemove.push({ start: box.offset, end: box.offset + box.size });
        }
    }

    const strippedSize = mp5Size - rangesToRemove.reduce((s, r) => s + (r.end - r.start), 0);
    const result = new Uint8Array(strippedSize);
    let readOffset = 0, writeOffset = 0;
    for (const range of rangesToRemove.sort((a, b) => a.start - b.start)) {
        const chunk = new Uint8Array(mp5Buffer, readOffset, range.start - readOffset);
        result.set(chunk, writeOffset);
        writeOffset += chunk.length;
        readOffset = range.end;
    }
    if (readOffset < mp5Size) {
        const chunk = new Uint8Array(mp5Buffer, readOffset, mp5Size - readOffset);
        result.set(chunk, writeOffset);
    }
    const mp4Buffer = result.buffer;

    // 验证 stripped 后没有 gloc/gsyn
    const mp4Boxes = parseBoxes(mp4Buffer);
    const hasGloc = findBox(mp4Boxes, 'gloc') !== null;
    const hasGsyn = findBox(mp4Boxes, 'gsyn') !== null;
    assert(!hasGloc, 'strip后无gloc box');
    assert(!hasGsyn, 'strip后无gsyn box');
    assert(findBox(mp4Boxes, 'ftyp') !== null, 'strip后仍有ftyp box');
    assert(findBox(mp4Boxes, 'moov') !== null, 'strip后仍有moov box');
    assert(findBox(mp4Boxes, 'mdat') !== null, 'strip后仍有mdat box');
    assert(mp4Buffer.byteLength < mp5Size, `MP4 < MP5 (${mp4Buffer.byteLength} < ${mp5Size})`);
}

// 测试7: GPS 数据精度验证
testSection('GPS 数据精度验证');
{
    // 验证 ×10^7 整数存储的精度
    const testLat = 39.9042000;
    const encoded = Math.round(testLat * 1e7); // 399042000
    const decoded = encoded / 1e7;

    assert(encoded === 399042000, `纬度编码: ${encoded} (期望: 399042000)`);
    assert(decoded === testLat, `纬度解码: ${decoded} (期望: ${testLat})`);

    // 负数经纬度（南半球/西半球）
    const testLatNeg = -33.8688;
    const encodedNeg = Math.round(testLatNeg * 1e7);
    const decodedNeg = encodedNeg / 1e7;
    assert(decodedNeg === testLatNeg, `负纬度精度: ${decodedNeg} (期望: ${testLatNeg})`);

    // 海拔 ×10 存储
    const testAlt = 123.4;
    const altEncoded = Math.round(testAlt * 10);
    const altDecoded = altEncoded / 10;
    assert(altDecoded === testAlt, `海拔精度: ${altDecoded} (期望: ${testAlt})`);

    // 速度 ×10 存储
    const testSpeed = 12.3;
    const speedEncoded = Math.round(testSpeed * 10);
    const speedDecoded = speedEncoded / 10;
    assert(speedDecoded === testSpeed, `速度精度: ${speedDecoded} (期望: ${testSpeed})`);
}

// 测试8: gloc 文件大小估算
testSection('gloc 文件大小估算');
{
    // 1Hz采样，1小时 = 3600个点
    const entries1h = 3600;
    const size1h = 8 + 4 + 4 + entries1h * GLOC_ENTRY_SIZE; // header + count + entries
    assert(size1h < 130 * 1024, `1Hz/1h 大小 < 130KB (实际: ${size1h} bytes = ${(size1h/1024).toFixed(1)}KB)`);

    // 10Hz采样，1小时 = 36000个点
    const entries10h = 36000;
    const size10h = 8 + 4 + 4 + entries10h * GLOC_ENTRY_SIZE;
    assert(size10h < 1300 * 1024, `10Hz/1h 大小 < 1.3MB (实际: ${size10h} bytes = ${(size10h/1024/1024).toFixed(2)}MB)`);
}

// ============================================================
// 测试结果
// ============================================================

console.log('\n=============================');
console.log(`测试结果: ${passCount} 通过, ${failCount} 失败`);
console.log(failCount === 0 ? '🎉 全部通过!' : '⚠️ 有失败的测试');
process.exit(failCount === 0 ? 0 : 1);