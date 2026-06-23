import ctypes
import numpy as np
from OpenGL.GL import (
    glGenVertexArrays, glBindVertexArray,
    glGenBuffers, glBindBuffer, glBufferData,
    glEnableVertexAttribArray, glVertexAttribPointer, glVertexAttribIPointer,
    glDrawElements, glDeleteVertexArrays, glDeleteBuffers,
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER,
    GL_STATIC_DRAW, GL_FLOAT, GL_UNSIGNED_SHORT, GL_UNSIGNED_INT,
    GL_TRIANGLES, GL_FALSE,
)

from .gltf_loader import SkinnedMeshData

MAX_BONES = 100  # deve bater com `#define MAX_BONES 100` em skinned.vert


class SkinnedMesh:
    """
    Mesh com skinning. Uso:
        smesh = SkinnedMesh(skinned_mesh_data)
        ...
        shader.use()
        shader.set_mat4_array("uBoneMatrices", bone_matrices_list)  # ver shader.py
        smesh.draw()
    """

    POS_NRM_UV_STRIDE = 8 * 4          # 32 bytes
    JOINTS_STRIDE      = 4 * 2          # 8 bytes  (4 x uint16)
    WEIGHTS_STRIDE     = 4 * 4          # 16 bytes (4 x float32)

    def __init__(self, mesh_data: SkinnedMeshData):
        self.name         = mesh_data.name
        self.index_count  = len(mesh_data.indices)
        self.bones        = mesh_data.bones
        self.clips        = mesh_data.clips
        self.texture_path = mesh_data.texture_path
        self.base_color   = mesh_data.base_color

        # Material defaults — mesmos campos que Mesh usa em scene.py:SceneNode.draw,
        # para podermos reaproveitar uniforms de Phong sem mexer em scene.py.
        self.ka = 0.3
        self.kd = 0.8
        self.ks = 0.3
        self.shininess = 24.0

        self._destroyed = False
        self._upload(mesh_data)

    def _upload(self, mesh_data: SkinnedMeshData):
        self.vao = glGenVertexArrays(1)
        vbo_pos, vbo_joints, vbo_weights, ibo = glGenBuffers(4)
        self.vbo_pos     = vbo_pos
        self.vbo_joints  = vbo_joints
        self.vbo_weights = vbo_weights
        self.ibo         = ibo

        glBindVertexArray(self.vao)

        # VBO 0: position/normal/uv (Estrutura Intercalada vinda do gltf_loader)
        glBindBuffer(GL_ARRAY_BUFFER, vbo_pos)
        glBufferData(GL_ARRAY_BUFFER, mesh_data.vertices.nbytes, mesh_data.vertices, GL_STATIC_DRAW)
        
        # Correção: Forçando conversão para int puro antes do c_void_p para evitar ponteiros corrompidos
        offset_pos    = ctypes.c_void_p(0)
        offset_normal = ctypes.c_void_p(int(3 * 4))  # 12 bytes
        offset_uv     = ctypes.c_void_p(int(6 * 4))  # 24 bytes

        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, self.POS_NRM_UV_STRIDE, offset_pos)
        
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, self.POS_NRM_UV_STRIDE, offset_normal)
        
        glEnableVertexAttribArray(2)
        glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, self.POS_NRM_UV_STRIDE, offset_uv)

        # VBO 1: joints (location 3) — inteiros, usa glVertexAttribIPointer
        glBindBuffer(GL_ARRAY_BUFFER, vbo_joints)
        joints_data = mesh_data.joints.astype(np.uint16)
        glBufferData(GL_ARRAY_BUFFER, joints_data.nbytes, joints_data, GL_STATIC_DRAW)
        glEnableVertexAttribArray(3)
        glVertexAttribIPointer(3, 4, GL_UNSIGNED_SHORT, self.JOINTS_STRIDE, ctypes.c_void_p(0))

        # VBO 2: weights (location 4)
        glBindBuffer(GL_ARRAY_BUFFER, vbo_weights)
        weights_data = mesh_data.weights.astype(np.float32)
        glBufferData(GL_ARRAY_BUFFER, weights_data.nbytes, weights_data, GL_STATIC_DRAW)
        glEnableVertexAttribArray(4)
        glVertexAttribPointer(4, 4, GL_FLOAT, GL_FALSE, self.WEIGHTS_STRIDE, ctypes.c_void_p(0))

        # IBO
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ibo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, mesh_data.indices.nbytes, mesh_data.indices, GL_STATIC_DRAW)

        glBindVertexArray(0)

    def draw(self):
        if self._destroyed:
            return
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, self.index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        glDeleteVertexArrays(1, [self.vao])
        glDeleteBuffers(4, [self.vbo_pos, self.vbo_joints, self.vbo_weights, self.ibo])

    cleanup = destroy