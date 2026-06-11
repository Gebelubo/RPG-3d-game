"""
hud.py  –  2-D HUD rendered as OpenGL quads (no pygame.draw calls).
Text is rasterized by pygame.font → Surface → uploaded as a texture,
then drawn as a screen-space quad using the unlit shader.
"""

import pygame
import numpy as np
import ctypes
from OpenGL.GL import (
    glGenVertexArrays, glBindVertexArray,
    glGenBuffers, glBindBuffer, glBufferData,
    glEnableVertexAttribArray, glVertexAttribPointer,
    glDrawElements, glDeleteVertexArrays, glDeleteBuffers,
    glGenTextures, glBindTexture, glTexImage2D, glDeleteTextures,
    glTexParameteri, glActiveTexture,
    glEnable, glDisable, glBlendFunc,
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER,
    GL_STATIC_DRAW,
    GL_FLOAT, GL_UNSIGNED_INT, GL_TRIANGLES, GL_FALSE,
    GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_LINEAR,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE,
    GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    GL_TEXTURE0,
)

# Local imports (engine is a sibling package when run from rpg3d/)
from engine.math3d import ortho, identity
from engine.shader import ShaderProgram


_FONT_CACHE: dict = {}


def _get_font(size: int) -> pygame.font.Font:
    if size not in _FONT_CACHE:
        _FONT_CACHE[size] = pygame.font.SysFont("monospace", size)
    return _FONT_CACHE[size]


def _make_quad_vao(x, y, w, h):
    """Screen-space quad. y increases downward."""
    verts = np.array([
        x,   y,   0,  0, 1,
        x+w, y,   0,  1, 1,
        x+w, y+h, 0,  1, 0,
        x,   y+h, 0,  0, 0,
    ], dtype=np.float32)
    idxs = np.array([0,1,2, 0,2,3], dtype=np.uint32)

    vao = glGenVertexArrays(1)
    vbo, ibo = glGenBuffers(2)
    glBindVertexArray(vao)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ibo)
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, idxs.nbytes, idxs, GL_STATIC_DRAW)
    stride = 5 * 4
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
    glEnableVertexAttribArray(2)
    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
    glBindVertexArray(0)
    return vao, vbo, ibo


def _text_to_texture(text: str, font_size: int, color=(255,255,255)):
    font    = _get_font(font_size)
    surface = font.render(text, True, color)
    surface = surface.convert_alpha()
    w, h    = surface.get_size()
    data    = pygame.image.tostring(surface, "RGBA", True)
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glBindTexture(GL_TEXTURE_2D, 0)
    return tex, w, h


class HUD:
    def __init__(self, screen_w: int, screen_h: int, shader: ShaderProgram):
        self.sw     = screen_w
        self.sh     = screen_h
        self.shader = shader
        self.proj   = ortho(0, screen_w, screen_h, 0, -1, 1)
        self.view   = identity()
        self.model  = identity()

    def resize(self, w: int, h: int):
        self.sw   = w
        self.sh   = h
        self.proj = ortho(0, w, h, 0, -1, 1)

    def draw_text(self, text: str, x: float, y: float,
                  font_size: int = 18, color=(255,255,255)):
        tex, tw, th = _text_to_texture(text, font_size, color)
        vao, vbo, ibo = _make_quad_vao(x, y, tw, th)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        self.shader.use()
        self.shader.set_mat4("uProjection", self.proj)
        self.shader.set_mat4("uView",       self.view)
        self.shader.set_mat4("uModel",      self.model)
        self.shader.set_bool("uUseTexture", True)
        self.shader.set_int("uTexture",     0)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, tex)
        glBindVertexArray(vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glDisable(GL_BLEND)

        glDeleteVertexArrays(1, [vao])
        glDeleteBuffers(2, [vbo, ibo])
        glDeleteTextures(1, [tex])

    def draw_bar(self, x, y, w, h, fill: float,
                 bar_color=(0.8,0.1,0.1), bg_color=(0.2,0.2,0.2)):
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.shader.use()
        self.shader.set_mat4("uProjection", self.proj)
        self.shader.set_mat4("uView",       self.view)
        self.shader.set_mat4("uModel",      self.model)
        self.shader.set_bool("uUseTexture", False)

        def _solid(cx, cy, cw, ch, col):
            vao, vbo, ibo = _make_quad_vao(cx, cy, cw, ch)
            self.shader.set_vec3("uBaseColor", col)
            glBindVertexArray(vao)
            glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)
            glDeleteVertexArrays(1, [vao])
            glDeleteBuffers(2, [vbo, ibo])

        _solid(x, y, w, h, bg_color)
        _solid(x, y, w * max(0.0, min(1.0, fill)), h, bar_color)
        glDisable(GL_BLEND)
