# Two-Person Dialogue Route

Use this route for a conversation between two characters. It is the preferred
route whenever the script alternates speakers.

## Required Inputs

- Two distinct user-supplied character photos.
- User-supplied background photos: a dedicated 16:9 image and a dedicated
  9:16 image are preferred; a shared `default` image is supported.
- Dialogue text with every line assigned to one of the two characters.
- One voice per character. Distinct voices are strongly recommended.

## Pipeline

1. Validate exactly two characters, two photos, both voices, backgrounds, and
   speaker names.
2. Synthesize the alternating dialogue into a master track and one padded
   track per character.
3. Crop each user background to the exact target aspect with an explicit focus
   point.
4. Cut out both characters and build refined masks plus contact shadows.
5. Run Wav2Lip sequentially for each complete padded track.
6. Overlay both shadows and color-matched characters over the cropped scene.
7. Add speaker-colored captions, subtle independent sway, optional music, and
   fades.
8. Render only the requested aspects.

## Composition

- `16x9`: first character left, second character right.
- `9x16`: first character top, second character bottom.

Both characters remain visible throughout the video. Only their mouth regions
animate from their respective full dialogue tracks; the final soundtrack comes
from the dialogue master, not the temporary lip-sync videos.

Do not composite directly from the uncropped background. The `backgrounds`
stage must run before rendering so both people are placed into a stable,
aspect-correct scene.

## Checks

- Confirm both faces are visible in the first, middle, and last frames.
- Confirm captions do not cover either mouth.
- Confirm the two voice assignments are not accidentally identical.
- Confirm the 9:16 safe area keeps the lower character's face above captions.
