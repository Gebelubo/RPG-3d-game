"""
mesh.py  –  GPU-side mesh (VAO/VBO/IBO).
Uploads MeshData and draws with glDrawElements.
"""

import numpy as np
from OpenGL.GL import (
    glGenVertexArrays, glBindVertexArray,
    glGenBuffers, glBindBuffer, glBufferData,
    glEnableVertexAttribArray, glVertexAttribPointer,
    glDrawElements, glDeleteVertexArrays, glDeleteBuffers,
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER,
    GL_STATIC_DRAW, GL_FLOAT, GL_UNSIGNED_INT, GL_TRIANGLES, GL_FALSE,
)
from .obj_loader import MeshData


class Mesh:
    """
    Vertex layout (stride = 8 floats = 32 bytes):
      location 0 → position  (3 floats)
      location 1 → normal    (3 floats)
      location 2 → texcoord  (2 floats)
    """

    STRIDE = 8 * 4  

    def __init__(self, mesh_data: MeshData):
        self.name         = mesh_data.name
        self.index_count  = len(mesh_data.indices)

        self.base_color    = mesh_data.base_color
        self.ka            = mesh_data.ka
        self.kd            = mesh_data.kd
        self.ks            = mesh_data.ks
        self.shininess     = mesh_data.shininess
        self.texture_path  = mesh_data.texture_path

        self._destroyed = False
        self._upload(mesh_data.vertices, mesh_data.indices)

    def _upload(self, vertices: np.ndarray, indices: np.ndarray):
        self.vao = glGenVertexArrays(1)
        vbo, ibo = glGenBuffers(2)
        self.vbo = vbo
        self.ibo = ibo

        glBindVertexArray(self.vao)

        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ibo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

  
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, self.STRIDE,
                              ctypes_offset(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, self.STRIDE,
                              ctypes_offset(3 * 4))
        glEnableVertexAttribArray(2)
        glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, self.STRIDE,
                              ctypes_offset(6 * 4))

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
        glDeleteBuffers(2, [self.vbo, self.ibo])

    cleanup = destroy



import ctypes

def ctypes_offset(byte_offset: int):
    return ctypes.c_void_p(byte_offset)



class ProceduralMesh(Mesh):

    def __init__(self, name: str, vertices: np.ndarray, indices: np.ndarray,
                 base_color=(0.8, 0.8, 0.8), ka=0.2, kd=0.8, ks=0.5, shininess=32.0):
        self.name        = name
        self.index_count = len(indices)
        self.base_color  = base_color
        self.ka          = ka
        self.kd          = kd
        self.ks          = ks
        self.shininess   = shininess
        self.texture_path = None
        self._destroyed  = False
        self._upload(vertices, indices)


def make_cube(half=0.5) -> tuple[np.ndarray, np.ndarray]:
    h = half

    faces = [
        [ h,-h,-h,  1,0,0,  0,0],  [ h, h,-h,  1,0,0,  1,0],
        [ h, h, h,  1,0,0,  1,1],  [ h,-h, h,  1,0,0,  0,1],
        [-h,-h, h, -1,0,0,  0,0],  [-h, h, h, -1,0,0,  1,0],
        [-h, h,-h, -1,0,0,  1,1],  [-h,-h,-h, -1,0,0,  0,1],
        [-h, h,-h,  0,1,0,  0,0],  [-h, h, h,  0,1,0,  0,1],
        [ h, h, h,  0,1,0,  1,1],  [ h, h,-h,  0,1,0,  1,0],
        [-h,-h, h,  0,-1,0, 0,0],  [-h,-h,-h,  0,-1,0, 0,1],
        [ h,-h,-h,  0,-1,0, 1,1],  [ h,-h, h,  0,-1,0, 1,0],
        [ h,-h, h,  0,0,1,  0,0],  [ h, h, h,  0,0,1,  1,0],
        [-h, h, h,  0,0,1,  1,1],  [-h,-h, h,  0,0,1,  0,1],
        [-h,-h,-h,  0,0,-1, 0,0],  [-h, h,-h,  0,0,-1, 1,0],
        [ h, h,-h,  0,0,-1, 1,1],  [ h,-h,-h,  0,0,-1, 0,1],
    ]
    verts = np.array(faces, dtype=np.float32)
    idxs = []
    for f in range(6):
        b = f * 4
        idxs.extend([b, b+1, b+2, b, b+2, b+3])
    indices = np.array(idxs, dtype=np.uint32)
    return verts, indices


def make_plane(w=10.0, d=10.0, divs=1, tile_u=1.0, tile_v=1.0):
    verts = []
    idxs = []

    step_x = w / divs
    step_z = d / divs

    for iz in range(divs + 1):
        for ix in range(divs + 1):
            x = -w/2 + ix * step_x
            z = -d/2 + iz * step_z

            u = (ix / divs) * tile_u
            v = (iz / divs) * tile_v

            verts.extend([
                x, 0.0, z,
                0, 1, 0,
                u, v
            ])

    for iz in range(divs):
        for ix in range(divs):
            row = divs + 1
            base = iz * row + ix

            idxs.extend([
                base, base + row, base + 1,
                base + 1, base + row, base + row + 1
            ])

    return (
        np.array(verts, dtype=np.float32).reshape(-1, 8),
        np.array(idxs, dtype=np.uint32)
    )

def make_sphere(radius=0.5, stacks=16, slices=16) -> tuple[np.ndarray, np.ndarray]:
    import math
    verts = []
    idxs  = []
    for i in range(stacks + 1):
        phi = math.pi * i / stacks
        for j in range(slices + 1):
            theta = 2 * math.pi * j / slices
            x = math.sin(phi) * math.cos(theta)
            y = math.cos(phi)
            z = math.sin(phi) * math.sin(theta)
            u = j / slices
            v = i / stacks
            verts.extend([x*radius, y*radius, z*radius, x, y, z, u, v])
    for i in range(stacks):
        for j in range(slices):
            row  = slices + 1
            a    = i * row + j
            b    = a + row
            idxs.extend([a, b, a+1, a+1, b, b+1])
    return (np.array(verts, dtype=np.float32).reshape(-1, 8),
            np.array(idxs,  dtype=np.uint32))
