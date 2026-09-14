from pydantic import BaseModel, Field
from typing import List, Optional

class TaskCatalogItem(BaseModel):
    task_code: str = Field(description="Snake_case identifier (e.g. 'oil_change')")
    name: str = Field(description="Short human-readable name")
    description: str = Field(description="Brief description of what the task involves")
    interval_km: Optional[int] = Field(None, description="Km interval, null if not mileage-based")
    interval_months: Optional[int] = Field(None, description="Month interval, null if not time-based")
    is_safety_critical: bool = Field(description="True if safety-critical, otherwise False")

class TaskCatalogList(BaseModel):
    tasks: List[TaskCatalogItem] = Field(description="List of recommended maintenance tasks")

class InvoiceAnalysis(BaseModel):
    tipo_servicio: str = Field(description="Description of the service performed")
    task_codes: List[str] = Field(description="List of task codes detected matching valid tasks")
    km: Optional[int] = Field(None, description="Current vehicle mileage read from the document")
    coste_total: Optional[float] = Field(None, description="Total cost of the invoice/receipt")
    fecha: Optional[str] = Field(None, description="Date of the service in YYYY-MM-DD format")
    taller: Optional[str] = Field(None, description="Name of the workshop/store")
    piezas: List[str] = Field(description="List of parts or ingredients bought/serviced")
    observaciones: Optional[str] = Field(None, description="General observations or notes")

class NormalizedTask(BaseModel):
    task_code: str = Field(description="Normalized English snake_case task code (e.g. 'oil_change')")
    name: str = Field(description="Short user-friendly name in the same language as the input")
