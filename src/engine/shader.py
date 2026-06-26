import os
import numpy as np
from OpenGL.GL import (
    glCreateShader, glShaderSource, glCompileShader, glGetShaderiv,
    glGetShaderInfoLog, glCreateProgram, glAttachShader, glLinkProgram,
    glGetProgramiv, glGetProgramInfoLog, glUseProgram, glDeleteShader,
    glGetUniformLocation,
    glUniform1i, glUniform1f, glUniform3f, glUniform3fv,
    glUniformMatrix4fv, glUniformMatrix3fv,
    GL_VERTEX_SHADER, GL_FRAGMENT_SHADER,
    GL_COMPILE_STATUS, GL_LINK_STATUS, GL_TRUE,
)


class ShaderProgram:
    def __init__(self, vert_path: str, frag_path: str):
        self.id = self._build(vert_path, frag_path)
        self._loc_cache: dict[str, int] = {}


    def _read(self, path: str) -> str:
        with open(path, "r") as f:
            return f.read()

    def _compile(self, source: str, shader_type) -> int:
        sid = glCreateShader(shader_type)
        glShaderSource(sid, source)
        glCompileShader(sid)
        if glGetShaderiv(sid, GL_COMPILE_STATUS) != GL_TRUE:
            log = glGetShaderInfoLog(sid).decode()
            raise RuntimeError(f"Shader compile error:\n{log}")
        return sid

    def _build(self, vert_path: str, frag_path: str) -> int:
        vs = self._compile(self._read(vert_path), GL_VERTEX_SHADER)
        fs = self._compile(self._read(frag_path), GL_FRAGMENT_SHADER)
        prog = glCreateProgram()
        glAttachShader(prog, vs)
        glAttachShader(prog, fs)
        glLinkProgram(prog)
        if glGetProgramiv(prog, GL_LINK_STATUS) != GL_TRUE:
            log = glGetProgramInfoLog(prog).decode()
            raise RuntimeError(f"Shader link error:\n{log}")
        glDeleteShader(vs)
        glDeleteShader(fs)
        return prog


    def use(self):
        glUseProgram(self.id)


    def _loc(self, name: str) -> int:
        if name not in self._loc_cache:
            self._loc_cache[name] = glGetUniformLocation(self.id, name)
        return self._loc_cache[name]

    def set_int(self, name: str, value: int):
        glUniform1i(self._loc(name), value)

    def set_float(self, name: str, value: float):
        glUniform1f(self._loc(name), value)

    def set_vec3(self, name: str, x, y=None, z=None):
        if y is None:
            v = np.array(x, dtype=np.float32)
            glUniform3fv(self._loc(name), 1, v)
        else:
            glUniform3f(self._loc(name), float(x), float(y), float(z))

    def set_mat4(self, name: str, mat: np.ndarray):
        glUniformMatrix4fv(self._loc(name), 1, False, mat.T.astype(np.float32))

    def set_mat4_array(self, name: str, mats: list):
        if not mats:
            return
        count = len(mats)
        flat = np.stack([m.T.astype(np.float32) for m in mats], axis=0)  
        glUniformMatrix4fv(self._loc(name), count, False, flat)

    def set_mat3(self, name: str, mat: np.ndarray):
        glUniformMatrix3fv(self._loc(name), 1, False, mat.T.astype(np.float32))

    def set_bool(self, name: str, value: bool):
        glUniform1i(self._loc(name), int(value))
