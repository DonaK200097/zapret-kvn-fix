# Project Rules

- Keep page-level surfaces transparent. Do not add local background fills or page/root/scroll-area style sheets that block Windows 11 Mica.
- Prefer built-in `qfluentwidgets` appearance over custom page styling. Add local UI styling only when the user explicitly asks for it or when the library cannot provide the needed result.
- Do not force `WA_TranslucentBackground` on full pages, scroll areas, or their viewports unless it is explicitly needed and visually verified; prefer the same built-in page behavior used by working screens.
- After UI changes, rebuild the app and verify it still starts.
