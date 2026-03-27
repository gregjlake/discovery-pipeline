from pydantic import BaseModel
from typing import List, Optional

class ScatterRequest(BaseModel):
    dataset_x:      str
    dataset_y:      str
    year:           int = 2022
    norm_method:    str = 'zscore'
    outlier_method: str = 'keep'
    weight_method:  str = 'equal'

class CountyPoint(BaseModel):
    fips:     str
    name:     str
    region:   str
    x:        float
    y:        float
    raw_x:    float
    raw_y:    float
    pop:      Optional[float] = None
    residual: float

class ScatterResponse(BaseModel):
    query_id:     str
    r:            float
    n:            int
    r_squared:    float
    points:       List[dict]
    config:       ScatterRequest

class AskRequest(BaseModel):
    question:     str
    dataset_x:    str
    dataset_y:    str
    available_datasets: List[str] = ['library', 'mobility', 'air', 'broadband']

class AskResponse(BaseModel):
    query_type:   str
    params:       dict
    raw_llm_json: Optional[str] = None
    error:        Optional[str] = None
