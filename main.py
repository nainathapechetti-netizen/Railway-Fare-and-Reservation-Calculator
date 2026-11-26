from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import math


class TravelClass(str, Enum):
    SECOND_SITTING = "2S"
    SLEEPER = "SL"
    AC_3_TIER = "3A"
    AC_2_TIER = "2A"
    AC_1_FIRST = "1A"


class BookingQuota(str, Enum):
    GENERAL = "General"
    TATKAL = "Tatkal"
    LADIES = "Ladies"


class TicketStatus(str, Enum):
    CONFIRMED = "CNF"
    RAC = "RAC"
    WAITLISTED = "WL"


class SpecialConcession(str, Enum):
    NONE = "None"
    SENIOR_CITIZEN = "Senior Citizen"
    STUDENT = "Student"
    DIVYANGJAN = "Divyangjan"


@dataclass(frozen=True)
class DistanceSlab:
    """Represents a telescopic distance bracket (in km) with a marginal rate discount."""
    upper_km: Optional[float]  # None indicates open-ended distance beyond previous slab
    discount_pct: float


@dataclass(frozen=True)
class ClassTariffConfig:
    """Tariff parameters for a single railway travel class."""
    rate_per_km: float
    min_base_fare: float
    reservation_fee: float
    superfast_surcharge: float
    tatkal_surcharge_pct: float
    tatkal_max_cap: float
    flat_cancellation_fee: float   # Per-passenger base clerkage/cancellation fee
    gst_pct: float                 # 5% for AC classes, 0% for Non-AC


@dataclass(frozen=True)
class CancellationSlab:
    """Defines cancellation deduction rules based on hours remaining before departure."""
    min_hours_before_departure: float
    deduction_pct_of_fare: float   # Applied subject to minimum flat_cancellation_fee


@dataclass(frozen=True)
class RailwayTariffPolicy:
    """Master railway pricing, concession, and cancellation penalty configuration."""
    distance_slabs: List[DistanceSlab] = field(
        default_factory=lambda: [
            DistanceSlab(upper_km=100.0, discount_pct=0.0),
            DistanceSlab(upper_km=500.0, discount_pct=10.0),
            DistanceSlab(upper_km=1000.0, discount_pct=20.0),
            DistanceSlab(upper_km=2500.0, discount_pct=30.0),
            DistanceSlab(upper_km=None, discount_pct=40.0),
        ]
    )
    class_configs: Dict[TravelClass, ClassTariffConfig] = field(
        default_factory=lambda: {
            TravelClass.SECOND_SITTING: ClassTariffConfig(0.45, 15.0, 15.0, 15.0, 10.0, 50.0, 60.0, 0.0),
            TravelClass.SLEEPER: ClassTariffConfig(0.75, 35.0, 20.0, 30.0, 30.0, 200.0, 120.0, 0.0),
            TravelClass.AC_3_TIER: ClassTariffConfig(1.95, 105.0, 40.0, 45.0, 40.0, 400.0, 180.0, 5.0),
            TravelClass.AC_2_TIER: ClassTariffConfig(2.80, 180.0, 50.0, 45.0, 50.0, 500.0, 200.0, 5.0),
            TravelClass.AC_1_FIRST: ClassTariffConfig(4.60, 360.0, 60.0, 75.0, 30.0, 600.0, 240.0, 5.0),
        }
    )
    # 2026 Indian Railways confirmed-ticket cancellation slabs (evaluated descending by hours)
    confirmed_cancellation_slabs: List[CancellationSlab] = field(
        default_factory=lambda: [
            CancellationSlab(min_hours_before_departure=72.0, deduction_pct_of_fare=0.0),   # >72h: flat fee only
            CancellationSlab(min_hours_before_departure=24.0, deduction_pct_of_fare=25.0),  # 72h-24h: max(flat, 25%)
            CancellationSlab(min_hours_before_departure=8.0, deduction_pct_of_fare=50.0),   # 24h-8h: max(flat, 50%)
        ]
    )
    rac_wl_clerkage_fee: float = 60.0
    rac_wl_cutoff_minutes: int = 30
    infant_age_limit: int = 5
    child_age_limit: int = 12
    child_no_berth_discount_pct: float = 50.0
    senior_male_min_age: int = 60
    senior_female_min_age: int = 58
    senior_male_concession_pct: float = 40.0
    senior_female_concession_pct: float = 50.0


@dataclass
class Passenger:
    """Represents a single passenger on a railway reservation."""
    name: str
    age: int
    gender: str  # "M", "F", or "O"
    requires_berth: bool = True
    berth_preference: str = "No Preference"
    special_concession: SpecialConcession = SpecialConcession.NONE


@dataclass
class PassengerFareDetail:
    """Itemized fare calculation for an individual passenger."""
    name: str
    age: int
    fare_category: str
    distance_base_fare: float
    age_or_special_discount: float
    tatkal_surcharge: float
    reservation_fee: float
    superfast_fee: float
    gst_amount: float
    net_ticket_fare: float
    berth_allocation_note: str


@dataclass
class ReservationQuote:
    """Complete multi-passenger reservation invoice."""
    train_number: str
    train_name: str
    distance_km: float
    travel_class: TravelClass
    quota: BookingQuota
    is_superfast: bool
    passenger_details: List[PassengerFareDetail]
    total_base_fare: float
    total_discounts: float
    total_fees_and_surcharges: float
    total_gst: float
    grand_total_payable: float


@dataclass
class CancellationRefundDetail:
    """Cancellation penalty and refund breakdown for one passenger."""
    name: str
    ticket_status: TicketStatus
    original_fare_paid: float
    cancellation_penalty: float
    gst_on_penalty: float
    total_deduction: float
    net_refund: float
    applied_rule: str


class RailwayFareAndReservationCalculator:
    """Calculates telescopic fares, age concessions, fees, and cancellation penalties."""

    def __init__(self, policy: Optional[RailwayTariffPolicy] = None):
        self.policy = policy or RailwayTariffPolicy()

    @staticmethod
    def _round_to_nearest_5(amount: float) -> float:
        """Indian Railways rounds base fare components up to the next multiple of ₹5."""
        return float(math.ceil(amount / 5.0) * 5) if amount > 0 else 0.0

    def compute_telescopic_base_fare(self, distance_km: float, travel_class: TravelClass) -> float:
        """Calculates base distance fare across progressive telescopic distance slabs."""
        if distance_km <= 0:
            raise ValueError("Distance must be greater than 0 km.")

        cfg = self.policy.class_configs[travel_class]
        remaining_km = distance_km
        prev_upper = 0.0
        raw_fare = 0.0

        for slab in self.policy.distance_slabs:
            if remaining_km <= 0:
                break

            if slab.upper_km is None:
                slab_km = remaining_km
            else:
                band_width = slab.upper_km - prev_upper
                if band_width <= 0:
                    raise ValueError("Distance slabs must be strictly increasing.")
                slab_km = min(remaining_km, band_width)
                prev_upper = slab.upper_km

            discounted_rate = cfg.rate_per_km * (1.0 - slab.discount_pct / 100.0)
            raw_fare += slab_km * discounted_rate
            remaining_km -= slab_km

        rounded_fare = self._round_to_nearest_5(raw_fare)
        return max(cfg.min_base_fare, rounded_fare)

    def _evaluate_age_and_concession(
        self,
        passenger: Passenger,
        adult_base_fare: float,
        travel_class: TravelClass,
        quota: BookingQuota,
    ) -> Tuple[str, float, float]:
        """
        Determines passenger fare category, applicable base fare, and concession discount.
        Returns: (fare_category_label, gross_base_for_passenger, concession_discount_amount)
        """
        if passenger.age < 0 or passenger.age > 130:
            raise ValueError(f"Invalid passenger age: {passenger.age}")

        # 1. Infant (< 5 years): Free travel without separate berth
        if passenger.age < self.policy.infant_age_limit:
            return "Infant (<5 yrs - Free)", 0.0, 0.0

        # 2. Child (5 to < 12 years): 50% base fare if no separate berth; full fare if berth requested
        if passenger.age < self.policy.child_age_limit:
            if not passenger.requires_berth:
                half_fare = self._round_to_nearest_5(
                    adult_base_fare * (1.0 - self.policy.child_no_berth_discount_pct / 100.0)
                )
                return "Child (No Berth - 50%)", adult_base_fare, adult_base_fare - half_fare
            return "Child (Full Berth)", adult_base_fare, 0.0

        # 3. Tatkal quota disables age/special concessions
        if quota == BookingQuota.TATKAL:
            return "Adult (Tatkal - No Concession)", adult_base_fare, 0.0

        gender_norm = passenger.gender.strip().upper()
        concession_pct = 0.0
        category_label = "Adult (Full Fare)"

        # Age-based Senior Citizen eligibility
        is_senior = (
            (gender_norm == "M" and passenger.age >= self.policy.senior_male_min_age)
            or (gender_norm == "F" and passenger.age >= self.policy.senior_female_min_age)
            or (gender_norm not in {"M", "F"} and passenger.age >= self.policy.senior_male_min_age)
        )

        if is_senior or passenger.special_concession == SpecialConcession.SENIOR_CITIZEN:
            concession_pct = (
                self.policy.senior_female_concession_pct
                if gender_norm == "F"
                else self.policy.senior_male_concession_pct
            )
            category_label = f"Senior Citizen ({concession_pct:.0f}% off)"
        elif passenger.special_concession == SpecialConcession.STUDENT:
            if travel_class in {TravelClass.SECOND_SITTING, TravelClass.SLEEPER}:
                concession_pct = 50.0
                category_label = "Student (50% off)"
        elif passenger.special_concession == SpecialConcession.DIVYANGJAN:
            concession_pct = (
                75.0
                if travel_class in {TravelClass.SECOND_SITTING, TravelClass.SLEEPER, TravelClass.AC_3_TIER}
                else 50.0
            )
            category_label = f"Divyangjan ({concession_pct:.0f}% off)"

        discount_amt = self._round_to_nearest_5(adult_base_fare * (concession_pct / 100.0))
        return category_label, adult_base_fare, discount_amt

    def calculate_reservation(
        self,
        train_number: str,
        train_name: str,
        distance_km: float,
        travel_class: TravelClass,
        passengers: List[Passenger],
        quota: BookingQuota = BookingQuota.GENERAL,
        is_superfast: bool = True,
    ) -> ReservationQuote:
        """Calculates full multi-passenger reservation fares, fees, and taxes."""
        if not passengers:
            raise ValueError("At least one passenger is required.")
        if len(passengers) > 6:
            raise ValueError("Maximum 6 passengers allowed per single reservation PNR.")
        if quota == BookingQuota.TATKAL and len(passengers) > 4:
            raise ValueError("Maximum 4 passengers allowed per Tatkal PNR.")

        cfg = self.policy.class_configs[travel_class]
        adult_base_fare = self.compute_telescopic_base_fare(distance_km, travel_class)
        details: List[PassengerFareDetail] = []

        for p in passengers:
            if p.age < self.policy.infant_age_limit:
                details.append(
                    PassengerFareDetail(
                        name=p.name,
                        age=p.age,
                        fare_category="Infant (<5 yrs - Free)",
                        distance_base_fare=0.0,
                        age_or_special_discount=0.0,
                        tatkal_surcharge=0.0,
                        reservation_fee=0.0,
                        superfast_fee=0.0,
                        gst_amount=0.0,
                        net_ticket_fare=0.0,
                        berth_allocation_note="Shared with adult (No separate berth)",
                    )
                )
                continue

            cat_label, gross_base, discount = self._evaluate_age_and_concession(
                p, adult_base_fare, travel_class, quota
            )
            net_base = max(0.0, gross_base - discount)

            tatkal_fee = 0.0
            if quota == BookingQuota.TATKAL:
                raw_tatkal = adult_base_fare * (cfg.tatkal_surcharge_pct / 100.0)
                tatkal_fee = min(cfg.tatkal_max_cap, self._round_to_nearest_5(raw_tatkal))

            res_fee = cfg.reservation_fee
            sf_fee = cfg.superfast_surcharge if is_superfast else 0.0

            pre_tax_total = net_base + tatkal_fee + res_fee + sf_fee
            gst = round(pre_tax_total * (cfg.gst_pct / 100.0), 2)
            net_fare = float(math.ceil(pre_tax_total + gst))

            gender_norm = p.gender.strip().upper()
            if p.age >= 60 or (gender_norm == "F" and p.age >= 45):
                berth_note = "Priority Lower Berth Quota"
            elif p.age < self.policy.child_age_limit and not p.requires_berth:
                berth_note = "No Separate Berth (NOSB)"
            else:
                berth_note = p.berth_preference

            details.append(
                PassengerFareDetail(
                    name=p.name,
                    age=p.age,
                    fare_category=cat_label,
                    distance_base_fare=gross_base,
                    age_or_special_discount=discount,
                    tatkal_surcharge=tatkal_fee,
                    reservation_fee=res_fee,
                    superfast_fee=sf_fee,
                    gst_amount=gst,
                    net_ticket_fare=net_fare,
                    berth_allocation_note=berth_note,
                )
            )

        return ReservationQuote(
            train_number=train_number,
            train_name=train_name,
            distance_km=distance_km,
            travel_class=travel_class,
            quota=quota,
            is_superfast=is_superfast,
            passenger_details=details,
            total_base_fare=round(sum(d.distance_base_fare for d in details), 2),
            total_discounts=round(sum(d.age_or_special_discount for d in details), 2),
            total_fees_and_surcharges=round(
                sum(d.tatkal_surcharge + d.reservation_fee + d.superfast_fee for d in details), 2
            ),
            total_gst=round(sum(d.gst_amount for d in details), 2),
            grand_total_payable=round(sum(d.net_ticket_fare for d in details), 2),
        )

    def calculate_cancellation_refund(
        self,
        passenger_detail: PassengerFareDetail,
        travel_class: TravelClass,
        quota: BookingQuota,
        ticket_status: TicketStatus,
        hours_before_departure: float,
        train_cancelled_by_railway: bool = False,
    ) -> CancellationRefundDetail:
        """
        Computes cancellation penalties and net refund per passenger based on:
        - Ticket status (CNF, RAC, WL)
        - Quota (Confirmed Tatkal = 0% refund unless train cancelled)
        - Hours remaining before scheduled departure
        - Class flat clerkage vs percentage slab + GST on penalty
        """
        fare_paid = passenger_detail.net_ticket_fare
        if fare_paid == 0.0:
            return CancellationRefundDetail(
                name=passenger_detail.name,
                ticket_status=ticket_status,
                original_fare_paid=0.0,
                cancellation_penalty=0.0,
                gst_on_penalty=0.0,
                total_deduction=0.0,
                net_refund=0.0,
                applied_rule="Zero-fare infant ticket",
            )

        if train_cancelled_by_railway:
            return CancellationRefundDetail(
                name=passenger_detail.name,
                ticket_status=ticket_status,
                original_fare_paid=fare_paid,
                cancellation_penalty=0.0,
                gst_on_penalty=0.0,
                total_deduction=0.0,
                net_refund=fare_paid,
                applied_rule="100% Full Refund (Train Cancelled by Railway)",
            )

        cfg = self.policy.class_configs[travel_class]
        minutes_before = hours_before_departure * 60.0

        # 1. RAC / Waitlisted tickets
        if ticket_status in {TicketStatus.RAC, TicketStatus.WAITLISTED}:
            if minutes_before < self.policy.rac_wl_cutoff_minutes:
                return CancellationRefundDetail(
                    name=passenger_detail.name,
                    ticket_status=ticket_status,
                    original_fare_paid=fare_paid,
                    cancellation_penalty=fare_paid,
                    gst_on_penalty=0.0,
                    total_deduction=fare_paid,
                    net_refund=0.0,
                    applied_rule=f"No refund (<{self.policy.rac_wl_cutoff_minutes} mins before departure)",
                )
            base_penalty = self.policy.rac_wl_clerkage_fee
            gst_penalty = round(base_penalty * (cfg.gst_pct / 100.0), 2)
            total_ded = min(fare_paid, round(base_penalty + gst_penalty, 2))
            return CancellationRefundDetail(
                name=passenger_detail.name,
                ticket_status=ticket_status,
                original_fare_paid=fare_paid,
                cancellation_penalty=base_penalty,
                gst_on_penalty=gst_penalty,
                total_deduction=total_ded,
                net_refund=round(max(0.0, fare_paid - total_ded), 2),
                applied_rule=f"RAC/WL flat clerkage (₹{base_penalty:.0f} + GST)",
            )

        # 2. Confirmed Tatkal ticket (Non-refundable)
        if quota == BookingQuota.TATKAL and ticket_status == TicketStatus.CONFIRMED:
            return CancellationRefundDetail(
                name=passenger_detail.name,
                ticket_status=ticket_status,
                original_fare_paid=fare_paid,
                cancellation_penalty=fare_paid,
                gst_on_penalty=0.0,
                total_deduction=fare_paid,
                net_refund=0.0,
                applied_rule="Confirmed Tatkal ticket (Non-refundable)",
            )

        # 3. Confirmed General/Ladies ticket evaluated against time-window slabs
        sorted_slabs = sorted(
            self.policy.confirmed_cancellation_slabs,
            key=lambda s: s.min_hours_before_departure,
            reverse=True,
        )

        matched_slab: Optional[CancellationSlab] = None
        for slab in sorted_slabs:
            if hours_before_departure >= slab.min_hours_before_departure:
                matched_slab = slab
                break

        if matched_slab is None:
            min_cutoff = sorted_slabs[-1].min_hours_before_departure
            return CancellationRefundDetail(
                name=passenger_detail.name,
                ticket_status=ticket_status,
                original_fare_paid=fare_paid,
                cancellation_penalty=fare_paid,
                gst_on_penalty=0.0,
                total_deduction=fare_paid,
                net_refund=0.0,
                applied_rule=f"Closed window (<{min_cutoff:.0f}h before departure - No Refund)",
            )

        pct_penalty = fare_paid * (matched_slab.deduction_pct_of_fare / 100.0)
        base_penalty = max(cfg.flat_cancellation_fee, pct_penalty)
        gst_penalty = round(base_penalty * (cfg.gst_pct / 100.0), 2)
        total_ded = min(fare_paid, round(base_penalty + gst_penalty, 2))
        net_refund = round(max(0.0, fare_paid - total_ded), 2)

        rule_desc = (
            f">{matched_slab.min_hours_before_departure:.0f}h window: "
            f"max(Flat ₹{cfg.flat_cancellation_fee:.0f}, {matched_slab.deduction_pct_of_fare:.0f}% fare) + GST"
        )

        return CancellationRefundDetail(
            name=passenger_detail.name,
            ticket_status=ticket_status,
            original_fare_paid=fare_paid,
            cancellation_penalty=round(base_penalty, 2),
            gst_on_penalty=gst_penalty,
            total_deduction=total_ded,
            net_refund=net_refund,
            applied_rule=rule_desc,
        )


# --- Example Execution ---
if __name__ == "__main__":
    calculator = RailwayFareAndReservationCalculator()

    passengers = [
        Passenger("Ramesh Iyer", age=64, gender="M", berth_preference="Lower"),
        Passenger("Lakshmi Iyer", age=60, gender="F", berth_preference="Lower"),
        Passenger("Vikram Iyer", age=34, gender="M", berth_preference="Side Upper"),
        Passenger("Ananya Iyer", age=9, gender="F", requires_berth=False),
        Passenger("Kabir Iyer", age=3, gender="M", requires_berth=False),
    ]

    quote = calculator.calculate_reservation(
        train_number="12622",
        train_name="Tamil Nadu Superfast Express",
        distance_km=780.0,
        travel_class=TravelClass.AC_3_TIER,
        passengers=passengers,
        quota=BookingQuota.GENERAL,
        is_superfast=True,
    )

    print(f"PNR FARE QUOTE | Train: {quote.train_number} {quote.train_name} ({quote.distance_km:.0f} km | {quote.travel_class.value})")
    print("-" * 105)
    print(f"{'PASSENGER':<15} {'AGE':<4} {'FARE CATEGORY':<26} {'BASE':<8} {'DISC':<8} {'FEES':<7} {'GST':<7} {'NET FARE':<9} {'BERTH NOTE'}")
    print("-" * 105)
    for d in quote.passenger_details:
        fees = d.reservation_fee + d.superfast_fee + d.tatkal_surcharge
        print(
            f"{d.name:<15} {d.age:<4} {d.fare_category:<26} {d.distance_base_fare:<8.2f} "
            f"-{d.age_or_special_discount:<7.2f} {fees:<7.2f} {d.gst_amount:<7.2f} "
            f"{d.net_ticket_fare:<9.2f} {d.berth_allocation_note}"
        )
    print("-" * 105)
    print(f"GRAND TOTAL PAYABLE: INR {quote.grand_total_payable:,.2f}\n")

    # Simulate cancellation 36 hours before departure (falls into 72h - 24h window: max(flat, 25%) + GST)
    print("CANCELLATION SIMULATION (36 Hours Before Departure - Confirmed Tickets):")
    print("-" * 105)
    for d in quote.passenger_details:
        refund = calculator.calculate_cancellation_refund(
            passenger_detail=d,
            travel_class=TravelClass.AC_3_TIER,
            quota=BookingQuota.GENERAL,
            ticket_status=TicketStatus.CONFIRMED,
            hours_before_departure=36.0,
        )
        print(
            f"{refund.name:<15} | Paid: {refund.original_fare_paid:>7.2f} | "
            f"Deduction: -{refund.total_deduction:>6.2f} | Refund: {refund.net_refund:>7.2f} | "
            f"Rule: {refund.applied_rule}"
        )
