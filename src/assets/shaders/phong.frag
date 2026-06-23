#version 400 core

in vec3 vFragPos;
in vec3 vNormal;
in vec2 vTexCoord;

// ── Material ──────────────────────────────────────────────────────────────────
uniform bool  uUseTexture;
uniform vec3  uBaseColor;        // used when uUseTexture == false
uniform sampler2D uTexture;

uniform float uAmbientStrength;  // Ka
uniform float uDiffuseStrength;  // Kd
uniform float uSpecularStrength; // Ks
uniform float uShininess;        // shininess exponent

// ── Light (single moving point-light + global ambient) ────────────────────────
uniform vec3  uLightPos;
uniform vec3  uLightColor;
uniform float uLightIntensity;

// ── Camera ────────────────────────────────────────────────────────────────────
uniform vec3  uViewPos;

out vec4 FragColor;

void main() {
    // Base colour from texture or solid
    vec3 baseColor;
    if (uUseTexture) {
        baseColor = texture(uTexture, vTexCoord).rgb;
    } else {
        baseColor = uBaseColor;
    }

    vec3 N = normalize(vNormal);
    vec3 L = normalize(uLightPos - vFragPos);
    vec3 V = normalize(uViewPos  - vFragPos);
    vec3 R = reflect(-L, N);            // Phong reflection vector

    // ── Phong components ─────────────────────────────────────────────────────
    vec3 ambient  = uAmbientStrength  * uLightColor * baseColor;

    float diff    = max(dot(N, L), 0.0);
    vec3 diffuse  = uDiffuseStrength  * diff * uLightColor * baseColor;

    float spec    = pow(max(dot(V, R), 0.0), uShininess);
    vec3 specular = uSpecularStrength * spec * uLightColor;   // highlights use light colour

    vec3 result   = (ambient + diffuse + specular) * uLightIntensity;
    FragColor     = vec4(result, 1.0);
}
