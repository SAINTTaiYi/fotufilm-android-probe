#!/usr/bin/env python3
"""Drops the HEIF and OpenEXR decoders from the Android codecs.

They are 1.26 MB of text and about as much again in rodata for two formats a phone camera does
not produce: the fixtures are JPEG, TIFF and camera raw. Removing them means three things:
the two translation units stop being compiled, `Encode.cpp` stops seeing libheif's header (it
gates on `__has_include`), and the link stops naming the seven libraries they needed.

`DecodeStubs.cpp` supplies the three entry points the dispatch table still names. It throws
`Failure`, which is what a caller already reports for an unreadable file, so a HEIC dropped on
the app gets the same "Could not read image" as anything else it cannot open — no crash, and no
half-decoded raster reaching `sceneLinear`.
"""
import io
import os
import sys

STUBS = r'''// The HEIF and OpenEXR decoders are not part of a build configured by
// patches/apply_lean_codecs.py. These keep the dispatch table linkable and keep a caller's
// error path the one it already has for a file it cannot read.

#include "Codecs.hpp"

namespace {

[[noreturn]] void unsupported(const char *what, const std::string &path) {
    throw Failure(std::string(what) + " support is not part of this build: " + path);
}

}  // namespace

Raster decodeEXR(const std::string &path, ffc_capture &) {
    unsupported("OpenEXR", path);
}

Raster decodeHEIF(const std::string &path, ffc_capture &) {
    unsupported("HEIF", path);
}

Raster decodeHEIFReduced(const std::string &path, uint32_t) {
    unsupported("HEIF", path);
}
'''


def patch(path, old, new, what, marker):
    source = io.open(path, encoding="utf-8").read()
    if marker in source:
        print("%s: already patched" % what)
        return
    if source.count(old) != 1:
        raise SystemExit("%s: anchor count %d" % (what, source.count(old)))
    io.open(path, "w", encoding="utf-8").write(source.replace(old, new, 1))
    print("%s: patched" % what)


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "."

    patch(os.path.join(repo, "tools", "build-android-engine.sh"),
          "for source in Sources/CFotufilmCodecs/*.cpp; do\n",
          "for source in Sources/CFotufilmCodecs/*.cpp; do\n"
          "  # Skip the two decoders this build does not carry; DecodeStubs.cpp stands in for them.\n"
          "  case \"$(basename \"$source\")\" in DecodeHEIF.cpp|DecodeEXR.cpp) continue;; esac\n",
          "build script: skip HEIF/EXR", "DecodeHEIF.cpp|DecodeEXR.cpp")

    patch(os.path.join(repo, "tools", "build-android-engine.sh"),
          '-lraw_r -lheif -lde265 -ltiff -lpng16 -ljpeg -llcms2\n'
          '  -lOpenEXR-3_5 -lOpenEXRUtil-3_5 -lOpenEXRCore-3_5 -lIex-3_5 -lIlmThread-3_5 -lImath-3_2',
          '-lraw_r -ltiff -lpng16 -ljpeg -llcms2',
          "build script: drop the libraries", "-lraw_r -ltiff -lpng16 -ljpeg -llcms2")

    patch(os.path.join(repo, "Sources", "CFotufilmCodecs", "Encode.cpp"),
          "#if __has_include(<libheif/heif.h>)",
          "// The lean codecs build has no libheif headers, and this must not go looking for them.\n"
          "#if 0",
          "Encode.cpp: no HEIF encoder", "#if 0")

    stubs = os.path.join(repo, "Sources", "CFotufilmCodecs", "DecodeStubs.cpp")
    io.open(stubs, "w", encoding="utf-8").write(STUBS)
    print("wrote", stubs)


main()
