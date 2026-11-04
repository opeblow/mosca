# Mosca launch film

**The film:** [`mosca-launch-film.mp4`](mosca-launch-film.mp4), 2:54, 1920x1080, 30 fps, H.264 with AAC stereo, loudness normalised to -16 LUFS. Subtitles: [`mosca-launch-film.srt`](mosca-launch-film.srt).

## Creative brief

- **Idea.** The data you encrypt today has a decryption date. The film opens in the dark, on a recording in progress (ciphertext scrolling, a capture light), and turns to paper when Mosca appears: threat, then clarity.
- **Audience.** Hackathon judges (Switch, DevTools Academy, WeMakeDevs), security leads and platform engineers.
- **Arc.** Hook (someone is recording) / problem (RSA and ECC break, NIST dates) / Mosca's inequality / three questions every team must answer / reveal / the real room session: scan, owner answer, fix, rescan, review, a person decides / the record / close.
- **Look.** Mosca's own identity: warm paper `#f1eee6`, ink `#141413`, one signal red `#d9481f`, Instrument Serif headlines, IBM Plex Mono for evidence. No gradients, no fake interface.
- **Honesty.** Every interface shot is a capture of the real product: the `#q-day` Switch room on Mattermost (session of Nov 4, 2026), the website and the ledger dashboard with live data. The hook and problem scenes are illustrative typography, and are clearly not product UI.

## Structure

| Time | Scene | Shows |
|---|---|---|
| 0:00 | hook | Ciphertext rows scrolling, "capture in progress"; the recording line, then "Not yet." |
| 0:15 | problem | RSA, ECDSA, X25519, Diffie-Hellman struck through; a 2024 to 2036 timeline with FIPS 203/204/205, deprecation (2030) and disallowed (2035), as proposed in NIST IR 8547 |
| 0:36 | inequality | X + Y > Z, each term lit as it is explained |
| 0:51 | questions | Where is our cryptography? What matters most? Who fixes it? |
| 0:59 | reveal | The wordmark, then the real website hero |
| 1:08 | scan | The real room (wide), then Mosca's report with the P(exposed) column marked, the CBOM document and a real CBOM excerpt |
| 1:27 | question | Mosca's question, the owner's answer, the ledger record; 1% to 70% |
| 1:45 | migrate | Claude Code in the exclusive migrator role, its change, then Mosca's rescan: 3DES resolved, exposure down 6%, readiness 13% to 16% |
| 2:05 | review | OpenCode in the shared reviewer role approves; a person approves; the migrator declines to merge |
| 2:21 | ledger | The live ledger dashboard, then the open model on the website |
| 2:37 | close | "The data you encrypt today has a decryption date." Wordmark, repository, Apache 2.0, built on Switch |

Exact timings: [`timeline.json`](timeline.json). Narration with timings: [`SCRIPT.md`](SCRIPT.md).

## Screen coverage

- [x] Website landing page (hero)
- [x] Website method section with the interactive model
- [x] Ledger dashboard with live data from the session
- [x] Switch room, wide view
- [x] Mosca: scan command, ranked report, CBOM room document
- [x] Mosca: owner question, owner answer, ledger record
- [x] Claude Code (migrator role): request and reply
- [x] Mosca: branch rescan
- [x] OpenCode (reviewer role): review and approval
- [x] Person approves; migrator declines to merge
- [x] A real CBOM excerpt (CycloneDX 1.6) from a scan of the sample repository

## Pipeline

All local, no paid services.

| Step | Tool | Source |
|---|---|---|
| Capture | Playwright + Chromium: the real room, website and ledger at 2x | [`src/capture.py`](src/capture.py) |
| Narration | Kokoro TTS v1.0 (Apache 2.0), voice `af_heart`, rendered per line | [`src/tts.py`](src/tts.py), [`narration.json`](narration.json) |
| Timeline | Scenes timed to the measured narration | [`src/build_timeline.py`](src/build_timeline.py) |
| Picture | One HTML composition with a deterministic `seek(t)`, rendered frame by frame | [`src/film.html`](src/film.html), [`src/render.py`](src/render.py) |
| Score and mix | Original score synthesised in NumPy (pads, plucks, bells, a clock tick), narration placed on cues, music ducked about 9 dB under speech | [`src/audio.py`](src/audio.py) |
| Finish | FFmpeg: H.264 CRF 16, AAC 192k, loudnorm to -16 LUFS | [`src/finish.py`](src/finish.py) |

### Rebuild

```bash
pip install playwright kokoro-onnx soundfile numpy
# model files into assets/models/: kokoro-v1.0.onnx and voices-v1.0.bin
#   from https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
python src/capture.py --web http://localhost:3000 --mm http://localhost:8065   # needs the room running
python src/tts.py
python src/build_timeline.py
python src/audio.py
python src/render.py --stills 5,45,100          # preview frames
python src/render.py --video                    # or render ranges in parallel with --start/--end
python src/finish.py out/video.mp4
```

## Asset inventory

| Asset | Source | Basis |
|---|---|---|
| Interface captures | This project's website, ledger and Switch room | Own work |
| Fonts | Instrument Serif, IBM Plex Sans, IBM Plex Mono (Google Fonts) | SIL Open Font License |
| Voice | Kokoro-82M v1.0, voice `af_heart` | Apache 2.0 |
| Music and sound effects | Synthesised in `src/audio.py` | Original |
| Ciphertext texture | Generated pseudo-random hex | Original |

Model files, captures and intermediate renders are not committed. They are regenerated by the pipeline.
