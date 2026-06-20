# flix

Tools for netflix processing workflow. All data, temporary or final, lives in the data/ folder. All generic operations should live in the lib/ folder.

## 01_rough_cut.py

Cuts a video into multiple segments using ffmpeg and prompts from the user. These do not need to be precise, just user inputted.

## 02_merge.py

Takes a video and TTML as input. Transcribes a short audio sample (ElevenLabs STT) and asks Claude to find the constant offset between the subtitle and audio timing, shifts the TTML cues accordingly, converts them to SRT, and muxes the result into the .mp4 with proper subtitle metadata.

## 03_transcode.py

Compress the .mp4 using the following operation (CRF 23, preset slow, 720p, H.264).
```bash
ffmpeg -i input.mp4 -map 0 -vf scale=-2:720 -c:v libx264 -c:a aac -c:s copy -crf 23 -preset slow -y output.mp4
```
