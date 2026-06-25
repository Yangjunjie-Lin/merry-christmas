#!/usr/bin/env python3
"""
Aurora Christmas Tree.

A polished Tkinter desktop app that renders a dense, animated Christmas tree
from thousands of tiny moving particles.
"""
from __future__ import annotations

import argparse
import math
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont


tk = None
filedialog = None
simpledialog = None
ImageTk = None


def load_tkinter() -> None:
    global tk, filedialog, simpledialog, ImageTk
    if tk is not None:
        return

    import tkinter as tk_module
    from tkinter import filedialog as filedialog_module
    from tkinter import simpledialog as simpledialog_module
    from PIL import ImageTk as image_tk_module

    tk = tk_module
    filedialog = filedialog_module
    simpledialog = simpledialog_module
    ImageTk = image_tk_module


THEMES = {
    "aurora": {
        "name": "Aurora",
        "bg_top": "#020713",
        "bg_mid": "#071827",
        "bg_bottom": "#13091f",
        "mist_a": "#00e5ff",
        "mist_b": "#b36bff",
        "leaf_shadow": "#05391f",
        "leaf_mid": "#13b86a",
        "leaf_light": "#7dffb2",
        "gold": "#ffd166",
        "rose": "#ff5fa2",
        "cyan": "#5de7ff",
        "violet": "#b892ff",
        "snow": "#f5fbff",
    },
    "ruby": {
        "name": "Ruby",
        "bg_top": "#12040d",
        "bg_mid": "#260a1b",
        "bg_bottom": "#070918",
        "mist_a": "#ff4d8d",
        "mist_b": "#ffcf6e",
        "leaf_shadow": "#07361f",
        "leaf_mid": "#1cc46d",
        "leaf_light": "#95ffb8",
        "gold": "#ffe08a",
        "rose": "#ff6e8a",
        "cyan": "#79e5ff",
        "violet": "#e09cff",
        "snow": "#fff8f1",
    },
    "frost": {
        "name": "Frost",
        "bg_top": "#03101a",
        "bg_mid": "#082b38",
        "bg_bottom": "#10162c",
        "mist_a": "#5df4ff",
        "mist_b": "#9fb7ff",
        "leaf_shadow": "#074039",
        "leaf_mid": "#12bfa5",
        "leaf_light": "#8fffe8",
        "gold": "#fff0aa",
        "rose": "#ff8fc7",
        "cyan": "#68e8ff",
        "violet": "#9fa8ff",
        "snow": "#f8ffff",
    },
}


@dataclass(frozen=True)
class TreeParticle:
    theta: float
    level: float
    radius: float
    size: float
    color: str
    role: str
    phase: float
    spin: float
    orbit: float
    depth: float


@dataclass(frozen=True)
class SnowParticle:
    x: float
    y: float
    size: float
    speed: float
    drift: float
    phase: float
    alpha: int


@dataclass(frozen=True)
class StarParticle:
    x: float
    y: float
    z: float
    size: float
    color: str
    phase: float


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: Iterable[float]) -> str:
    channels = [max(0, min(255, int(channel))) for channel in rgb]
    return "#{:02x}{:02x}{:02x}".format(*channels)


def blend(left: str, right: str, amount: float) -> str:
    a = hex_to_rgb(left)
    b = hex_to_rgb(right)
    t = clamp(amount)
    return rgb_to_hex(a[index] * (1 - t) + b[index] * t for index in range(3))


def brighten(color: str, factor: float) -> str:
    r, g, b = hex_to_rgb(color)
    return rgb_to_hex((r * factor, g * factor, b * factor))


def rgba(color: str, alpha: int) -> tuple[int, int, int, int]:
    return (*hex_to_rgb(color), max(0, min(255, int(alpha))))


def ease_out(value: float) -> float:
    value = clamp(value)
    return 1 - (1 - value) ** 3


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


class ParticleTreeScene:
    """Headless Pillow renderer shared by the GUI and preview command."""

    def __init__(
        self,
        width: int,
        height: int,
        name: str,
        theme: str = "aurora",
        density: float = 1.0,
        seed: int | None = None,
    ) -> None:
        self.width = max(720, int(width))
        self.height = max(560, int(height))
        self.name = name.strip() or "Friend"
        self.theme_name = theme if theme in THEMES else "aurora"
        self.theme = THEMES[self.theme_name]
        self.density = clamp(density, 0.55, 1.65)
        self.seed = random.randrange(1_000_000) if seed is None else seed
        self.rng = random.Random(self.seed)
        self.rotation_offset = 0.0
        self.tree_particles: list[TreeParticle] = []
        self.snow_particles: list[SnowParticle] = []
        self.star_particles: list[StarParticle] = []
        self.background = Image.new("RGBA", (self.width, self.height))
        self._build()

    def rebuild(self, width: int, height: int, density: float | None = None) -> None:
        self.width = max(720, int(width))
        self.height = max(560, int(height))
        if density is not None:
            self.density = clamp(density, 0.55, 1.65)
        self.rng = random.Random(self.seed)
        self._build()

    def set_theme(self, theme: str) -> None:
        self.theme_name = theme if theme in THEMES else "aurora"
        self.theme = THEMES[self.theme_name]
        self.rng = random.Random(self.seed)
        self._build()

    def reseed(self) -> None:
        self.seed = random.randrange(1_000_000)
        self.rng = random.Random(self.seed)
        self._build()

    def rotate_by(self, delta: float) -> None:
        self.rotation_offset += delta

    def _build(self) -> None:
        self.tree_particles = []
        self.snow_particles = []
        self.star_particles = []
        self.background = self._create_background()
        self._create_tree()
        self._create_snow()

    def _create_background(self) -> Image.Image:
        image = Image.new("RGBA", (self.width, self.height), self.theme["bg_top"])
        draw = ImageDraw.Draw(image, "RGBA")

        for y in range(self.height):
            t = y / max(1, self.height - 1)
            if t < 0.55:
                color = blend(self.theme["bg_top"], self.theme["bg_mid"], t / 0.55)
            else:
                color = blend(self.theme["bg_mid"], self.theme["bg_bottom"], (t - 0.55) / 0.45)
            draw.line([(0, y), (self.width, y)], fill=color)

        self._draw_nebula(image)
        self._draw_background_stars(image)
        self._draw_ground_haze(image)
        return image

    def _draw_nebula(self, image: Image.Image) -> None:
        layer = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")
        for band, color in enumerate((self.theme["mist_a"], self.theme["mist_b"], self.theme["gold"])):
            points = []
            base_y = self.height * (0.13 + band * 0.055)
            amplitude = self.height * (0.025 + band * 0.009)
            for x in range(-80, self.width + 100, 28):
                y = base_y + math.sin(x * 0.010 + band * 1.85) * amplitude
                points.append((x, y))
            for offset in range(16):
                shifted = [(x, y + offset * 5) for x, y in points]
                draw.line(
                    shifted,
                    fill=rgba(color, max(0, 34 - offset * 2)),
                    width=max(1, 8 - offset // 2),
                    joint="curve",
                )
        image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(3)))

    def _draw_background_stars(self, image: Image.Image) -> None:
        draw = ImageDraw.Draw(image, "RGBA")
        moon_x = self.width * 0.82
        moon_y = self.height * 0.14
        moon_radius = max(18, self.width * 0.023)
        glow = self._glow((moon_x, moon_y), "#fff4cc", int(moon_radius * 4.2), 72, 22)
        image.alpha_composite(glow)
        draw.ellipse(
            [moon_x - moon_radius, moon_y - moon_radius, moon_x + moon_radius, moon_y + moon_radius],
            fill=rgba("#fff7d4", 230),
        )
        draw.ellipse(
            [
                moon_x - moon_radius * 0.2,
                moon_y - moon_radius * 1.05,
                moon_x + moon_radius * 1.08,
                moon_y + moon_radius * 0.55,
            ],
            fill=rgba(self.theme["bg_mid"], 230),
        )

        for _ in range(145):
            x = self.rng.uniform(12, self.width - 12)
            y = self.rng.uniform(12, self.height * 0.58)
            radius = self.rng.uniform(0.45, 1.45)
            alpha = self.rng.randint(70, 190)
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=rgba("#ffffff", alpha))

    def _draw_ground_haze(self, image: Image.Image) -> None:
        draw = ImageDraw.Draw(image, "RGBA")
        y = self.height * 0.895
        points = [(0, self.height), (0, y)]
        for x in range(0, self.width + 80, 70):
            wave = math.sin(x / self.width * math.tau * 1.45) * self.height * 0.012
            points.append((x, y + wave))
        points.extend([(self.width, self.height), (0, self.height)])
        draw.polygon(points, fill=rgba("#071523", 185))
        draw.line(points[1:-2], fill=rgba(self.theme["mist_a"], 42), width=2)

    def _create_tree(self) -> None:
        leaf_count = int(4700 * self.density)
        light_count = int(760 * self.density)
        ornament_count = int(180 * self.density)
        dust_count = int(520 * self.density)
        trunk_count = int(240 * self.density)

        for _ in range(leaf_count):
            level = self.rng.random() ** 0.58
            cone_radius = 1.95 * (level ** 0.86)
            theta = self.rng.random() * math.tau
            radius = cone_radius * self.rng.uniform(0.36, 1.02)
            color_mix = self.rng.random()
            if color_mix < 0.46:
                color = blend(self.theme["leaf_shadow"], self.theme["leaf_mid"], self.rng.uniform(0.25, 0.85))
            else:
                color = blend(self.theme["leaf_mid"], self.theme["leaf_light"], self.rng.uniform(0.18, 0.82))
            self.tree_particles.append(
                TreeParticle(
                    theta=theta,
                    level=level,
                    radius=radius,
                    size=self.rng.uniform(0.75, 1.9),
                    color=color,
                    role="leaf",
                    phase=self.rng.random() * math.tau,
                    spin=self.rng.uniform(-0.012, 0.018),
                    orbit=self.rng.uniform(0.004, 0.030),
                    depth=self.rng.uniform(0.78, 1.25),
                )
            )

        for spiral in range(5):
            turns = self.rng.uniform(2.15, 3.35)
            phase = self.rng.random() * math.tau
            color = [self.theme["gold"], self.theme["cyan"], self.theme["rose"], self.theme["violet"], "#ffffff"][spiral]
            for index in range(max(1, light_count // 5)):
                level = (index + self.rng.random()) / max(1, light_count // 5)
                cone_radius = 1.95 * (level ** 0.86)
                theta = phase + level * math.tau * turns
                radius = cone_radius * self.rng.uniform(0.90, 1.04)
                self.tree_particles.append(
                    TreeParticle(
                        theta=theta,
                        level=level,
                        radius=radius,
                        size=self.rng.uniform(1.35, 2.65),
                        color=color,
                        role="light",
                        phase=self.rng.random() * math.tau,
                        spin=self.rng.uniform(0.0, 0.012),
                        orbit=self.rng.uniform(0.010, 0.045),
                        depth=self.rng.uniform(0.92, 1.35),
                    )
                )

        ornament_palette = [self.theme["gold"], self.theme["rose"], self.theme["cyan"], self.theme["violet"], "#ff6961"]
        for _ in range(ornament_count):
            level = self.rng.uniform(0.22, 0.98)
            theta = self.rng.random() * math.tau
            radius = 1.95 * (level ** 0.86) * self.rng.uniform(0.70, 1.02)
            self.tree_particles.append(
                TreeParticle(
                    theta=theta,
                    level=level,
                    radius=radius,
                    size=self.rng.uniform(2.0, 3.65),
                    color=self.rng.choice(ornament_palette),
                    role="ornament",
                    phase=self.rng.random() * math.tau,
                    spin=self.rng.uniform(-0.01, 0.012),
                    orbit=self.rng.uniform(0.004, 0.020),
                    depth=self.rng.uniform(0.92, 1.28),
                )
            )

        for _ in range(dust_count):
            level = self.rng.random()
            theta = self.rng.random() * math.tau
            radius = 1.95 * (level ** 0.86) * self.rng.uniform(1.05, 1.32)
            self.tree_particles.append(
                TreeParticle(
                    theta=theta,
                    level=level,
                    radius=radius,
                    size=self.rng.uniform(0.55, 1.25),
                    color=self.rng.choice([self.theme["gold"], self.theme["cyan"], "#ffffff"]),
                    role="spark",
                    phase=self.rng.random() * math.tau,
                    spin=self.rng.uniform(-0.018, 0.024),
                    orbit=self.rng.uniform(0.030, 0.095),
                    depth=self.rng.uniform(0.7, 1.45),
                )
            )

        for _ in range(trunk_count):
            level = self.rng.uniform(1.005, 1.12)
            theta = self.rng.random() * math.tau
            radius = self.rng.uniform(0.05, 0.23)
            self.tree_particles.append(
                TreeParticle(
                    theta=theta,
                    level=level,
                    radius=radius,
                    size=self.rng.uniform(1.4, 2.4),
                    color=blend("#6b3519", "#d08a45", self.rng.random()),
                    role="trunk",
                    phase=self.rng.random() * math.tau,
                    spin=0.0,
                    orbit=self.rng.uniform(0.001, 0.008),
                    depth=self.rng.uniform(0.9, 1.15),
                )
            )

        star_palette = [self.theme["gold"], "#fff8d6", "#ffffff"]
        for i in range(155):
            angle = i / 155 * math.tau
            arm = 1.0 if i % 2 == 0 else 0.46
            distance = self.rng.uniform(0.0, 0.22) + arm * self.rng.uniform(0.08, 0.22)
            self.star_particles.append(
                StarParticle(
                    x=math.cos(angle) * distance,
                    y=math.sin(angle) * distance * 0.92,
                    z=self.rng.uniform(-0.08, 0.08),
                    size=self.rng.uniform(1.4, 3.1),
                    color=self.rng.choice(star_palette),
                    phase=self.rng.random() * math.tau,
                )
            )

    def _create_snow(self) -> None:
        count = int((self.width * self.height) / 7800)
        for _ in range(max(85, min(210, count))):
            self.snow_particles.append(
                SnowParticle(
                    x=self.rng.uniform(0, self.width),
                    y=self.rng.uniform(0, self.height),
                    size=self.rng.uniform(0.6, 2.0),
                    speed=self.rng.uniform(10, 38),
                    drift=self.rng.uniform(4, 22),
                    phase=self.rng.random() * math.tau,
                    alpha=self.rng.randint(70, 170),
                )
            )

    def render(self, elapsed: float) -> Image.Image:
        image = self.background.copy()
        draw = ImageDraw.Draw(image, "RGBA")
        self._draw_snow(draw, elapsed)
        self._draw_tree(image, elapsed)
        self._draw_message(image, elapsed)
        return image

    def _draw_snow(self, draw: ImageDraw.ImageDraw, elapsed: float) -> None:
        for snow in self.snow_particles:
            y = (snow.y + elapsed * snow.speed) % (self.height + 24) - 12
            x = snow.x + math.sin(elapsed * 0.45 + snow.phase) * snow.drift
            size = snow.size * (0.75 + 0.25 * math.sin(elapsed + snow.phase))
            draw.ellipse([x - size, y - size, x + size, y + size], fill=rgba(self.theme["snow"], snow.alpha))

    def _draw_tree(self, image: Image.Image, elapsed: float) -> None:
        scale = min(self.width * 0.120, self.height * 0.145)
        center_x = self.width * 0.5
        center_y = self.height * 0.455
        auto_rotation = elapsed * 0.27 + self.rotation_offset
        breathe = 1.0 + 0.026 * math.sin(elapsed * 1.1)
        projected = []

        for particle in self.tree_particles:
            x, y, z = self._particle_position(particle, elapsed, auto_rotation, breathe)
            perspective = 2.9 / (2.9 + z)
            screen_x = center_x + x * scale * perspective
            screen_y = center_y - y * scale * perspective
            size = particle.size * perspective * (0.72 + 0.18 * particle.depth)
            projected.append((self._depth_sort_key(particle, z), z, screen_x, screen_y, size, particle))

        projected.sort(key=lambda item: item[0], reverse=True)

        glow = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow, "RGBA")
        draw = ImageDraw.Draw(image, "RGBA")

        for _sort_z, z, x, y, size, particle in projected:
            if not (-20 <= x <= self.width + 20 and -20 <= y <= self.height + 20):
                continue
            pulse = math.sin(elapsed * self._pulse_speed(particle.role) + particle.phase)
            color = self._particle_color(particle, pulse, z)
            alpha = self._particle_alpha(particle, z)
            radius = max(0.55, size * (1.0 + 0.12 * max(0, pulse)))

            if particle.role in {"light", "ornament", "spark"}:
                glow_radius = radius * (4.2 if particle.role == "light" else 2.8)
                glow_alpha = 58 if particle.role == "light" else 32
                glow_draw.ellipse(
                    [x - glow_radius, y - glow_radius, x + glow_radius, y + glow_radius],
                    fill=rgba(color, glow_alpha),
                )

            if radius <= 1.1:
                draw.point((x, y), fill=rgba(color, alpha))
            else:
                draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=rgba(color, alpha))
                if particle.role in {"light", "ornament"}:
                    highlight = max(0.75, radius * 0.35)
                    draw.ellipse(
                        [x - radius * 0.42, y - radius * 0.48, x - radius * 0.42 + highlight, y - radius * 0.48 + highlight],
                        fill=rgba("#ffffff", 180),
                    )

        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(4)))
        self._draw_star(image, elapsed, center_x, center_y, scale, auto_rotation)
        self._draw_base_sparkles(image, elapsed, center_x, center_y, scale)

    def _depth_sort_key(self, particle: TreeParticle, z: float) -> float:
        # Larger z is farther from the camera in this projection, so it is drawn first.
        # The trunk is an inner structure and should sit behind leaf/light particles.
        role_bias = {
            "trunk": 3.0,
            "light": -0.04,
            "ornament": -0.03,
            "spark": -0.02,
        }.get(particle.role, 0.0)
        return z + role_bias

    def _particle_position(
        self,
        particle: TreeParticle,
        elapsed: float,
        rotation: float,
        breathe: float,
    ) -> tuple[float, float, float]:
        level = particle.level
        tree_y = 2.28 - 4.42 * min(level, 1.0)
        if particle.role == "trunk":
            tree_y = -2.22 - (level - 1.0) * 2.7

        sway = math.sin(elapsed * 0.78 + level * 4.8 + particle.phase) * (0.035 + 0.05 * (1 - min(level, 1.0)))
        theta = particle.theta + rotation + particle.spin * elapsed + sway
        radius = particle.radius * breathe
        radius += math.sin(elapsed * 1.55 + particle.phase) * particle.orbit
        x = math.cos(theta) * radius
        z = math.sin(theta) * radius
        y = tree_y + math.sin(elapsed * 1.2 + particle.phase) * particle.orbit * 0.55
        x += math.sin(elapsed * 0.92 + y * 1.2) * 0.026 * (1 - min(level, 1.0))
        return x, y, z

    def _particle_color(self, particle: TreeParticle, pulse: float, z: float) -> str:
        depth_light = clamp((z + 2.0) / 4.0)
        factor = 0.78 + depth_light * 0.28
        if particle.role == "leaf":
            factor += max(0, pulse) * 0.20
        elif particle.role == "light":
            factor += 0.45 + max(0, pulse) * 0.50
        elif particle.role == "spark":
            factor += 0.30 + max(0, pulse) * 0.42
        elif particle.role == "ornament":
            factor += 0.22 + max(0, pulse) * 0.25
        return brighten(particle.color, factor)

    def _particle_alpha(self, particle: TreeParticle, z: float) -> int:
        base = {
            "leaf": 225,
            "light": 245,
            "ornament": 238,
            "spark": 185,
            "trunk": 220,
        }.get(particle.role, 220)
        return int(base * (0.74 + 0.26 * clamp((z + 2.1) / 4.2)))

    def _pulse_speed(self, role: str) -> float:
        return {
            "leaf": 1.7,
            "light": 5.8,
            "ornament": 3.2,
            "spark": 7.0,
            "trunk": 1.1,
        }.get(role, 2.0)

    def _draw_star(
        self,
        image: Image.Image,
        elapsed: float,
        center_x: float,
        center_y: float,
        scale: float,
        rotation: float,
    ) -> None:
        star_center_y = center_y - 2.58 * scale
        pulse = 1.0 + 0.08 * math.sin(elapsed * 4.6)
        image.alpha_composite(self._glow((center_x, star_center_y), self.theme["gold"], int(scale * 0.46), 110, 18))
        draw = ImageDraw.Draw(image, "RGBA")

        for star in self.star_particles:
            x3 = star.x * math.cos(rotation * 0.4) - star.z * math.sin(rotation * 0.4)
            z3 = star.x * math.sin(rotation * 0.4) + star.z * math.cos(rotation * 0.4)
            perspective = 3.0 / (3.0 + z3)
            x = center_x + x3 * scale * perspective * pulse
            y = star_center_y + star.y * scale * perspective * pulse
            size = star.size * perspective * (1.0 + 0.16 * math.sin(elapsed * 5.4 + star.phase))
            color = brighten(star.color, 1.0 + 0.35 * max(0, math.sin(elapsed * 5.0 + star.phase)))
            draw.ellipse([x - size, y - size, x + size, y + size], fill=rgba(color, 238))

    def _draw_base_sparkles(self, image: Image.Image, elapsed: float, center_x: float, center_y: float, scale: float) -> None:
        draw = ImageDraw.Draw(image, "RGBA")
        base_y = center_y + 2.28 * scale
        for index in range(80):
            phase = index * 0.77
            x = center_x + math.sin(index * 1.91) * scale * 1.03 + math.sin(elapsed * 0.8 + phase) * 5
            y = base_y + math.cos(index * 1.37) * 18 + math.sin(elapsed * 1.6 + phase) * 3
            alpha = int(80 + 80 * max(0, math.sin(elapsed * 2.3 + phase)))
            size = 0.8 + (index % 5) * 0.18
            draw.ellipse([x - size, y - size, x + size, y + size], fill=rgba(self.theme["gold"], alpha))

    def _draw_message(self, image: Image.Image, elapsed: float) -> None:
        draw = ImageDraw.Draw(image, "RGBA")
        title = f"Merry Christmas, {self.name}"
        subtitle = "May your holidays shine bright."
        title_font = load_font(max(26, int(self.width * 0.032)), bold=True)
        subtitle_font = load_font(max(13, int(self.width * 0.014)), bold=False)
        title_box = draw.textbbox((0, 0), title, font=title_font)
        subtitle_box = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        title_h = title_box[3] - title_box[1]
        subtitle_h = subtitle_box[3] - subtitle_box[1]
        gap = max(8, int(self.height * 0.012))
        top = self.height - title_h - subtitle_h - gap - max(20, int(self.height * 0.030))

        for text, font, y, color in (
            (title, title_font, top, self.theme["gold"]),
            (subtitle, subtitle_font, top + title_h + gap, "#eef8ff"),
        ):
            box = draw.textbbox((0, 0), text, font=font)
            x = (self.width - (box[2] - box[0])) / 2
            draw.text((x + 2, y + 2), text, font=font, fill=rgba("#01040a", 175))
            if text == title:
                glow = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
                glow_draw = ImageDraw.Draw(glow, "RGBA")
                glow_draw.text((x, y), text, font=font, fill=rgba(color, int(88 + 30 * math.sin(elapsed * 2.1))))
                image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(5)))
            draw.text((x, y), text, font=font, fill=rgba(color, 245))

    def _glow(
        self,
        center: tuple[float, float],
        color: str,
        radius: int,
        alpha: int,
        blur: int,
    ) -> Image.Image:
        layer = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")
        x, y = center
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=rgba(color, alpha))
        return layer.filter(ImageFilter.GaussianBlur(blur))


class ChristmasTreeApp:
    def __init__(self, name: str, width: int, height: int, theme: str, density: float) -> None:
        load_tkinter()
        self.root = tk.Tk()
        self.root.title("Aurora Christmas Tree")
        self.root.minsize(860, 660)
        self.root.configure(bg="#050b16")

        self.scene = ParticleTreeScene(width, height - 66, name, theme=theme, density=density)
        self.start_time = time.perf_counter()
        self.elapsed_before_pause = 0.0
        self.paused = False
        self.after_id: str | None = None
        self.resize_after_id: str | None = None
        self.drag_x: int | None = None

        self.canvas = tk.Canvas(self.root, bg="#050b16", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        self.toolbar = tk.Frame(self.root, bg="#071221", padx=12, pady=10)
        self.toolbar.grid(row=1, column=0, sticky="ew")
        self.status_var = tk.StringVar(value=f"{len(self.scene.tree_particles):,} particles")
        self.pause_var = tk.StringVar(value="Pause")
        self.theme_var = tk.StringVar(value=f"Theme: {self.scene.theme['name']}")
        self.density_var = tk.DoubleVar(value=density)
        self._build_toolbar()

        self.photo = None
        self.canvas_image = self.canvas.create_image(0, 0, anchor="nw")

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag_rotate)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.root.bind("<space>", lambda _event: self.toggle_pause())
        self.root.bind("<r>", lambda _event: self.replay())
        self.root.bind("<R>", lambda _event: self.replay())
        self.root.bind("<s>", lambda _event: self.save_snapshot())
        self.root.bind("<S>", lambda _event: self.save_snapshot())
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_toolbar(self) -> None:
        button_style = {
            "bg": "#13243a",
            "fg": "#f5fbff",
            "activebackground": "#1f3d61",
            "activeforeground": "#ffffff",
            "relief": "flat",
            "bd": 0,
            "padx": 14,
            "pady": 8,
            "font": ("Segoe UI", 10, "bold"),
            "cursor": "hand2",
        }
        tk.Button(self.toolbar, textvariable=self.pause_var, command=self.toggle_pause, **button_style).pack(side="left")
        tk.Button(self.toolbar, text="Replay", command=self.replay, **button_style).pack(side="left", padx=(8, 0))
        tk.Button(self.toolbar, text="Save PNG", command=self.save_snapshot, **button_style).pack(side="left", padx=(8, 0))
        tk.Button(self.toolbar, textvariable=self.theme_var, command=self.next_theme, **button_style).pack(side="left", padx=(8, 0))

        tk.Label(self.toolbar, text="Density", bg="#071221", fg="#b9c8dc", font=("Segoe UI", 10)).pack(
            side="left",
            padx=(18, 6),
        )
        tk.Scale(
            self.toolbar,
            from_=0.55,
            to=1.65,
            resolution=0.05,
            orient="horizontal",
            length=145,
            variable=self.density_var,
            command=self._density_changed,
            bg="#071221",
            troughcolor="#1f3d61",
            fg="#f5fbff",
            highlightthickness=0,
            bd=0,
        ).pack(side="left")

        tk.Label(self.toolbar, textvariable=self.status_var, bg="#071221", fg="#dcecff", font=("Segoe UI", 10)).pack(
            side="right"
        )

    def _density_changed(self, value: str) -> None:
        try:
            density = float(value)
        except ValueError:
            return
        self.scene.rebuild(self.scene.width, self.scene.height, density=density)
        self.status_var.set(f"{len(self.scene.tree_particles):,} particles")

    def _on_canvas_configure(self, event: tk.Event) -> None:
        if event.width < 20 or event.height < 20:
            return
        if self.resize_after_id:
            self.root.after_cancel(self.resize_after_id)
        self.resize_after_id = self.root.after(150, lambda: self._resize_scene(event.width, event.height))

    def _resize_scene(self, width: int, height: int) -> None:
        self.resize_after_id = None
        self.scene.rebuild(width, height, density=self.density_var.get())

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_x = event.x

    def _drag_rotate(self, event: tk.Event) -> None:
        if self.drag_x is None:
            self.drag_x = event.x
            return
        self.scene.rotate_by((event.x - self.drag_x) * 0.006)
        self.drag_x = event.x

    def _end_drag(self, _event: tk.Event) -> None:
        self.drag_x = None

    def current_elapsed(self) -> float:
        if self.paused:
            return self.elapsed_before_pause
        return self.elapsed_before_pause + time.perf_counter() - self.start_time

    def toggle_pause(self) -> None:
        if self.paused:
            self.paused = False
            self.start_time = time.perf_counter()
            self.pause_var.set("Pause")
            self._schedule()
        else:
            self.elapsed_before_pause = self.current_elapsed()
            self.paused = True
            self.pause_var.set("Resume")
            if self.after_id:
                self.root.after_cancel(self.after_id)
                self.after_id = None

    def replay(self) -> None:
        self.scene.reseed()
        self.start_time = time.perf_counter()
        self.elapsed_before_pause = 0.0
        self.paused = False
        self.pause_var.set("Pause")
        self.status_var.set(f"{len(self.scene.tree_particles):,} particles")
        self._schedule()

    def save_snapshot(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save PNG",
            defaultextension=".png",
            initialfile=f"aurora_tree_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            filetypes=[("PNG image", "*.png")],
        )
        if not path:
            return
        self.scene.render(self.current_elapsed()).save(path)
        self.status_var.set(f"Saved {Path(path).name}")

    def next_theme(self) -> None:
        themes = list(THEMES)
        next_index = (themes.index(self.scene.theme_name) + 1) % len(themes)
        self.scene.set_theme(themes[next_index])
        self.theme_var.set(f"Theme: {self.scene.theme['name']}")

    def _schedule(self) -> None:
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(24, self.animate)

    def animate(self) -> None:
        self.after_id = None
        image = self.scene.render(self.current_elapsed())
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.itemconfigure(self.canvas_image, image=self.photo)
        if not self.paused:
            self._schedule()

    def run(self) -> None:
        self._schedule()
        self.root.mainloop()

    def close(self) -> None:
        if self.after_id:
            self.root.after_cancel(self.after_id)
        if self.resize_after_id:
            self.root.after_cancel(self.resize_after_id)
        self.root.destroy()


def ask_name() -> str:
    load_tkinter()
    dialog = tk.Tk()
    dialog.withdraw()
    value = simpledialog.askstring("Aurora Christmas Tree", "Name for the greeting:", parent=dialog)
    dialog.destroy()
    return value or "Friend"


def save_preview(path: str, name: str, width: int, height: int, theme: str, density: float) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    scene = ParticleTreeScene(width, height, name, theme=theme, density=density, seed=20241225)
    scene.render(5.0).save(output)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an animated GUI Christmas tree made from tiny particles.")
    parser.add_argument("--name", default=None, help="Name displayed in the greeting")
    parser.add_argument("--width", type=int, default=1100, help="Window or preview width")
    parser.add_argument("--height", type=int, default=780, help="Window or preview height")
    parser.add_argument("--theme", choices=sorted(THEMES), default="aurora", help="Initial color theme")
    parser.add_argument("--density", type=float, default=1.0, help="Particle density from 0.55 to 1.65")
    parser.add_argument("--preview", help="Save a static PNG preview and exit")
    parser.add_argument("--no-dialog", action="store_true", help="Use --name or Friend without opening the name dialog")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    name = args.name or "Friend"
    density = clamp(args.density, 0.55, 1.65)
    if args.preview:
        output = save_preview(args.preview, name, args.width, args.height, args.theme, density)
        print(f"Preview saved to {output}")
        return

    if args.name is None and not args.no_dialog:
        name = ask_name()
    app = ChristmasTreeApp(name=name, width=args.width, height=args.height, theme=args.theme, density=density)
    app.run()


if __name__ == "__main__":
    main()
