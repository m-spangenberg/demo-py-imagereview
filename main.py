from __future__ import annotations

import importlib
import os
import shutil
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

try:
    from PIL import Image, ImageOps

    ImageTk = importlib.import_module("PIL.ImageTk")
except ImportError:
    Image = None
    ImageOps = None
    ImageTk = None


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
DECISION_LABELS = {
    "unmarked": ("UNMARKED", "#6b7280"),
    "keep": ("KEEP", "#0f9d58"),
    "discard": ("DISCARD", "#c62828"),
}


@dataclass
class ReviewItem:
    image_name: str
    image_path: Path
    decision: str = "unmarked"


@dataclass
class ReviewAction:
    kind: str
    index: int
    previous_index: int
    previous_decision: str | None = None
    snapshot: list[str] | None = None


class ImageReviewApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Image Review 0.1.0")
        self.root.geometry("1100x780")
        self.root.minsize(820, 620)

        self.current_dir: Path | None = None
        self.items: list[ReviewItem] = []
        self.current_index = 0
        self.current_photo: Any = None
        self.resize_after_id: str | None = None
        self.undo_history: list[ReviewAction] = []
        self.folder_var = tk.StringVar(value="No folder selected")
        self.progress_var = tk.StringVar(value="0 reviewed")
        self.summary_keep_var = tk.StringVar(value="Keep: 0")
        self.summary_discard_var = tk.StringVar(value="Discard: 0")
        self.summary_unmarked_var = tk.StringVar(value="Unmarked: 0")

        self._set_icon()
        self._configure_style()
        self._build_menu()
        self._build_ui()
        self._bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self._handle_exit)
        self._update_ui_state()

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("HeaderTitle.TLabel", font=("TkDefaultFont", 16, "bold"))
        style.configure("HeaderMeta.TLabel", foreground="#475569")
        style.configure("Metric.TLabel", font=("TkDefaultFont", 10, "bold"))
        style.configure("Toolbar.TButton", padding=(10, 8))

    def _set_icon(self) -> None:
        icon_path = Path(__file__).with_name("icon.png")
        if not icon_path.exists():
            return

        try:
            self.root.iconphoto(True, tk.PhotoImage(file=str(icon_path)))
        except tk.TclError:
            pass

    def _build_menu(self) -> None:
        main_menu = tk.Menu(self.root)
        self.root.config(menu=main_menu)

        file_menu = tk.Menu(main_menu, tearoff=False)
        file_menu.add_command(
            label="Open Folder", command=self.select_folder, accelerator="Ctrl+O"
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Commit Changes", command=self.commit_changes, accelerator="W"
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Exit", command=self._handle_exit, accelerator="Esc"
        )
        main_menu.add_cascade(label="File", menu=file_menu)

        review_menu = tk.Menu(main_menu, tearoff=False)
        review_menu.add_command(
            label="Mark Keep", command=self.mark_keep, accelerator="Up"
        )
        review_menu.add_command(
            label="Mark Discard", command=self.mark_discard, accelerator="Down"
        )
        review_menu.add_separator()
        review_menu.add_command(
            label="Back", command=self.go_previous, accelerator="Left"
        )
        review_menu.add_command(
            label="Forward", command=self.go_next, accelerator="Right"
        )
        review_menu.add_command(
            label="Next Unmarked", command=self.jump_to_next_unmarked, accelerator="N"
        )
        review_menu.add_separator()
        review_menu.add_command(
            label="Undo", command=self.undo_last_action, accelerator="U / Ctrl+Z"
        )
        review_menu.add_command(
            label="Reset Marks", command=self.reset_changes, accelerator="R"
        )
        main_menu.add_cascade(label="Review", menu=review_menu)

        help_menu = tk.Menu(main_menu, tearoff=False)
        help_menu.add_command(label="Shortcuts", command=self.show_shortcuts)
        help_menu.add_command(label="About", command=self.show_about)
        main_menu.add_cascade(label="Help", menu=help_menu)

    def _build_metric_label(
        self, parent: ttk.Frame, textvariable: tk.StringVar
    ) -> ttk.Label:
        label = ttk.Label(
            parent, textvariable=textvariable, style="Metric.TLabel", padding=(10, 6)
        )
        label.pack(side="left", padx=(0, 8))
        return label

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        container = ttk.Frame(self.root, padding=12)
        container.grid(sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        header = ttk.Frame(container, padding=(0, 0, 0, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title_row = ttk.Frame(header)
        title_row.grid(row=0, column=0, sticky="ew")
        title_row.columnconfigure(0, weight=1)

        title_block = ttk.Frame(title_row)
        title_block.grid(row=0, column=0, sticky="w")
        # ttk.Label(title_block, text="Image Review", style="HeaderTitle.TLabel").grid(
        #     row=0, column=0, sticky="w"
        # )
        ttk.Label(
            title_block, textvariable=self.folder_var, style="HeaderMeta.TLabel"
        ).grid(row=1, column=0, sticky="w")

        header_actions = ttk.Frame(title_row)
        header_actions.grid(row=0, column=1, sticky="e")

        metrics_row = ttk.Frame(header, padding=(0, 8, 0, 0))
        metrics_row.grid(row=1, column=0, sticky="ew")
        ttk.Label(
            metrics_row,
            textvariable=self.progress_var,
            style="Metric.TLabel",
            padding=(10, 6),
        ).pack(side="left", padx=(0, 8))
        self._build_metric_label(metrics_row, self.summary_keep_var)
        self._build_metric_label(metrics_row, self.summary_discard_var)
        self._build_metric_label(metrics_row, self.summary_unmarked_var)

        self.canvas = tk.Canvas(
            container,
            background="#101417",
            highlightthickness=0,
            takefocus=False,
        )
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        controls = ttk.Frame(container, padding=(0, 10, 0, 10))
        controls.grid(row=2, column=0, sticky="ew")
        for index in range(8):
            controls.columnconfigure(index, weight=1)

        self.back_button = ttk.Button(
            controls,
            text="Back (Left)",
            command=self.go_previous,
            style="Toolbar.TButton",
        )
        self.back_button.grid(row=0, column=0, padx=4, sticky="ew")

        self.keep_button = ttk.Button(
            controls, text="Keep (Up)", command=self.mark_keep, style="Toolbar.TButton"
        )
        self.keep_button.grid(row=0, column=1, padx=4, sticky="ew")

        self.discard_button = ttk.Button(
            controls,
            text="Discard (Down)",
            command=self.mark_discard,
            style="Toolbar.TButton",
        )
        self.discard_button.grid(row=0, column=2, padx=4, sticky="ew")

        self.forward_button = ttk.Button(
            controls,
            text="Forward (Right)",
            command=self.go_next,
            style="Toolbar.TButton",
        )
        self.forward_button.grid(row=0, column=3, padx=4, sticky="ew")

        self.next_unmarked_button = ttk.Button(
            controls,
            text="Next Unmarked (N)",
            command=self.jump_to_next_unmarked,
            style="Toolbar.TButton",
        )
        self.next_unmarked_button.grid(row=0, column=4, padx=4, sticky="ew")

        self.undo_button = ttk.Button(
            controls,
            text="Undo (U)",
            command=self.undo_last_action,
            style="Toolbar.TButton",
        )
        self.undo_button.grid(row=0, column=5, padx=4, sticky="ew")

        self.commit_button = ttk.Button(
            controls,
            text="Commit (W)",
            command=self.commit_changes,
            style="Toolbar.TButton",
        )
        self.commit_button.grid(row=0, column=6, padx=4, sticky="ew")

        self.reset_button = ttk.Button(
            controls,
            text="Reset (R)",
            command=self.reset_changes,
            style="Toolbar.TButton",
        )
        self.reset_button.grid(row=0, column=7, padx=4, sticky="ew")

        self.status_var = tk.StringVar(
            value="Select a folder to start reviewing images."
        )
        self.status_bar = ttk.Label(
            container,
            textvariable=self.status_var,
            anchor="w",
            relief="sunken",
            padding=(8, 6),
        )
        self.status_bar.grid(row=3, column=0, sticky="ew")

    def _bind_keys(self) -> None:
        self.root.bind("<Control-o>", lambda _event: self.select_folder())
        self.root.bind("<Control-O>", lambda _event: self.select_folder())
        self.root.bind("<Up>", lambda _event: self.mark_keep())
        self.root.bind("<Down>", lambda _event: self.mark_discard())
        self.root.bind("<Left>", lambda _event: self.go_previous())
        self.root.bind("<Right>", lambda _event: self.go_next())
        self.root.bind("<n>", lambda _event: self.jump_to_next_unmarked())
        self.root.bind("<N>", lambda _event: self.jump_to_next_unmarked())
        self.root.bind("<u>", lambda _event: self.undo_last_action())
        self.root.bind("<U>", lambda _event: self.undo_last_action())
        self.root.bind("<Control-z>", lambda _event: self.undo_last_action())
        self.root.bind("<Control-Z>", lambda _event: self.undo_last_action())
        self.root.bind("<w>", lambda _event: self.commit_changes())
        self.root.bind("<W>", lambda _event: self.commit_changes())
        self.root.bind("<r>", lambda _event: self.reset_changes())
        self.root.bind("<R>", lambda _event: self.reset_changes())
        self.root.bind("<Escape>", lambda _event: self._handle_exit())

    def select_folder(self) -> None:
        initial_dir = str(self.current_dir or Path.cwd())
        dir_path = filedialog.askdirectory(
            initialdir=initial_dir, title="Select image directory"
        )
        if not dir_path:
            return

        items, skipped_count = build(Path(dir_path))
        if not items:
            messagebox.showinfo(
                "No supported images",
                "The selected folder does not contain any supported image files.",
            )
            return

        self.current_dir = Path(dir_path)
        self.items = items
        self.current_index = 0
        self.undo_history.clear()
        self._render_current_image()

        if skipped_count:
            self._update_ui_state(
                extra_message=f"Skipped {skipped_count} unsupported file(s)."
            )

    def _has_pending_session_changes(self) -> bool:
        return any(item.decision != "unmarked" for item in self.items)

    def _handle_exit(self) -> None:
        if self._has_pending_session_changes():
            should_exit = messagebox.askyesno(
                "Exit Image Review",
                "There are uncommitted review decisions in this session. Exit anyway?",
                default=messagebox.NO,
            )
            if not should_exit:
                return

        self.root.quit()

    def show_shortcuts(self) -> None:
        messagebox.showinfo(
            "Keyboard shortcuts",
            (
                "Ctrl+O: Open folder\n"
                "Up / Down: Mark keep or discard\n"
                "Left / Right: Move backward or forward\n"
                "N: Jump to next unmarked image\n"
                "U or Ctrl+Z: Undo last action\n"
                "W: Commit discards\n"
                "R: Reset all marks\n"
                "Esc: Exit"
            ),
        )

    def show_about(self) -> None:
        messagebox.showinfo(
            "About Image Review",
            "Image Review 0.1.0\nA lightweight Tkinter tool for triaging image folders safely.",
        )

    def _render_empty_state(self, message: str, secondary: str | None = None) -> None:
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.canvas.create_text(
            width / 2,
            max(height / 2 - 50, 80),
            text=message,
            fill="#e5e7eb",
            font=("TkDefaultFont", 18, "bold"),
            justify="center",
        )
        body = secondary or "Use Open Folder or Ctrl+O to load a directory of images."
        self.canvas.create_text(
            width / 2,
            height / 2 + 10,
            text=body,
            fill="#94a3b8",
            font=("TkDefaultFont", 11),
            justify="center",
            width=max(width - 120, 220),
        )

    def _draw_caption_bar(self, item: ReviewItem) -> None:
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.canvas.create_rectangle(
            0, height - 50, width, height, fill="#111827", outline=""
        )
        self.canvas.create_text(
            18,
            height - 25,
            text=item.image_name,
            fill="#f8fafc",
            font=("TkDefaultFont", 11, "bold"),
            anchor="w",
        )

    def _on_canvas_resize(self, _event: tk.Event) -> None:
        if not self.items:
            return

        if self.resize_after_id:
            self.root.after_cancel(self.resize_after_id)

        self.resize_after_id = self.root.after(120, self._render_current_image)

    def _render_current_image(self) -> None:
        self.resize_after_id = None
        self.canvas.delete("all")

        if not self.items:
            self.current_photo = None
            self._render_empty_state(
                "Select a folder to start reviewing images.",
                "Supported formats: JPG, JPEG, PNG, TIF, TIFF\nMark images with the keyboard or toolbar, then commit only the discards.",
            )
            self._update_ui_state()
            return

        if Image is None or ImageOps is None or ImageTk is None:
            messagebox.showerror(
                "Missing dependency",
                "Pillow is required to display images. Install it with: pip install pillow",
            )
            self.root.quit()
            return

        item = self.items[self.current_index]
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        frame_width = max(width - 40, 100)
        frame_height = max(height - 40, 100)

        try:
            with Image.open(item.image_path) as image:
                prepared = ImageOps.exif_transpose(image).convert("RGB")
                prepared.thumbnail((frame_width, frame_height))
                display_image = prepared.copy()
        except OSError as exc:
            self._render_empty_state(
                "Unable to open the current image.",
                f"{item.image_name}\n{exc}",
            )
            self._update_ui_state(extra_message="Unable to render current image")
            return

        self.current_photo = ImageTk.PhotoImage(display_image)
        self.canvas.create_image(
            width / 2, height / 2, image=self.current_photo, anchor="center"
        )
        self._draw_overlay(item)
        self._draw_caption_bar(item)
        self._update_ui_state()

    def _draw_overlay(self, item: ReviewItem) -> None:
        decision_text, color = DECISION_LABELS[item.decision]
        if item.decision == "unmarked":
            return

        self.canvas.create_rectangle(20, 20, 220, 70, fill=color, outline="")
        self.canvas.create_text(
            120,
            45,
            text=decision_text,
            fill="#ffffff",
            font=("TkDefaultFont", 18, "bold"),
        )

    def _update_ui_state(self, extra_message: str | None = None) -> None:
        has_items = bool(self.items)
        keep_count = sum(item.decision == "keep" for item in self.items)
        pending_discards = sum(item.decision == "discard" for item in self.items)
        unmarked_count = sum(item.decision == "unmarked" for item in self.items)
        reviewed_count = keep_count + pending_discards

        # limit current directory immediate parent folder name for better readability in UI
        # self.folder_var.set(f"Folder: {self.current_dir}" if self.current_dir else "No folder selected")

        folder_name = (
            os.path.basename(self.current_dir)
            if self.current_dir
            else "No folder selected"
        )
        self.folder_var.set(
            f"Folder: {folder_name}" if has_items else "No folder selected"
        )

        self.progress_var.set(
            f"Reviewed: {reviewed_count}/{len(self.items)}"
            if has_items
            else "Reviewed: 0/0"
        )
        self.summary_keep_var.set(f"Keep: {keep_count}")
        self.summary_discard_var.set(f"Discard: {pending_discards}")
        self.summary_unmarked_var.set(f"Unmarked: {unmarked_count}")

        button_states = {
            self.back_button: tk.NORMAL
            if has_items and self.current_index > 0
            else tk.DISABLED,
            self.keep_button: tk.NORMAL if has_items else tk.DISABLED,
            self.discard_button: tk.NORMAL if has_items else tk.DISABLED,
            self.forward_button: tk.NORMAL
            if has_items and self.current_index < len(self.items) - 1
            else tk.DISABLED,
            self.next_unmarked_button: tk.NORMAL
            if has_items and unmarked_count > 0
            else tk.DISABLED,
            self.undo_button: tk.NORMAL if bool(self.undo_history) else tk.DISABLED,
            self.commit_button: tk.NORMAL if pending_discards > 0 else tk.DISABLED,
            self.reset_button: tk.NORMAL if has_items else tk.DISABLED,
        }
        for button, state in button_states.items():
            button.configure(state=state)

        if not has_items:
            self.status_var.set(
                extra_message or "Select a folder to start reviewing images."
            )
            return

        item = self.items[self.current_index]
        decision_text, _ = DECISION_LABELS[item.decision]
        prefix = f"{self.current_index + 1}/{len(self.items)} | {item.image_name} | {decision_text}"
        suffix = f"Keep: {keep_count} | Discard: {pending_discards} | Unmarked: {unmarked_count}"
        if extra_message:
            self.status_var.set(f"{prefix} | {suffix} | {extra_message}")
            return

        self.status_var.set(f"{prefix} | {suffix}")

    def _mark_current(self, decision: str) -> None:
        if not self.items:
            return

        current_item = self.items[self.current_index]
        self.undo_history.append(
            ReviewAction(
                kind="mark",
                index=self.current_index,
                previous_index=self.current_index,
                previous_decision=current_item.decision,
            )
        )
        current_item.decision = decision
        self._render_current_image()

    def _find_next_unmarked_index(self) -> int | None:
        if not self.items:
            return None

        total_items = len(self.items)
        for step in range(1, total_items + 1):
            candidate_index = (self.current_index + step) % total_items
            if self.items[candidate_index].decision == "unmarked":
                return candidate_index

        return None

    def mark_keep(self) -> None:
        if not self.items:
            return

        self._mark_current("keep")
        if self.current_index < len(self.items) - 1:
            self.current_index += 1
            self._render_current_image()

    def mark_discard(self) -> None:
        if not self.items:
            return

        self._mark_current("discard")
        if self.current_index < len(self.items) - 1:
            self.current_index += 1
            self._render_current_image()

    def go_previous(self) -> None:
        if not self.items or self.current_index == 0:
            return

        self.current_index -= 1
        self._render_current_image()

    def go_next(self) -> None:
        if not self.items or self.current_index >= len(self.items) - 1:
            return

        self.current_index += 1
        self._render_current_image()

    def jump_to_next_unmarked(self) -> None:
        if not self.items:
            return

        next_index = self._find_next_unmarked_index()
        if next_index is None:
            self._update_ui_state(extra_message="No unmarked images remain.")
            return

        self.current_index = next_index
        self._render_current_image()

    def undo_last_action(self) -> None:
        if not self.undo_history:
            self._update_ui_state(extra_message="Nothing to undo.")
            return

        action = self.undo_history.pop()
        if action.kind == "mark":
            if (
                0 <= action.index < len(self.items)
                and action.previous_decision is not None
            ):
                self.items[action.index].decision = action.previous_decision
                self.current_index = action.index
        elif (
            action.kind == "reset"
            and action.snapshot is not None
            and len(action.snapshot) == len(self.items)
        ):
            for item, prior_decision in zip(self.items, action.snapshot):
                item.decision = prior_decision
            self.current_index = min(action.previous_index, len(self.items) - 1)

        self._render_current_image()

    def commit_changes(self) -> None:
        if not self.items:
            return

        if self.current_dir is None:
            messagebox.showerror("Commit failed", "No source directory is selected.")
            return

        discard_count = sum(item.decision == "discard" for item in self.items)
        unmarked_count = sum(item.decision == "unmarked" for item in self.items)
        if discard_count == 0:
            messagebox.showinfo(
                "Nothing to commit", "There are no images marked for discard."
            )
            return

        answer = messagebox.askyesno(
            "Commit discard changes",
            (
                f"Move {discard_count} image(s) into the DISCARDED subfolder?\n\n"
                f"Unmarked images remaining: {unmarked_count}"
            ),
            default=messagebox.NO,
        )
        if not answer:
            return

        discard_dir = self.current_dir / "DISCARDED"

        try:
            moved_count = discard(self.current_dir, self.items)
        except OSError as exc:
            messagebox.showerror(
                "Commit failed", f"Unable to move discarded images.\n\n{exc}"
            )
            return

        self.items = [item for item in self.items if item.decision != "discard"]
        self.undo_history.clear()
        if self.items:
            self.current_index = min(self.current_index, len(self.items) - 1)
            self._render_current_image()
        else:
            self.current_index = 0
            self._render_current_image()

        messagebox.showinfo(
            "Commit complete",
            f"Moved {moved_count} image(s) into {discard_dir}",
        )

    def reset_changes(self) -> None:
        if not self.items:
            return

        if not self._has_pending_session_changes():
            self._update_ui_state(extra_message="There are no marks to reset.")
            return

        should_reset = messagebox.askyesno(
            "Reset all marks",
            "Clear every keep and discard mark for the current session?",
            default=messagebox.NO,
        )
        if not should_reset:
            return

        self.undo_history.append(
            ReviewAction(
                kind="reset",
                index=self.current_index,
                previous_index=self.current_index,
                snapshot=[item.decision for item in self.items],
            )
        )

        for item in self.items:
            item.decision = "unmarked"

        self._render_current_image()


def build(dir_path: Path) -> tuple[list[ReviewItem], int]:
    """Scan the directory for supported images and return the review list and skipped count."""
    if not dir_path.exists() or not dir_path.is_dir():
        return [], 0

    entries = [path for path in dir_path.iterdir() if path.is_file()]
    image_paths = typecheck(entries)
    skipped_count = len(entries) - len(image_paths)

    return [
        ReviewItem(image_name=image_path.name, image_path=image_path)
        for image_path in sorted(image_paths, key=lambda item: item.name.lower())
    ], skipped_count


def typecheck(paths: list[Path]) -> list[Path]:
    """Remove unsupported file types from a list of file paths."""
    return [path for path in paths if path.suffix.lower() in SUPPORTED_SUFFIXES]


def _unique_target_path(target_dir: Path, image_name: str) -> Path:
    target_path = target_dir / image_name
    if not target_path.exists():
        return target_path

    stem = target_path.stem
    suffix = target_path.suffix
    counter = 1
    while True:
        candidate = target_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def discard(base_dir: Path | None, items: list[ReviewItem]) -> int:
    """Move discarded images into a DISCARDED sub-folder."""
    if base_dir is None:
        raise OSError("No source directory selected.")

    discard_dir = base_dir / "DISCARDED"
    discard_dir.mkdir(exist_ok=True)

    moved_count = 0
    for item in items:
        if item.decision != "discard":
            continue

        target_path = _unique_target_path(discard_dir, item.image_name)
        shutil.move(str(item.image_path), str(target_path))
        moved_count += 1

    return moved_count


def main() -> None:
    root = tk.Tk()
    app = ImageReviewApp(root)
    app._render_current_image()
    root.mainloop()


if __name__ == "__main__":
    main()
