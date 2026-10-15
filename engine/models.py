"""engine/models.py: Core data models with constraint validations."""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field, field_validator


class Batch(BaseModel):
    batch_id: str
    commodity: str
    quantity_kg: float = Field(gt=0, description="Quantity in kilograms")
    remaining_shelf_life_hrs: float = Field(gt=0, description="Remaining shelf life in hours")
    base_cost_per_kg: float = Field(ge=0, description="Cost of procurement/production per kg")
    origin: str = "Warehouse-Central"
    harvest_date: Optional[str] = None


class Destination(BaseModel):
    dest_id: str
    name: str
    commodity: str
    demand_kg: float = Field(ge=0, description="Maximum demand at destination")
    selling_price_per_kg: float = Field(gt=0, description="Market price per kg")
    handling_time_hrs: float = Field(default=2.0, ge=0, description="Unloading and shelf placement time")
    max_reception_capacity_kg: Optional[float] = None


class TransportRoute(BaseModel):
    origin: str
    dest_id: str
    travel_time_hrs: float = Field(gt=0, description="Transit time in hours")
    cost_per_kg: float = Field(ge=0, description="Transport cost in ₹ per kg")
    vehicle_capacity_kg: float = Field(default=10000.0, gt=0)


class AllocationDecision(BaseModel):
    batch_id: str
    dest_id: str
    commodity: str
    quantity_kg: float
    travel_time_hrs: float
    remaining_shelf_life_hrs: float
    shelf_life_buffer_hrs: float
    base_price_per_kg: float
    discount_pct: float
    final_price_per_kg: float
    transport_cost_per_kg: float
    base_cost_per_kg: float
    gross_revenue: float
    transport_cost_total: float
    procurement_cost_total: float
    net_profit: float
    reason: str


class OptimizationSummary(BaseModel):
    strategy_name: str
    total_inventory_kg: float
    dispatched_kg: float
    spoiled_kg: float
    unsold_unspoiled_kg: float
    spoilage_rate_pct: float
    demand_fulfillment_pct: float
    total_gross_revenue: float
    total_transport_cost: float
    total_procurement_cost: float
    net_profit: float
    allocations: List[AllocationDecision]
    disposal_waste_cost: float = 0.0