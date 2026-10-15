"""engine/data_generator.py: Dataset generator, cold-chain telemetry, and disruption scenarios."""

from typing import List, Tuple
from .models import Batch, Destination, TransportRoute


def get_standard_scenario() -> Tuple[List[Batch], List[Destination], List[TransportRoute]]:
    """Standard Indian agricultural corridor scenario: Nashik Hub to Mumbai, Pune, Surat, and Goa."""
    origin = "Hub-Nashik"

    batches = [
        # Highly perishable: Tomatoes
        Batch(
            batch_id="B-TOM-01",
            commodity="Tomato",
            quantity_kg=3000,
            remaining_shelf_life_hrs=18.0,
            base_cost_per_kg=15.0,
            origin=origin,
            storage_temp_c=4.0,
        ),
        Batch(
            batch_id="B-TOM-02",
            commodity="Tomato",
            quantity_kg=4000,
            remaining_shelf_life_hrs=36.0,
            base_cost_per_kg=14.0,
            origin=origin,
            storage_temp_c=4.0,
        ),
        Batch(
            batch_id="B-TOM-03",
            commodity="Tomato",
            quantity_kg=2500,
            remaining_shelf_life_hrs=10.0,
            base_cost_per_kg=15.0,
            origin=origin,
            storage_temp_c=4.0,
        ),
        # Ultra perishable: Spinach / Leafy Greens
        Batch(
            batch_id="B-SPN-01",
            commodity="Spinach",
            quantity_kg=1500,
            remaining_shelf_life_hrs=14.0,
            base_cost_per_kg=22.0,
            origin=origin,
            storage_temp_c=4.0,
        ),
        Batch(
            batch_id="B-SPN-02",
            commodity="Spinach",
            quantity_kg=2000,
            remaining_shelf_life_hrs=8.0,
            base_cost_per_kg=22.0,
            origin=origin,
            storage_temp_c=4.0,
        ),
        # Medium perishable: Mangoes (Alphonso)
        Batch(
            batch_id="B-MNG-01",
            commodity="Mango",
            quantity_kg=2000,
            remaining_shelf_life_hrs=72.0,
            base_cost_per_kg=60.0,
            origin=origin,
            storage_temp_c=4.0,
        ),
        Batch(
            batch_id="B-MNG-02",
            commodity="Mango",
            quantity_kg=1800,
            remaining_shelf_life_hrs=48.0,
            base_cost_per_kg=62.0,
            origin=origin,
            storage_temp_c=4.0,
        ),
        # Storable: Onions
        Batch(
            batch_id="B-ONI-01",
            commodity="Onion",
            quantity_kg=5000,
            remaining_shelf_life_hrs=240.0,
            base_cost_per_kg=18.0,
            origin=origin,
            storage_temp_c=4.0,
        ),
        Batch(
            batch_id="B-ONI-02",
            commodity="Onion",
            quantity_kg=6000,
            remaining_shelf_life_hrs=180.0,
            base_cost_per_kg=17.5,
            origin=origin,
            storage_temp_c=4.0,
        ),
    ]

    destinations = [
        # Mumbai APMC Mandi (Close, high demand, medium price)
        Destination(
            dest_id="DEST-MUM",
            name="Mumbai Vashi Mandi",
            commodity="Tomato",
            demand_kg=4000,
            selling_price_per_kg=32.0,
            handling_time_hrs=2.0,
        ),
        Destination(
            dest_id="DEST-MUM-S",
            name="Mumbai Retail Hub",
            commodity="Spinach",
            demand_kg=2200,
            selling_price_per_kg=45.0,
            handling_time_hrs=1.5,
        ),
        Destination(
            dest_id="DEST-MUM-M",
            name="Mumbai Export Term",
            commodity="Mango",
            demand_kg=2500,
            selling_price_per_kg=120.0,
            handling_time_hrs=3.0,
        ),
        Destination(
            dest_id="DEST-MUM-O",
            name="Mumbai Wholesale",
            commodity="Onion",
            demand_kg=6000,
            selling_price_per_kg=28.0,
            handling_time_hrs=2.0,
        ),
        # Pune Regional Market (Very close, lower price)
        Destination(
            dest_id="DEST-PUN",
            name="Pune Gultekdi Mandi",
            commodity="Tomato",
            demand_kg=3500,
            selling_price_per_kg=26.0,
            handling_time_hrs=1.5,
        ),
        Destination(
            dest_id="DEST-PUN-S",
            name="Pune Local Markets",
            commodity="Spinach",
            demand_kg=1500,
            selling_price_per_kg=38.0,
            handling_time_hrs=1.0,
        ),
        # Surat Commercial Center (Medium distance, high tomato prices)
        Destination(
            dest_id="DEST-SUR",
            name="Surat Agro Market",
            commodity="Tomato",
            demand_kg=3000,
            selling_price_per_kg=35.0,
            handling_time_hrs=2.5,
        ),
        Destination(
            dest_id="DEST-SUR-O",
            name="Surat Wholesale",
            commodity="Onion",
            demand_kg=5000,
            selling_price_per_kg=30.0,
            handling_time_hrs=2.0,
        ),
        # Goa Premium Coastal Market (Far, high prices for mango & vegetables)
        Destination(
            dest_id="DEST-GOA-M",
            name="Goa Supermarkets",
            commodity="Mango",
            demand_kg=1500,
            selling_price_per_kg=140.0,
            handling_time_hrs=2.0,
        ),
        Destination(
            dest_id="DEST-GOA-T",
            name="Goa Hospitality Hub",
            commodity="Tomato",
            demand_kg=2000,
            selling_price_per_kg=40.0,
            handling_time_hrs=2.0,
        ),
    ]

    routes = [
        # To Mumbai
        TransportRoute(
            origin=origin, dest_id="DEST-MUM", travel_time_hrs=4.5, cost_per_kg=2.5, vehicle_capacity_kg=8000
        ),
        TransportRoute(
            origin=origin, dest_id="DEST-MUM-S", travel_time_hrs=4.5, cost_per_kg=3.0, vehicle_capacity_kg=4000
        ),
        TransportRoute(
            origin=origin, dest_id="DEST-MUM-M", travel_time_hrs=5.0, cost_per_kg=4.0, vehicle_capacity_kg=5000
        ),
        TransportRoute(
            origin=origin, dest_id="DEST-MUM-O", travel_time_hrs=4.5, cost_per_kg=2.0, vehicle_capacity_kg=10000
        ),
        # To Pune
        TransportRoute(
            origin=origin, dest_id="DEST-PUN", travel_time_hrs=3.0, cost_per_kg=1.8, vehicle_capacity_kg=7000
        ),
        TransportRoute(
            origin=origin, dest_id="DEST-PUN-S", travel_time_hrs=3.0, cost_per_kg=2.2, vehicle_capacity_kg=3000
        ),
        # To Surat
        TransportRoute(
            origin=origin, dest_id="DEST-SUR", travel_time_hrs=7.0, cost_per_kg=3.8, vehicle_capacity_kg=6000
        ),
        TransportRoute(
            origin=origin, dest_id="DEST-SUR-O", travel_time_hrs=7.0, cost_per_kg=3.2, vehicle_capacity_kg=8000
        ),
        # To Goa (Long haul: 14 hrs transit)
        TransportRoute(
            origin=origin, dest_id="DEST-GOA-M", travel_time_hrs=14.0, cost_per_kg=7.5, vehicle_capacity_kg=4000
        ),
        TransportRoute(
            origin=origin, dest_id="DEST-GOA-T", travel_time_hrs=14.0, cost_per_kg=7.0, vehicle_capacity_kg=4000
        ),
    ]

    return batches, destinations, routes


def apply_disruption(
    routes: List[TransportRoute],
    destinations: List[Destination],
    delay_hours: float = 6.0,
    demand_shock_pct: float = -0.30,
    capacity_reduction_pct: float = 0.0,
) -> Tuple[List[TransportRoute], List[Destination]]:
    """Simulates realistic supply-chain complications (highway delays, demand shocks, fleet reduction)."""
    if delay_hours < 0:
        raise ValueError("delay_hours must be non-negative.")
    if not -1.0 <= demand_shock_pct <= 5.0:
        raise ValueError("demand_shock_pct must be between -1.0 and 5.0.")
    if not 0.0 <= capacity_reduction_pct < 1.0:
        raise ValueError("capacity_reduction_pct must be in [0.0, 1.0).")

    disrupted_routes = [
        r.model_copy(
            update={
                "travel_time_hrs": round(r.travel_time_hrs + delay_hours, 2),
                "vehicle_capacity_kg": max(1.0, round(r.vehicle_capacity_kg * (1.0 - capacity_reduction_pct), 2)),
            }
        )
        for r in routes
    ]

    disrupted_dests = [
        d.model_copy(
            update={
                "demand_kg": max(0.0, round(d.demand_kg * (1.0 + demand_shock_pct), 2)),
            }
        )
        for d in destinations
    ]

    return disrupted_routes, disrupted_dests


def apply_temperature_excursion(
    batches: List[Batch],
    ambient_temp_c: float = 4.0,
    reference_temp_c: float = 4.0,
    q10_factor: float = 2.0,
) -> List[Batch]:
    """
    Adjusts batch remaining shelf life using the biological Q10 thermal respiration law:
    Effective Shelf Life = Nominal Shelf Life / (Q10 ^ ((T_actual - T_ref) / 10)).
    """
    if ambient_temp_c <= reference_temp_c:
        return [b.model_copy(update={"storage_temp_c": ambient_temp_c}) for b in batches]

    acceleration = q10_factor ** ((ambient_temp_c - reference_temp_c) / 10.0)
    adjusted_batches: List[Batch] = []
    for b in batches:
        # Storable dry bulbs (Onion) are less sensitive to cold-chain excursion than wet produce
        effective_accel = 1.0 + (acceleration - 1.0) * (0.25 if b.commodity == "Onion" else 1.0)
        new_shelf_life = max(1.0, round(b.remaining_shelf_life_hrs / effective_accel, 1))
        adjusted_batches.append(
            b.model_copy(
                update={
                    "remaining_shelf_life_hrs": new_shelf_life,
                    "storage_temp_c": ambient_temp_c,
                }
            )
        )
    return adjusted_batches