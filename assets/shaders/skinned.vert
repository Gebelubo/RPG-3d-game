#version 400 core

// Mesmo trio de atributos do phong.vert...
layout(location = 0) in vec3  aPosition;
layout(location = 1) in vec3  aNormal;
layout(location = 2) in vec2  aTexCoord;
// ...+ os 2 atributos extra de skinning (JOINTS_0 / WEIGHTS_0 do glTF)
layout(location = 3) in uvec4 aJoints;
layout(location = 4) in vec4  aWeights;

#define MAX_BONES 100

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform mat3 uNormalMatrix;        // transpose(inverse(model)) para normais
uniform mat4 uBoneMatrices[MAX_BONES];

out vec3 vFragPos;
out vec3 vNormal;
out vec2 vTexCoord;

void main() {
    // mat4 por vértice = soma ponderada das matrizes de osso
    mat4 skinMatrix =
          aWeights.x * uBoneMatrices[aJoints.x]
        + aWeights.y * uBoneMatrices[aJoints.y]
        + aWeights.z * uBoneMatrices[aJoints.z]
        + aWeights.w * uBoneMatrices[aJoints.w];

    vec4 skinnedPos    = skinMatrix * vec4(aPosition, 1.0);
    vec3 skinnedNormal = mat3(skinMatrix) * aNormal;

    vec4 worldPos = uModel * skinnedPos;
    vFragPos      = vec3(worldPos);
    vNormal       = normalize(uNormalMatrix * skinnedNormal);
    vTexCoord     = aTexCoord;
    gl_Position   = uProjection * uView * worldPos;
}
