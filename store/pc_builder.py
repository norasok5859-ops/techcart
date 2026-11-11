"""PC builder: pick one part per slot, check that the parts work together, add the build to the cart.

Used by the "Build your PC" page (through the API) so the rules live in one place.
"""
import math
from decimal import Decimal

from django.db import transaction

from . import services
from .models import Product

# (slot, label, category slug, required, icon)
SLOTS = [
    ("cpu", "Processor", "processors", True, "cpu"),
    ("motherboard", "Motherboard", "motherboards", True, "motherboard"),
    ("ram", "Memory", "memory", True, "memory"),
    ("gpu", "Graphics card", "graphics-cards", False, "gpu-card"),
    ("storage", "Storage", "storage", True, "device-ssd"),
    ("psu", "Power supply", "power-supplies", True, "plug"),
    ("case", "Case", "pc-cases", True, "pc"),
]
SLOT_CATEGORY = {s[0]: s[2] for s in SLOTS}
SLOT_LABEL = {s[0]: s[1] for s in SLOTS}
BASE_WATTS = 80  # motherboard, memory, drives and fans


class BuildError(Exception):
    pass


def parts_by_slot():
    """All active parts for each slot (for the builder page)."""
    qs = Product.objects.filter(is_active=True, category__slug__in=SLOT_CATEGORY.values()) \
        .select_related("category").order_by("price")
    grouped = {slot: [] for slot in SLOT_CATEGORY}
    slot_of = {cat: slot for slot, cat in SLOT_CATEGORY.items()}
    for p in qs:
        grouped[slot_of[p.category.slug]].append(p)
    return grouped


def load_parts(ids):
    """{"cpu": 3, ...} -> {"cpu": Product}. Unknown slots or ids raise BuildError."""
    if not isinstance(ids, dict):
        raise BuildError("'parts' must be an object like {\"cpu\": 12, \"motherboard\": 20}.")
    parts = {}
    for slot, pid in ids.items():
        if pid in (None, ""):
            continue
        if slot not in SLOT_CATEGORY:
            raise BuildError(f"Unknown part type '{slot}'.")
        try:
            product = Product.objects.select_related("category").get(pk=int(pid), is_active=True)
        except (Product.DoesNotExist, ValueError, TypeError):
            raise BuildError(f"{SLOT_LABEL[slot]}: product {pid} was not found.")
        if product.category.slug != SLOT_CATEGORY[slot]:
            raise BuildError(f"{product.name} is not a {SLOT_LABEL[slot].lower()}.")
        parts[slot] = product
    return parts


def check(parts):
    """Compatibility report for a (possibly incomplete) build."""
    s = {slot: p.compat for slot, p in parts.items()}
    issues = []

    def problem(level, msg):
        issues.append({"level": level, "message": msg})

    cpu, mb, ram, case = s.get("cpu"), s.get("motherboard"), s.get("ram"), s.get("case")
    if cpu and mb and cpu.get("socket") != mb.get("socket"):
        problem("error", f"The processor uses socket {cpu.get('socket')} but the motherboard is {mb.get('socket')}.")
    if ram and mb and ram.get("memory_type") != mb.get("memory_type"):
        problem("error", f"The motherboard takes {mb.get('memory_type')} memory, not {ram.get('memory_type')}.")
    if case and mb and mb.get("form_factor") not in case.get("form_factors", []):
        problem("error", f"The {mb.get('form_factor')} motherboard does not fit in this case "
                         f"(it supports {', '.join(case.get('form_factors', []))}).")
    if cpu and cpu.get("integrated_graphics") is False and "gpu" not in parts:
        problem("error", "This processor has no built-in graphics, so the PC needs a graphics card.")

    watts = BASE_WATTS + int(cpu.get("tdp", 0) if cpu else 0) + int(s["gpu"].get("tdp", 0) if "gpu" in s else 0)
    recommended = int(math.ceil(watts * 1.4 / 50) * 50)
    if "psu" in s:
        psu_w = int(s["psu"].get("wattage", 0))
        if psu_w < watts:
            problem("error", f"The {psu_w}W power supply is too weak: this build draws about {watts}W.")
        elif psu_w < recommended:
            problem("warning", f"{psu_w}W works, but {recommended}W or more is recommended for headroom.")

    for slot, p in parts.items():
        if not p.in_stock:
            problem("error", f"{p.name} is out of stock.")

    # The graphics card is optional (the missing-GPU case is reported above when it matters).
    missing = [SLOT_LABEL[slot] for slot, _l, _c, required, _i in SLOTS if required and slot not in parts]
    errors = [i for i in issues if i["level"] == "error"]
    return {
        "parts": {slot: p.pk for slot, p in parts.items()},
        "total": str(sum((p.price for p in parts.values()), Decimal("0.00"))),
        "estimated_watts": watts,
        "recommended_psu_watts": recommended,
        "missing": missing,
        "issues": issues,
        "compatible": not errors,
        "complete": not missing,
        "ready": not missing and not errors,
    }


@transaction.atomic
def add_to_cart(user, parts):
    """Add a complete, compatible build to the user's cart (one of each part)."""
    report = check(parts)
    if report["missing"]:
        raise BuildError("Choose a part for: " + ", ".join(report["missing"]) + ".")
    if not report["compatible"]:
        raise BuildError(next(i["message"] for i in report["issues"] if i["level"] == "error"))
    try:
        for p in parts.values():
            services.add_to_cart(user, p, 1)
    except services.CartError as e:
        raise BuildError(str(e))
    return report
