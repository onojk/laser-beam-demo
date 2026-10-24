# Laser Beam — a haunted demoscene music video

A real-time-style demoscene video for **"Laser Beam"**, a haunted 1960s psych-pop song:
minor-key pipe organ, a ghostly barbershop quartet, theremin, music box, church bells and
tape wobble at 68.8 bpm. It's rendered offline and deterministically from GLSL shaders
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
# 1. analyse the song -> cache/features.json (tempo, beat grid, onsets, rms, low/mid/high
#    bands, tape-wobble estimate, novelty curve)
.venv/bin/python analyze.py "/path/to/Laser Beam.wav"

# 2. section map -> cache/sections.json, prints the timestamps
.venv/bin/python sections.py

# 3. render: a 10 s look test at 1080p with the song muxed in
.venv/bin/python render.py renders/looktest.mp4 --audio "/path/to/Laser Beam.wav" \
    --start 38 --dur 10 --scene looktest --still 42.3
```

Analysis uses ffmpeg and numpy only and takes about a second.

## The look

Each scene shader writes three emission channels, not colours: sickly green phosphor, violet
glow and bone white. A shared post pass turns them into the haunted phosphor palette over a
near-black ground. It also adds bloom, CRT scanlines (540 per frame at any resolution), a
vignette and film grain. The tape-wobble warp follows the wobble measured in the song's
pitch. On big on-beat onsets the frame flashes bone-white, at most once every 1.5 s.
Rendering is deterministic: time is `frame / 30`, and the grain comes from a fixed seed.
The same command gives byte-identical frames every time.

## Effects

Each section of the song gets its own effect. Cuts between sections are hard, on the beat.

| Section | Effect |
|---|---|
| intro | A music-box cylinder made of dots. The bright pins are the intro's real onsets, placed so each one plucks its comb tine exactly when the note sounds. Then "LASER BEAM" is drawn in as a glowing vector logo by a moving pen. |
| verses | A candlelit brick tunnel (the classic angle / 1-over-r tunnel). Mortar is a phosphor grid, candles flicker in niches, and sheet ghosts drift toward the camera. Speed follows the song's loudness. |
| *(in progress)* | organ-pipe copper bars with a ghost quartet, church-bell rings and the listening archive, theremin plasma, collapse to a laser line |

Throughout, a classic sine scroller carries the greetings along the bottom. It goes dark for
the breakdown and the outro. Strong onsets lift the glow (never more than 3 a second), and the
biggest on-beat ones flash bone-white.

## License

MIT, see [LICENSE](LICENSE). This covers the code only. The song belongs to its author.
