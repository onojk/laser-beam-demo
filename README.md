# Laser Beam — a haunted demoscene music video

A real-time-style demoscene video for **"Laser Beam"**, a haunted 1960s psych-pop song:
minor-key pipe organ, a ghostly barbershop quartet, theremin, music box, church bells and
tape wobble at about 72 bpm. It's rendered offline and deterministically from GLSL shaders
driven by an analysis of the song.

> Work in progress: built in stages (setup → audio analysis → look → scenes → render).

## The song is not included

This repo has no audio in it. Bring your own WAV of "Laser Beam" and pass its path to the scripts.

## Requirements

- Python 3.10+
- ffmpeg on `PATH`
- a GPU/driver with EGL + OpenGL 3.3 (Mesa works headless)

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```sh
# 1. analyse the song -> cache/features.json, prints tempo and section timestamps
.venv/bin/python analyze.py "/path/to/Laser Beam.wav"
```

## License

MIT, see [LICENSE](LICENSE). This covers the code only. The song belongs to its author.
