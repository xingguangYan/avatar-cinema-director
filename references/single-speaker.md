# Single Presenter Route

Use this route for a monologue, news-style update, product explanation, or one
character reading a script.

## Required Inputs

- One user-supplied character photo.
- One user-supplied background photo, or separate 16:9 and 9:16 backgrounds.
- A dialogue array in which every line names that character.
- One voice assignment.

## Pipeline

1. Validate the manifest and source images.
2. Synthesize one line at a time and build a master track plus one padded
   speaker track.
3. Crop the user background to every requested aspect before compositing.
4. Remove the character photo background and create a 768x1280 transparent
   panel, refined alpha mask, and contact shadow.
5. Run one static-image Wav2Lip render for the complete padded track.
6. Overlay the shadow and color-matched character over the cropped background.
7. Add captions, subtle body sway, optional music, fades, and metadata.
8. Render only the requested aspects.

## Composition

- `16x9`: character centered and nearly full height.
- `9x16`: character centered with more headroom and caption-safe lower space.

Return one output video per requested aspect.
