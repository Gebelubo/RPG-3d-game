#version 400 core

in vec2 vTexCoord;

uniform bool      uUseTexture;
uniform vec3      uBaseColor;
uniform sampler2D uTexture;
uniform float     uAlpha;      // 1.0 = opaco, 0.0 = invisível

out vec4 FragColor;

void main() {
    if (uUseTexture) {
        vec4 tex = texture(uTexture, vTexCoord);
        FragColor = vec4(tex.rgb, tex.a * uAlpha);
    } else {
        FragColor = vec4(uBaseColor, uAlpha);
    }
}
