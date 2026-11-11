#!/usr/bin/env python3
"""Dumps the spectral front end's intermediate values beside a bake.

A host that regenerates the exposure table cannot tell a wrong formula from a different
rounding by comparing the table alone: the error is one unit in the last place either way.
What it needs is the illuminant, a few reflectance spectra and the record exposures exactly as
the engine holds them, so the comparison can be made one step at a time.
"""
import io
import sys

ANCHOR = "        let exposure = exposureTable(for: stock, illuminant: filmReferenceIlluminant(for: stock))\n"

DUMP = r'''        if let directory = ProcessInfo.processInfo.environment["FOTUFILM_BAKE_DIR"] {
            var probe = ""
            // Whether the reflectance prior loaded at all. With no model the exposure table takes
            // the compact fallback, which reads a different array entirely.
            probe += "has_model=\(MeasuredReflectanceTable.shared != nil ? 1 : 0)\n"
            let reference = filmReferenceIlluminant(for: stock)
            for (index, value) in reference.enumerated() {
                probe += "illuminant_\(index)=\(value)\n"
            }
            // The two sensitivity arrays the exposure path can read from.
            for layer in 0..<3 {
                var layerSum: Float = 0
                var layerNonZero = 0
                for value in stock.spectralProfile.layerSensitivity[layer] {
                    layerSum += value
                    if value != 0 { layerNonZero += 1 }
                }
                probe += "layer_sens_\(layer)_sum=\(layerSum)\n"
                probe += "layer_sens_\(layer)_nz=\(layerNonZero)\n"
                var compactSum: Float = 0
                for value in stock.sensitivity[layer] { compactSum += value }
                probe += "compact_sens_\(layer)_sum=\(compactSum)\n"
            }
            // The one cell the host disagrees on: a saturated red inside the cube.
            let probeScene = SIMD3<Float>(0.25, 0, 0)
            if let model = MeasuredReflectanceTable.shared {
                for (index, value) in model.reflectance(probeScene).enumerated() {
                    probe += "reflectance_probe_\(index)=\(value)\n"
                }
            }
            let probeExposure = spectralExposure(probeScene, stock: stock,
                                                 illuminant: reference,
                                                 referenceIlluminant: reference)
            probe += "exposure_probe=\(probeExposure.x),\(probeExposure.y),\(probeExposure.z)\n"
            // A reversal's balance is what the film table multiplies its transmittance by.
            if stock.isReversal {
                let basis = neutralDensityBasis(for: stock)
                let balance = reversalBalance(for: stock, aligned: { basis($0) })
                probe += "balance=\(balance.x),\(balance.y),\(balance.z)\n"
                let white = transmissionRGB(density: basis(stock.curves.map(\.dMin)), stock: stock) * balance
                probe += "white=\(white.x),\(white.y),\(white.z)\n"
            }
            // FilmStock has no id: `name` is the product name the engine ships and is unique
            // across the pack, so it is the only stable handle a file name can use.
            let handle = stock.name.replacingOccurrences(of: " ", with: "-")
            let path = (directory as NSString)
                .appendingPathComponent("spectral-probe-\(handle).txt")
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
