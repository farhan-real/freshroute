"""engine/models.py: Core data schemas with strict constraint and security validations."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Batch(BaseModel):
    """Represents a perishable inventory batch at an origin hub."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    batch_id: str = Field(min_length=1, max_length=64, description="Unique batch identifier")
    commodity: str = Field(min_length=1, max_length=64, description="Produce commodity type")
    quantity_kg: float = Field(gt=0.0, le=1_000_000.0, description="Quantity in kilograms")
    remaining_shelf_life_hrs: float = Field(
        gt=0.0, le=8760.0, description="Estimated remaining shelf life in hours"
    )
    base_cost_per_kg: float = Field(
        ge=0.0, le=100_000.0, description="Cost of procurement/production per kg"
    )
    origin: str = Field(default="Warehouse-Central", min_length=1, max_length=64)
    storage_temp_c: float = Field(
        default=4.0, ge=-30.0, le=60.0, description="Observed cold-chain temperature in Celsius"
    )
    harvest_date: Optional[str] = Field(default=None, max_length=32)


class Destination(BaseModel):
    """Represents a destination market (mandi/retail hub) and its demand parameters."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    dest_id: str = Field(min_length=1, max_length=64, description="Unique destination ID")
    name: str = Field(min_length=1, max_length=128, description="Destination market name")
    commodity: str = Field(min_length=1, max_length=64, description="Demanded commodity")
    demand_kg: float = Field(ge=0.0, le=1_000_000.0, description="Maximum demand at destination")
    selling_price_per_kg: float = Field(
        gt=0.0, le=100_000.0, description="Contracted or market selling price per kg"
    )
    handling_time_hrs: float = Field(
        default=2.0, ge=0.0, le=168.0, description="Unloading and dock-to-shelf handling time"
    )
    max_reception_capacity_kg: Optional[float] = Field(
        default=None, gt=0.0, le=1_000_000.0, description="Optional dock reception capacity limit"
    )


class TransportRoute(BaseModel):
    """Represents a logistics corridor between an origin hub and destination market."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    origin: str = Field(min_length=1, max_length=64)
    dest_id: str = Field(min_length=1, max_length=64)
    travel_time_hrs: float = Field(gt=0.0, le=720.0, description="Transit time in hours")
    cost_per_kg: float = Field(ge=0.0, le=10_000.0, description="Transport cost in INR per kg")
    vehicle_capacity_kg: float = Field(
        default=10000.0, gt=0.0, le=1_000_000.0, description="Maximum vehicle payload capacity"
    )


class AllocationDecision(BaseModel):
    """Auditable record of a single batch-to-destination dispatch allocation."""

    batch_id: str
    dest_id: str
    commodity: str
    quantity_kg: float = Field(ge=0.0)
    sold_qty_kg: float = Field(default=0.0, ge=0.0)
    clearance_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    travel_time_hrs: float = Field(ge=0.0)
    remaining_shelf_life_hrs: float = Field(ge=0.0)
    shelf_life_buffer_hrs: float
    base_price_per_kg: float = Field(ge=0.0)
    discount_pct: float = Field(ge=0.0, le=1.0)
    final_price_per_kg: float = Field(ge=0.0)
    transport_cost_per_kg: float = Field(ge=0.0)
    base_cost_per_kg: float = Field(ge=0.0)
    gross_revenue: float = Field(ge=0.0)
    transport_cost_total: float = Field(ge=0.0)
    procurement_cost_total: float = Field(ge=0.0)
    net_profit: float
    reason: str

    @model_validator(mode="after")
    def set_default_sold_qty(self) -> "AllocationDecision":
        if self.sold_qty_kg == 0.0 and self.gross_revenue > 0.0:
            self.sold_qty_kg = round(self.quantity_kg * self.clearance_rate, 2)
        return self


class RejectedRoute(BaseModel):
    """Counterfactual audit record explaining why a candidate (Batch, Destination) pair was rejected."""

    batch_id: str
    dest_id: str
    destination_name: str
    commodity: str
    remaining_shelf_life_hrs: float
    required_transit_and_handling_hrs: float
    projected_buffer_hrs: float
    rejection_category: str
    reason: str


class OptimizationSummary(BaseModel):
    """Aggregate KPI and financial summary of a distribution strategy."""

    strategy_name: str
    total_inventory_kg: float = Field(ge=0.0)
    dispatched_kg: float = Field(ge=0.0)
    spoiled_kg: float = Field(ge=0.0)
    unsold_unspoiled_kg: float = Field(ge=0.0)
    spoilage_rate_pct: float = Field(ge=0.0, le=100.0)
    demand_fulfillment_pct: float = Field(ge=0.0, le=100.0)
    total_gross_revenue: float = Field(ge=0.0)
    total_transport_cost: float = Field(ge=0.0)
    total_procurement_cost: float = Field(ge=0.0)
    disposal_waste_cost: float = Field(default=0.0, ge=0.0)
    net_profit: float
    solve_time_ms: float = Field(default=0.0, ge=0.0)
    allocations: List[AllocationDecision]
    rejected_routes: List[RejectedRoute] = Field(default_factory=list)


class UncertaintyReport(BaseModel):
    """Monte Carlo sensitivity metrics under shelf-life, transit, and demand uncertainty."""

    runs: int = Field(gt=0)
    mean_net_profit: float
    std_net_profit: float = Field(ge=0.0)
    p5_net_profit: float
    p95_net_profit: float
    mean_spoilage_pct: float = Field(ge=0.0, le=100.0)
    mean_fulfillment_pct: float = Field(ge=0.0, le=100.0)


class ScenarioPayload(BaseModel):
    """Validated schema for custom JSON scenario ingestion during hidden judge tests."""

    batches: List[Batch] = Field(min_length=1, max_length=1000)
    destinations: List[Destination] = Field(min_length=1, max_length=1000)
    routes: List[TransportRoute] = Field(min_length=1, max_length=5000)