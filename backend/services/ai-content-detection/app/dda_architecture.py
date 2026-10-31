"""DDA inference architecture, adapted from the official Apache-2.0 implementation.

Upstream: https://github.com/roy-ch/Dual-Data-Alignment
Upstream revision: 08d6b414a33826403b9096cfdb7758d5eae12dbb
"""
from __future__ import annotations

import math

import torch
from torch import nn

DINOV2_CHANNELS = {"dinov2_vitl14": 1024}


class LoRALayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, rank: int = 8, alpha: float = 1.0):
        super().__init__()
        self.alpha = alpha
        self.rank = rank
        self.lora_A = nn.Parameter(torch.zeros((rank, in_dim)))
        self.lora_B = nn.Parameter(torch.zeros((out_dim, rank)))
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        nn.init.zeros_(self.lora_B)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return (x @ self.lora_A.T @ self.lora_B.T) * (self.alpha / self.rank)


class LoRALinear(nn.Module):
    def __init__(self, original_layer: nn.Linear, rank: int = 8, alpha: float = 1.0):
        super().__init__()
        self.original_layer = original_layer
        for parameter in self.original_layer.parameters():
            parameter.requires_grad = False
        self.lora = LoRALayer(original_layer.in_features, original_layer.out_features, rank, alpha)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.original_layer(x) + self.lora(x)

    def __getattr__(self, name: str):
        if name in {"weight", "bias"}:
            return getattr(self.original_layer, name)
        return super().__getattr__(name)


def _submodule(root: nn.Module, path: str) -> nn.Module:
    current = root
    for part in path.split("."):
        current = current[int(part)] if part.isdigit() else getattr(current, part)
    return current


def apply_lora(model: nn.Module) -> nn.Module:
    targets = ("attn.qkv", "attn.proj", "mlp.fc1", "mlp.fc2")
    replacements = []
    for name, module in list(model.named_modules()):
        if isinstance(module, nn.Linear) and any(target in name for target in targets):
            parent_name, _, child_name = name.rpartition(".")
            replacements.append((parent_name, child_name or name, module))
    for parent_name, child_name, module in replacements:
        parent = _submodule(model, parent_name) if parent_name else model
        setattr(parent, child_name, LoRALinear(module, rank=8, alpha=1.0))
    return model


class DINOv2Model(nn.Module):
    def __init__(self):
        super().__init__()
        # Pin remote model code to a reviewed commit; no floating "main" branch.
        self.model = torch.hub.load(
            "facebookresearch/dinov2:7b187bd4df8efce2cbcbbb67bd01532c19bf4c9c",
            "dinov2_vitl14",
            pretrained=True,
            trust_repo=True,
        )
        self.fc = nn.Linear(DINOV2_CHANNELS["dinov2_vitl14"], 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.model.forward_features(x)
        return self.fc(features["x_norm_clstoken"])


class DINOv2ModelWithLoRA(nn.Module):
    def __init__(self):
        super().__init__()
        self.base_model = DINOv2Model()
        self.base_model.model = apply_lora(self.base_model.model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.base_model(x)
