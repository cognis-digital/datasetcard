"""datasetcard - Auto Dataset Cards / datasheets with Croissant + provenance.

Generate ML data governance documentation (HuggingFace-style dataset cards)
from tabular data files using only the Python standard library.
"""
from .core import (
    DatasetProfile,
    profile_dataset,
    build_croissant,
    build_card_markdown,
    build_datasheet,
    sha256_file,
)

TOOL_NAME = "datasetcard"
TOOL_VERSION = "1.0.0"

__all__ = [
    "DatasetProfile",
    "profile_dataset",
    "build_croissant",
    "build_card_markdown",
    "build_datasheet",
    "sha256_file",
    "TOOL_NAME",
    "TOOL_VERSION",
]
