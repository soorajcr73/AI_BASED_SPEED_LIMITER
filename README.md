# AI-Based Speed Limit Detection and Speed Limiter System
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


