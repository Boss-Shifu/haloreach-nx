# Halo: Reach (Xbox 360, Title ID 4D53085B) — Nintendo Switch CMakeLists.txt
# Compila el código C++ generado por ReXGlue + los 4 módulos DLL XEX estáticos + Mesa/NVK (Vulkan 1.4 GM20B)
# Optimizado para 60 FPS en Switch con OC (1750 MHz CPU / 765 MHz GPU / 2600 MHz RAM).

cmake_minimum_required(VERSION 3.25)
project(haloreach VERSION 0.1.0 LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(HR_PROJECT "${CMAKE_CURRENT_SOURCE_DIR}/../project")
set(REXSDK_DIR "" CACHE PATH "ReXGlue SDK source (Horizon Switch fork)")
if(NOT REXSDK_DIR)
    message(FATAL_ERROR "Set REXSDK_DIR to the patched Horizon-fork ReXGlue SDK")
endif()

add_compile_definitions(REX_HAS_FIDELITYFX_SDK=1)
add_subdirectory("${REXSDK_DIR}" rexglue-sdk)

if(NOT EXISTS "${HR_PROJECT}/generated/default/sources.cmake")
    message(FATAL_ERROR "Run tools/codegen.sh first to generate Halo: Reach C++ sources")
endif()

include("${HR_PROJECT}/generated/default/sources.cmake")
set(HR_GENERATED "")
foreach(src ${GENERATED_SOURCES})
    if(IS_ABSOLUTE "${src}")
        list(APPEND HR_GENERATED "${src}")
    else()
        list(APPEND HR_GENERATED "${HR_PROJECT}/${src}")
    endif()
endforeach()

add_library(haloreach_recomp OBJECT ${HR_GENERATED})
target_include_directories(haloreach_recomp PRIVATE
    "${HR_PROJECT}"
    "${HR_PROJECT}/src"
    "${HR_PROJECT}/generated/default")
target_link_libraries(haloreach_recomp PRIVATE rex::runtime)
rexglue_apply_target_settings(haloreach_recomp)
if(EXISTS "${HR_PROJECT}/generated/default/haloreach_pch.h")
    target_precompile_headers(haloreach_recomp PRIVATE "${HR_PROJECT}/generated/default/haloreach_pch.h")
endif()

set(HR_EXTRA_TARGETS "")
foreach(m waveshell_xbox waveslibdll l360 q10)
    if(EXISTS "${HR_PROJECT}/generated/${m}/sources.cmake")
        unset(GENERATED_SOURCES)
        include("${HR_PROJECT}/generated/${m}/sources.cmake")
        set(_SRCS "")
        foreach(src ${GENERATED_SOURCES})
            if(IS_ABSOLUTE "${src}")
                list(APPEND _SRCS "${src}")
            else()
                list(APPEND _SRCS "${HR_PROJECT}/${src}")
            endif()
        endforeach()
        if(m STREQUAL "l360" AND EXISTS "${HR_PROJECT}/src/autoport/haloreach_L360_xdll_imports.cpp")
            list(APPEND _SRCS "${HR_PROJECT}/src/autoport/haloreach_L360_xdll_imports.cpp")
        elseif(m STREQUAL "q10" AND EXISTS "${HR_PROJECT}/src/autoport/haloreach_Q10_xdll_imports.cpp")
            list(APPEND _SRCS "${HR_PROJECT}/src/autoport/haloreach_Q10_xdll_imports.cpp")
        endif()
        add_library(haloreach_${m} OBJECT ${_SRCS})
        target_compile_definitions(haloreach_${m} PRIVATE
            ReXModule_Register=${m}_ReXModule_Register
            ReXModule_GetImageInfo=${m}_ReXModule_GetImageInfo
            PPCImageConfig=${m}_PPCImageConfig
            PPCFuncMappings=${m}_PPCFuncMappings
        )
        target_include_directories(haloreach_${m} PRIVATE
            "${HR_PROJECT}"
            "${HR_PROJECT}/src"
            "${HR_PROJECT}/generated/${m}"
            "${HR_PROJECT}/generated/default"
        )
        target_link_libraries(haloreach_${m} PRIVATE rex::runtime)
        rexglue_apply_target_settings(haloreach_${m})
        if(EXISTS "${HR_PROJECT}/generated/${m}/haloreach_pch.h")
            target_precompile_headers(haloreach_${m} PRIVATE "${HR_PROJECT}/generated/${m}/haloreach_pch.h")
        endif()
        if(EXISTS "${HR_PROJECT}/generated/${m}/haloreach_register.cpp")
            set_source_files_properties("${HR_PROJECT}/generated/${m}/haloreach_register.cpp"
                PROPERTIES COMPILE_OPTIONS "-O0" SKIP_PRECOMPILE_HEADERS ON)
        endif()
        list(APPEND HR_EXTRA_TARGETS haloreach_${m})
    endif()
endforeach()

set(HR_APP_SOURCES
    "${HR_PROJECT}/src/main.cpp"
    "${HR_PROJECT}/src/haloreach_hooks.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/static_modules.cpp"
)

add_executable(haloreach ${HR_APP_SOURCES})
target_include_directories(haloreach PRIVATE
    "${HR_PROJECT}"
    "${HR_PROJECT}/src"
    "${HR_PROJECT}/generated/default"
    "${REXSDK_DIR}/src/core"
    "${REXSDK_DIR}/src/graphics"
    "${REXSDK_DIR}/thirdparty/glslang")
target_compile_definitions(haloreach PRIVATE HALOREACH_LINK_STATIC_MODULES=1)
target_link_libraries(haloreach PRIVATE haloreach_recomp ${HR_EXTRA_TARGETS} rex::runtime)
rexglue_configure_target(haloreach GPU_PLUGINS xenos)

set_property(TARGET haloreach APPEND PROPERTY LINK_DEPENDS "${REXGLUE_SWITCH_NVK_SDK}/lib/libvulkan.a")

# Presupuesto de Heap en Switch (Title Takeover tiene ~3.2 GB; reservamos 2304 MB para el heap del invitado y dejamos margen para NVK/Mesa)
set(HR_SWITCH_HEAP_MB 2304 CACHE STRING "Capped Switch heap size in MiB")
set_source_files_properties("${REXSDK_DIR}/src/ui/runtime_switch.cpp" DIRECTORY "${REXSDK_DIR}"
    PROPERTIES COMPILE_DEFINITIONS "REX_SWITCH_HEAP_MB=${HR_SWITCH_HEAP_MB}")

set(HR_SWITCH_HOST_STACK_MB 2 CACHE STRING "Host stack budget per Xbox thread in MiB")
set_source_files_properties("${REXSDK_DIR}/src/system/xthread.cpp" DIRECTORY "${REXSDK_DIR}/src/system"
    PROPERTIES COMPILE_DEFINITIONS "REX_SWITCH_HOST_STACK_MB=${HR_SWITCH_HOST_STACK_MB}")

if(EXISTS "${HR_PROJECT}/generated/default/haloreach_register.cpp")
    set_source_files_properties("${HR_PROJECT}/generated/default/haloreach_register.cpp"
        PROPERTIES COMPILE_OPTIONS "-O0" SKIP_PRECOMPILE_HEADERS ON)
endif()

# Flags de optimización ARM64 Cortex-A57 (Tegra X1) para alcanzar 60 FPS con OC 1750/765/2600 MHz
foreach(t haloreach haloreach_recomp ${HR_EXTRA_TARGETS})
    target_compile_options(${t} PRIVATE
        -mcpu=cortex-a57+crc+crypto
        -ffp-contract=off
        -fno-strict-aliasing
        -fno-math-errno
        -fno-trapping-math)
endforeach()

rexglue_switch_add_nro(haloreach
    NAME "Halo: Reach NX"
    AUTHOR "NXMasters"
    VERSION "0.1.0"
    ICON "${CMAKE_CURRENT_SOURCE_DIR}/../extras/icon.jpg")
