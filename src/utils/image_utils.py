import os

def is_image_path(path):
    image_exts = {
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".gif",
        ".webp",
        ".tga",
    }

    return (
        isinstance(path, str)
        and os.path.isfile(path)
        and os.path.splitext(path)[1].lower() in image_exts
    )