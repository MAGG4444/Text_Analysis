import math
import struct
import zlib
from pathlib import Path
from typing import Dict, List, Tuple

from utils import ensure_directory


Color = Tuple[int, int, int]
PALETTE: List[Color] = [
    (29, 111, 140),
    (208, 88, 58),
    (88, 163, 92),
    (145, 94, 181),
    (217, 161, 51),
    (75, 75, 75),
]

FONT_3X5 = {
    " ": ["000", "000", "000", "000", "000"],
    "-": ["000", "000", "111", "000", "000"],
    "'": ["010", "010", "000", "000", "000"],
    ".": ["000", "000", "000", "000", "010"],
    "?": ["111", "001", "010", "000", "010"],
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    "A": ["010", "101", "111", "101", "101"],
    "B": ["110", "101", "110", "101", "110"],
    "C": ["011", "100", "100", "100", "011"],
    "D": ["110", "101", "101", "101", "110"],
    "E": ["111", "100", "110", "100", "111"],
    "F": ["111", "100", "110", "100", "100"],
    "G": ["011", "100", "101", "101", "011"],
    "H": ["101", "101", "111", "101", "101"],
    "I": ["111", "010", "010", "010", "111"],
    "J": ["001", "001", "001", "101", "010"],
    "K": ["101", "101", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101"],
    "N": ["101", "111", "111", "111", "101"],
    "O": ["111", "101", "101", "101", "111"],
    "P": ["111", "101", "111", "100", "100"],
    "Q": ["111", "101", "101", "111", "001"],
    "R": ["110", "101", "110", "101", "101"],
    "S": ["011", "100", "111", "001", "110"],
    "T": ["111", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "010"],
    "W": ["101", "101", "111", "111", "101"],
    "X": ["101", "101", "010", "101", "101"],
    "Y": ["101", "101", "010", "010", "010"],
    "Z": ["111", "001", "010", "100", "111"],
}


class SimplePNGCanvas:
    """Small PNG canvas used when matplotlib is unavailable."""

    def __init__(self, width: int, height: int, background: Color = (255, 255, 255)) -> None:
        self.width = width
        self.height = height
        self._pixels = bytearray(background) * (width * height)

    def _offset(self, x: int, y: int) -> int:
        return (y * self.width + x) * 3

    def set_pixel(self, x: int, y: int, color: Color) -> None:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        offset = self._offset(x, y)
        self._pixels[offset : offset + 3] = bytes(color)

    def draw_line(self, x1: int, y1: int, x2: int, y2: int, color: Color, thickness: int = 1) -> None:
        steps = max(abs(x2 - x1), abs(y2 - y1), 1)
        for step in range(steps + 1):
            ratio = step / steps
            x = int(round(x1 + (x2 - x1) * ratio))
            y = int(round(y1 + (y2 - y1) * ratio))
            radius = max(0, thickness - 1)
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    self.set_pixel(x + dx, y + dy, color)

    def draw_circle(self, cx: int, cy: int, radius: int, color: Color) -> None:
        radius_squared = radius * radius
        for x in range(cx - radius, cx + radius + 1):
            for y in range(cy - radius, cy + radius + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius_squared:
                    self.set_pixel(x, y, color)

    def draw_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: Color,
        fill: bool = False,
        thickness: int = 1,
    ) -> None:
        if fill:
            for draw_x in range(x, x + width):
                for draw_y in range(y, y + height):
                    self.set_pixel(draw_x, draw_y, color)
            return

        self.draw_line(x, y, x + width, y, color, thickness=thickness)
        self.draw_line(x, y, x, y + height, color, thickness=thickness)
        self.draw_line(x + width, y, x + width, y + height, color, thickness=thickness)
        self.draw_line(x, y + height, x + width, y + height, color, thickness=thickness)

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        color: Color = (0, 0, 0),
        scale: int = 2,
    ) -> None:
        cursor_x = x
        for character in text.upper():
            glyph = FONT_3X5.get(character, FONT_3X5["?"])
            for row_index, row in enumerate(glyph):
                for col_index, bit in enumerate(row):
                    if bit != "1":
                        continue
                    pixel_x = cursor_x + col_index * scale
                    pixel_y = y + row_index * scale
                    self.draw_rect(pixel_x, pixel_y, scale - 1, scale - 1, color, fill=True)
            cursor_x += (len(glyph[0]) + 1) * scale

    def save(self, output_path: str | Path) -> Path:
        destination = Path(output_path)
        ensure_directory(destination.parent)

        raw_rows = []
        row_stride = self.width * 3
        for y in range(self.height):
            start = y * row_stride
            end = start + row_stride
            raw_rows.append(b"\x00" + bytes(self._pixels[start:end]))
        compressed_data = zlib.compress(b"".join(raw_rows), level=9)

        def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
            crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        png_bytes = b"".join(
            [
                b"\x89PNG\r\n\x1a\n",
                png_chunk(b"IHDR", ihdr),
                png_chunk(b"IDAT", compressed_data),
                png_chunk(b"IEND", b""),
            ]
        )
        destination.write_bytes(png_bytes)
        return destination


def _plot_overall_with_matplotlib(
    trajectory: List[Dict[str, float | int]],
    output_path: Path,
    use_smoothed_values: bool,
) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False

    plt.figure(figsize=(10, 5))
    plt.axhline(0, color="gray", linestyle="--", linewidth=1)

    if trajectory:
        x_values = [int(item["scene_id"]) for item in trajectory]
        y_values = [float(item["tone_score"]) for item in trajectory]
        plt.plot(x_values, y_values, marker="o", linewidth=2, color="#1d6f8c", label="Overall Tone")
        plt.legend(title="Lines")
    else:
        plt.text(0.5, 0.5, "No tone data available", ha="center", va="center", transform=plt.gca().transAxes)

    title = "Overall Tone Trajectory"
    if use_smoothed_values:
        title += " (Smoothed)"

    plt.title(title)
    plt.xlabel("Scene ID")
    plt.ylabel("Tone Score")
    plt.ylim(-1.05, 1.05)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return True


def _plot_characters_with_matplotlib(
    trajectories: Dict[str, List[Dict[str, str | float | int]]],
    output_path: Path,
    use_smoothed_values: bool,
) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False

    plt.figure(figsize=(11, 6))

    if trajectories:
        for character, points in sorted(trajectories.items()):
            if not points:
                continue
            x_values = [int(point["scene_id"]) for point in points]
            y_values = [float(point["emotion_score"]) for point in points]
            plt.plot(x_values, y_values, marker="o", linewidth=2, label=character)
        plt.legend(title="Lines")
    else:
        plt.text(
            0.5,
            0.5,
            "No character emotion data available",
            ha="center",
            va="center",
            transform=plt.gca().transAxes,
        )

    title = "Character Emotion Trajectories"
    if use_smoothed_values:
        title += " (Smoothed)"

    plt.title(title)
    plt.xlabel("Scene ID")
    plt.ylabel("Emotion Score")
    plt.ylim(0.0, 1.05)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return True


def _map_value(value: float, lower_bound: float, upper_bound: float, pixel_min: int, pixel_max: int) -> int:
    if math.isclose(upper_bound, lower_bound):
        return int((pixel_min + pixel_max) / 2)
    ratio = (value - lower_bound) / (upper_bound - lower_bound)
    return int(round(pixel_min + ratio * (pixel_max - pixel_min)))


def _plot_line_chart_fallback(
    series_map: Dict[str, List[Dict[str, str | float | int]]],
    score_key: str,
    output_path: Path,
    y_min: float,
    y_max: float,
    title: str,
) -> Path:
    canvas = SimplePNGCanvas(width=1000, height=600)

    left_margin = 70
    right_margin = 30
    legend_width = 220
    top_margin = 55
    bottom_margin = 60
    plot_left = left_margin
    plot_right = canvas.width - right_margin - legend_width
    plot_top = top_margin
    plot_bottom = canvas.height - bottom_margin

    canvas.draw_text(35, 18, title, scale=3)

    for grid_index in range(6):
        y = int(round(plot_top + (plot_bottom - plot_top) * grid_index / 5))
        canvas.draw_line(plot_left, y, plot_right, y, (230, 230, 230))

    canvas.draw_line(plot_left, plot_top, plot_left, plot_bottom, (0, 0, 0), thickness=2)
    canvas.draw_line(plot_left, plot_bottom, plot_right, plot_bottom, (0, 0, 0), thickness=2)

    all_points = [
        point
        for points in series_map.values()
        for point in points
    ]
    if not all_points:
        canvas.draw_text(390, 290, "NO DATA", scale=4)
        return canvas.save(output_path)

    min_scene = min(int(point["scene_id"]) for point in all_points)
    max_scene = max(int(point["scene_id"]) for point in all_points)
    if min_scene == max_scene:
        min_scene -= 1
        max_scene += 1

    legend_x = plot_right + 25
    legend_y = 70
    legend_entries = sorted(series_map.items())
    legend_height = max(55, len(legend_entries) * 36 + 28)
    canvas.draw_rect(legend_x - 10, legend_y - 18, 185, legend_height, (210, 210, 210), fill=True)
    canvas.draw_rect(legend_x - 10, legend_y - 18, 185, legend_height, (120, 120, 120), thickness=1)
    canvas.draw_text(legend_x, legend_y, "LEGEND", scale=2)

    for index, (series_name, points) in enumerate(legend_entries):
        if not points:
            continue

        color = PALETTE[index % len(PALETTE)]
        ordered_points = sorted(points, key=lambda point: int(point["scene_id"]))
        previous_coordinates = None

        entry_y = legend_y + 28 + index * 36
        canvas.draw_line(legend_x, entry_y, legend_x + 28, entry_y, color, thickness=2)
        canvas.draw_circle(legend_x + 14, entry_y, radius=4, color=color)
        canvas.draw_text(legend_x + 40, entry_y - 8, series_name[:18], scale=2)

        for point in ordered_points:
            x_value = int(point["scene_id"])
            y_value = float(point[score_key])
            x = _map_value(x_value, min_scene, max_scene, plot_left, plot_right)
            y = _map_value(y_value, y_min, y_max, plot_bottom, plot_top)

            if previous_coordinates is not None:
                canvas.draw_line(previous_coordinates[0], previous_coordinates[1], x, y, color, thickness=2)
            canvas.draw_circle(x, y, radius=4, color=color)
            previous_coordinates = (x, y)

    return canvas.save(output_path)


def plot_overall_tone_trajectory(
    trajectory: List[Dict[str, float | int]],
    output_path: str | Path,
    use_smoothed_values: bool = False,
) -> Path:
    """Save the overall tone trajectory plot to disk."""
    destination = Path(output_path)
    ensure_directory(destination.parent)

    if _plot_overall_with_matplotlib(trajectory, destination, use_smoothed_values):
        return destination

    series_map = {"Overall Tone": trajectory}
    return _plot_line_chart_fallback(
        series_map,
        "tone_score",
        destination,
        y_min=-1.0,
        y_max=1.0,
        title="Overall Tone",
    )


def plot_character_emotion_trajectories(
    trajectories: Dict[str, List[Dict[str, str | float | int]]],
    output_path: str | Path,
    use_smoothed_values: bool = False,
) -> Path:
    """Save the per-character emotion trajectory plot to disk."""
    destination = Path(output_path)
    ensure_directory(destination.parent)

    if _plot_characters_with_matplotlib(trajectories, destination, use_smoothed_values):
        return destination

    return _plot_line_chart_fallback(
        trajectories,
        "emotion_score",
        destination,
        y_min=0.0,
        y_max=1.0,
        title="Character Emotions",
    )
