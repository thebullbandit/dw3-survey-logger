# Clean UI theme separation

This patch introduces `theme.py` to hold UI color constants and keeps them out of user settings.

Changes:
- `theme.py`: new module with DEFAULT_COLORS and resolve_color(config,key)
- `view.py`: now uses theme defaults (still allows runtime overrides)
- `main.py`: no longer expects `config['GREEN']`; uses theme.resolve_color

Apply by overwriting the files in your project root.
