# compressor.py
from pathlib import Path
from PIL import Image

DEFAULT_MAX_SIZE = 1024
DEFAULT_JPEG_QUALITY = 85
OUTPUT_SUFFIX = "_compressed"

def compress_image(src_path: Path, out_dir: Path,
                   max_size: int = DEFAULT_MAX_SIZE,
                   quality: int = DEFAULT_JPEG_QUALITY) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(src_path) as img:
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        if max(w, h) > max_size:
            ratio = max_size / max(w, h)
            new_w = max(1, int(w * ratio))
            new_h = max(1, int(h * ratio))
            img = img.resize((new_w, new_h), Image.LANCZOS)

        out_name = src_path.stem + OUTPUT_SUFFIX + ".jpg"
        out_path = out_dir / out_name
        img.save(out_path, "JPEG", quality=quality, optimize=True)

    return out_path
