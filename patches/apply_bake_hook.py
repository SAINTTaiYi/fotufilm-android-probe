#!/usr/bin/env python3
"""Adds the bake dump hook to fotufilm's two Halide shims.

The hook is one header (FotofilmBakeDump.h, copied beside them) and a call at
each place a frame is delivered:

  * FotufilmHalideAndroid.cpp -- the CPU developer, which is the one that runs on
    Android (the CI job builds it beside the Linux shim under the real names).
    Hooked at the tail of `process_tile_output`, the funnel behind
    `fotufilm_halide_process{,_strip,_tile,_tile_with_exposure,_region}`, and at
    `fotufilm_halide_set_film_tiles` for the grain model's tiles.
  * FotufilmHalideLinux.cpp -- the Vulkan shim, hooked at the tail of the
    `develop()` template it funnels every entry point through, and at its own
    `set_film_tiles`. Dead code when the phone runs the CPU developer, and the
    same files when a driver ever accepts Halide's compute pipelines.

Idempotent: running it twice leaves both files unchanged.
"""

import sys

HEADER = "FotufilmBakeDump.h"

INCLUDE_ANCHOR = '#include "Pipeline/FilmTileStore.h"\n'
INCLUDE_PATCHED = INCLUDE_ANCHOR + '#include "%s"\n' % HEADER

# --- the CPU shim -----------------------------------------------------------------

CPU_TAIL_ANCHOR = """    return 0;
}

extern "C" int32_t fotufilm_halide_process_tile_with_exposure("""

CPU_TAIL_PATCHED = """    fotufilm::bake::dump_planar(
        input_r, input_g, input_b, output_r, output_g, output_b,
        compact_output ? 0
                       : int64_t(origin_y + interior_top) * output_width + origin_x
                             + interior_left,
        compact_output ? int64_t(interior_width) : int64_t(output_width),
        width, height, interior_width, interior_height,
        configuration, FOTUFILM_FRAME_CONFIGURATION_COUNT,
        exposure_lut, film_output_lut, paper_output_lut,
        lut_dimension, kLutValueCount,
        int32_t(configuration[FOTUFILM_CONFIG_GRAIN_MODE]),
        int32_t(configuration[FOTUFILM_CONFIG_FILM_TILE + fotufilm::kFilmTileId]),
        feature_mask, seed, origin_x, origin_y, error);
    return 0;
}

extern "C" int32_t fotufilm_halide_process_tile_with_exposure("""

CPU_TILES_ANCHOR = """extern "C" int32_t fotufilm_halide_set_film_tiles(int32_t id, const float *tiles,
                                                  int64_t count) {
    return FilmTileStore::shared().set(id, tiles, count) ? 0 : -1;
}
"""

CPU_TILES_PATCHED = """extern "C" int32_t fotufilm_halide_set_film_tiles(int32_t id, const float *tiles,
                                                  int64_t count) {
    fotufilm::bake::dump_tiles(id, tiles, count);
    return FilmTileStore::shared().set(id, tiles, count) ? 0 : -1;
}
"""

# --- the Vulkan shim --------------------------------------------------------------

GPU_TAIL_ANCHOR = """        error = attempt();
    }
    return error;
}

}  // namespace
"""

GPU_TAIL_PATCHED = """        error = attempt();
    }
    fotufilm::bake::dump_frame(
        input, output, width, height, origin_x, origin_y,
        configuration, FOTUFILM_FRAME_CONFIGURATION_COUNT,
        exposure_lut, film_output_lut, paper_output_lut,
        lut_dimension, kLutValueCount,
        int32_t(configuration[FOTUFILM_CONFIG_GRAIN_MODE]),
        int32_t(configuration[FOTUFILM_CONFIG_FILM_TILE + fotufilm::kFilmTileId]),
        feature_mask, seed, window.x, window.columns, window.y, window.rows,
        window.channels, error);
    return error;
}

}  // namespace
"""

GPU_TILES_ANCHOR = """extern "C" int32_t fotufilm_halide_set_film_tiles(int32_t id, const float *tiles,
                                                  int64_t count) {
    return film_tile_store().set(id, tiles, count) ? 0 : -1;
}
"""

GPU_TILES_PATCHED = """extern "C" int32_t fotufilm_halide_set_film_tiles(int32_t id, const float *tiles,
                                                  int64_t count) {
    fotufilm::bake::dump_tiles(id, tiles, count);
    return film_tile_store().set(id, tiles, count) ? 0 : -1;
}
"""


def replace_once(text, old, new, what):
    count = text.count(old)
    if count != 1:
        raise SystemExit("error: %s anchor occurs %d times, expected 1" % (what, count))
    return text.replace(old, new, 1)


def patch(path, edits, label):
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    if HEADER in text:
        print("bake hook: %s already applied" % label)
        return
    text = replace_once(text, INCLUDE_ANCHOR, INCLUDE_PATCHED, label + " include")
    for old, new, what in edits:
        text = replace_once(text, old, new, label + " " + what)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("bake hook: applied to %s" % path)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_bake_hook.py <engine source root>")
    root = sys.argv[1].rstrip("/")
    cpu = root + "/Sources/FotufilmHalide/FotufilmHalideAndroid.cpp"
    gpu = root + "/Sources/FotufilmHalide/FotufilmHalideLinux.cpp"
    patch(cpu, [(CPU_TAIL_ANCHOR, CPU_TAIL_PATCHED, "process_tile_output"),
                (CPU_TILES_ANCHOR, CPU_TILES_PATCHED, "set_film_tiles")], "cpu")
    patch(gpu, [(GPU_TAIL_ANCHOR, GPU_TAIL_PATCHED, "develop tail"),
                (GPU_TILES_ANCHOR, GPU_TILES_PATCHED, "set_film_tiles")], "gpu")


if __name__ == "__main__":
    main()
