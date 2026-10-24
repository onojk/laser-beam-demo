# Laser Beam — a haunted demoscene music video

A real-time-style demoscene video for **"Laser Beam"**, a haunted 1960s psych-pop song:
minor-key pipe organ, a ghostly barbershop quartet, theremin, music box, church bells and
tape wobble at 68.8 bpm. It's rendered offline and deterministically from GLSL shaders
driven by an analysis of the song.

## About the song

"Laser Beam" is about getting laser-focused on a research project without knowing whether it
amounts to anything, and publishing it anyway: gold or just sand, it still counts. Once it's
out, the work lives on as a ghost in the archive, where somebody, or the machine that is
listening, may one day find it. The video follows that arc: a music box winds up, the work
becomes a tunnel you can't stop walking down, the ghosts sing, the archive catalogues
everything, and in the end it all collapses into one thin beam of light.

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

# 3. render the whole film at 1080p (preview, CRF 22) with the song muxed in
.venv/bin/python render.py renders/laser_beam_1080p.mp4 --audio "/path/to/Laser Beam.wav" --full

# the 4K master: 3840x2160, CRF 16, full grain (about 9.5 GB, about 32 min on a laptop iGPU)
.venv/bin/python render.py renders/laser_beam_2160p.mp4 --audio "/path/to/Laser Beam.wav" \
    --full --res 2160 --crf 16

# ...or any stretch of it, a single scene, or stills
.venv/bin/python render.py renders/clip.mp4 --audio "/path/to/Laser Beam.wav" --start 40 --dur 26
.venv/bin/python render.py - --still 47 --still 215          # PNGs into renders/
```

Analysis uses ffmpeg and numpy only and takes about a second. A 1080p render runs at about
25 fps on a laptop iGPU (Intel Lunar Lake, Mesa).

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
| verses | A candlelit brick tunnel (the classic angle / 1-over-r tunnel). Mortar is a phosphor grid, candles flicker in niches, and sheet ghosts drift toward the camera. Speed follows the song's loudness. On each bone-white flash one ghost swoops past close to the camera. |
| choruses | An organ-pipe façade lit by copper bars (the classic raster effect) that swell with the bass, each pipe speaking from its mouth on the beat. In front, the barbershop quartet: four glowing ghost heads in boater hats (bass, baritone, lead, tenor). Each lights up and sings with its band, and they sway together on the beat. In the final chorus all four burn at once. |
| instrumental break | A theremin-wave plasma: the classic sum-of-sines plasma drawn as glowing contours, moving at a speed driven by the high band. Across it an oscilloscope theremin wave runs between the pitch rod and the volume loop. Its pitch follows the song's brightness, its vibrato the tape wobble, its amplitude the high band. |
| bridge | A church bell swings on the beat, and every onset sends a shockwave ring out from its mouth. Below, the archive turns: catalogue cards bearing lines from the song ("WRITE IT DOWN", "THE MACHINE IS LISTENING", ...) drift round a carousel like pages being filed. |
| breakdown | Almost dark. Only the strong onsets ring, faint and slow, and a single dim ghost head listens. |
| outro | The tunnel, the pipes and quartet, and the archive are replayed and squeezed into the centre line with inward motion streaks. They collapse into one green laser line, which holds, wobbles slower and slower through the tape stop, then snaps off like an old CRT at the music's last beat (4:28.13). Black through the tail. |

Throughout, a classic sine scroller carries the greetings along the bottom. It goes dark for
the breakdown and the outro. Strong onsets lift the glow (never more than 3 a second), and the
biggest on-beat ones flash bone-white.

## License

MIT, see [LICENSE](LICENSE). This covers the code only. The song belongs to its author.
