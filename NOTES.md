# fotufilm-android-probe

Builds [DhaliwalX/fotufilm-engine](https://github.com/DhaliwalX/fotufilm-engine)'s Android
Vulkan engine (`libfotufilm.so`, arm64-v8a) on an x86_64 runner.

**Not affiliated with Fotufilm.** This repository only runs their public build scripts at a
pinned commit and publishes the resulting binary, for evaluation purposes. The engine is
Apache-2.0, the film profiles are CC BY-SA 4.0; see their `NOTICE`, `LICENSING.md` and
`THIRD_PARTY_NOTICES.md`.

## Why a runner and not the phone

`tools/build-android-engine.sh` needs, all at once:

| | |
|---|---|
| LLVM / Clang / LLD | >= 21 (their `tools/aot-toolchain.json` pins 22.1.8) |
| Halide | their `third_party/Halide` pin **plus five Vulkan patches** — without them the Vulkan kernels develop a flat, near-black frame (their own note) |
| Swift | 6.3.3 **and** the Swift SDK for Android |
| NDK | `aarch64-linux-android28` |
| codecs | libraw_r, libheif, libde265, libtiff, libpng16, libjpeg, lcms2, OpenEXR x4, Imath |

Building LLVM and Halide from source and cross-compiling 60k lines of Swift does not happen
on a phone, so this runs on GitHub's runners. Each run is 1.5-3 h.

## What you get

`fotufilm-android-engine.zip` containing `jniLibs/arm64-v8a/libfotufilm.so` and the Swift
runtime it needs beside it. The C ABI is `Sources/CFotufilmHost/include/fotufilm.h`:

```c
fotufilm_engine *fotufilm_engine_create(char **error);
fotufilm_image  *fotufilm_image_open(fotufilm_engine *, const char *path, char **error);
int32_t fotufilm_render(fotufilm_engine *, fotufilm_image *, const char *request_json, ...);
```

A request is JSON, so a host does not need the Swift engine's types.

## Cost

Step 5 of their script says the Swift runtime and Foundation/ICU ride beside the library in
the APK. Expect a 100 MB-class package. That is fine for a probe and not fine for a
15.9 MB app.

## Ground truth for "does it look right"

`fotufilm.com/demo` is WASM + WebGPU and runs in Android Chrome, so the reference output can
be had from a phone browser without building anything.
