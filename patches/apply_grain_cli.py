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

// Lays one stock's film tiles with the Swift reference and writes the packed bank, so the
// C++ host that replaces this path can be compared texel for texel on any Swift toolchain.
//
//   grain-probe <stock> <out-dir> [records]

let args = CommandLine.arguments
guard args.count >= 3 else {
    FileHandle.standardError.write(Data("usage: grain-probe <stock> <out-dir>\n".utf8))
    exit(2)
}
let stockID = args[1]
let outDir = args[2]
guard let stock = FilmStock.named(stockID) else {
    FileHandle.standardError.write(Data("no stock \(stockID)\n".utf8))
    exit(1)
}
try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

let started = Date()
let population = FilmGrain(stock: stock)
FileHandle.standardError.write(Data("population \(stockID) in \(-started.timeIntervalSinceNow)s\n".utf8))

// `records` stops here: the population is 10 KB, the tiles 13.5 MB, and most stocks only
// need the first written down.
if args.count >= 4, args[3] == "records" {
    print("records only \(stockID)")
    exit(0)
}

let marks = Date()
let tiles = population.tiles()
let packed = tiles.packed()
FileHandle.standardError.write(Data("tiles \(packed.count) floats in \(-marks.timeIntervalSinceNow)s\n".utf8))

let url = URL(fileURLWithPath: outDir).appendingPathComponent("tiles-\(stockID).f32")
do {
    try packed.withUnsafeBytes { Data($0) }.write(to: url)
} catch {
    FileHandle.standardError.write(Data("could not write \(url.path): \(error)\n".utf8))
    exit(1)
}
print("wrote \(url.path) \(packed.count)")
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
