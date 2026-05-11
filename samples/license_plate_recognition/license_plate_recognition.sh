#!/bin/bash
# ==============================================================================
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: MIT
# ==============================================================================
# License Plate Recognition sample — shell launcher
#
# Usage:
#   export MODELS_PATH="$HOME/models"
#   ./license_plate_recognition.sh [INPUT] [DEVICE] [OUTPUT]
#
# Arguments:
#   INPUT   Local file, /dev/videoN, or streaming URL
#           (default: sample parking video from GitHub)
#   DEVICE  OpenVINO(TM) device: CPU | GPU | AUTO  (default: AUTO)
#   OUTPUT  Output mode: display | fps | json | file  (default: fps)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --------------------------------------------------------------------------
# Validate MODELS_PATH
# --------------------------------------------------------------------------
if [ -z "${MODELS_PATH:-}" ]; then
  echo "Error: MODELS_PATH is not set." >&2
  echo "Set it to the directory that contains downloaded OpenVINO models," >&2
  echo "for example:  export MODELS_PATH=\"\$HOME/models\"" >&2
  exit 1
fi
echo "MODELS_PATH: $MODELS_PATH"

# --------------------------------------------------------------------------
# Help message
# --------------------------------------------------------------------------
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  echo "Usage: $0 [INPUT] [DEVICE] [OUTPUT]"
  echo ""
  echo "Arguments:"
  echo "  INPUT   Input source (default: sample parking video URL)"
  echo "  DEVICE  Inference device: CPU | GPU | AUTO  (default: AUTO)"
  echo "  OUTPUT  Output mode: display | fps | json | file  (default: fps)"
  exit 0
fi

# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------
INPUT=${1:-"https://github.com/open-edge-platform/edge-ai-resources/raw/main/videos/ParkingVideo.mp4"}
DEVICE=${2:-AUTO}
OUTPUT=${3:-fps}

# Fall back to CPU if no GPU render node is available
if [ ! -e "/dev/dri/renderD128" ] && [ "$DEVICE" = "GPU" ]; then
  echo "Warning: GPU render node not found — falling back to CPU." >&2
  DEVICE="CPU"
fi
echo "DEVICE: $DEVICE"

# --------------------------------------------------------------------------
# Model paths
# --------------------------------------------------------------------------
DETECTION_MODEL="${MODELS_PATH}/public/yolov8_license_plate_detector/FP32/yolov8_license_plate_detector.xml"
OCR_MODEL="${MODELS_PATH}/public/ch_PP-OCRv4_rec_infer/FP32/ch_PP-OCRv4_rec_infer.xml"

check_model() {
  if [ ! -f "$1" ]; then
    echo "Error: model not found: $1" >&2
    echo "Download it first with (from a DL Streamer installation):" >&2
    echo "  /opt/intel/dlstreamer/samples/download_public_models.sh $(basename "$(dirname "$(dirname "$1")")")" >&2
    exit 1
  fi
}
check_model "$DETECTION_MODEL"
check_model "$OCR_MODEL"

# --------------------------------------------------------------------------
# Run Python application
# --------------------------------------------------------------------------
python3 "${SCRIPT_DIR}/license_plate_recognition.py" \
  --input    "${INPUT}" \
  --device   "${DEVICE}" \
  --output   "${OUTPUT}" \
  --detection-model "${DETECTION_MODEL}" \
  --ocr-model       "${OCR_MODEL}"
