## Automation idea

Can you help me make a Claude skill. We can modify the 01-04 here if needed. Or add other scripts/ that you can give the skill.

I want to drop in a bunch of disorganized files (mp4 and TTML subtitles). The mp4 files will contain multiple TTML files, where the last one will be cut off.

We want to identify how to rough cut the videos and which TTML to pair the rough cuts with. For example:
- Given abcdef.mp4 and s1e1.ttml, s1e2.ttml, and s1e3.ttml
- We want to identify that abcdef.mp4 begins with s1e1.ttml (using Elevenlabs sampling)
- Then we can trust the s1e1.ttml to trust how to cut the start and end
- Now we want to look at the end of this segment and do the same process (check which ttml it matches, in this case it would match s1e2.ttml)
- In this example, we see that s1e3.ttml is longer than the remaining length of the video (e.g.), so we just discard the rest of the video. s1e3.ttml will exist at the start of another video.

Feel free to make big changes here to accomplish our goal. Do some thinking then let's go over the plan.



