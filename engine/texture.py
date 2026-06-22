"""
texture.py  –  Load images into OpenGL textures.
Uses Pillow only for image decoding; all GL calls are explicit.
"""

import numpy as np
from PIL import Image
from OpenGL.GL import (
    glGenTextures, glBindTexture, glTexImage2D, glGenerateMipmap,
    glTexParameteri, glActiveTexture, glDeleteTextures,
    GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T,
    GL_LINEAR_MIPMAP_LINEAR, GL_LINEAR,
    GL_REPEAT, GL_RGBA, GL_RGB, GL_UNSIGNED_BYTE,
    GL_TEXTURE0,
)


class Texture:
    def __init__(self, path: str):
        self.id   = 0
        self.path = path
        self._load(path)

    def _load(self, path: str):
        try:
            img = Image.open(path)
            img.thumbnail((1024, 1024), Image.LANCZOS)   # limita a 1024px mantendo proporção
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            fmt  = GL_RGBA if img.mode == "RGBA" else GL_RGB
            data = img.convert("RGBA" if fmt == GL_RGBA else "RGB").tobytes()

            self.id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.id)
            glTexImage2D(GL_TEXTURE_2D, 0, fmt, img.width, img.height,
                         0, fmt, GL_UNSIGNED_BYTE, data)
            glGenerateMipmap(GL_TEXTURE_2D)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glBindTexture(GL_TEXTURE_2D, 0)
        except Exception as exc:
            # Fail gracefully: create a small procedural 4x4 checker texture
            print(f"Texture load failed for {path}: {exc}")
            size = 4
            data = []
            ca = (200, 200, 200); cb = (80, 80, 100)
            for y in range(size):
                for x in range(size):
                    c = ca if (x + y) % 2 == 0 else cb
                    data.extend([c[0], c[1], c[2]])
            arr = np.array(data, dtype=np.uint8)
            self.id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.id)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, size, size,
                         0, GL_RGB, GL_UNSIGNED_BYTE, arr)
            glGenerateMipmap(GL_TEXTURE_2D)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glBindTexture(GL_TEXTURE_2D, 0)

    def bind(self, unit: int = 0):
        glActiveTexture(GL_TEXTURE0 + unit)
        glBindTexture(GL_TEXTURE_2D, self.id)

    def unbind(self):
        glBindTexture(GL_TEXTURE_2D, 0)

    def destroy(self):
        if self.id:
            glDeleteTextures(1, [self.id])
            self.id = 0


class ProceduralTexture(Texture):
    """Generate a simple checkerboard texture without any image file."""

    def __init__(self, size=64, color_a=(200,200,200), color_b=(100,100,100)):
        # bypass parent __init__
        self.path = "<procedural>"
        self.id   = 0
        self._generate(size, color_a, color_b)

    def _generate(self, size, ca, cb):
        data = []
        for y in range(size):
            for x in range(size):
                c = ca if (x // (size//8) + y // (size//8)) % 2 == 0 else cb
                data.extend([c[0], c[1], c[2]])
        arr = np.array(data, dtype=np.uint8)

        self.id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, size, size,
                     0, GL_RGB, GL_UNSIGNED_BYTE, arr)
        glGenerateMipmap(GL_TEXTURE_2D)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glBindTexture(GL_TEXTURE_2D, 0)
