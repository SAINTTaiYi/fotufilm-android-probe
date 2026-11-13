#!/usr/bin/env python3
"""Adds a CLI that lays one stock's grain tiles, so the C++ port can be checked without a device.

  grain-probe <stock> <out-dir>

Writes `tiles-<stock>.f32` (the same packed layout the kernel reads) and, through the patch
beside this one, `records-<stock>.txt` -- the population that laid it.
"""
import io
import sys

ENTRY = r'''
        .executableTarget(name: "grain-probe", dependencies: ["FotufilmCore"]),
'''

MAIN = r'''import Foundation
import FotufilmCore

// Lays a stock's film tiles with the Swift reference and writes the packed bank, so the C++
// host that replaces this path can be compared texel for texel on any Swift toolchain.
//
//   grain-probe <stock|all> <out-dir> [records]
//
// `records` stops after the population: 10 KB a stock, against 13.5 MB of tiles, and most
// stocks only need the first written down.

let args = CommandLine.arguments
guard args.count >= 3 else {
    FileHandle.standardError.write(Data("usage: grain-probe <stock|all> <out-dir> [records]\n".utf8))
    exit(2)
}
let outDir = args[2]
let recordsOnly = args.count >= 4 && args[3] == "records"

// The pack resolves through `FilmStockPack.searchPaths`, which reaches the SwiftPM bundle's
// copy of `Stocks`, so no directory has to be passed in.
let stockIDs: [String]
if args[1] == "all" {
    stockIDs = FilmStock.allPresetIDs
} else {
    stockIDs = [args[1]]
}
guard !stockIDs.isEmpty else {
    FileHandle.standardError.write(Data("no stocks\n".utf8))
    exit(1)
}
try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

for id in stockIDs {
    guard let stock = FilmStock.named(id) else {
        FileHandle.standardError.write(Data("no stock \(id)\n".utf8))
        continue
    }
    // The population's dump is keyed by this, so it lands beside the tiles.
    setenv("FOTOFILM_BAKE_TAG", id, 1)
    // The printing balance the `printCorrection` control scales: three numbers a sheet,
    // from a forty-one-stop wedge solved neutral. A host re-deriving them has to land on
    // these, so they are printed beside the population.
    if ProcessInfo.processInfo.environment["FOTOFILM_BALANCE_DUMP"] != nil {
        for paperName in ["crystal-archive", "endura-premier", "vision-2383", "ilfochrome-cps-1k"] {
            if let sheet = PrintPaper(rawValue: paperName) {
                let scale = stock.printingContrastScale(correction: 1, paper: sheet)
                print(String(format: "balance %@ %@ %.6f %.6f %.6f", id, paperName,
                             scale[0], scale[1], scale[2]))
            }
        }
    }
    let started = Date()
    let population = FilmGrain(stock: stock)
    let populationSeconds = -started.timeIntervalSinceNow
    if recordsOnly {
        print("records \(id) in \(populationSeconds)s")
        continue
    }
    let marks = Date()
    let packed = population.tiles().packed()
    let tilesSeconds = -marks.timeIntervalSinceNow
    let url = URL(fileURLWithPath: outDir).appendingPathComponent("tiles-\(id).f32")
    do {
        try packed.withUnsafeBytes { Data($0) }.write(to: url)
    } catch {
        FileHandle.standardError.write(Data("could not write \(url.path): \(error)\n".utf8))
        exit(1)
    }
    print("tiles \(id) \(packed.count) floats population \(populationSeconds)s tiles \(tilesSeconds)s")
}
'''


def main():
    root = sys.argv[1]
    package = io.open(root + "/Package.swift", encoding="utf-8").read()
    if 'name: "grain-probe"' in package:
        print("grain cli: package already has it")
    else:
        anchor = '        .target(name: "FotufilmUpdate"),\n'
        if package.count(anchor) != 1:
            raise SystemExit("package anchor count %d" % package.count(anchor))
        package = package.replace(anchor, anchor + ENTRY, 1)
        io.open(root + "/Package.swift", "w", encoding="utf-8").write(package)
        print("grain cli: target added")
    import os
    os.makedirs(root + "/Sources/grain-probe", exist_ok=True)
    io.open(root + "/Sources/grain-probe/main.swift", "w", encoding="utf-8").write(MAIN)
    print("grain cli: main.swift written")


main()
