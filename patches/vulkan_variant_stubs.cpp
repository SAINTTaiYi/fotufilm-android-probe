// The Vulkan AOT variants this build does not compile, defined so the library loads.
//
// `FotofilmHalideLinux.cpp` keeps one table of every generated Vulkan variant and
// takes each one's address. Those are data relocations: Android's linker resolves
// them when the library is opened, so a table entry with no definition is not a
// link failure -- the .so links (undefined symbols are legal in a shared object)
// and then fails to load with
//     cannot locate symbol "fotufilm_aot_vulkan_color"
// which is what a build without the 2864 per-variant kernels produces.
//
// The CI job deliberately does not generate them (123 MB of .rodata, and the CPU
// developer is the one that runs), so the addresses have to exist. Returning -3
// is the code `develop()` already treats as "this variant is not available"; on a
// phone the CPU developer is chosen before any of this is reached, so nothing
// calls them.
//
// Built only when the real kernels are absent (FOTUFILM_VULKAN_STUBS): with them
// present these would be duplicate definitions.

#if defined(FOTUFILM_VULKAN_STUBS)

#include "FotufilmAotFrame.h"

#define FOTUFILM_AOT_STUB(variant_name, variant_mask)                                  \
    extern "C" int fotufilm_aot_vulkan_##variant_name(FOTUFILM_AOT_FRAME_SIGNATURE) { \
        (void)variant_mask;                                                            \
        return -3;                                                                     \
    }

FOTOFILM_AOT_VARIANTS(FOTOFILM_AOT_STUB)

#undef FOTOFILM_AOT_STUB

#endif  // FOTUFILM_VULKAN_STUBS
