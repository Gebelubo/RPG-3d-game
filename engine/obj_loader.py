"""
obj_loader.py  –  Own implementation of a .obj / .mtl reader.
No third-party geometry library used.

Returns a list of Mesh data-objects ready to be uploaded to the GPU.
"""

import os
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MeshData:
    """Raw CPU-side mesh after loading."""
    name:      str
    vertices:  np.ndarray   # (N, 8)  [x,y,z, nx,ny,nz, u,v]
    indices:   np.ndarray   # (M,)    uint32
    material:  Optional[str] = None   # material name
    # resolved after mtl parse:
    texture_path:   Optional[str] = None
    base_color:     tuple = (0.8, 0.8, 0.8)
    ka:             float = 0.2
    kd:             float = 0.8
    ks:             float = 0.5
    shininess:      float = 32.0


# ─────────────────────────────────────────────────────────────────────────────

class OBJLoader:
    """
    Parses a Wavefront .obj file and returns a list[MeshData].
    Supports:
      v, vn, vt, f  (triangles and quads – quads are fan-triangulated)
      o / g         (object / group names → separate meshes)
      usemtl        (material assignment)
      mtllib        (loads .mtl alongside)
    """

    def load(self, path: str) -> list[MeshData]:
        base_dir = os.path.dirname(os.path.abspath(path))

        pos:    list[tuple] = []   # (x,y,z)
        norms:  list[tuple] = []   # (nx,ny,nz)
        uvs:    list[tuple] = []   # (u,v)

        # per-object accumulation
        groups:   list[dict]  = []
        cur_group: dict | None = None
        materials: dict[str, dict] = {}

        def new_group(name: str):
            nonlocal cur_group
            g = {"name": name, "faces": [], "material": None}
            groups.append(g)
            cur_group = g

        new_group("default")

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                tok = parts[0]

                if tok == "v":
                    pos.append((float(parts[1]), float(parts[2]), float(parts[3])))

                elif tok == "vn":
                    norms.append((float(parts[1]), float(parts[2]), float(parts[3])))

                elif tok == "vt":
                    u = float(parts[1])
                    v = float(parts[2]) if len(parts) > 2 else 0.0
                    uvs.append((u, v))

                elif tok in ("o", "g"):
                    name = parts[1] if len(parts) > 1 else tok
                    # only create a new group when it would be non-empty
                    if cur_group and cur_group["faces"]:
                        new_group(name)
                    else:
                        cur_group["name"] = name

                elif tok == "usemtl":
                    mat_name = parts[1] if len(parts) > 1 else ""
                    if cur_group["faces"]:
                        # split current group at material boundary
                        new_group(cur_group["name"])
                    cur_group["material"] = mat_name

                elif tok == "mtllib":
                    for mtl_file in parts[1:]:
                        mtl_path = os.path.join(base_dir, mtl_file)
                        if os.path.isfile(mtl_path):
                            materials.update(self._parse_mtl(mtl_path, base_dir))

                elif tok == "f":
                    verts = parts[1:]
                    # fan-triangulate (works for convex polygons)
                    indices = [self._parse_face_vert(v) for v in verts]
                    for i in range(1, len(indices) - 1):
                        cur_group["faces"].append((indices[0], indices[i], indices[i+1]))

        # ── Build MeshData per group ──────────────────────────────────────────
        result = []
        for g in groups:
            if not g["faces"]:
                continue
            md = self._build_mesh(g, pos, norms, uvs)
            # attach material
            mat_name = g["material"]
            md.material = mat_name
            if mat_name and mat_name in materials:
                m = materials[mat_name]
                md.base_color   = m.get("Kd", (0.8, 0.8, 0.8))
                md.ka           = m.get("Ka_s",  0.2)
                md.kd           = m.get("Kd_s",  0.8)
                md.ks           = m.get("Ks_s",  0.5)
                md.shininess    = m.get("Ns",    32.0)
                md.texture_path = m.get("map_Kd", None)
                if md.texture_path:
                    md.texture_path = os.path.join(base_dir, md.texture_path)
            result.append(md)

        return result if result else []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_face_vert(self, token: str) -> tuple:
        """'v/vt/vn' → (vi, ti, ni)  (0-based, -1 = absent)"""
        parts = token.split("/")
        def idx(s):
            return int(s) - 1 if s else -1
        vi = idx(parts[0]) if len(parts) > 0 else -1
        ti = idx(parts[1]) if len(parts) > 1 else -1
        ni = idx(parts[2]) if len(parts) > 2 else -1
        return (vi, ti, ni)

    def _build_mesh(self, group: dict, pos, norms, uvs) -> MeshData:
        """
        Convert raw face data into an indexed triangle list.
        Each unique (v/vt/vn) combination → one vertex in the VBO.
        """
        vertex_map: dict[tuple, int] = {}
        vbo_data:   list[float]      = []
        ibo_data:   list[int]        = []

        def get_or_add(vi, ti, ni) -> int:
            key = (vi, ti, ni)
            if key in vertex_map:
                return vertex_map[key]
            idx = len(vertex_map)
            vertex_map[key] = idx

            x, y, z = pos[vi] if vi >= 0 else (0.0, 0.0, 0.0)
            if ni >= 0 and ni < len(norms):
                nx, ny, nz = norms[ni]
            else:
                nx, ny, nz = 0.0, 1.0, 0.0   # default up-normal
            if ti >= 0 and ti < len(uvs):
                u, v = uvs[ti]
            else:
                u, v = 0.0, 0.0

            vbo_data.extend([x, y, z, nx, ny, nz, u, v])
            return idx

        for tri in group["faces"]:
            for (vi, ti, ni) in tri:
                ibo_data.append(get_or_add(vi, ti, ni))

        vertices = np.array(vbo_data, dtype=np.float32).reshape(-1, 8)
        indices  = np.array(ibo_data,  dtype=np.uint32)

        # ── Compute flat normals if none supplied ─────────────────────────────
        if not norms:
            self._compute_normals(vertices, indices)

        return MeshData(name=group["name"], vertices=vertices, indices=indices)

    def _compute_normals(self, vertices: np.ndarray, indices: np.ndarray):
        """Fill normals column (3:6) using face cross products."""
        positions = vertices[:, :3]
        normals   = np.zeros_like(positions)

        for i in range(0, len(indices), 3):
            i0, i1, i2 = indices[i], indices[i+1], indices[i+2]
            v0, v1, v2 = positions[i0], positions[i1], positions[i2]
            edge1 = v1 - v0
            edge2 = v2 - v0
            face_n = np.cross(edge1, edge2)
            normals[i0] += face_n
            normals[i1] += face_n
            normals[i2] += face_n

        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        norms[norms < 1e-8] = 1.0
        normals /= norms
        vertices[:, 3:6] = normals

    def _parse_mtl(self, path: str, base_dir: str) -> dict:
        materials: dict[str, dict] = {}
        cur: dict | None = None

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                tok = parts[0]

                if tok == "newmtl":
                    cur = {}
                    materials[parts[1]] = cur

                elif cur is None:
                    continue

                elif tok == "Ka":
                    cur["Ka_s"] = float(parts[1])   # use red channel as ambient scalar

                elif tok == "Kd":
                    cur["Kd"] = (float(parts[1]), float(parts[2]), float(parts[3]))
                    cur["Kd_s"] = float(parts[1])

                elif tok == "Ks":
                    cur["Ks_s"] = float(parts[1])

                elif tok == "Ns":
                    cur["Ns"] = float(parts[1])

                elif tok == "map_Kd":
                    tex_file = " ".join(parts[1:])
                    tex_path = os.path.join(base_dir, tex_file)
                    cur["map_Kd"] = tex_path if os.path.isfile(tex_path) else None

        return materials
