import os
import sys
import csv
import time
import shutil
import hashlib
import ctypes

from pathlib import Path
from collections import defaultdict
from datetime import datetime


# ==========================================================
# CONFIGURATION
# ==========================================================

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".heic",
    ".heif"
}

CHUNK_SIZE = 1024 * 1024

# Set True to print the path of every scanned image.
VERBOSE_SCAN = True

# Set True to display hashing logs.
VERBOSE_HASH = True


# ==========================================================
# ENABLE TERMINAL COLORS ON WINDOWS
# ==========================================================

def enable_windows_colors():

    if os.name != "nt":
        return True

    try:

        kernel32 = ctypes.windll.kernel32

        handle = kernel32.GetStdHandle(-11)

        mode = ctypes.c_uint32()

        if not kernel32.GetConsoleMode(
            handle,
            ctypes.byref(mode)
        ):
            return False

        return bool(
            kernel32.SetConsoleMode(
                handle,
                mode.value | 0x0004
            )
        )

    except Exception:
        return False


COLORS_ENABLED = enable_windows_colors() and sys.stdout.isatty()


# ==========================================================
# TERMINAL COLORS
# ==========================================================

class Color:

    RESET = "\033[0m" if COLORS_ENABLED else ""

    RED = "\033[91m" if COLORS_ENABLED else ""

    GREEN = "\033[92m" if COLORS_ENABLED else ""

    YELLOW = "\033[93m" if COLORS_ENABLED else ""

    BLUE = "\033[94m" if COLORS_ENABLED else ""

    PURPLE = "\033[95m" if COLORS_ENABLED else ""

    CYAN = "\033[96m" if COLORS_ENABLED else ""

    WHITE = "\033[97m" if COLORS_ENABLED else ""

    BOLD = "\033[1m" if COLORS_ENABLED else ""

    DIM = "\033[2m" if COLORS_ENABLED else ""


# ==========================================================
# LOGGER
# ==========================================================

def log(message, color=Color.WHITE, level="INFO"):

    timestamp = datetime.now().strftime("%H:%M:%S")

    print(
        f"{Color.DIM}[{timestamp}]{Color.RESET} "
        f"{color}[{level}]{Color.RESET} "
        f"{message}",
        flush=True
    )


def info(message):

    log(message, Color.BLUE, "INFO")


def success(message):

    log(message, Color.GREEN, "SUCCESS")


def warning(message):

    log(message, Color.YELLOW, "WARNING")


def error(message):

    log(message, Color.RED, "ERROR")


def duplicate_log(message):

    log(message, Color.PURPLE, "DUPLICATE")


def scan_log(message):

    log(message, Color.CYAN, "SCAN")


def print_header(title):

    print()

    print(
        Color.CYAN
        + Color.BOLD
        + "=" * 80
        + Color.RESET
    )

    print(
        Color.PURPLE
        + Color.BOLD
        + title.center(80)
        + Color.RESET
    )

    print(
        Color.CYAN
        + Color.BOLD
        + "=" * 80
        + Color.RESET
    )

    print()


# ==========================================================
# PROGRESS BAR
# ==========================================================

def progress_bar(current, total, title="Progress"):

    if total == 0:
        return

    percentage = current / total

    width = 35

    filled = int(width * percentage)

    bar = (
        Color.GREEN
        + "█" * filled
        + Color.RESET
        + Color.DIM
        + "░" * (width - filled)
        + Color.RESET
    )

    print(
        f"\r{Color.CYAN}{title}: "
        f"{bar} "
        f"{percentage * 100:6.2f}% "
        f"({current}/{total})"
        f"{Color.RESET}",
        end="",
        flush=True
    )

    if current >= total:
        print()


# ==========================================================
# FORMAT FILE SIZE
# ==========================================================

def format_size(size):

    size = float(size)

    for unit in ["B", "KB", "MB", "GB", "TB"]:

        if size < 1024 or unit == "TB":

            return f"{size:.2f} {unit}"

        size /= 1024


# ==========================================================
# SHA-256 HASH
# ==========================================================

def calculate_hash(file_path):

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while True:

            chunk = file.read(CHUNK_SIZE)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


# ==========================================================
# SCAN IMAGE FILES
# ==========================================================

def scan_images(root_folder, destination):

    print_header("PHASE 1: SCANNING PHOTO FOLDERS")

    files_by_size = defaultdict(list)

    total_scanned = 0

    skipped = 0

    folders_scanned = 0

    total_image_size = 0

    scan_log(
        f"Starting recursive scan: {root_folder}"
    )

    scan_log(
        f"Excluded destination: {destination}"
    )

    for current_folder, folders, files in os.walk(
        root_folder
    ):

        current_folder = Path(current_folder)

        # Never scan the moved folder.
        folders[:] = sorted(
            [
                folder
                for folder in folders
                if (
                    current_folder / folder
                ).resolve() != destination
                and not (
                    current_folder / folder
                ).is_symlink()
            ],
            key=str.lower
        )

        folders_scanned += 1

        scan_log(
            f"Opening folder: {current_folder}"
        )

        folder_image_count = 0

        for filename in sorted(files, key=str.lower):

            file_path = current_folder / filename

            if (
                file_path.suffix.lower()
                not in IMAGE_EXTENSIONS
            ):
                continue

            if file_path.is_symlink():
                warning(
                    f"Skipping symbolic link: {file_path}"
                )
                skipped += 1
                continue

            try:

                file_size = file_path.stat().st_size

                files_by_size[file_size].append(
                    file_path
                )

                total_scanned += 1

                folder_image_count += 1

                total_image_size += file_size

                if VERBOSE_SCAN:

                    scan_log(
                        f"Found: {file_path.name} "
                        f"| {format_size(file_size)}"
                    )

            except OSError as exception:

                skipped += 1

                error(
                    f"Cannot access {file_path}: "
                    f"{exception}"
                )

        info(
            f"Folder complete | "
            f"{folder_image_count} image(s)"
        )

    print_header("SCAN SUMMARY")

    success(
        f"Folders scanned: {folders_scanned}"
    )

    success(
        f"Photos discovered: {total_scanned}"
    )

    info(
        "Combined photo size: "
        f"{format_size(total_image_size)}"
    )

    warning(
        f"Files skipped: {skipped}"
    )

    return (
        files_by_size,
        total_scanned,
        skipped,
        folders_scanned
    )


# ==========================================================
# IDENTIFY DUPLICATES
# ==========================================================

def find_duplicates(files_by_size):

    print_header("PHASE 2: DETECTING DUPLICATES")

    hashes = defaultdict(list)

    skipped = 0

    # Only hash files that share the same file size.
    candidate_groups = {
        size: paths
        for size, paths in files_by_size.items()
        if len(paths) > 1
    }

    total_candidates = sum(
        len(paths)
        for paths in candidate_groups.values()
    )

    info(
        f"Files requiring SHA-256: "
        f"{total_candidates}"
    )

    checked = 0

    for size, paths in candidate_groups.items():

        info(
            f"Checking size group: "
            f"{format_size(size)} "
            f"({len(paths)} files)"
        )

        for file_path in paths:

            try:

                file_hash = calculate_hash(
                    file_path
                )

                hashes[
                    (size, file_hash)
                ].append(file_path)

                if VERBOSE_HASH:

                    scan_log(
                        f"Hashed: {file_path.name} "
                        f"| SHA-256: "
                        f"{file_hash[:16]}..."
                    )

            except OSError as exception:

                skipped += 1

                error(
                    f"Hash failed: {file_path} "
                    f"| {exception}"
                )

            checked += 1

            progress_bar(
                checked,
                total_candidates,
                "Hashing"
            )

    duplicates = [
        paths
        for paths in hashes.values()
        if len(paths) > 1
    ]

    print_header("DUPLICATE ANALYSIS")

    duplicate_count = sum(
        len(paths) - 1
        for paths in duplicates
    )

    duplicate_size = sum(
        size * (len(paths) - 1)
        for (size, file_hash), paths in hashes.items()
        if len(paths) > 1
    )

    success(
        f"Duplicate groups: {len(duplicates)}"
    )

    duplicate_log(
        f"Extra duplicate copies: "
        f"{duplicate_count}"
    )

    duplicate_log(
        f"Total duplicate size: "
        f"{format_size(duplicate_size)}"
    )

    return duplicates, skipped


# ==========================================================
# PRINT DUPLICATE GROUP DETAILS
# ==========================================================

def show_duplicate_groups(duplicates):

    print_header("PHASE 3: DUPLICATE GROUP DETAILS")

    for group_number, paths in enumerate(
        duplicates,
        start=1
    ):

        original_file = paths[0]

        try:

            file_size = original_file.stat().st_size

        except OSError:

            file_size = 0

        group_size = file_size * (
            len(paths) - 1
        )

        print(
            f"\n{Color.PURPLE}"
            f"{Color.BOLD}"
            f"GROUP {group_number}"
            f"{Color.RESET}"
        )

        print(
            Color.PURPLE
            + "-" * 70
            + Color.RESET
        )

        success(
            f"KEEPING: {original_file}"
        )

        for duplicate_file in paths[1:]:

            duplicate_log(
                f"MOVE: {duplicate_file}"
            )

        info(
            f"Extra copies: {len(paths) - 1}"
        )

        info(
            f"Individual file size: "
            f"{format_size(file_size)}"
        )

        duplicate_log(
            f"Group duplicate size: "
            f"{format_size(group_size)}"
        )


# ==========================================================
# GENERATE UNIQUE DESTINATION
# ==========================================================

def get_unique_destination(folder, filename):

    target = folder / filename

    if not target.exists():
        return target

    original = Path(filename)

    counter = 1

    while True:

        new_name = (
            f"{original.stem}_duplicate_{counter}"
            f"{original.suffix}"
        )

        target = folder / new_name

        if not target.exists():
            return target

        counter += 1


# ==========================================================
# MOVE DUPLICATE FILES
# ==========================================================

def move_duplicates(
    duplicates,
    root_folder,
    destination,
    report_path
):

    print_header("PHASE 4: MOVING DUPLICATE PHOTOS")

    moved_count = 0

    moved_size = 0

    failed_count = 0

    report_data = []

    total_to_move = sum(
        len(paths) - 1
        for paths in duplicates
    )

    processed = 0

    for group_number, paths in enumerate(
        duplicates,
        start=1
    ):

        original_file = paths[0]

        info(
            f"Processing duplicate group "
            f"{group_number}/{len(duplicates)}"
        )

        success(
            f"Retaining original: "
            f"{original_file}"
        )

        for duplicate_file in paths[1:]:

            try:

                info(
                    f"Preparing: {duplicate_file}"
                )

                original_size = (
                    original_file.stat().st_size
                )

                duplicate_size = (
                    duplicate_file.stat().st_size
                )

                # Verify identical content again.
                if original_size != duplicate_size:

                    warning(
                        f"Size changed: {duplicate_file}"
                    )

                    failed_count += 1

                    continue

                if (
                    calculate_hash(original_file)
                    != calculate_hash(duplicate_file)
                ):

                    warning(
                        f"Content changed: "
                        f"{duplicate_file}"
                    )

                    failed_count += 1

                    continue

                # Preserve original folder structure.
                relative_path = (
                    duplicate_file.relative_to(
                        root_folder
                    )
                )

                target_folder = (
                    destination
                    / relative_path.parent
                )

                target_folder.mkdir(
                    parents=True,
                    exist_ok=True
                )

                target = get_unique_destination(
                    target_folder,
                    duplicate_file.name
                )

                info(
                    f"Destination: {target}"
                )

                # Move duplicate.
                shutil.move(
                    str(duplicate_file),
                    str(target)
                )

                moved_count += 1

                moved_size += duplicate_size

                success(
                    f"MOVED: {duplicate_file.name}"
                )

                success(
                    f"Size: "
                    f"{format_size(duplicate_size)}"
                )

                report_data.append({

                    "Group": group_number,

                    "Original Photo": str(
                        original_file
                    ),

                    "Duplicate Original Location": str(
                        duplicate_file
                    ),

                    "Moved To": str(target),

                    "Size Bytes": duplicate_size,

                    "Size MB": round(
                        duplicate_size / (1024 * 1024),
                        3
                    )

                })

            except OSError as exception:

                failed_count += 1

                error(
                    f"Move failed: {duplicate_file}"
                )

                error(str(exception))

            finally:

                processed += 1

                progress_bar(
                    processed,
                    total_to_move,
                    "Moving"
                )

    # Save CSV report.
    with open(
        report_path,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as csvfile:

        fieldnames = [
            "Group",
            "Original Photo",
            "Duplicate Original Location",
            "Moved To",
            "Size Bytes",
            "Size MB"
        ]

        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(report_data)

    success(
        f"CSV report generated: "
        f"{report_path}"
    )

    return (
        moved_count,
        moved_size,
        failed_count
    )


# ==========================================================
# MAIN PROGRAM
# ==========================================================

def main():

    start_time = time.perf_counter()

    print_header(
        "DUPLICATE PHOTO FINDER & ORGANIZER"
    )

    info("Python duplicate photo utility")

    info("Duplicate detection: SHA-256")

    info("Folder structure preservation: ON")

    info("Automatic deletion: OFF")

    root_input = input(
        f"\n{Color.YELLOW}"
        f"Enter your main photo folder: "
        f"{Color.RESET}"
    ).strip().strip('"').strip("'")

    if not root_input:

        error("No folder path was provided.")

        return

    root_folder = Path(
        root_input
    ).expanduser().resolve()

    if not root_folder.is_dir():

        error(
            f"Invalid folder: {root_folder}"
        )

        return

    # Destination is always inside the root.
    destination = root_folder / "moved"

    info(
        f"Source: {root_folder}"
    )

    info(
        f"Duplicate destination: {destination}"
    )

    # Scan.
    (
        files_by_size,
        scanned,
        scan_skipped,
        folders_scanned
    ) = scan_images(
        root_folder,
        destination
    )

    # Identify duplicates.
    (
        duplicates,
        hash_skipped
    ) = find_duplicates(
        files_by_size
    )

    if not duplicates:

        print_header("SCAN COMPLETE")

        success(
            "No exact duplicate photos found!"
        )

        info(
            f"Photos scanned: {scanned}"
        )

        info(
            f"Folders scanned: {folders_scanned}"
        )

        return

    # Display details.
    show_duplicate_groups(
        duplicates
    )

    duplicate_count = sum(
        len(paths) - 1
        for paths in duplicates
    )

    duplicate_size = 0

    for paths in duplicates:

        for file_path in paths[1:]:

            try:

                duplicate_size += (
                    file_path.stat().st_size
                )

            except OSError:
                pass

    print_header("PRE-MOVE SUMMARY")

    info(
        f"Photos scanned: {scanned}"
    )

    info(
        f"Folders scanned: {folders_scanned}"
    )

    duplicate_log(
        f"Duplicate groups: {len(duplicates)}"
    )

    duplicate_log(
        f"Files to move: {duplicate_count}"
    )

    duplicate_log(
        f"Total duplicate size: "
        f"{format_size(duplicate_size)}"
    )

    warning(
        f"Skipped files: "
        f"{scan_skipped + hash_skipped}"
    )

    warning(
        "One copy from each duplicate group "
        "will remain in its original folder."
    )

    warning(
        "All remaining copies will be moved "
        "into the moved folder."
    )

    # Confirmation.
    confirmation = input(
        f"\n{Color.YELLOW}"
        f"{Color.BOLD}"
        f"Type YES to begin moving duplicates: "
        f"{Color.RESET}"
    ).strip()

    if confirmation != "YES":

        warning(
            "Operation cancelled. "
            "No files were moved."
        )

        return

    destination.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    report_path = destination / (
        f"duplicate_report_{timestamp}.csv"
    )

    # Move duplicates.
    (
        moved_count,
        moved_size,
        failed_count
    ) = move_duplicates(
        duplicates,
        root_folder,
        destination,
        report_path
    )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    # Final summary.
    print_header("FINAL EXECUTION SUMMARY")

    success(
        f"Total photos scanned: {scanned}"
    )

    success(
        f"Folders scanned: {folders_scanned}"
    )

    duplicate_log(
        f"Duplicate groups: {len(duplicates)}"
    )

    success(
        f"Successfully moved: {moved_count}"
    )

    if failed_count:

        error(
            f"Failed moves: {failed_count}"
        )

    else:

        success(
            "Failed moves: 0"
        )

    success(
        f"Total size moved: "
        f"{format_size(moved_size)}"
    )

    info(
        f"Execution time: {elapsed:.2f} seconds"
    )

    print()

    success(
        f"Duplicate folder:\n{destination}"
    )

    success(
        f"CSV report:\n{report_path}"
    )

    print_header("PROCESS COMPLETED")


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()

        warning(
            "Operation interrupted by user."
        )

        warning(
            "Previously completed file moves "
            "have not been reversed."
        )

        sys.exit(130)