from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "backend" / "app" / "model_architecture.png"

WIDTH = 1700
HEIGHT = 1100
BG = "#f6f8fc"
TEXT = "#10233d"
MUTED = "#5c6b82"
OUTLINE = "#b8c7da"
BLUE = "#dfeeff"
GREEN = "#def7ea"
YELLOW = "#fff4cc"
RED = "#ffe1e1"
GRAY = "#eef3f8"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(["arialbd.ttf", "segoeuib.ttf"])
    candidates.extend(["arial.ttf", "segoeui.ttf", "calibri.ttf"])
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


TITLE_FONT = load_font(40, bold=True)
SUBTITLE_FONT = load_font(24, bold=True)
BODY_FONT = load_font(20)
SMALL_FONT = load_font(18)


def draw_box(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int, int, int],
    title: str,
    lines: list[str],
    fill: str,
) -> None:
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline=OUTLINE, width=3)
    x1, y1, x2, y2 = xy
    draw.text((x1 + 20, y1 + 16), title, fill=TEXT, font=SUBTITLE_FONT)
    y = y1 + 58
    for line in lines:
        draw.text((x1 + 20, y), line, fill=TEXT, font=BODY_FONT)
        y += 28


def center_text(draw: ImageDraw.ImageDraw, text: str, y: int, font: ImageFont.ImageFont, fill: str = TEXT) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (WIDTH - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, font=font, fill=fill)


def arrow(draw: ImageDraw.ImageDraw, start: Tuple[int, int], end: Tuple[int, int], fill: str = "#5779a8", width: int = 5) -> None:
    draw.line([start, end], fill=fill, width=width)
    ex, ey = end
    if abs(end[0] - start[0]) >= abs(end[1] - start[1]):
        direction = 1 if end[0] > start[0] else -1
        draw.polygon([(ex, ey), (ex - 16 * direction, ey - 9), (ex - 16 * direction, ey + 9)], fill=fill)
    else:
        direction = 1 if end[1] > start[1] else -1
        draw.polygon([(ex, ey), (ex - 9, ey - 16 * direction), (ex + 9, ey - 16 * direction)], fill=fill)


def label(draw: ImageDraw.ImageDraw, pos: Tuple[int, int], text: str) -> None:
    draw.text(pos, text, fill=MUTED, font=SMALL_FONT)


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    center_text(draw, "Dispatch AI Agent - ReAct Architecture", 28, TITLE_FONT)
    center_text(
        draw,
        "Dynamic Thought -> Action -> Observation loop with optional retrieval and optional LLM disambiguation",
        82,
        BODY_FONT,
        fill=MUTED,
    )

    draw_box(
        draw,
        (70, 150, 410, 255),
        "Complaint Intake",
        [
            "Citizen prompt or complaint record",
            "POST /api/execute or complaint_id flow",
        ],
        BLUE,
    )

    draw_box(
        draw,
        (520, 150, 1180, 320),
        "Agent_Thought",
        [
            "Build compact state snapshot",
            "Check deterministic guardrails:",
            "  emergency / out-of-scope / obvious missing info",
            "Otherwise use LLM planner for ambiguous next-step choice",
        ],
        GREEN,
    )

    draw_box(
        draw,
        (1260, 150, 1610, 320),
        "Action Space",
        [
            "PARSE_COMPLAINT",
            "RETRIEVE_SIMILAR_CASES",
            "RUN_LLM_DISAMBIGUATION",
            "ASK_FOR_MISSING_INFO",
            "SKIP_RETRIEVAL / FINALIZE",
            "EMERGENCY_ESCALATE / MARK_IRRELEVANT",
        ],
        YELLOW,
    )

    draw_box(
        draw,
        (140, 410, 520, 565),
        "Agent_Action",
        [
            "Execute exactly one chosen tool",
            "No fixed mandatory pipeline",
            "Tool invocation depends on current state",
        ],
        BLUE,
    )

    draw_box(
        draw,
        (600, 390, 1020, 620),
        "Tool Layer",
        [
            "PARSE -> preprocessing + baseline decision",
            "RETRIEVE -> Pinecone + evidence summary",
            "LLM -> planner/disambiguation only when needed",
            "FOLLOW-UP / ESCALATE / IRRELEVANT policies",
        ],
        GRAY,
    )

    draw_box(
        draw,
        (1110, 410, 1530, 565),
        "Agent_Observation",
        [
            "Record tool result",
            "Update state: parsed fields, evidence,",
            "confidence, missing fields, review flags",
        ],
        BLUE,
    )

    draw_box(
        draw,
        (1160, 690, 1590, 860),
        "Termination / Finalization",
        [
            "Stop when agent decides enough is known",
            "or guardrails force early stop",
            "Apply confidence gating",
            "Apply human review escalation",
            "Generate final response text",
        ],
        RED,
    )

    draw_box(
        draw,
        (110, 700, 860, 880),
        "Persistence + Audit",
        [
            "Supabase: complaints, executions, steps trace",
            "Trace includes Agent_Thought / Action / Observation",
            "Pinecone remains retrieval tool only",
            "No PII stored in vector metadata",
        ],
        GREEN,
    )

    arrow(draw, (410, 202), (520, 202))
    label(draw, (436, 170), "input")

    arrow(draw, (1180, 235), (1260, 235))
    label(draw, (1198, 202), "allowed next actions")

    arrow(draw, (850, 320), (850, 390))
    label(draw, (875, 347), "choose action")

    arrow(draw, (520, 485), (600, 485))
    arrow(draw, (1020, 485), (1110, 485))
    label(draw, (725, 450), "tool call")
    label(draw, (1040, 450), "result")

    arrow(draw, (1320, 565), (1320, 650))
    arrow(draw, (1320, 650), (850, 650))
    arrow(draw, (850, 650), (850, 320))
    label(draw, (1010, 620), "continue loop if not finalized")

    arrow(draw, (1320, 565), (1320, 690))
    label(draw, (1350, 620), "stop")

    arrow(draw, (860, 790), (1160, 790))
    label(draw, (930, 758), "execution trace + decision")

    footer = (
        "Course alignment: dynamic ReAct loop, optional tool usage, early stopping for emergency/irrelevant cases, "
        "hybrid planner with deterministic guardrails + LLM planner + deterministic fallback."
    )
    draw.text((70, 1000), footer, fill=MUTED, font=SMALL_FONT)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
