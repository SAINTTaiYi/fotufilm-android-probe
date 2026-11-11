#ifndef FOTOFILM_HALIDE_BAKE_DUMP_H
#define FOTOFILM_HALIDE_BAKE_DUMP_H

// Records a develop exactly as the kernels receive it, so the same frame can be replayed
// outside the engine -- a C++ probe with no Swift runtime, no Halide compiler, no Flutter.
//
// Off unless FOTUFILM_BAKE_DIR names a directory in the process environment:
//
//   FOTUFILM_BAKE_DIR         where to write; created if missing
//   FOTUFILM_BAKE_TAG         file-name prefix (default "bake")
//   FOTUFILM_BAKE_MAX_PIXELS  skip frames above this pixel count (default 4,000,000)
//   FOTUFILM_BAKE_MAX_CALLS   stop after this many develops (default 1)
//
// A call writes <dir>/<tag>-<n>-meta.txt and, beside it:
//   config.f32    FOTUFILM_FRAME_CONFIGURATION_COUNT floats, the packed configuration
//   exposure.f32  the three spectral tables the develop reads, 33^3 * 4 floats each
//   film.f32
//   paper.f32
//   input.f32     the whole frame, interleaved RGBA, in the caller's element type
//   output.f32    the window the call delivered, interleaved
// and, once per tile id, <dir>/<tag>-tiles-<id>.f32 when the grain model registers tiles.
//
// Plain stdio on purpose: the hook must add nothing to the engine's link, and a phone has no
// business formatting JSON on a render thread. Every entry point returns immediately when the
// environment names no directory, so a frame without the hook costs one getenv.

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>

#if defined(__unix__) || defined(__ANDROID__)
#include <sys/stat.h>
#endif

namespace fotufilm {
namespace bake {

/// The lock the call counter and the file writes share: a tiled develop can arrive on two
/// threads, and two calls must not pick the same index.
inline std::mutex &gate() {
    static std::mutex shared;
    return shared;
}

inline int &calls() {
    static int count = 0;
    return count;
}

inline int &tiles_written() {
    static int count = 0;
    return count;
}

inline const char *text(const char *name) {
    const char *value = std::getenv(name);
    return value && *value ? value : nullptr;
}

inline long long integer(const char *name, long long fallback) {
    const char *value = std::getenv(name);
    if (!value || !*value) return fallback;
    char *end = nullptr;
    const long long parsed = std::strtoll(value, &end, 10);
    return end && end != value ? parsed : fallback;
}

inline void make_directory(const std::string &directory) {
#if defined(__unix__) || defined(__ANDROID__)
    ::mkdir(directory.c_str(), 0777);  // An existing directory is the normal case.
#endif
}

inline bool write_block(const std::string &directory, const char *name,
                        const void *data, size_t bytes) {
    if (!data || bytes == 0) return false;
    const std::string path = directory + "/" + name;
    std::FILE *file = std::fopen(path.c_str(), "wb");
    if (!file) return false;
    const size_t written = std::fwrite(data, 1, bytes, file);
    const bool flushed = std::fflush(file) == 0;
    std::fclose(file);
    return written == bytes && flushed;
}

/// The element type's tag: floats are what the stills path carries, bytes the video one.
template <typename Element>
inline const char *element_name() {
    return sizeof(Element) == 4 ? "f32" : "u8";
}

/// What one develop saw. `config_count` and `lut_count` are passed rather than read from the
/// layout header, so the hook compiles against any revision of it.
template <typename Element>
inline void dump_frame(const Element *input, const Element *output,
                       int32_t width, int32_t height, int32_t origin_x, int32_t origin_y,
                       const float *configuration, int32_t config_count,
                       const float *exposure, const float *film, const float *paper,
                       int32_t lut_dimension, int32_t lut_count,
                       int32_t grain_mode, int32_t tile_id,
                       int32_t feature_mask, uint32_t seed,
                       int32_t window_x, int32_t window_columns,
                       int32_t window_y, int32_t window_rows, int32_t window_channels,
                       int32_t status) {
    const char *root = text("FOTUFILM_BAKE_DIR");
    if (!root || width <= 0 || height <= 0) return;
    const long long pixels = int64_t(width) * height;
    if (pixels > integer("FOTUFILM_BAKE_MAX_PIXELS", 4000000)) return;

    std::lock_guard<std::mutex> lock(gate());
    const long long limit = integer("FOTUFILM_BAKE_MAX_CALLS", 1);
    if (calls() >= limit) return;
    const int index = calls()++;

    const std::string directory(root);
    make_directory(directory);
    const std::string tag = text("FOTUFILM_BAKE_TAG") ? text("FOTUFILM_BAKE_TAG") : "bake";
    const std::string prefix = tag + "-" + std::to_string(index) + "-";
    const std::string element = element_name<Element>();

    char meta[1024];
    std::snprintf(meta, sizeof meta,
                  "format=fotufilm-bake-1\n"
                  "call=%d\n"
                  "status=%d\n"
                  "element=%s\n"
                  "width=%d\n"
                  "height=%d\n"
                  "origin_x=%d\n"
                  "origin_y=%d\n"
                  "feature_mask=%d\n"
                  "seed=%u\n"
                  "lut_dimension=%d\n"
                  "lut_count=%d\n"
                  "config_count=%d\n"
                  "grain_mode=%d\n"
                  "tile_id=%d\n"
                  "window_x=%d\n"
                  "window_columns=%d\n"
                  "window_y=%d\n"
                  "window_rows=%d\n"
                  "window_channels=%d\n",
                  index, status, element.c_str(), width, height, origin_x, origin_y,
                  feature_mask, seed, lut_dimension, lut_count, config_count,
                  grain_mode, tile_id, window_x, window_columns, window_y, window_rows,
                  window_channels);
    write_block(directory, (prefix + "meta.txt").c_str(), meta, std::strlen(meta));

    write_block(directory, (prefix + "config.f32").c_str(), configuration,
                size_t(config_count) * sizeof(float));
    write_block(directory, (prefix + "exposure.f32").c_str(), exposure,
                size_t(lut_count) * sizeof(float));
    write_block(directory, (prefix + "film.f32").c_str(), film,
                size_t(lut_count) * sizeof(float));
    write_block(directory, (prefix + "paper.f32").c_str(), paper,
                size_t(lut_count) * sizeof(float));

    const size_t element_bytes = sizeof(Element);
    write_block(directory, (prefix + "input." + element).c_str(), input,
                size_t(width) * size_t(height) * 4u * element_bytes);
    if (output && window_columns > 0 && window_rows > 0 && window_channels > 0) {
        write_block(directory, (prefix + "output." + element).c_str(), output,
                    size_t(window_columns) * size_t(window_rows) * size_t(window_channels) *
                        element_bytes);
    }
}

/// The grain model's tiles, as the host registers them. Called once per stock, not per frame.
inline void dump_tiles(int32_t id, const float *tiles, int64_t count) {
    const char *root = text("FOTUFILM_BAKE_DIR");
    if (!root || !tiles || count <= 0) return;
    std::lock_guard<std::mutex> lock(gate());
    if (tiles_written() >= integer("FOTUFILM_BAKE_MAX_TILE_SETS", 4)) return;
    ++tiles_written();
    const std::string directory(root);
    make_directory(directory);
    const std::string tag = text("FOTUFILM_BAKE_TAG") ? text("FOTUFILM_BAKE_TAG") : "bake";
    const std::string name = tag + "-tiles-" + std::to_string(id) + ".f32";
    write_block(directory, name.c_str(), tiles, size_t(count) * sizeof(float));
}

}  // namespace bake
}  // namespace fotufilm

#endif  // FOTOFILM_HALIDE_BAKE_DUMP_H
