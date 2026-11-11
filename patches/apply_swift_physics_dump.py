#!/usr/bin/env python3
"""Writes the millimetre figures a C++ host cannot recover from the packed configuration.

The configuration carries pixel-spaced radii, so a host developing the same film at
another size must re-derive them. Most come straight from the stock's JSON; the ones
that do not -- what the halation kernel resolved to, what the enlarger's sampled stage
left over, the clump the silver equivalence landed on -- are computed here, in the one
place that has them, and written beside the bake dump.
"""
import io
import sys

ANCHOR = "        let mottleRadius = Self.gaussianRadius(mottleSigma)\n"
DUMP = r'''        // A C++ host re-deriving the pixel-spaced slots for another frame size needs the
        // millimetre figures this initializer folded them from. They are not in the packed
        // configuration, and rounding them back out of it loses exactly what it needs.
        if options.stage == .full,
           let directory = ProcessInfo.processInfo.environment["FOTUFILM_BAKE_DIR"] {
            var physics = ""
            func record(_ name: String, _ value: Float) { physics += "\(name)=\(value)\n" }
            func record(_ name: String, _ values: [Float]) {
                for (index, value) in values.enumerated() { record("\(name)_\(index)", value) }
            }
            record("pxPerMM", pxPerMM)
            record("emulsionDiffusionMM", stock.emulsionDiffusionMM)
            record("emulsionDiffusionSecondaryMM", stock.emulsionDiffusionSecondaryMM)
            record("lumaDiffusionMM", stock.lumaDiffusionMM)
            record("couplerDiffusionMM", stock.couplerDiffusionMM)
            record("adjacencyRadiusMM", stock.adjacencyRadiusMM)
            record("adjacencyScreened", (options.adjacencyModel ?? stock.adjacencyModel) == .screenedDiffusion ? 1 : 0)
            record("grainClumpsPerMM2", stock.grainClumpsPerMM2)
            record("halationSigmaMM", halation.sigmaMM)
            record("halationRingRadiusMM", halation.ringRadiusMM)
            record("enlargerBlurMM", printMedium.enlargerBlurMM)
            record("enlargerScanSharpening", printMedium.scanSharpening)
            record("renderedClumpMM", renderedClumpMM)
            record("renderedMottleMM", renderedMottleMM)
            record("mottleSizeRatio", mottleSizeRatio)
            // Named for the frame it belongs to: a suggestion or a scan builds its own
            // invocation at its own size, and only the full frame's figures describe the
            // configuration beside it.
            let path = (directory as NSString)
                .appendingPathComponent("physio-\(width)x\(height).txt")
            try? physics.write(toFile: path, atomically: true, encoding: .utf8)
        }

'''


def main():
    path = sys.argv[1]
    source = io.open(path, encoding="utf-8").read()
    if "FOTUFILM_BAKE_DIR\"] {\n            var physics" in source:
        print("physics dump: already applied")
        return
    if source.count(ANCHOR) != 1:
        raise SystemExit("anchor count %d" % source.count(ANCHOR))
    source = source.replace(ANCHOR, ANCHOR + DUMP, 1)
    io.open(path, "w", encoding="utf-8").write(source)
    print("physics dump: applied")


main()
