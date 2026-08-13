# AI-Based Speed Limit Detection and Speed Limiter System
<p align="center">

<img src="https://img.shields.io/badge/PYTHON-3.10%2B-1E90FF?style=for-the-badge&logo=python&logoColor=yellow">
<img src="https://img.shields.io/badge/YOLOv5-OBJECT%20DETECTION-E53935?style=for-the-badge">
<img src="https://img.shields.io/badge/OPENCV-COMPUTER%20VISION-5C3EE8?style=for-the-badge&logo=opencv&logoColor=purple">

<br>

<img src="https://img.shields.io/badge/FLASK-WEB%20SERVER-000000?style=for-the-badge&logo=flask&logoColor=blue">
<img src="https://img.shields.io/badge/ARDUINO-HARDWARE-00979D?style=for-the-badge&logo=arduino&logoColor=violet">
<img src="https://img.shields.io/badge/LICENSE-MIT-32CD00?style=for-the-badge">

</p>
# Description
Overspeeding is one of the leading causes of road accidents worldwide. This project aims to develop a system that detects traffic signs, extracts speed limits, and transmits the detected speed to a speed-limiting system that automatically controls the vehicle's speed.

## Flow Chart

```mermaid
flowchart TD
    A["Video Input"] --> B["Frame Extraction"]
    B --> C["Deep Learning Model Detection and Classification"]
    C --> D["Speed Limit Sign Detection"]
    D --> E["ROI Extraction and Image Preprocessing"]
    E --> F["Speed Limit Value Extraction (OCR)"]
    F --> G["Speed Sent to Arduino Uno via PySerial"]
    G --> H["Motor Speed Control"]
```


