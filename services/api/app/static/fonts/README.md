# HUD font placeholder

Drop the exact TUESDAY HUD font here as:

- `tuesday-hud.woff2` (preferred)
- or `.ttf` / `.otf`

Then update `styles.css`:

```css
@font-face {
  font-family: "TuesdayHUD";
  src: url("/static/fonts/tuesday-hud.woff2") format("woff2");
  font-display: swap;
}
```

Until then, the UI uses system UI fonts with the same layout language.
