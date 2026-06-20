# flix

Tools for netflix processing workflow. All data, temporary or final, lives in the data/ folder. All generic operations should live in the lib/ folder.

## 01_rough_cut.py

Cuts a video into multiple segments using ffmpeg and prompts from the user. These do not need to be precise, just user inputted.

## 02_merge.py

Takes a video and TTML as input. We want to:
1. Ensure the TTML subtitles are aligned with the contents of the video. We can use a STT library (elevenlabs) to capture a sample and then use the sample to align the timings.
9. Convert the TTML to SRT and embed in the .mp4

## 03_transcode.py

Compress the .mp4 using the following operation (CRF 23, preset slow, 720p, H.264).
```bash
ffmpeg -i input.mp4 -map 0 -vf scale=-2:720 -c:v libx264 -c:a aac -c:s copy -crf 23 -preset slow -y output.mp4
```
