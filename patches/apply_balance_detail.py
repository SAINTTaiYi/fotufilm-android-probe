#!/usr/bin/env python3
"""Dumps the intermediate values a host re-deriving `neutralPrintingBalance` needs.

The balance alone cannot say which step drifted: a trim off by a thousandth and a
relative exposure off by as much both move it. These are the numbers in between.
"""
import io
import sys

TRIM_ANCHOR = """    static func reflectionPrintDensityTrim(for paper: PrintPaper) -> SIMD3<Float> {
        reflectionPrintDensityTrims[paper] ?? .zero"""

TRIM_DUMP = """    static func reflectionPrintDensityTrim(for paper: PrintPaper) -> SIMD3<Float> {
        let trim = reflectionPrintDensityTrims[paper] ?? .zero
        if ProcessInfo.processInfo.environment["FOTOFILM_BALANCE_DUMP"] != nil {
            print(String(format: "trim %@ %.7f %.7f %.7f", paper.rawValue,
                         trim.x, trim.y, trim.z))
        }
        return trim"""

BAL_ANCHOR = """            }

        let viewingLight = referenceViewingLight(for: paper)
"""

BAL_DUMP = """        if ProcessInfo.processInfo.environment["FOTOFILM_BALANCE_DUMP"] != nil {
            print(String(format: "midenergy %@ %@ %.7f %.7f %.7f", stock.name, paper.rawValue,
                         midEnergy.x, midEnergy.y, midEnergy.z))
            print(String(format: "xmids %@ %@ %.7f %.7f %.7f", stock.name, paper.rawValue,
                         xMids[0], xMids[1], xMids[2]))
            for (i, r) in relatives.enumerated() where i % 10 == 0 {
                print(String(format: "rel %@ %@ %d %.7f %.7f %.7f", stock.name, paper.rawValue,
                             i, r.x, r.y, r.z))
            }
        }
            }

        let viewingLight = referenceViewingLight(for: paper)
"""


def patch(path, anchor, replacement, tag):
    source = io.open(path, encoding="utf-8").read()
    if tag in source:
        print(f"{tag}: already patched")
        return
    if source.count(anchor) != 1:
        raise SystemExit(f"{tag}: anchor count {source.count(anchor)}")
    io.open(path, "w", encoding="utf-8").write(source.replace(anchor, replacement, 1))
    print(f"{tag}: patched")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "src"
    path = f"{root}/Sources/FotufilmCore/SpectralModel.swift"
    patch(path, TRIM_ANCHOR, TRIM_DUMP, "trim %@ %.7f")
    patch(path, BAL_ANCHOR, BAL_DUMP, "balance detail")


if __name__ == "__main__":
    main()
