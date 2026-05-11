# License Plate Recognition Sample

This sample demonstrates an end-to-end **License Plate Recognition (LPR)** pipeline built with [Intel® DL Streamer](https://github.com/open-edge-platform/dlstreamer).

The pipeline:
1. Reads video from a file, webcam, or network stream
2. Detects license plates using a YOLOv8-based detector
3. Reads the plate text using a PaddleOCR-based classifier
4. Outputs bounding boxes with plate text overlaid, FPS metrics, JSON metadata, or an annotated video file

---

## How It Works

The pipeline is built with `Gst.parse_launch` and links these elements:

```
source → decodebin3 → gvadetect → gvaclassify → sink
```

| Element | Role |
|---------|------|
| `filesrc` / `urisourcebin` / `v4l2src` | Read from file, URL, or webcam |
| `decodebin3` | Decode the video stream |
| `gvadetect` | Run the YOLOv8 license plate detector |
| `gvaclassify` | Run the PaddleOCR text recognition model |
| `gvawatermark` | Overlay bounding boxes and plate text |
| `gvametaconvert` + `gvametapublish` | Export inference metadata to JSON |
| `gvafpscounter` | Measure and print frames per second |
| `fakesink` / `autovideosink` / `filesink` | Discard, display, or save output |

---

## Models

| Model | Purpose | Source |
|-------|---------|--------|
| `yolov8_license_plate_detector` | Detect license plates in each frame | [edge-ai-resources](https://github.com/open-edge-platform/edge-ai-resources) (packaged in `license-plate-reader.zip`, converted by `download_public_models.sh`) |
| `ch_PP-OCRv4_rec_infer` | OCR — read the text on each plate | [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) |

Both models are downloaded and converted to OpenVINO™ IR format by the `download_public_models.sh` script from the DL Streamer repository.

---

## Prerequisites

* Intel® DL Streamer installed (see [DL Streamer installation guide](https://dlstreamer.github.io/get_started/install/install_guide_ubuntu.html))
* `MODELS_PATH` environment variable pointing to your OpenVINO models directory

---

## Downloading the Models

From a DL Streamer installation, run:

```sh
export MODELS_PATH="$HOME/models"
/opt/intel/dlstreamer/samples/download_public_models.sh yolov8_license_plate_detector
/opt/intel/dlstreamer/samples/download_public_models.sh ch_PP-OCRv4_rec_infer
```

---

## Running

```sh
export MODELS_PATH="$HOME/models"
chmod +x license_plate_recognition.sh
./license_plate_recognition.sh [INPUT] [DEVICE] [OUTPUT]
```

Or call the Python script directly:

```sh
python3 license_plate_recognition.py \
  --detection-model "$MODELS_PATH/public/yolov8_license_plate_detector/FP32/yolov8_license_plate_detector.xml" \
  --ocr-model       "$MODELS_PATH/public/ch_PP-OCRv4_rec_infer/FP32/ch_PP-OCRv4_rec_infer.xml" \
  --input  /path/to/parking.mp4 \
  --device AUTO \
  --output display
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `INPUT` | Sample parking video URL | Local file, `/dev/videoN`, or `rtsp://` / `http://` URL |
| `DEVICE` | `AUTO` | OpenVINO™ device: `CPU`, `GPU`, or `AUTO` |
| `OUTPUT` | `fps` | `display` · `fps` · `json` · `file` |

### Output Modes

| Mode | Description |
|------|-------------|
| `display` | Render video with bounding boxes and plate text on screen |
| `fps` | Print frames-per-second to the terminal, no display |
| `json` | Write inference metadata to `output.json` (JSON-lines format) |
| `file` | Save annotated video to `lpr_<basename>_<device>.mp4` |

---

## Sample Output

Running in `fps` mode:

```
MODELS_PATH: /home/user/models
DEVICE: AUTO
Pipeline:
  urisourcebin buffer-size=4096 uri=https://...ParkingVideo.mp4 ! decodebin3 ! ...

FpsCounter(1sec): total=28.40 frame_num=28
FpsCounter(1sec): total=29.10 frame_num=57
...
End of stream.
```

Running in `display` mode, the sample opens a window showing detected license plates with overlaid bounding boxes and OCR text, while also printing recognised plate strings to the terminal:

```
Detected plate(s): AB1234CD
Detected plate(s): XY9876ZZ
```

---

## See Also

* [Intel® DL Streamer](https://github.com/open-edge-platform/dlstreamer)
* [DL Streamer samples overview](https://github.com/open-edge-platform/dlstreamer/tree/master/samples/gstreamer)
* [Existing gst-launch LPR sample](https://github.com/open-edge-platform/dlstreamer/tree/master/samples/gstreamer/gst_launch/license_plate_recognition)
