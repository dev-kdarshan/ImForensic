#!/usr/bin/env python3
"""Report host PyTorch, CUDA and image-decoder capabilities; does not run inference."""
from __future__ import annotations

import json
import platform

import PIL
import torch
import torchvision


def main():
    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "pillow": PIL.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_runtime": torch.version.cuda,
        "device_count": torch.cuda.device_count(),
        "devices": [],
    }
    for index in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(index)
        report["devices"].append({"index": index, "name": props.name, "total_memory_bytes": props.total_memory})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
