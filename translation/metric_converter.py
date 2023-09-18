import re

# Imperial
# Put the longuest first for the regexp match
METRIC_FEET = ["ft"]
METRIC_FEET_LONG = ["feets", "foots", "feet", "foot"]
METRIC_YARD = ["yd"]
METRIC_YARD_LONG = ["yard"]
METRIC_MILE = ["mi"]
METRIC_MILE_LONG = ["miles", "mile"]
METRIC_POUND = ["lb"]
METRIC_POUND_LONG = ["pounds", "pound"]

# Metric
METRIC_METER = "m"
METRIC_METER_LONG = "metre"
METRIC_KILOMETER = "km"
METRIC_KILOMETER_LONG = "kilometer"
METRIC_KILOGRAM = "kg"
METRIC_KILOGRAM_LONG = "kilogramm"


def convertMetric(unit: str, value: float):
    # Dnd Official conversion are rounded, these are not the true values
    MILES_TO_KILOMETRES = 1.5
    FEET_TO_METRES = 0.3
    YARDS_TO_METRES = 0.9
    POUNDS_TO_KILOGRAMS = 0.5

    out_unit = None

    if unit in METRIC_FEET + METRIC_YARD:
        out_unit = METRIC_METER
    elif unit in METRIC_FEET_LONG + METRIC_YARD_LONG:
        out_unit = METRIC_METER_LONG
    elif unit in METRIC_MILE:
        out_unit = METRIC_KILOMETER
    elif unit in METRIC_MILE_LONG:
        out_unit = METRIC_KILOMETER_LONG
    elif unit in METRIC_POUND:
        out_unit = METRIC_KILOGRAM
    elif unit in METRIC_POUND_LONG:
        out_unit = METRIC_KILOGRAM_LONG
    else:
        raise Exception("Metric converter unknowed unit")
    out_value = None

    if unit in METRIC_FEET + METRIC_FEET_LONG:
        out_value = value * FEET_TO_METRES
    elif unit in METRIC_YARD + METRIC_YARD_LONG:
        out_value = value * YARDS_TO_METRES
    elif unit in METRIC_MILE + METRIC_MILE_LONG:
        out_value = value * MILES_TO_KILOMETRES
    elif unit in METRIC_POUND + METRIC_POUND_LONG:
        out_value = value * POUNDS_TO_KILOGRAMS

    # Never pluralize shortform. Those are symbols.
    metrics_to_pluralize = (
        METRIC_FEET_LONG + METRIC_YARD_LONG + METRIC_MILE_LONG + METRIC_POUND_LONG
    )
    if out_value > 1 and out_unit in metrics_to_pluralize:
        out_unit += "s"

    # Format the out_value to have two decimals with rounding
    formatted_value = "{:.2f}".format(out_value)
    # Remove all trailing zeros and the decimal point if it's an integer
    while formatted_value.endswith("0") or formatted_value.endswith("."):
        formatted_value = formatted_value[:-1]
    return formatted_value, out_unit


def convertToMetric(text: str):
    # Match the long first !
    all_metrics = (
        METRIC_FEET_LONG
        + METRIC_FEET
        + METRIC_YARD_LONG
        + METRIC_YARD
        + METRIC_MILE_LONG
        + METRIC_MILE
        + METRIC_POUND_LONG
        + METRIC_POUND
    )
    # Formats seen
    # 5 ft, 5 feet, 5-feet-long, 5-feet, 5-feet-radious
    pattern = r"(\d+)([\s-]*)({})\b".format(
        "|".join(
            map(
                re.escape,
                all_metrics,
            )
        )
    )

    def replace_metric(match):
        value = float(match.group(1))
        unit = match.group(3).lower()
        converted_value, converted_unit = convertMetric(unit, value)
        return f"{converted_value}{match.group(2)}{converted_unit}"

    result_text = re.sub(
        pattern,
        replace_metric,
        text,
        flags=re.IGNORECASE,
    )
    return result_text
