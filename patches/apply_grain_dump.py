#!/usr/bin/env python3
"""Writes the crystal population a C++ host needs to lay the film's grain itself.

The tiles are 13.5 MB a stock and cannot ship; the population that lays them is 10 KB.
The host draws the same crystals with the same hashes and lands on the same tile.
"""
import io
import sys

ANCHOR = '        timing.mark("anchor")\n'

DUMP = r'''        if let directory = ProcessInfo.processInfo.environment["FOTOFILM_BAKE_DIR"] {
            let tag = ProcessInfo.processInfo.environment["FOTOFILM_BAKE_TAG"] ?? "bake"
            var text = "stock \(tag) monochrome \(monochrome ? 1 : 0) records \(records.count)\n"
            text += "markShape \(Self.markShape) tableSamples \(Self.tableSamples)\n"
            for (index, record) in records.enumerated() {
                text += "record \(index) dMin \(record.dMin) dMax \(record.dMax)"
                text += " sublayers \(record.sublayers.count)\n"
                for layer in record.sublayers {
                    text += "sub profile \(layer.profile.rawValue) coated \(layer.coatedPerMM2)"
                    text += " sigma \(layer.sigmaMM) peak \(layer.peakDemand)"
                    text += " capacity \(layer.capacity) edge \(layer.edge)"
                    text += " smallest \(layer.smallestSigmaMM) dye \(layer.dyePerCloudMM2)"
                    text += " cell \(layer.cellMM) void \(layer.voidIntegralMM2) forming:\n"
                    text += layer.forming.map { " " + String($0) }.joined() + "\n"
                }
            }
            let path = (directory as NSString).appendingPathComponent("records-\(tag).txt")
            try? text.write(toFile: path, atomically: true, encoding: .utf8)
        }
'''


def main():
    path = sys.argv[1]
    source = io.open(path, encoding="utf-8").read()
    if "records-\\(tag).txt" in source:
        print("grain records dump: already applied")
        return
    if source.count(ANCHOR) != 1:
        raise SystemExit("anchor count %d" % source.count(ANCHOR))
    source = source.replace(ANCHOR, ANCHOR + DUMP, 1)
    io.open(path, "w", encoding="utf-8").write(source)
    print("grain records dump: applied")


main()
