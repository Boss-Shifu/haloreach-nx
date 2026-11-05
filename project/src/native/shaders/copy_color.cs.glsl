// Adapted from Project8Recomp (GPL-3.0), src/game/src/native/; generic Xenos GPU code.
#version 450
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Copies a rectangle of a color image into another of the same format, for
// resolves. vkCmdCopyImage on NVK draws through its meta path, which creates
// image views and buffers for every copy and destroys them when the command
// buffer is reset: with about 30 resolves a frame that was 5% of the command
// ring thread. This needs no objects of its own (shaderStorageImageWrite-
// WithoutFormat covers every destination format with one pipeline).
//
// Rebuild copy_color_cs.h after editing:
//   glslangValidator -S comp -V --target-env vulkan1.1
//     --vn kCopyColorCs -o copy_color_cs.h copy_color.cs.glsl
#extension GL_EXT_samplerless_texture_functions : require
layout(local_size_x = 8, local_size_y = 8) in;
layout(set = 0, binding = 0) uniform texture2D source;
layout(set = 0, binding = 1) uniform writeonly image2D dest;
layout(push_constant) uniform Params {
  ivec2 source_origin;
  ivec2 dest_origin;
  uvec2 size;
  // Resolve format conversion: multiply by 2^exp_bias, and clamp to
  // [0, maximum] when maximum > 0 (FH2: 7e3 render targets hold nothing above
  // 31.875 on the console; the host float16 keeps more).
  float scale;
  float maximum;
};
void main() {
  uvec2 p = gl_GlobalInvocationID.xy;
  if (p.x >= size.x || p.y >= size.y) {
    return;
  }
  vec4 v = texelFetch(source, source_origin + ivec2(p), 0) * scale;
  if (maximum > 0.0) {
    v = clamp(v, vec4(0.0), vec4(maximum));
  }
  imageStore(dest, dest_origin + ivec2(p), v);
}
