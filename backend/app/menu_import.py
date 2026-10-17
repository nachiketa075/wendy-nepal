"""Repeatable import of the owner's printed menu into the database menu.

    python -m app.cli import-menu                 # dry run: shows what would change
    python -m app.cli import-menu --apply         # write the changes
    python -m app.cli import-menu --apply --hide-legacy

Rules:
* Items and categories are matched by their stable slug, so running the import
  again never creates duplicates.
* Each imported row remembers what the import wrote (`imported_snapshot`). If
  the live row no longer matches that snapshot, the owner has edited it in the
  dashboard and the import leaves it alone and reports it.
* Rows the owner created are never touched. To take an imported item off the
  menu, hide it in the dashboard rather than deleting it: a deleted imported
  item would be listed under "to create" on the next run.
* Nothing runs at API startup. The import only happens when this command is run.
"""

import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MenuCategory, MenuItem
from .routers.staff import item_snapshot, snapshot_of

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "menu_cm_pdf.json"
LEGACY_SOURCES = ("listing", "menu_photo")


@dataclass
class ImportSummary:
    applied: bool
    source_document: str = ""
    categories_created: list[str] = field(default_factory=list)
    categories_updated: list[str] = field(default_factory=list)
    categories_kept_owner_edit: list[str] = field(default_factory=list)
    items_created: list[str] = field(default_factory=list)
    items_updated: list[str] = field(default_factory=list)
    items_unchanged: int = 0
    items_kept_owner_edit: list[str] = field(default_factory=list)
    flagged_for_review: list[str] = field(default_factory=list)
    legacy_items_visible: int = 0
    legacy_items_hidden: int = 0

    def lines(self) -> list[str]:
        mode = "APPLIED" if self.applied else "DRY RUN (nothing was written; add --apply to write)"
        out = [
            f"Menu import from {self.source_document}: {mode}",
            f"  categories: {len(self.categories_created)} to create, {len(self.categories_updated)} to update, "
            f"{len(self.categories_kept_owner_edit)} kept (edited by owner)",
            f"  items:      {len(self.items_created)} to create, {len(self.items_updated)} to update, "
            f"{self.items_unchanged} unchanged, {len(self.items_kept_owner_edit)} kept (edited by owner)",
        ]
        if self.items_kept_owner_edit:
            out.append("  owner edits left untouched: " + ", ".join(self.items_kept_owner_edit))
        if self.categories_kept_owner_edit:
            out.append("  owner-edited categories left untouched: " + ", ".join(self.categories_kept_owner_edit))
        if self.flagged_for_review:
            out.append("  flagged for the owner to review (text kept as printed): " + ", ".join(self.flagged_for_review))
        if self.legacy_items_hidden:
            out.append(f"  older listing-based items hidden from the public menu (still in the editor): {self.legacy_items_hidden}")
        if self.legacy_items_visible:
            out.append(
                f"  NOTE: {self.legacy_items_visible} older listing-based item(s) are still on the public menu. "
                "Run with --hide-legacy to hide them (they stay in the owner's editor)."
            )
        return out


def _validate(data: dict) -> None:
    """Fail loudly on a malformed file rather than importing half a menu."""
    slugs: set[str] = set()
    if not data.get("categories"):
        raise ValueError("The menu file has no categories.")
    for category in data["categories"]:
        for key in ("slug", "name", "sort_order", "items"):
            if key not in category:
                raise ValueError(f"Category is missing '{key}': {category.get('name', '?')}")
        for item in category["items"]:
            if not item.get("slug") or not item.get("name"):
                raise ValueError(f"An item in {category['name']} has no slug or name.")
            if item["slug"] in slugs:
                raise ValueError(f"Duplicate item slug in the file: {item['slug']}")
            slugs.add(item["slug"])
            price = item.get("price_npr")
            if price is not None and (not isinstance(price, (int, float)) or price < 0):
                raise ValueError(f"Bad price for {item['slug']}: {price!r}")
            for addon in item.get("addons", []):
                if not addon.get("label") or not isinstance(addon.get("price"), (int, float)):
                    raise ValueError(f"Bad add-on on {item['slug']}")


def _category_snapshot(category: MenuCategory) -> dict:
    return {"name": category.name, "sort_order": category.sort_order, "notes": category.notes or []}


def import_menu(db: Session, path: Path = DEFAULT_FILE, apply: bool = False, hide_legacy: bool = False) -> ImportSummary:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate(data)
    summary = ImportSummary(applied=apply, source_document=data.get("source_document", str(path)))
    review = {r["slug"]: r["note"] for r in data.get("owner_review", [])}

    for entry in data["categories"]:
        wanted = {"name": entry["name"], "sort_order": entry["sort_order"], "notes": entry.get("notes", [])}
        category = db.scalar(select(MenuCategory).where(MenuCategory.slug == entry["slug"]))
        if category is None:
            category = MenuCategory(slug=entry["slug"], tagline=None, imported_snapshot=wanted, **wanted)
            db.add(category)
            db.flush()
            summary.categories_created.append(entry["slug"])
        elif category.imported_snapshot is None or _category_snapshot(category) != category.imported_snapshot:
            # Created or since edited by the owner: leave its name, order and notes alone.
            summary.categories_kept_owner_edit.append(entry["slug"])
        elif _category_snapshot(category) != wanted:
            category.name, category.sort_order, category.notes = wanted["name"], wanted["sort_order"], wanted["notes"]
            category.imported_snapshot = wanted
            summary.categories_updated.append(entry["slug"])

        for raw in entry["items"]:
            values = {
                "name": raw["name"],
                "description": raw.get("description"),
                "price_npr": Decimal(str(raw["price_npr"])) if raw.get("price_npr") is not None else None,
                "addons": raw.get("addons", []),
                "sort_order": raw["sort_order"],
            }
            if raw["slug"] in review:
                summary.flagged_for_review.append(raw["slug"])
            item = db.scalar(select(MenuItem).where(MenuItem.slug == raw["slug"]))
            if item is None:
                item = MenuItem(slug=raw["slug"], category_id=category.id, source="owner_pdf",
                                source_document=data.get("source_document"), source_page=entry.get("page"),
                                review_note=review.get(raw["slug"]), is_available=True, is_published=True, **values)
                db.add(item)
                db.flush()
                item.imported_snapshot = item_snapshot(item, entry["slug"])
                summary.items_created.append(raw["slug"])
                continue

            current = item_snapshot(item, item.category.slug)
            if item.imported_snapshot is not None and current != item.imported_snapshot:
                summary.items_kept_owner_edit.append(raw["slug"])
                continue
            wanted_snapshot = snapshot_of(category_slug=entry["slug"], **values)
            if current == wanted_snapshot:
                summary.items_unchanged += 1
                continue
            for key, value in values.items():
                setattr(item, key, value)
            item.category_id = category.id
            item.review_note = review.get(raw["slug"])
            item.imported_snapshot = wanted_snapshot
            summary.items_updated.append(raw["slug"])

    legacy = db.scalars(select(MenuItem).where(MenuItem.source.in_(LEGACY_SOURCES), MenuItem.is_published.is_(True))).all()
    if hide_legacy:
        for item in legacy:
            item.is_published = False
        summary.legacy_items_hidden = len(legacy)
    else:
        summary.legacy_items_visible = len(legacy)

    if apply:
        db.commit()
    else:
        db.rollback()
    return summary
