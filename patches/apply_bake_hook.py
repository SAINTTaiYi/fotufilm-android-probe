#!/usr/bin/env python3
"""Adds the bake dump hook to FotofilmHalideLinux.cpp.

The hook is one header (FotofilmBakeDump.h, copied beside it) and three edits:
the include, one call at the tail of `develop()` -- the funnel every still-image
path on Android goes through -- and one at `fotufilm_halide_set_film_tiles`.

Idempotent: running it twice leaves the file unchanged.
"""

import sys

INCLUDE_ANCHOR = '#include "Pipeline/FilmTileStore.h"\n'

TAIL_ANCHOR = """        error = attempt();
    }
    return error;
}

}  // namespace
"""

TAIL_PATCHED = """        error = attempt();
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

TILES_ANCHOR = """extern "C" int32_t fotufilm_halide_set_film_tiles(int32_t id, const float *tiles,
                                                  int64_t count) {
    return film_tile_store().set(id, tiles, count) ? 0 : -1;
}
"""

TILES_PATCHED = """extern "C" int32_t fotufilm_halide_set_film_tiles(int32_t id, const float *tiles,
                                                  int64_t count) {
    fotufilm::bake::dump_tiles(id, tiles, count);
    return film_tile_store().set(id, tiles, count) ? 0 : -1;
}
"""


def replace_once(text, old, new, what):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"error: {what} anchor occurs {count} times, expected 1")
    return text.replace(old, new, 1)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_bake_hook.py <path to FotofilmHalideLinux.cpp>")
    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()

    if "FotofilmBakeDump.h" in text:
        print("bake hook: already applied")
        return

    text = replace_once(text, INCLUDE_ANCHOR,
                        INCLUDE_ANCHOR + '#include "FotofilmBakeDump.h"\n', "include")
    text = replace_once(text, TAIL_ANCHOR, TAIL_PATCHED, "develop tail")
    text = replace_once(text, TILES_ANCHOR, TILES_PATCHED, "set_film_tiles")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"bake hook: applied to {path}")


if __name__ == "__main__":
    main()
