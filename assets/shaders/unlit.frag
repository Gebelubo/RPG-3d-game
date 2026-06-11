#version 400 core

in vec2 vTexCoord;

uniform bool      uUseTexture;
uniform vec3      uBaseColor;
uniform sampler2D uTexture;

out vec4 FragColor;

void main() {
    if (uUseTexture) {
        FragColor = texture(uTexture, vTexCoord);
    } else {
        FragColor = vec4(uBaseColor, 1.0);
    }
}
