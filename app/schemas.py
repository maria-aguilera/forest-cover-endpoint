from typing import Literal

from pydantic import BaseModel, Field

COVER_LABELS: dict[int, str] = {
    1: "Spruce/Fir",
    2: "Lodgepole Pine",
    3: "Ponderosa Pine",
    4: "Cottonwood/Willow",
    5: "Aspen",
    6: "Douglas-fir",
    7: "Krummholz",
}


class PredictRequest(BaseModel):
    """One observation. Numeric features come straight from the UCI dataset;
    wilderness_area (1–4) and soil_type (1–40) are accepted as integers and
    expanded to the one-hot columns the model was trained on."""

    elevation: float = Field(..., description="Elevation in meters.")
    aspect: float = Field(..., ge=0, le=360, description="Aspect in degrees azimuth.")
    slope: float = Field(..., ge=0, description="Slope in degrees.")
    horizontal_distance_to_hydrology: float
    vertical_distance_to_hydrology: float
    horizontal_distance_to_roadways: float
    hillshade_9am: float = Field(..., ge=0, le=255)
    hillshade_noon: float = Field(..., ge=0, le=255)
    hillshade_3pm: float = Field(..., ge=0, le=255)
    horizontal_distance_to_fire_points: float
    wilderness_area: Literal[1, 2, 3, 4] = Field(
        ..., description="1=Rawah, 2=Neota, 3=Comanche Peak, 4=Cache la Poudre."
    )
    soil_type: int = Field(..., ge=1, le=40, description="Soil type 1–40.")


class PredictResponse(BaseModel):
    cover_type: int = Field(..., ge=1, le=7)
    cover_label: str
    probabilities: dict[str, float]
    model_version: str
