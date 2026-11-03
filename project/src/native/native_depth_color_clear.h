#pragma once

#include "native_stencil_clear.h"

namespace reach_nx::native {

// Format enum values are interpreted according to the render-target kind.
// These are the only cross-kind formats for which the current depth-zero
// clear mirror is known to preserve the guest's packed 32-bit zero value.
constexpr uint32_t kDepthClearFormatD24S8 = 0;
constexpr uint32_t kDepthClearFormatD24FS8 = 1;
constexpr uint32_t kColorClearFormatR8G8B8A8 = 0;
constexpr uint32_t kColorClearFormatR8G8B8A8Gamma = 1;

constexpr bool IsColorClearFormat32bpp(uint32_t format) {
  // 5 = k_16_16_16_16, 7 = k_16_16_16_16_FLOAT, 9 = k_32_32_FLOAT (64bpp).
  // All other Xenos color render-target formats are 32bpp (1 dword per sample).
  return format != 5 && format != 7 && format != 9 && format <= 15;
}

// With an identity viewport Z transform, a predivided Z is already the
// rasterized depth. Otherwise require W=1 before comparing a guest D24 clear.
constexpr bool IsConstantDepthClearVertex(float z, float w, bool z_predivided,
                                          float expected_depth) {
  return z == expected_depth && (z_predivided || w == 1.0f);
}

namespace depth_color_clear_detail {

constexpr uint32_t kEdramTileWidthSamples = 80;
constexpr uint32_t kEdramTileHeightSamples = 16;

constexpr bool IsTileEdge(int32_t edge, uint32_t tile_size_pixels) {
  return edge >= 0 && tile_size_pixels != 0 &&
         uint32_t(edge) % tile_size_pixels == 0;
}

constexpr bool IsFullTileRect(const StencilClearRect& rect, uint32_t tile_width_pixels,
                              uint32_t tile_height_pixels) {
  return rect.x1 > rect.x0 && rect.y1 > rect.y0 &&
         IsTileEdge(rect.x0, tile_width_pixels) && IsTileEdge(rect.x1, tile_width_pixels) &&
         IsTileEdge(rect.y0, tile_height_pixels) && IsTileEdge(rect.y1, tile_height_pixels);
}

}  // namespace depth_color_clear_detail

// Maps a depth-zero clear to the corresponding color alias only when it covers
// whole physical Xenos EDRAM tiles. Depth and color targets have separate host
// images, so callers must additionally prove that both layouts refer to the
// same guest EDRAM owner and that the depth and stencil clear values are zero.
// Coordinates are guest logical pixels; for identical guest MSAA layouts they
// remain unchanged. `destination_rect` is zeroed on failure.
constexpr bool MapConstantDepthColorClearRectangle(
    const StencilClearLayout& source_depth, const StencilClearLayout& destination_color,
    const StencilClearRect& source_rect, StencilClearRect& destination_rect) {
  destination_rect = {};

  if (source_depth.format > kDepthClearFormatD24FS8 ||
      !IsColorClearFormat32bpp(destination_color.format) ||
      source_depth.base_tiles != destination_color.base_tiles ||
      source_depth.pitch_pixels == 0 || destination_color.pitch_pixels == 0 ||
      source_depth.guest_msaa > 2 || destination_color.guest_msaa > 2 ||
      stencil_clear_detail::EdramPitchTiles(source_depth) !=
          stencil_clear_detail::EdramPitchTiles(destination_color) ||
      source_depth.width == 0 || source_depth.height == 0 || destination_color.width == 0 ||
      destination_color.height == 0 || source_rect.x1 <= source_rect.x0 ||
      source_rect.y1 <= source_rect.y0) {
    return false;
  }

  // Vulkan clips the original clear to the source image. Reject any clipped
  // source rectangle that no longer covers whole physical EDRAM tiles.
  const int64_t sx0 = stencil_clear_detail::Clamp(source_rect.x0, 0, source_depth.width);
  const int64_t sy0 = stencil_clear_detail::Clamp(source_rect.y0, 0, source_depth.height);
  const int64_t sx1 = stencil_clear_detail::Clamp(source_rect.x1, 0, source_depth.width);
  const int64_t sy1 = stencil_clear_detail::Clamp(source_rect.y1, 0, source_depth.height);
  if (sx1 <= sx0 || sy1 <= sy0 || sx1 > INT32_MAX || sy1 > INT32_MAX) return false;

  const StencilClearRect clipped_source{int32_t(sx0), int32_t(sy0), int32_t(sx1),
                                        int32_t(sy1)};
  const uint32_t source_tile_width =
      depth_color_clear_detail::kEdramTileWidthSamples /
      stencil_clear_detail::SampleScaleX(source_depth.guest_msaa);
  const uint32_t source_tile_height =
      depth_color_clear_detail::kEdramTileHeightSamples /
      stencil_clear_detail::SampleScaleY(source_depth.guest_msaa);
  if (!depth_color_clear_detail::IsFullTileRect(clipped_source, source_tile_width,
                                                source_tile_height)) {
    return false;
  }

  StencilClearRect mapped{};
  if (!stencil_clear_detail::MapEdge(
          sx0, stencil_clear_detail::SampleScaleX(source_depth.guest_msaa),
          stencil_clear_detail::SampleScaleX(destination_color.guest_msaa), mapped.x0) ||
      !stencil_clear_detail::MapEdge(
          sx1, stencil_clear_detail::SampleScaleX(source_depth.guest_msaa),
          stencil_clear_detail::SampleScaleX(destination_color.guest_msaa), mapped.x1) ||
      !stencil_clear_detail::MapEdge(
          sy0, stencil_clear_detail::SampleScaleY(source_depth.guest_msaa),
          stencil_clear_detail::SampleScaleY(destination_color.guest_msaa), mapped.y0) ||
      !stencil_clear_detail::MapEdge(
          sy1, stencil_clear_detail::SampleScaleY(source_depth.guest_msaa),
          stencil_clear_detail::SampleScaleY(destination_color.guest_msaa), mapped.y1)) {
    return false;
  }

  mapped.x0 = int32_t(stencil_clear_detail::Clamp(mapped.x0, 0, destination_color.width));
  mapped.y0 = int32_t(stencil_clear_detail::Clamp(mapped.y0, 0, destination_color.height));
  mapped.x1 = int32_t(stencil_clear_detail::Clamp(mapped.x1, 0, destination_color.width));
  mapped.y1 = int32_t(stencil_clear_detail::Clamp(mapped.y1, 0, destination_color.height));
  const uint32_t destination_tile_width =
      depth_color_clear_detail::kEdramTileWidthSamples /
      stencil_clear_detail::SampleScaleX(destination_color.guest_msaa);
  const uint32_t destination_tile_height =
      depth_color_clear_detail::kEdramTileHeightSamples /
      stencil_clear_detail::SampleScaleY(destination_color.guest_msaa);
  if (!depth_color_clear_detail::IsFullTileRect(mapped, destination_tile_width,
                                                destination_tile_height)) {
    return false;
  }

  destination_rect = mapped;
  return true;
}

constexpr bool MapZeroDepthColorClearRectangle(const StencilClearLayout& source_depth,
                                              const StencilClearLayout& destination_color,
                                              const StencilClearRect& source_rect,
                                              StencilClearRect& destination_rect) {
  return MapConstantDepthColorClearRectangle(source_depth, destination_color, source_rect,
                                             destination_rect);
}

}  // namespace reach_nx::native
