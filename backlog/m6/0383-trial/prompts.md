# 0383: ChatGPT prompts for painting mc03_female's texture

For the Owner. Free on the subscription; nothing here calls the API. This step only answers one question: **does GPT Image paint
flat, unlit colour in the rooms' style, on the same figure?** It needs no exact alignment (that is measured afterwards).

## What is in `packet/`

| File | What it is |
|---|---|
| `packet/front_view.png` | mc03_female (body only, no Wearable), front, rest pose (T-pose), unlit flat colour, 1024 x 1536, the figure 1024 px tall, plain grey background (160, 160, 160). **Attach this first.** |
| `packet/plate_annex_bedroom.png` | The style reference: the full-size GPT Image Source of `annex_bedroom` (1392 x 768, `assets/room/annex_bedroom/src/7bd7ce3dddc3f12a.png`, the same file as `work/source/source.png`). **Attach this second.** Not the 336 x 192 pixel Plate: the point is the painted detail (folds, grain, highlights), which the downscale throws away. |

What the front view shows, so you know what ChatGPT starts from: the Model has **no texture image**. Each of its four materials
(skin, underwear, hair, eyes) is one flat colour times a faint per-vertex shade (63 distinct colours in the whole view). So there
is no detail to keep: ChatGPT must invent all of it. The two dark ovals in the face are the `eyes` material; `finish` stamps the
eyes over them in the game's own style, so whatever is painted inside them is thrown away.

## Steps

1. Open a **new** ChatGPT chat (image creation on). One chat per wording, so the attempts don't see each other.
2. Attach `front_view.png` first, then `plate_annex_bedroom.png`, and paste one of the wordings below. Ask for a 2:3 portrait
   image if it asks about the size (the view is 1024 x 1536).
3. Look at the result against the checklist. Then, in the same chat, you may refine it by talking ("flatter", "less outline", "keep
   the arms where they were"); note what you said.
4. Save each result you want judged in this folder, as `result_<wording>_<n>.png` (`result_A_1.png`, `result_A_2.png`,
   `result_B_1.png`, `result_C_1.png`, ...), the original size, no cropping. Copy the final wording of any refined prompt into
   `winning_prompt.md` here.
5. Fill the table at the bottom. A line or two is enough; "no" with the reason is useful.

Look for, in this order:

- **Same figure**: same outline, same T-pose, same size and position on the canvas, the arms the same length, the legs apart the
  same. (The measure later gives the numbers; your eye catches the big shifts first.)
- **Flat unlit colour**: no light side and dark side, no cast shadow, no glow behind, no soft gradient over the whole body. Detail
  *inside* a colour is wanted: folds, seams, hair strands, small highlights as paint, not as lighting.
- **The rooms' feel**: the muted, slightly warm palette and the crisp painted detail of the Plate, not glossy 3D, not a cartoon
  outline.
- **No outline added**, no text or label, background still plain and the same grey.
- **The face**: kept simple; the dark eye ovals left as they are.

## Wording A: short

> Repaint the first image, the same figure, as flat colour in the painted style of the room in the second image. Keep the exact
> same pose, outline, size and position on the same canvas and the same plain grey background. Paint fabric folds, seams, hair
> strands and small highlights as colour detail only. No lighting and no shadows, no added outline, no text. Keep the face
> simple and leave the two dark eye shapes as they are. Use only the second image for the colour palette and the painting style.

## Wording B: detailed

> Image 1 is a 3D character shown flat and unlit, from the front, in a T-pose. Image 2 is a room from a game, only a style
> reference.
>
> Redraw image 1 as the same character painted in the style and palette of image 2: the muted, slightly warm colours and the crisp
> painted detail of the wood, the blanket and the cloth.
>
> Keep, exactly: the silhouette and outline, the pose (arms straight out, legs straight), the size, the position, the canvas size
> and shape, and the plain grey background.
>
> Make it a flat, unlit colour image, like a texture. There must be no light source: no light side and dark side, no cast or
> contact shadows, no ambient darkening, no rim light, no gradient across the body. A game engine will add the lighting later, so
> any shading you paint would be applied twice.
>
> Put the detail in the colour itself: folds and seams of the top and shorts, individual hair strands and hair colour variation,
> skin tone variation, a few small highlights painted as colour (not as light).
>
> Keep the face simple, no detailed eyes: leave the two dark eye shapes exactly as they are, with no pupils, lashes or glints
> added. Do not add an outline or a border around the figure. No text, no labels, no watermark, nothing added to the background.

## Wording C: texture-sheet / albedo-map framing

> Create an albedo map (a base-colour texture) for the character in image 1, as it would look projected flat onto the 3D model
> seen from the front. Albedo means pure surface colour: no lighting, no shadows, no highlights from a light, no ambient
> occlusion, no reflections.
>
> Keep image 1's exact layout: same silhouette, same T-pose, same scale and position, the same canvas and the same flat grey
> background, so that the result lines up with image 1 pixel for pixel.
>
> Paint it with the surface detail and the palette of the room in image 2: woven fabric with seams and folds drawn as darker and
> lighter *colour*, hair strands in several browns, subtle skin variation. The detail is paint, not light.
>
> Leave the two dark eye shapes unchanged and the face simple. No outline, no text, no extra objects.

## Table for the Owner

Score "style" 1 (not the rooms') to 5 (as the rooms'). Pose/outline: yes, mostly, no. Flat unlit: yes / some shading / lit.

| File | Wording | Flat unlit? | Style (1 to 5) | Same pose and outline? | Eyes left alone? | Outline / text added? | What you said to refine it, and notes |
|---|---|---|---|---|---|---|---|
| `result_A_1.png` | A | | | | | | |
| `result_B_1.png` | B | | | | | | |
| `result_C_1.png` | C | | | | | | |
| | | | | | | | |

Winner (wording and file):

Then tell the agent: it measures how far each result's silhouette is from `packet/front_view.png`, and says whether it lines up
well enough to project (ticket 0383, step 3).
