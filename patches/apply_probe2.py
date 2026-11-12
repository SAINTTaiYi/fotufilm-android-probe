#!/usr/bin/env python3
"""Rewrites the spectral probe so one CI run also dumps what the port must not re-derive:
the per-camera dual-illuminant matrices and the push conditions' curve slots."""
import io, os, sys

MAIN = r'''import Foundation
import FotufilmCore

// spectral-probe <stock> <paper> <out-dir>     the three spectral tables
// spectral-probe --profiles <out.bin>          the camera matrices and their raw sensitivity
// spectral-probe --push <out.bin>              each development condition's curve slots
//
// The second and third exist because those numbers are derived from machinery the port does not
// reproduce (a constrained spectral reconstruction, and the coupler warp's 4x128 solve). Letting
// the engine write them once keeps the port lossless without re-deriving anything by hand.

let args = CommandLine.arguments

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

func write(_ data: Data, _ path: String) {
    do { try data.write(to: URL(fileURLWithPath: path)) }
    catch { fail("could not write \(path): \(error)") }
}

func f32(_ values: [Float]) -> Data { values.withUnsafeBytes { Data($0) } }

if args.count == 3 && args[1] == "--profiles" {
    // Every bundled camera profile: the raw 3x81 sensitivity verbatim, plus the two matrices the
    // engine solves from it and its training reflectances.
    let store = CameraSpectralProfileStore.bundledProfiles
    var out = Data("CPR1".utf8)
    func u32(_ v: UInt32) { withUnsafeBytes(of: v.littleEndian) { out.append(contentsOf: $0) } }
    u32(UInt32(store.count))
    for profile in store {
        let id = Array(profile.id.utf8)
        u32(UInt32(id.count)); out.append(contentsOf: id)
        let pair = profile.dualIlluminantMatrices()
        for row in pair.tungsten { for v in [row.x, row.y, row.z] { u32(v.bitPattern) } }
        for row in pair.daylight { for v in [row.x, row.y, row.z] { u32(v.bitPattern) } }
        // The sensitivity the matrices were solved from, so the file is a record and not only a
        // result. 3 layers x 81 bands, float64 to keep every decimal the JSON carried.
        let bands = 81
        u32(UInt32(bands))
        for layer in 0..<3 {
            for i in 0..<bands {
                let v = Double(profile.sensitivity[layer][i])
                withUnsafeBytes(of: v.bitPattern.littleEndian) { out.append(contentsOf: $0) }
            }
        }
    }
    write(out, args[2])
    print("profiles=\(store.count) bytes=\(out.count)")
    exit(0)
}

if args.count == 3 && args[1] == "--push" {
    // Each stock's listed development conditions, with the configuration slots the curve swap
    // moves. `FilmEngineInvocation` is public, and those slots are pure functions of the curves,
    // so an invocation at one size answers for every size.
    var out = Data("PCH1".utf8)
    func u32(_ v: UInt32) { withUnsafeBytes(of: v.littleEndian) { out.append(contentsOf: $0) } }
    func f32v(_ v: Float) { u32(v.bitPattern) }

    let blocks: [(String, Int, Int)] = [
        ("curves", 0, 18),
        ("sampled", FilmEngineInvocation.sampledCurvesOffset,
         FilmEngineInvocation.sampledCurveStride * 3),
        ("warp", FilmEngineInvocation.couplerWarpOffset, FilmEngineInvocation.couplerWarpSamples * 3),
        ("donor", 8743, 6),
    ]

    var payload = Data()
    var nstocks: UInt32 = 0
    var nconds = 0
    for id in FilmStock.allPresetIDs {
        guard let stock = FilmStock.named(id) else { continue }
        let stops = stock.supportedDevelopmentStops
        if stops.isEmpty { continue }
        nstocks += 1
        var body = Data()
        func bu32(_ v: UInt32) { withUnsafeBytes(of: v.littleEndian) { body.append(contentsOf: $0) } }
        let nameBytes = Array(id.utf8)
        bu32(UInt32(nameBytes.count)); body.append(contentsOf: nameBytes)
        bu32(UInt32(stops.count))
        for stop in stops {
            guard let pushed = try? stock.pushed(stops: stop) else { continue }
            var options = FotufilmEngine.Options()
            options.grainScale = 1
            guard let inv = try? FilmEngineInvocation(
                validating: pushed, options: options, width: 675, height: 900,
                bindsFilmGrain: false) else { continue }
            let configuration = inv.configuration
            withUnsafeBytes(of: stop.bitPattern.littleEndian) { body.append(contentsOf: $0) }
            bu32(UInt32(blocks.count))
            for (_, offset, count) in blocks {
                bu32(UInt32(offset)); bu32(UInt32(count))
                for i in 0..<count {
                    withUnsafeBytes(of: configuration[offset + i].bitPattern.littleEndian) {
                        body.append(contentsOf: $0)
                    }
                }
            }
            nconds += 1
        }
        payload.append(body)
    }
    u32(nstocks)
    out.append(payload)
    write(out, args[2])
    print("push stocks=\(nstocks) conditions=\(nconds) bytes=\(out.count)")
    exit(0)
}

guard args.count >= 4 else {
    fail("usage: spectral-probe <stock> <paper> <out-dir>  |  --profiles <out>  |  --push <out>")
}
let stockID = args[1]
let paperID = args[2]
let outDir = args[3]

guard let stock = FilmStock.named(stockID) else { fail("no stock \(stockID)") }
guard let paper = PrintPaper.preset(id: paperID) else { fail("no paper \(paperID)") }

try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

func dump(_ lut: SpectralLUT, _ name: String) {
    write(f32(lut.values), URL(fileURLWithPath: outDir).appendingPathComponent(name).path)
}

let tables = SpectralRuntime.tables(for: stock, paper: paper)
dump(tables.exposure, "exposure.f32")
dump(tables.filmOutput, "film.f32")
if let paperOutput = tables.paperOutput { dump(paperOutput, "paper.f32") }

print("""
stock=\(stock.name) id=\(stockID) paper=\(paperID) dim=\(tables.exposure.dimension) \
exposure=\(tables.exposure.values.count) film=\(tables.filmOutput.values.count) \
paper=\(tables.paperOutput?.values.count ?? 0)
""")
'''


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    directory = os.path.join(repo, "Sources", "spectral-probe")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "main.swift")
    io.open(path, "w", encoding="utf-8").write(MAIN)
    print("wrote", path, len(MAIN), "bytes")


main()
