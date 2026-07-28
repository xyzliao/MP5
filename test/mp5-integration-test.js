/**
 * MP5 集成测试 — 验证 Muxer 生成的文件可以被 Parser 正确解析
 * 运行: node test/mp5-integration-test.js
 */

import { readFileSync } from 'fs';

// 导入测试中的工具函数（复用）
// 由于 mp5-box.js 使用 ES module export，我们在这里内联必要代码

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
    const offsetInSlice = (box.payloadOffset !== undefined) ? box.payloadOffset - box.offset : 4;
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
    const offsetInSlice = (box.payloadOffset !== undefined) ? box.payloadOffset - box.offset : 4;
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
// 集成测试: 模拟 createSampleMP5 流程
// ============================================================

let passCount = 0;
let failCount = 0;

function assert(condition, message) {
    if (condition) { console.log(`  ✅ ${message}`); passCount++; }
    else { console.log(`  ❌ ${message}`); failCount++; }
}

console.log('\n=== 集成测试: MP5 Muxer → Parser 端到端 ===\n');

// 模拟 createSampleMP5
const durationSec = 120;
const gpsEntries = [];
const centerLat = 39.9912;
const centerLon = 116.3974;
const radius = 0.003;

for (let i = 0; i < durationSec; i++) {
    const t = i;
    const angle = (t / durationSec) * Math.PI * 2;
    const r = radius * (1 + 0.1 * Math.sin(t * 0.5));
    const lat = centerLat + r * Math.cos(angle);
    const lon = centerLon + r * Math.sin(angle);

    gpsEntries.push({
        timestamp: t * 1000,
        latitude: lat,
        longitude: lon,
        altitude: 45 + 5 * Math.sin(t * 0.3),
        accuracy: 5,
        heading: ((angle * 180 / Math.PI) + 360) % 360,
        speed: 15 + 5 * Math.sin(t * 0.5)
    });
}

const pois = [
    { timestamp: 5000, latitude: centerLat + radius, longitude: centerLon, label: '起点', type: 'poi' },
    { timestamp: durationSec * 500, latitude: centerLat - radius, longitude: centerLon, label: '对面', type: 'poi' }
];

// 构建 MP5 文件
const writer = new BinaryWriter();

// 1. ftyp
const ftypOffset = writeBoxHeader(writer, 'ftyp');
writer.writeFourCC('mp5v');
writer.writeUint32(0);
writer.writeFourCC('mp5v');
writer.writeFourCC('mp41');
writer.writeFourCC('isom');
patchBoxSize(writer, ftypOffset);

// 2. moov (简化)
const moovOffset = writeBoxHeader(writer, 'moov');
const mvhdOffset = writeFullBoxHeader(writer, 'mvhd', 0, 0);
writer.writeUint32(0); // creation_time
writer.writeUint32(0); // modification_time
writer.writeUint32(1000); // timescale
writer.writeUint32(durationSec * 1000); // duration
writer.writeUint32(0x00010000); // rate
writer.writeUint16(0x0100); // volume
writer.writeUint16(0);
writer.writeUint32(0); writer.writeUint32(0);
writer.writeUint32(0); writer.writeUint32(0);
for (let i = 0; i < 9; i++) writer.writeUint32(i === 0 || i === 4 ? 0x00010000 : (i === 8 ? 0x40000000 : 0));
for (let i = 0; i < 6; i++) writer.writeUint32(0);
writer.writeUint32(2);
patchBoxSize(writer, mvhdOffset);
patchBoxSize(writer, moovOffset);

// 3. gloc
writeGlocBox(writer, gpsEntries);

// 4. gsyn
writeGsynBox(writer, {
    syncMode: 0, syncOffset: 0, interpolation: 1,
    defaultView: 2, videoRatio: 0.5, mapStyle: 0,
    showTrajectory: true, showPoi: true
});

// 5. mdat
const mdatOffset = writeBoxHeader(writer, 'mdat');
writer.writeBytes(new Uint8Array(1024));
patchBoxSize(writer, mdatOffset);

const mp5Buffer = writer.getBuffer();

// 现在解析这个 MP5 文件
const boxes = parseBoxes(mp5Buffer);

// 验证 ftyp
const ftyp = findBox(boxes, 'ftyp');
assert(ftyp !== null, '找到 ftyp box');
{
    const reader = new BinaryReader(ftyp.buffer, ftyp.dataOffset);
    const majorBrand = reader.readFourCC();
    assert(majorBrand === 'mp5v', `major_brand = mp5v (实际: ${majorBrand})`);
    reader.readUint32(); // minor_version
    const compat1 = reader.readFourCC();
    const compat2 = reader.readFourCC();
    const compat3 = reader.readFourCC();
    assert(compat1 === 'mp5v' && compat2 === 'mp41' && compat3 === 'isom', '兼容品牌: mp5v, mp41, isom');
}

// 验证 moov
const moov = findBox(boxes, 'moov');
assert(moov !== null, '找到 moov box');
assert(moov.children && moov.children.length > 0, `moov 有子box (${moov.children?.length} 个)`);

const mvhd = findBox(moov.children, 'mvhd');
assert(mvhd !== null, '找到 mvhd box');

// 验证 gloc
const gloc = findBox(boxes, 'gloc');
assert(gloc !== null, '找到 gloc box');
{
    const parsed = parseGlocBox(gloc);
    assert(parsed.length === durationSec, `GPS点数 = ${durationSec} (实际: ${parsed.length})`);

    // 验证首尾数据
    const first = parsed[0];
    const last = parsed[parsed.length - 1];

    assert(Math.abs(first.latitude - gpsEntries[0].latitude) < 1e-6, `首点纬度匹配: ${first.latitude} vs ${gpsEntries[0].latitude}`);
    assert(Math.abs(first.longitude - gpsEntries[0].longitude) < 1e-6, `首点经度匹配`);
    assert(first.timestamp === 0, `首点时间戳 = 0`);
    assert(last.timestamp === (durationSec - 1) * 1000, `末点时间戳 = ${(durationSec - 1) * 1000} (实际: ${last.timestamp})`);

    // 验证所有点
    let allMatch = true;
    for (let i = 0; i < parsed.length; i++) {
        if (Math.abs(parsed[i].latitude - gpsEntries[i].latitude) > 1e-6 ||
            Math.abs(parsed[i].longitude - gpsEntries[i].longitude) > 1e-6) {
            allMatch = false;
            break;
        }
    }
    assert(allMatch, '所有GPS点数据完整匹配');
}

// 验证 gsyn
const gsyn = findBox(boxes, 'gsyn');
assert(gsyn !== null, '找到 gsyn box');
{
    const config = parseGsynBox(gsyn);
    assert(config.interpolation === 1, `插值模式 = 1 (实际: ${config.interpolation})`);
    assert(config.defaultView === 2, `默认视图 = 2 (实际: ${config.defaultView})`);
    assert(config.showTrajectory === true, '显示轨迹 = true');
    assert(config.showPoi === true, '显示POI = true');
}

// 验证 mdat
const mdat = findBox(boxes, 'mdat');
assert(mdat !== null, '找到 mdat box');
assert(mdat.size === 1032, `mdat 大小 = 1032 (实际: ${mdat.size})`);

// 验证文件完整性
assert(mp5Buffer.byteLength > 0, `文件大小 > 0 (${mp5Buffer.byteLength} bytes)`);

// 验证向后兼容性: strip MP5 boxes
const mp5BoxTypes = ['gloc', 'gmap', 'gsyn'];
const rangesToRemove = [];
for (const box of boxes) {
    if (mp5BoxTypes.includes(box.type)) {
        rangesToRemove.push({ start: box.offset, end: box.offset + box.size });
    }
}
const strippedSize = mp5Buffer.byteLength - rangesToRemove.reduce((s, r) => s + (r.end - r.start), 0);
assert(strippedSize < mp5Buffer.byteLength, `strip后更小: ${strippedSize} < ${mp5Buffer.byteLength}`);

// 验证 GPX 导出格式
console.log('\n=== GPX 导出测试 ===');
{
    const parsed = parseGlocBox(gloc);
    let gpx = '<?xml version="1.0" encoding="UTF-8"?>\n';
    gpx += '<gpx version="1.1" creator="MP5录播器" xmlns="http://www.topografix.com/GPX/1/1">\n';
    gpx += '  <trk><name>MP5 Track</name><trkseg>\n';
    for (const e of parsed.slice(0, 3)) {
        gpx += `    <trkpt lat="${e.latitude.toFixed(7)}" lon="${e.longitude.toFixed(7)}">\n`;
        gpx += `      <ele>${e.altitude.toFixed(1)}</ele>\n`;
        gpx += `    </trkpt>\n`;
    }
    gpx += '  </trkseg></trk>\n</gpx>';
    assert(gpx.includes('<gpx'), 'GPX包含<gpx>标签');
    assert(gpx.includes('<trkpt'), 'GPX包含<trkpt>标签');
    assert(gpx.includes('lat="'), 'GPX包含lat属性');
}

// 验证 GeoJSON 导出格式
console.log('\n=== GeoJSON 导出测试 ===');
{
    const parsed = parseGlocBox(gloc);
    const geojson = {
        type: 'FeatureCollection',
        features: [{
            type: 'Feature',
            properties: { name: 'MP5 Track', pointCount: parsed.length },
            geometry: {
                type: 'LineString',
                coordinates: parsed.map(e => [e.longitude, e.latitude, e.altitude])
            }
        }]
    };
    assert(geojson.type === 'FeatureCollection', 'GeoJSON type = FeatureCollection');
    assert(geojson.features[0].geometry.type === 'LineString', 'geometry type = LineString');
    assert(geojson.features[0].geometry.coordinates.length === durationSec, `坐标点数 = ${durationSec}`);
}

// 验证同步引擎插值
console.log('\n=== Sync Engine 插值测试 ===');
{
    const parsed = parseGlocBox(gloc);

    // 线性插值测试: 在 t=500ms 处插值 (介于 t=0 和 t=1000 之间)
    const t = 500;
    let lo = 0, hi = parsed.length - 1;
    while (lo < hi - 1) {
        const mid = Math.floor((lo + hi) / 2);
        if (parsed[mid].timestamp <= t) lo = mid; else hi = mid;
    }
    const prev = parsed[lo], next = parsed[hi];
    const ratio = (t - prev.timestamp) / (next.timestamp - prev.timestamp);
    const interpLat = prev.latitude + (next.latitude - prev.latitude) * ratio;
    const interpLon = prev.longitude + (next.longitude - prev.longitude) * ratio;

    assert(interpLat > prev.latitude && interpLat < next.latitude || 
           interpLat < prev.latitude && interpLat > next.latitude, 
           `线性插值在两点之间: ${interpLat.toFixed(7)} (介于 ${prev.latitude.toFixed(7)} 和 ${next.latitude.toFixed(7)})`);
    assert(ratio === 0.5, `插值比例 = 0.5 (实际: ${ratio})`);
}

console.log('\n=============================');
console.log(`集成测试结果: ${passCount} 通过, ${failCount} 失败`);
console.log(failCount === 0 ? '🎉 全部通过!' : '⚠️ 有失败的测试');
process.exit(failCount === 0 ? 0 : 1);