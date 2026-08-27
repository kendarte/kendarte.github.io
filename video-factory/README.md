# Video Factory V2 — Auto Director

Video Factory is a reusable local video-production studio that grew out of the LOOKS LEGIT production pipeline. It turns a structured scene project into a timed, directed MP4 instead of rebuilding the rendering stack for every video.

## Public access

- Web editor / workflow test: https://kendarte.github.io/video-factory/test.html
- Project page: https://kendarte.github.io/video-factory/

The public web test exposes the project/scene workflow, preview, scene inspector, auto timeline, JSON bridge and format controls. The full MP4 renderer currently runs locally because it depends on the installed Kokoro, Playwright/Edge and FFmpeg stack.

## V2 — Auto Director

Current V2 features:

- Kokoro silence trimming before timeline creation.
- Timeline duration derived from real narration instead of an arbitrary fixed video duration.
- Loudness mastering target of -16 LUFS.
- Micro-direction inside every scene: reveals, pushes, stamps and zooms.
- Evidence URL capture with optional focus-text crop.
- Evidence progression: full source → crop → excerpt.
- Chat scenes reveal message, recovered amount, fee and warning stamp in sequence.
- Image scenes use automatic Ken Burns movement.
- Split scenes animate both sides.
- Safer caption zone for vertical Shorts.
- 9:16, 16:9 and 1:1 project formats.
- JSON import/export designed as an AI-friendly project bridge.

## Local renderer

The installed V2 studio runs a local HTTP interface on `127.0.0.1:4173` and sends render jobs to a Node worker. The worker generates narration through Kokoro, captures evidence through Playwright/Edge, renders scene frames and encodes/masteres the final video with FFmpeg.

Local output convention:

`Z:\LooksLegit\renders\*_DIRECTOR_*.mp4`

## Status

**Functional local application / V2 Auto Director.** A real MP4 render has been produced from the system. The public version is currently the frontend/workflow test; the full renderer remains local.