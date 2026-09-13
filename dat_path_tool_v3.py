import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

# =========================================================
# DAT Path Replacement Tool - Three-file version
# =========================================================

ROW_COUNT = 3
preview_completed = False
preview_signature = None

file_entries = []
find_entries = []
replace_entries = []


def backup_path(dat_path):
    """Return the backup path used for a DAT file."""
    return dat_path + ".bak"


def get_rows(include_incomplete=False):
    """Collect populated rows from the interface."""
    rows = []
    incomplete = []

    for index, (file_entry, find_entry, replace_entry) in enumerate(
        zip(file_entries, find_entries, replace_entries), start=1
    ):
        dat_path = file_entry.get().strip()
        find_path = find_entry.get()
        replace_path = replace_entry.get()

        # Completely blank rows are unused and are skipped.
        if not dat_path and not find_path and not replace_path:
            continue

        if not dat_path or not find_path:
            incomplete.append(index)
            continue

        rows.append(
            {
                "row": index,
                "dat_path": dat_path,
                "find_path": find_path,
                "replace_path": replace_path,
            }
        )

    if include_incomplete:
        return rows, incomplete
    return rows


def current_signature():
    """Capture the current input values so Apply requires a current preview."""
    return tuple(
        (
            file_entry.get().strip(),
            find_entry.get(),
            replace_entry.get(),
        )
        for file_entry, find_entry, replace_entry in zip(
            file_entries, find_entries, replace_entries
        )
    )


def invalidate_preview(*_args):
    global preview_completed, preview_signature
    preview_completed = False
    preview_signature = None
    if "apply_button" in globals():
        apply_button.config(state="disabled")


def update_restore_button(*_args):
    """Enable Restore when at least one selected file has a backup."""
    available = any(
        entry.get().strip() and os.path.isfile(backup_path(entry.get().strip()))
        for entry in file_entries
    )
    restore_button.config(state="normal" if available else "disabled")


def browse_file(target_entry):
    """Browse for a DAT file and place it in the requested row."""
    selected_file = filedialog.askopenfilename(
        title="Select DAT File",
        filetypes=[("DAT files", "*.dat"), ("All files", "*.*")],
    )
    if selected_file:
        target_entry.delete(0, tk.END)
        target_entry.insert(0, selected_file)
        invalidate_preview()
        update_restore_button()


def replacement_variants(find_text, replace_text):
    """
    Return likely text encodings used by DAT files.

    Byte-level replacement preserves all unrelated bytes in the DAT file.
    UTF-8 also covers ordinary ASCII/ANSI-style paths containing ASCII only.
    """
    variants = []
    for encoding, label in (
        ("utf-8", "UTF-8/ASCII"),
        ("utf-16-le", "UTF-16 LE"),
        ("utf-16-be", "UTF-16 BE"),
    ):
        try:
            find_bytes = find_text.encode(encoding)
            replace_bytes = replace_text.encode(encoding)
        except UnicodeEncodeError:
            continue

        if find_bytes and not any(existing[0] == find_bytes for existing in variants):
            variants.append((find_bytes, replace_bytes, label))
    return variants


def inspect_file(row):
    """Read a file and count matches for supported encodings."""
    dat_path = row["dat_path"]
    if not os.path.isfile(dat_path):
        raise FileNotFoundError(dat_path)

    with open(dat_path, "rb") as handle:
        data = handle.read()

    matches = []
    total = 0
    for find_bytes, replace_bytes, label in replacement_variants(
        row["find_path"], row["replace_path"]
    ):
        count = data.count(find_bytes)
        if count:
            matches.append((find_bytes, replace_bytes, label, count))
            total += count

    return data, matches, total


def validate_rows():
    rows, incomplete = get_rows(include_incomplete=True)

    if incomplete:
        messagebox.showerror(
            "Incomplete Input",
            "Complete both DAT File and Path to Find for row(s): "
            + ", ".join(map(str, incomplete))
            + ".\n\nReplace With may be blank if you intend to remove the path.",
        )
        return None

    if not rows:
        messagebox.showwarning(
            "No DAT Files", "Enter at least one DAT file and path to find."
        )
        return None

    missing = [str(row["row"]) for row in rows if not os.path.isfile(row["dat_path"])]
    if missing:
        messagebox.showerror(
            "File Not Found",
            "The DAT file does not exist for row(s): " + ", ".join(missing),
        )
        return None

    return rows


def show_results(title, lines):
    result_text.config(state="normal")
    result_text.delete("1.0", tk.END)
    result_text.insert(tk.END, title + "\n" + ("=" * len(title)) + "\n\n")
    result_text.insert(tk.END, "\n".join(lines))
    result_text.config(state="disabled")


def scan_file():
    """Scan every populated DAT row without changing any file."""
    rows = validate_rows()
    if rows is None:
        return

    lines = []
    grand_total = 0
    try:
        for row in rows:
            _data, matches, total = inspect_file(row)
            grand_total += total
            lines.append(f"Row {row['row']}: {row['dat_path']}")
            lines.append(f"  Matches: {total}")
            if matches:
                for _find, _replace, label, count in matches:
                    lines.append(f"  - {label}: {count}")
            else:
                lines.append("  - Path not found")
            lines.append("")
    except OSError as exc:
        messagebox.showerror("Scan Failed", str(exc))
        status_label.config(text="Status: Scan failed")
        return

    show_results("Scan Results", lines)
    status_label.config(text=f"Status: Scan complete - {grand_total} match(es)")


def preview_changes():
    """Preview replacements for every populated row."""
    global preview_completed, preview_signature

    rows = validate_rows()
    if rows is None:
        return

    lines = []
    grand_total = 0
    try:
        for row in rows:
            _data, matches, total = inspect_file(row)
            grand_total += total
            lines.extend(
                [
                    f"Row {row['row']}: {row['dat_path']}",
                    f"  Find:    {row['find_path']}",
                    f"  Replace: {row['replace_path']}",
                    f"  Replacements to make: {total}",
                ]
            )
            for _find, _replace, label, count in matches:
                lines.append(f"  - {label}: {count}")
            if not matches:
                lines.append("  - No changes would be made")
            lines.append("")
    except OSError as exc:
        messagebox.showerror("Preview Failed", str(exc))
        status_label.config(text="Status: Preview failed")
        return

    preview_completed = grand_total > 0
    preview_signature = current_signature() if preview_completed else None
    apply_button.config(state="normal" if preview_completed else "disabled")
    show_results("Preview", lines)
    status_label.config(text=f"Status: Preview complete - {grand_total} replacement(s)")

    if grand_total == 0:
        messagebox.showinfo("Preview", "No matching paths were found. No files will be changed.")


def apply_changes():
    """Back up and update every file included in the current preview."""
    global preview_completed, preview_signature

    if not preview_completed or preview_signature != current_signature():
        invalidate_preview()
        messagebox.showwarning(
            "Preview Required", "Inputs changed or no preview exists. Preview the changes again."
        )
        return

    rows = validate_rows()
    if rows is None:
        return

    plans = []
    try:
        # Prepare every change before writing any file.
        for row in rows:
            data, matches, total = inspect_file(row)
            updated = data
            for find_bytes, replace_bytes, _label, _count in matches:
                updated = updated.replace(find_bytes, replace_bytes)
            plans.append((row, data, updated, total))
    except OSError as exc:
        messagebox.showerror("Apply Failed", str(exc))
        status_label.config(text="Status: Apply failed")
        return

    total_changes = sum(plan[3] for plan in plans)
    if total_changes == 0:
        invalidate_preview()
        messagebox.showinfo("No Changes", "No matching paths were found.")
        return

    if not messagebox.askyesno(
        "Apply Changes",
        f"Apply {total_changes} replacement(s) across "
        f"{sum(1 for plan in plans if plan[3])} DAT file(s)?\n\n"
        "A .bak backup will be created before each changed file is written.",
    ):
        return

    written = []
    try:
        for row, _original, updated, total in plans:
            if total == 0:
                continue
            dat_path = row["dat_path"]
            bak_path = backup_path(dat_path)
            shutil.copy2(dat_path, bak_path)
            with open(dat_path, "wb") as handle:
                handle.write(updated)
            written.append((row, total, bak_path))
    except OSError as exc:
        messagebox.showerror(
            "Apply Failed",
            f"An error occurred while writing files:\n{exc}\n\n"
            "Backups created before the error remain available.",
        )
        status_label.config(text="Status: Apply failed")
        update_restore_button()
        return

    lines = [
        f"Row {row['row']}: {count} replacement(s)\n  Backup: {bak_path}"
        for row, count, bak_path in written
    ]
    show_results("Changes Applied", lines)
    status_label.config(text=f"Status: Applied {total_changes} replacement(s)")
    invalidate_preview()
    update_restore_button()
    messagebox.showinfo("Complete", f"Applied {total_changes} replacement(s) successfully.")


def restore_backup():
    """Restore available .bak files for the populated DAT rows."""
    rows = get_rows()
    restorable = [
        row for row in rows if os.path.isfile(backup_path(row["dat_path"]))
    ]

    if not restorable:
        messagebox.showinfo("Restore Backup", "No backups were found for the selected DAT files.")
        update_restore_button()
        return

    if not messagebox.askyesno(
        "Restore Backup",
        f"Restore {len(restorable)} DAT file(s) from their .bak backups?\n\n"
        "The current DAT file contents will be overwritten.",
    ):
        return

    restored = []
    try:
        for row in restorable:
            bak_path = backup_path(row["dat_path"])
            shutil.copy2(bak_path, row["dat_path"])
            restored.append(row)
    except OSError as exc:
        messagebox.showerror("Restore Failed", str(exc))
        status_label.config(text="Status: Restore failed")
        return

    show_results(
        "Backups Restored",
        [f"Row {row['row']}: {row['dat_path']}" for row in restored],
    )
    status_label.config(text=f"Status: Restored {len(restored)} file(s)")
    invalidate_preview()
    update_restore_button()
    messagebox.showinfo("Restore Complete", f"Restored {len(restored)} file(s).")


# =========================================================
# Main window
# =========================================================

window = tk.Tk()
window.title("DAT Path Replacement Tool")
window.geometry("1050x760")
window.minsize(900, 650)

# Use a grid so the result area expands with the window.
window.columnconfigure(0, weight=1)
window.rowconfigure(2, weight=1)

title_label = tk.Label(
    window, text="DAT Path Replacement Tool", font=("Segoe UI", 18, "bold")
)
title_label.grid(row=0, column=0, pady=(18, 10))

input_frame = tk.LabelFrame(
    window,
    text="DAT files and path replacements (unused rows may be left blank)",
    font=("Segoe UI", 10, "bold"),
    padx=12,
    pady=10,
)
input_frame.grid(row=1, column=0, sticky="ew", padx=25, pady=5)
input_frame.columnconfigure(1, weight=1)

for row_index in range(ROW_COUNT):
    base_row = row_index * 3
    set_number = row_index + 1

    tk.Label(
        input_frame, text=f"DAT File {set_number}:", font=("Segoe UI", 9, "bold")
    ).grid(row=base_row, column=0, sticky="w", padx=(0, 8), pady=(7, 2))

    file_entry = tk.Entry(input_frame, font=("Segoe UI", 9))
    file_entry.grid(row=base_row, column=1, sticky="ew", pady=(7, 2))
    file_entries.append(file_entry)

    browse_button = tk.Button(
        input_frame,
        text="Browse",
        width=11,
        command=lambda entry=file_entry: browse_file(entry),
    )
    browse_button.grid(row=base_row, column=2, padx=(8, 0), pady=(7, 2))

    tk.Label(input_frame, text="Path to Find:").grid(
        row=base_row + 1, column=0, sticky="w", padx=(0, 8), pady=2
    )
    find_entry = tk.Entry(input_frame, font=("Consolas", 9))
    find_entry.grid(row=base_row + 1, column=1, columnspan=2, sticky="ew", pady=2)
    find_entries.append(find_entry)

    tk.Label(input_frame, text="Replace With:").grid(
        row=base_row + 2, column=0, sticky="w", padx=(0, 8), pady=(2, 7)
    )
    replace_entry = tk.Entry(input_frame, font=("Consolas", 9))
    replace_entry.grid(
        row=base_row + 2, column=1, columnspan=2, sticky="ew", pady=(2, 7)
    )
    replace_entries.append(replace_entry)

    for entry in (file_entry, find_entry, replace_entry):
        entry.bind("<KeyRelease>", invalidate_preview)
    file_entry.bind("<KeyRelease>", update_restore_button, add="+")

result_text = ScrolledText(window, height=12, font=("Consolas", 9), wrap="word")
result_text.grid(row=2, column=0, sticky="nsew", padx=25, pady=(10, 5))
result_text.insert(tk.END, "Ready. Add one to three DAT files, then scan or preview changes.")
result_text.config(state="disabled")

button_frame = tk.Frame(window)
button_frame.grid(row=3, column=0, pady=12)

scan_button = tk.Button(
    button_frame, text="Scan Files", width=18, height=2, command=scan_file
)
scan_button.pack(side="left", padx=5)

preview_button = tk.Button(
    button_frame, text="Preview Changes", width=18, height=2, command=preview_changes
)
preview_button.pack(side="left", padx=5)

apply_button = tk.Button(
    button_frame,
    text="Apply Changes",
    width=18,
    height=2,
    command=apply_changes,
    state="disabled",
)
apply_button.pack(side="left", padx=5)

restore_button = tk.Button(
    button_frame,
    text="Restore Backups",
    width=18,
    height=2,
    command=restore_backup,
    state="disabled",
)
restore_button.pack(side="left", padx=5)

status_label = tk.Label(window, text="Status: Ready", font=("Segoe UI", 10))
status_label.grid(row=4, column=0, pady=3)

dedication_label = tk.Label(
    window, text="Dedicated this tool to Chris Lane / LTS Team", font=("Segoe UI", 7)
)
dedication_label.grid(row=5, column=0, pady=(0, 5))

update_restore_button()
window.mainloop()
