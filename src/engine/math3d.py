import math
import numpy as np

Mat4 = np.ndarray  
Vec3 = np.ndarray   

def identity() -> Mat4:
    return np.eye(4, dtype=np.float32)


def translate(tx: float, ty: float, tz: float) -> Mat4:
    m = np.eye(4, dtype=np.float32)
    m[0, 3] = tx
    m[1, 3] = ty
    m[2, 3] = tz
    return m


def scale(sx: float, sy: float, sz: float) -> Mat4:
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = sx
    m[1, 1] = sy
    m[2, 2] = sz
    return m


def rotate_x(angle_deg: float) -> Mat4:
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4, dtype=np.float32)
    m[1, 1] =  c;  m[1, 2] = -s
    m[2, 1] =  s;  m[2, 2] =  c
    return m


def rotate_y(angle_deg: float) -> Mat4:
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4, dtype=np.float32)
    m[0, 0] =  c;  m[0, 2] =  s
    m[2, 0] = -s;  m[2, 2] =  c
    return m


def rotate_z(angle_deg: float) -> Mat4:
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4, dtype=np.float32)
    m[0, 0] =  c;  m[0, 1] = -s
    m[1, 0] =  s;  m[1, 1] =  c
    return m


def rotate_axis(axis: Vec3, angle_deg: float) -> Mat4:
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    t = 1.0 - c
    ax = normalize(axis)
    x, y, z = float(ax[0]), float(ax[1]), float(ax[2])
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = t*x*x + c;    m[0, 1] = t*x*y - s*z;  m[0, 2] = t*x*z + s*y
    m[1, 0] = t*x*y + s*z;  m[1, 1] = t*y*y + c;    m[1, 2] = t*y*z - s*x
    m[2, 0] = t*x*z - s*y;  m[2, 1] = t*y*z + s*x;  m[2, 2] = t*z*z + c
    return m

def look_at(eye: Vec3, center: Vec3, up: Vec3) -> Mat4:
    f = normalize(center - eye)
    r = normalize(np.cross(f, normalize(up)))
    u = np.cross(r, f)
    m = np.eye(4, dtype=np.float32)
    m[0, :3] =  r;  m[0, 3] = -np.dot(r, eye)
    m[1, :3] =  u;  m[1, 3] = -np.dot(u, eye)
    m[2, :3] = -f;  m[2, 3] =  np.dot(f, eye)
    return m


def perspective(fov_deg: float, aspect: float, near: float, far: float) -> Mat4:
    f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def ortho(left, right, bottom, top, near, far) -> Mat4:
    m = np.eye(4, dtype=np.float32)
    m[0, 0] =  2.0 / (right - left)
    m[1, 1] =  2.0 / (top   - bottom)
    m[2, 2] = -2.0 / (far   - near)
    m[0, 3] = -(right + left)   / (right - left)
    m[1, 3] = -(top   + bottom) / (top   - bottom)
    m[2, 3] = -(far   + near)   / (far   - near)
    return m

def vec3(x=0.0, y=0.0, z=0.0) -> Vec3:
    return np.array([x, y, z], dtype=np.float32)


def normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-8 else v.copy()


def mat3_normal_matrix(model: Mat4) -> np.ndarray:
    m3 = model[:3, :3].copy()
    try:
        return np.linalg.inv(m3).T.astype(np.float32)
    except np.linalg.LinAlgError:
        return np.eye(3, dtype=np.float32)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo, hi):
    return max(lo, min(hi, v))
