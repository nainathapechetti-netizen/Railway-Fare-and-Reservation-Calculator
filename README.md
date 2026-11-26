# Railway-Fare-and-Reservation-Calculator
# Railway Fare and Reservation Calculator

A comprehensive railway ticketing, concession, and cancellation refund engine built in Python. It calculates multi-passenger reservation quotes using **telescopic distance slabs**, **travel class tariffs**, **age-based and special concessions**, **reservation/superfast/Tatkal fees**, and **time-windowed cancellation penalties**.

---

## Core Features

1. **Telescopic Distance Pricing:** Computes marginal per-kilometer fares across progressive distance brackets (`0–100 km`, `101–500 km`, `501–1000 km`, `1001–2500 km`, `>2500 km`), rounded up to the nearest `₹5` and floored at each class's minimum base fare.
2. **Multi-Class & Quota Support:** Supports `2S` (Second Sitting), `SL` (Sleeper), `3A` (AC 3-Tier), `2A` (AC 2-Tier), and `1A` (AC First Class) across `General`, `Ladies`, and `Tatkal` quotas, adding reservation fees, superfast surcharges, and `5%` GST on AC classes.
3. **Age-Based & Special Concessions:**
   - **Infants (`< 5` years):** Free travel without a separate berth.
   - **Children (`5` to `< 12` years):** `50%` base fare when opting out of a separate berth (`NOSB`), or full fare when requesting a berth.
   - **Senior Citizens:** `40%` discount for men (`60+`) and `50%` discount for women (`58+`), plus automatic Lower Berth quota allocation.
   - **Student & Divyangjan:** Class-specific concession percentages (`50%` to `75%`), automatically disabled on Tatkal bookings.
4. **Cancellation Penalty & Refund Engine:**
   - **Confirmed Tickets:** Evaluates time remaining before departure (`>72h`: flat fee; `72–24h`: `max(flat, 25%)`; `24–8h`: `max(flat, 50%)`; `<8h`: no refund) plus `5%` GST on AC cancellation fees.
   - **RAC / Waitlisted Tickets:** Deducts flat `₹60` clerkage (+ GST on AC classes) if cancelled at least `30 minutes` before departure.
   - **Tatkal & Railway Cancellations:** Enforces zero refund on confirmed Tatkal tickets and `100%` full refund when the train is cancelled by the railway.

---

## Project Structure

```text
├── railway_fare_calculator.py   # Policy config, telescopic fare calculator, concession engine, cancellation rules & demo
└── README.md                    # System documentation
