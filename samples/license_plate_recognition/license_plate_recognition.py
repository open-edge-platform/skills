# ==============================================================================
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: MIT
# ==============================================================================
"""
License Plate Recognition sample application using Intel® DL Streamer.

Pipeline:
  source → decode → gvadetect (plate detection) → gvaclassify (OCR) → sink

Supported inputs : local file, RTSP/HTTP URL, /dev/videoN webcam
Supported outputs: display, fps, json, file
"""

import os
import sys
from argparse import ArgumentParser

import gi
gi.require_version("GLib", "2.0")
gi.require_version("Gst", "1.0")
gi.require_version("GstAnalytics", "1.0")
from gi.repository import GLib, Gst, GstAnalytics  # noqa: E402

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
parser = ArgumentParser(description="License Plate Recognition using Intel® DL Streamer")
parser.add_argument(
    "-i", "--input",
    default="https://github.com/open-edge-platform/edge-ai-resources/raw/main/videos/ParkingVideo.mp4",
    help="Input source: local video file, /dev/videoN, or streaming URL (default: sample parking video)",
)
parser.add_argument(
    "-d", "--device",
    default="AUTO",
    choices=["CPU", "GPU", "AUTO"],
    help="OpenVINO™ inference device (default: AUTO)",
)
parser.add_argument(
    "-o", "--output",
    default="fps",
    choices=["display", "fps", "json", "file"],
    help="Output mode (default: fps)",
)
parser.add_argument(
    "--detection-model",
    required=True,
    metavar="PATH",
    help="Path to the license plate detector .xml (e.g. yolov8_license_plate_detector.xml)",
)
parser.add_argument(
    "--ocr-model",
    required=True,
    metavar="PATH",
    help="Path to the OCR classifier .xml (e.g. ch_PP-OCRv4_rec_infer.xml)",
)


# ---------------------------------------------------------------------------
# Probe callback – print detected plate text to stdout
# ---------------------------------------------------------------------------
def _on_buffer(pad, info, _user_data):
    """GStreamer pad probe that reads GstAnalytics metadata and prints plates."""
    buf = info.get_buffer()
    if buf is None:
        return Gst.PadProbeReturn.OK

    rmeta = GstAnalytics.buffer_get_analytics_relation_meta(buf)
    if rmeta is None:
        return Gst.PadProbeReturn.OK

    plates = []
    for mtd in rmeta:
        if isinstance(mtd, GstAnalytics.ClsMtd):
            label = GLib.quark_to_string(mtd.get_highest_likelihood_class()[1])
            if label:
                plates.append(label)

    if plates:
        print(f"Detected plate(s): {', '.join(plates)}")

    return Gst.PadProbeReturn.OK


# ---------------------------------------------------------------------------
# Pipeline builder
# ---------------------------------------------------------------------------
def _build_source(input_uri: str) -> str:
    if input_uri.startswith("/dev/video"):
        return f"v4l2src device={input_uri}"
    if "://" in input_uri:
        return f"urisourcebin buffer-size=4096 uri={input_uri}"
    return f"filesrc location={input_uri}"


def _build_decode(device: str) -> str:
    if device == "GPU":
        return "decodebin3 ! vapostproc ! video/x-raw(memory:VAMemory)"
    return "decodebin3"


def _build_preproc(device: str) -> str:
    if device == "GPU":
        return "pre-process-backend=va-surface-sharing"
    return "pre-process-backend=opencv"


def _build_sink(output: str, input_uri: str, device: str) -> str:
    if output == "display":
        return (
            "vapostproc ! gvawatermark ! videoconvert ! "
            "gvafpscounter ! autovideosink sync=false"
        )
    if output == "fps":
        return "gvafpscounter ! fakesink async=false"
    if output == "json":
        return (
            "gvametaconvert ! "
            "gvametapublish file-format=json-lines file-path=output.json ! "
            "fakesink async=false"
        )
    if output == "file":
        basename = os.path.splitext(os.path.basename(input_uri))[0]
        out_file = f"lpr_{basename}_{device}.mp4"
        return (
            f"vapostproc ! gvawatermark ! gvafpscounter ! "
            f"vah264enc ! h264parse ! mp4mux ! filesink location={out_file}"
        )
    raise ValueError(f"Unsupported output mode: {output}")


def build_pipeline_string(args) -> str:
    source = _build_source(args.input)
    decode = _build_decode(args.device)
    preproc = _build_preproc(args.device)
    sink = _build_sink(args.output, args.input, args.device)

    return (
        f"{source} ! {decode} ! queue ! "
        f"gvadetect model={args.detection_model} device={args.device} {preproc} ! queue ! "
        f"videoconvert ! "
        f"gvaclassify model={args.ocr_model} device={args.device} {preproc} ! queue ! "
        f"{sink}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = parser.parse_args()

    Gst.init(None)

    pipeline_str = build_pipeline_string(args)
    print("Pipeline:\n ", pipeline_str, "\n")

    pipeline = Gst.parse_launch(pipeline_str)
    if pipeline is None:
        sys.stderr.write("ERROR: failed to create GStreamer pipeline.\n")
        sys.exit(1)

    # Attach probe to read OCR results when output is display or json
    if args.output in ("display", "json"):
        classify = pipeline.get_by_name("gvaclassify0")
        if classify:
            src_pad = classify.get_static_pad("src")
            if src_pad:
                src_pad.add_probe(Gst.PadProbeType.BUFFER, _on_buffer, None)

    bus = pipeline.get_bus()
    pipeline.set_state(Gst.State.PLAYING)

    try:
        while True:
            msg = bus.timed_pop_filtered(
                100 * Gst.MSECOND,
                Gst.MessageType.EOS | Gst.MessageType.ERROR,
            )
            if msg is None:
                continue
            if msg.type == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                sys.stderr.write(f"ERROR from {msg.src.get_name()}: {err.message}\n")
                if debug:
                    sys.stderr.write(f"Debug: {debug}\n")
                break
            if msg.type == Gst.MessageType.EOS:
                print("End of stream.")
                break
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        pipeline.set_state(Gst.State.NULL)

    return 0


if __name__ == "__main__":
    sys.exit(main())
