# Beat-Synced Video Effects

[![Support me on Patreon](https://img.shields.io/badge/Patreon-Support%20my%20work-FF424D?style=flat&logo=patreon&logoColor=white)](https://www.patreon.com/AndersBjarby)

A command-line tool that adds beat-synced visual effects to a video. It analyzes the audio across three frequency bands — bass, mid, and high — and triggers a different effect on the actual onset of each band: a zoom punch on bass hits, color saturation on mids, and a configurable effect (tint, vignette, sharpen, edge glow, invert, radial) on highs. Effects are layered interactively so you can tune intensity and timing before rendering.

## Requirements

```bash
pip install librosa numpy
```

Also requires FFmpeg on your PATH.

## Usage

```bash
python add_effects.py video.mp4
```

Optionally specify the six frequency-range bounds (bass low/high, mid low/high, high low/high in Hz):

```bash
python add_effects.py video.mp4 20 200 200 2000 6000 10000
```

The script walks you through each layer interactively and writes intermediate files (`_01_bass`, `_02_mid`) plus the final `_03_final.mp4`.

## Tech

Python, librosa (audio onset detection per band), FFmpeg (video effects).
