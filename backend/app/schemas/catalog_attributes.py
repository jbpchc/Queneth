"""Category-specific product attributes (spec §9), one Pydantic model per
category. Stored in Product.attributes (JSON) and validated on every write;
each category's JSON Schema is also saved on Category.attribute_schema so the
seller wizard (Phase 8) can render the right fields."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Attrs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FiberShare(_Attrs):
    fiber: str = Field(min_length=2, max_length=40)
    pct: int = Field(ge=1, le=100)


class ClothingAttributes(_Attrs):
    fit: Literal["slim", "regular", "oversized"]
    composition: list[FiberShare] = Field(min_length=1)
    care: list[str] = Field(default_factory=list)
    model_height_cm: int | None = Field(default=None, ge=140, le=210)
    model_size: str | None = None

    @model_validator(mode="after")
    def _composition_sums_to_100(self) -> "ClothingAttributes":
        if sum(f.pct for f in self.composition) != 100:
            raise ValueError("Fabric composition must add up to 100%.")
        return self


class ShoeAttributes(_Attrs):
    upper: str
    lining: str
    sole: str
    heel_height_cm: float = Field(ge=0, le=15)
    last: str | None = Field(
        default=None, description="Last or fit note, e.g. 'Almond toe, narrow last'"
    )


BagFit = Literal["phone", "wallet", "keys", "sunglasses", "tablet", "laptop", "water bottle"]


class BagAttributes(_Attrs):
    width_cm: float = Field(gt=0, le=80)
    height_cm: float = Field(gt=0, le=80)
    depth_cm: float = Field(gt=0, le=50)
    material: str
    hardware_finish: str
    closure: str
    strap_drop_cm: float | None = Field(default=None, ge=0, le=80)
    interior: str
    fits: list[BagFit] = Field(default_factory=list)


class AccessoryAttributes(_Attrs):
    material: str
    stone: str | None = None
    dimensions: str | None = None
    water_resistance_m: int | None = Field(default=None, ge=0, le=500)
    care: list[str] = Field(default_factory=list)


Concentration = Literal["Parfum", "EDP", "EDT", "EDC"]
OlfactoryFamily = Literal[
    "Floral",
    "Woody",
    "Amber",
    "Fresh",
    "Citrus",
    "Gourmand",
    "Chypre",
    "Fougère",
    "Aromatic",
    "Leather",
]


class PerfumeAttributes(_Attrs):
    concentration: Concentration
    family: OlfactoryFamily
    top_notes: list[str] = Field(min_length=1)
    heart_notes: list[str] = Field(min_length=1)
    base_notes: list[str] = Field(min_length=1)
    perfumer: str
    longevity: int = Field(ge=1, le=5)
    sillage: int = Field(ge=1, le=5)
    seasons: list[Literal["spring", "summer", "autumn", "winter"]] = Field(default_factory=list)
    occasions: list[str] = Field(default_factory=list)

    @field_validator("top_notes", "heart_notes", "base_notes")
    @classmethod
    def _tidy_notes(cls, notes: list[str]) -> list[str]:
        # Postel's Law: " Bergamot " and "bergamot" are the same note.
        return [n.strip().lower() for n in notes if n.strip()]


ATTRIBUTE_MODELS: dict[str, type[_Attrs]] = {
    "clothing": ClothingAttributes,
    "shoes": ShoeAttributes,
    "bags": BagAttributes,
    "accessories": AccessoryAttributes,
    "perfumes": PerfumeAttributes,
}

#: Variant option axes per category (spec §9 table).
VARIANT_AXES: dict[str, list[str]] = {
    "clothing": ["size", "color"],
    "shoes": ["size", "color", "width"],
    "bags": ["color", "size"],
    "accessories": ["color", "size"],
    "perfumes": ["volume"],
}


def validate_attributes(category_slug: str, data: dict[str, Any]) -> dict[str, Any]:
    model = ATTRIBUTE_MODELS[category_slug]
    return model.model_validate(data).model_dump(mode="json", exclude_none=True)


def attribute_json_schema(category_slug: str) -> dict[str, Any]:
    return ATTRIBUTE_MODELS[category_slug].model_json_schema()
