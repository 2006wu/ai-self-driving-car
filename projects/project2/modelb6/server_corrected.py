"""Student-owned corrected Step 5 ZeroMQ server for one explicit sequence."""

import argparse
from pathlib import Path

from corrections import corrected_datagen, derived_teacher_path
from serverB6 import start_server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--port", required=True, type=int, choices=(5557, 5558))
    parser.add_argument("--smoke-frames", type=int, default=5)
    args = parser.parse_args()
    original_root = Path("/data/dataB6")
    derived_root = Path("/derived/smoke/dataB6")
    camera = original_root / args.sequence / "yuv.h5"
    teacher = derived_teacher_path(camera, original_root, derived_root)
    if not teacher.is_file():
        raise FileNotFoundError(teacher)
    stream = corrected_datagen([str(camera)], steps=1, original_root=original_root,
                               derived_root=derived_root, frame_limit=args.smoke_frames)
    first = next(stream)
    if first[0].shape != (2, 12, 128, 256) or first[4].shape != (2, 385):
        raise ValueError("corrected server batch has unexpected shape")
    print(f"SERVING sequence={args.sequence} port={args.port} frames={args.smoke_frames}", flush=True)
    # Create a fresh stream so the probe and trainer receive the same first batch.
    start_server(corrected_datagen([str(camera)], steps=1, original_root=original_root,
                                   derived_root=derived_root, frame_limit=args.smoke_frames),
                 port=args.port, hwm=2)


if __name__ == "__main__":
    main()
