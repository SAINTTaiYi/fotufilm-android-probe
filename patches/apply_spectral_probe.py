#!/usr/bin/env python3
"""Dumps the spectral front end's intermediate values beside a bake.

A host that regenerates the exposure table cannot tell a wrong formula from a different
rounding by comparing the table alone: the error is one unit in the last place either way.
What it needs is the illuminant and a few reflectance spectra exactly as the engine holds
them, so the comparison can be made one step at a time.
"""
import io
import sys

ANCHOR = "        let exposure = exposureTable(for: stock, illuminant: filmReferenceIlluminant(for: stock))\n"

DUMP = r'''        if let directory = ProcessInfo.processInfo.environment["FOTUFILM_BAKE_DIR"] {
            var probe = ""
            let reference = filmReferenceIlluminant(for: stock)
            for (index, value) in reference.enumerated() {
                probe += "illuminant_\(index)=\(value)\n"
            }
            if let model = MeasuredReflectanceTable.shared {
                let samples: [SIMD3<Float>] = [
                    SIMD3(0.25, 0.25, 0.25),
                    SIMD3(0.5, 0.25, 0.125),
                    SIMD3(0.125, 0.5, 0.25),
                    SIMD3(0.8, 0.3, 0.1),
                    SIMD3(0.05, 0.05, 0.05),
                ]
                for (n, rgb) in samples.enumerated() {
                    for (index, value) in model.reflectance(rgb).enumerated() {
                        probe += "reflectance_\(n)_\(index)=\(value)\n"
                    }
                }
            }
            let path = (directory as NSString)
                .appendingPathComponent("spectral-probe-\(stock.id).txt")
            try? probe.write(toFile: path, atomically: true, encoding: .utf8)
        }

'''


def main():
    path = sys.argv[1]
    source = io.open(path, encoding="utf-8").read()
    if "spectral-probe-" in source:
        print("spectral probe: already applied")
        return
    if source.count(ANCHOR) != 1:
        raise SystemExit("anchor count %d" % source.count(ANCHOR))
    source = source.replace(ANCHOR, ANCHOR + DUMP, 1)
    io.open(path, "w", encoding="utf-8").write(source)
    print("spectral probe: applied")


main()
