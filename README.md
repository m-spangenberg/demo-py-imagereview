# py-imagereview

A Python and Tkinter-based image review desktop app for triaging a folder of images.

![demo](media/screenshot.png)

## Roadmap

- [ ] Add testing to cover core functionality
- [ ] Support nested folders (ignore `DISCARDED` subfolders)
- [ ] Support more image formats (e.g. GIF, BMP)

## Install and Run

```bash
# Option 1: Clone and run with UV:
git clone https://github.com/m-spangenberg/py-imagereview.git
cd py-imagereview
uv sync && uv run py-imagereview

# Option 2: Pull it from GitHub with just pip:
pip install git+https://github.com/m-spangenberg/py-imagereview.git
py-imagereview

# Option 3:same thing as 2 but with UV:
uv pip install git+https://github.com/m-spangenberg/py-imagereview.git
```

## Features

- Review one folder at a time without modifying files until commit
- Mark images as keep or discard with buttons or keyboard shortcuts
- Jump to the next unmarked image
- Undo the last mark or reset operation
- Commit only discarded files by moving them into a `DISCARDED` subfolder
- Reset all in-memory marks without touching files

## Shortcuts

- `Ctrl+O`: open folder
- `Up`: mark keep
- `Down`: mark discard
- `Left` / `Right`: previous or next image
- `N`: jump to next unmarked image
- `U` or `Ctrl+Z`: undo last action
- `W`: commit discards
- `R`: reset all marks
- `Esc`: exit

## Supported formats

- `.jpg`
- `.jpeg`
- `.png`
- `.tif`
- `.tiff`

## Dependencies

- Python 3.14.5 or later
- Tkinter (usually included as `python3-tkinter` in Linux distros)
- Pillow (Python Imaging Library fork)
