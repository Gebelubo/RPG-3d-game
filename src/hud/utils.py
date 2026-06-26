import math
import pygame
import numpy as np
import ctypes
from OpenGL.GL import (
    glGenVertexArrays, glBindVertexArray, glGenBuffers, glBindBuffer,
    glBufferData, glEnableVertexAttribArray, glVertexAttribPointer,
    glDeleteVertexArrays, glDeleteBuffers,
    glGenTextures, glBindTexture, glTexImage2D, glDeleteTextures,
    glTexParameteri,
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER, GL_STATIC_DRAW,
    GL_FLOAT, GL_FALSE,
    GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_LINEAR,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE,
)




_FONT_CACHE: dict = {}

def _get_font(size, bold=False):
    key = (size, bold)
    if key not in _FONT_CACHE:
        for fname in ("segoeui", "dejavusans", "freesans", "monospace"):
            try:
                _FONT_CACHE[key] = pygame.font.SysFont(fname, size, bold=bold)
                break
            except Exception:
                pass
        else:
            _FONT_CACHE[key] = pygame.font.Font(None, size)
    return _FONT_CACHE[key]



_TEX_CACHE: dict = {}        # key -> (tex_id, w, h)
_TEX_ORDER: list = []        # ordem de inserção para descarte
_TEX_CACHE_MAX = 256


def _upload_surface(surf) -> tuple:
    surf = surf.convert_alpha()
    w, h = surf.get_size()
    data = pygame.image.tostring(surf, "RGBA", True)
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    for p, v in [
        (GL_TEXTURE_MIN_FILTER, GL_LINEAR),
        (GL_TEXTURE_MAG_FILTER, GL_LINEAR),
        (GL_TEXTURE_WRAP_S,     GL_CLAMP_TO_EDGE),
        (GL_TEXTURE_WRAP_T,     GL_CLAMP_TO_EDGE),
    ]:
        glTexParameteri(GL_TEXTURE_2D, p, v)
    glBindTexture(GL_TEXTURE_2D, 0)
    return tex, w, h


def _cache_store(key, tex, w, h):
    if len(_TEX_ORDER) >= _TEX_CACHE_MAX:
        old_key = _TEX_ORDER.pop(0)
        old_tex, _, _ = _TEX_CACHE.pop(old_key, (None, 0, 0))
        if old_tex is not None:
            glDeleteTextures(1, [old_tex])
    _TEX_CACHE[key] = (tex, w, h)
    _TEX_ORDER.append(key)


def _text_tex(text: str, size: int, color=(255, 255, 255), bold=False,
              outline: bool = True, outline_color=(35, 20, 10),
              shadow: bool = False, shadow_color=(0, 0, 0), shadow_offset=(2, 2)):

    key = (text, size, color, bold, outline, outline_color, shadow, shadow_color, shadow_offset)
    if key in _TEX_CACHE:
        return _TEX_CACHE[key]

    font = _get_font(size, bold)
    base = font.render(text, True, color)
    tw, th = base.get_size()

    pad = 2 if outline else 0
    sx = abs(shadow_offset[0]) if shadow else 0
    sy = abs(shadow_offset[1]) if shadow else 0

    surf = pygame.Surface((tw + pad * 2 + sx, th + pad * 2 + sy), pygame.SRCALPHA)

    if shadow:
        shadow_surf = font.render(text, True, shadow_color)
        shadow_surf.set_alpha(140)
        ox = pad + max(0, shadow_offset[0])
        oy = pad + max(0, shadow_offset[1])
        surf.blit(shadow_surf, (ox, oy))

    if outline:
        outline_surf = font.render(text, True, outline_color)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                surf.blit(outline_surf, (pad + dx, pad + dy))

    surf.blit(base, (pad, pad))

    tex, w, h = _upload_surface(surf)
    _cache_store(key, tex, w, h)
    return tex, w, h



def _make_quad(x, y, w, h):
    verts = np.array([
        x,   y,   0, 0, 1,
        x+w, y,   0, 1, 1,
        x+w, y+h, 0, 1, 0,
        x,   y+h, 0, 0, 0,
    ], dtype=np.float32)
    idxs = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)
    vao = glGenVertexArrays(1)
    vbo, ibo = glGenBuffers(2)
    glBindVertexArray(vao)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ibo)
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, idxs.nbytes, idxs, GL_STATIC_DRAW)
    s = 5 * 4
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(0))
    glEnableVertexAttribArray(2)
    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(12))
    glBindVertexArray(0)
    return vao, vbo, ibo


def _make_poly(points):

    n = len(points)
    verts = []
    for (x, y) in points:
        verts += [x, y, 0.0, 0.0, 0.0]
    verts = np.array(verts, dtype=np.float32)

    idxs = []
    for i in range(1, n - 1):
        idxs += [0, i, i + 1]
    idxs = np.array(idxs, dtype=np.uint32)

    vao = glGenVertexArrays(1)
    vbo, ibo = glGenBuffers(2)
    glBindVertexArray(vao)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ibo)
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, idxs.nbytes, idxs, GL_STATIC_DRAW)
    s = 5 * 4
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(0))
    glEnableVertexAttribArray(2)
    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(12))
    glBindVertexArray(0)
    return vao, vbo, ibo, len(idxs)


def _ngon_points(cx, cy, r, sides=8, rotation=0.0, ry=None):
    ry = r if ry is None else ry
    pts = []
    for i in range(sides):
        ang = rotation + (2 * math.pi * i / sides)
        pts.append((cx + r * math.cos(ang), cy + ry * math.sin(ang)))
    return pts


def _banner_points(x, y, w, h, notch=12):

    return [
        (x - notch, y + h / 2),
        (x, y),
        (x + w, y),
        (x + w + notch, y + h / 2),
        (x + w, y + h),
        (x, y + h),
    ]


def _free_quad(vao, vbo, ibo):
    glDeleteVertexArrays(1, [vao])
    glDeleteBuffers(2, [vbo, ibo])


def clear_text_cache():

    global _TEX_CACHE, _TEX_ORDER
    for tex, _, _ in _TEX_CACHE.values():
        glDeleteTextures(1, [tex])
    _TEX_CACHE.clear()
    _TEX_ORDER.clear()