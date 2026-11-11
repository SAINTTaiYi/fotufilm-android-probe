#!/usr/bin/env python3
"""Adds a CLI that dumps the spectral tables, so a host can be checked without a device.

The Android engine only builds for aarch64-bionic, which no CI runner is. The tables
themselves are pure Swift: `FotufilmCore` guards every Metal, Android and CryptoKit import with
`#if canImport`, so the same source builds for x86_64 Linux. That makes a table comparison a
five-minute job on a stock runner instead of a 25-minute cross-build plus a phone.
"""
import io
import os
import sys

MAIN = r'''import Foundation
import FotufilmCore

// Dumps the three tables a render needs, in the same RGBA-interleaved f32 layout the bake hook
// writes, so a C++ host can be compared cell for cell on any machine with a Swift toolchain.
//
//   spectral-probe <stock-id> <paper-id> <out-dir>
//
// The stock pack resolves through `FilmStockPack.searchPaths`, which honours FOTUFILM_STOCKS and
// falls back to the bundle SwiftPM builds beside the executable.

let args = CommandLine.arguments
guard args.count >= 4 else {
    FileHandle.standardError.write(Data("usage: spectral-probe <stock> <paper> <out-dir>\n".utf8))
    exit(2)
}
let stockID = args[1]
let paperID = args[2]
let outDir = args[3]

guard let stock = FilmStock.named(stockID) else {
    FileHandle.standardError.write(Data("no stock \(stockID)\n".utf8))
    exit(1)
}
guard let paper = PrintPaper.preset(id: paperID) else {
    FileHandle.standardError.write(Data("no paper \(paperID)\n".utf8))
    exit(1)
}

try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

func dump(_ lut: SpectralLUT, _ name: String) {
    let url = URL(fileURLWithPath: outDir).appendingPathComponent(name)
    let data = lut.values.withUnsafeBytes { Data($0) }
    do {
        try data.write(to: url)
    } catch {
        FileHandle.standardError.write(Data("could not write \(url.path): \(error)\n".utf8))
        exit(1)
    }
}

// Resolving takes a cache lookup; building is what writes the probe file the patch beside this
// one installs into `buildTables`.
let tables = SpectralRuntime.tables(for: stock, paper: paper)
dump(tables.exposure, "exposure.f32")
dump(tables.filmOutput, "film.f32")
if let paperOutput = tables.paperOutput {
    dump(paperOutput, "paper.f32")
}

print("""
stock=\(stock.name) id=\(stockID) paper=\(paperID) dim=\(tables.exposure.dimension) \
exposure=\(tables.exposure.values.count) film=\(tables.filmOutput.values.count) \
paper=\(tables.paperOutput?.values.count ?? 0)
""")
'''


def patch_package(path):
    source = io.open(path, encoding="utf-8").read()
    if "spectral-probe" in source:
        print("package: already patched")
        return
    anchor = '        .target(name: "FotufilmUpdate"),\n'
    if source.count(anchor) != 1:
        raise SystemExit("package anchor count %d" % source.count(anchor))
    addition = (
        '        // Dumps the spectral tables on any platform the Swift toolchain runs on, so a\n'
        '        // host can be checked against them without a device.\n'
        '        .executableTarget(name: "spectral-probe", dependencies: ["FotufilmCore"]),\n')
    io.open(path, "w", encoding="utf-8").write(source.replace(anchor, anchor + addition, 1))
    print("package: added spectral-probe")


def publicize(path):
    source = io.open(path, encoding="utf-8").read()
    pairs = [
        ("    static var allPresetIDs: [String] {",
         "    public static var allPresetIDs: [String] {"),
        ("    static func named(_ id: String) -> FilmStock? {",
         "    public static func named(_ id: String) -> FilmStock? {"),
    ]
    changed = 0
    for old, new in pairs:
        if old in source:
            source = source.replace(old, new, 1)
            changed += 1
    io.open(path, "w", encoding="utf-8").write(source)
    print("stocks: %d accessors made public" % changed)


def write_main(repo):
    directory = os.path.join(repo, "Sources", "SpectralProbe")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "main.swift")
    io.open(path, "w", encoding="utf-8").write(MAIN)
    print("wrote", path)


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    patch_package(os.path.join(repo, "Package.swift"))
    publicize(os.path.join(repo, "Sources", "FotufilmCore", "FilmStockPack.swift"))
    write_main(repo)


main()
