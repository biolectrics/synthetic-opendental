#!/usr/bin/env python3
"""
Synthetic Open Dental Database Generator

Generates realistic synthetic data for Open Dental MySQL databases.
Zero real patient data - all names, addresses, SSNs, and details are computer-generated.

Usage:
    python generate.py                                    # 750 patients, random US city
    python generate.py --patients 500 --output data.sql   # Custom patient count
    python generate.py --city "Chicago" --state "IL"      # Specific metro area
    python generate.py --seed 12345                       # Reproducible output

Output: SQL INSERT statements compatible with Open Dental database schema.

For more information: https://github.com/dentaljosh/synthetic-opendental
Built by the team at Luna (https://yourluna.co)
"""

import argparse
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from collections import defaultdict

from faker import Faker

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_SEED = 42
DEFAULT_PATIENT_COUNT = 750

# Age distribution percentages (based on US dental patient demographics)
AGE_DISTRIBUTION = [
    (0, 12, 0.024),    # 2.4% ages 0-12
    (13, 17, 0.006),   # 0.6% ages 13-17
    (18, 34, 0.464),   # 46.4% ages 18-34
    (35, 54, 0.354),   # 35.4% ages 35-54
    (55, 64, 0.076),   # 7.6% ages 55-64
    (65, 90, 0.077),   # 7.7% ages 65+
]

# Insurance carrier distribution (of the 53% with dental insurance)
INSURANCE_CARRIERS = [
    ("MetLife Dental", 0.08),
    ("Cigna Dental", 0.093),
    ("Delta Dental", 0.115),
    ("Aetna Dental", 0.061),
    ("Guardian Dental", 0.045),
    ("United Healthcare Dental", 0.027),
    ("BlueCross BlueShield Dental", 0.05),
    ("Humana Dental", 0.03),
    ("Principal Dental", 0.029),
]

# =============================================================================
# STARTING IDs (high numbers to avoid collisions with existing data)
# =============================================================================

PROVIDER_START_NUM = 100
OPERATORY_START_NUM = 100

# Providers (will be numbered 100, 101, 102, 103)
PROVIDERS = [
    {"abbr": "SC", "lname": "Chen", "fname": "Sarah", "suffix": "DMD", "is_secondary": 0},
    {"abbr": "MT", "lname": "Torres", "fname": "Michael", "suffix": "DDS", "is_secondary": 0},
    {"abbr": "AR", "lname": "Rodriguez", "fname": "Amy", "suffix": "RDH", "is_secondary": 1},
    {"abbr": "JW", "lname": "Williams", "fname": "Jessica", "suffix": "RDH", "is_secondary": 1},
]

# Operatories (will be numbered 100, 101, 102, 103)
OPERATORIES = [
    {"name": "Op 1", "abbrev": "Op-1", "is_hygiene": 0, "prov_dentist": 100, "prov_hygienist": 0},
    {"name": "Op 2", "abbrev": "Op-2", "is_hygiene": 0, "prov_dentist": 101, "prov_hygienist": 0},
    {"name": "Op 3", "abbrev": "Op-3", "is_hygiene": 1, "prov_dentist": 0, "prov_hygienist": 102},
    {"name": "Op 4", "abbrev": "Op-4", "is_hygiene": 1, "prov_dentist": 0, "prov_hygienist": 103},
]

# =============================================================================
# OPEN DENTAL CodeNum MAPPINGS
# =============================================================================
# These CodeNum values match a standard Open Dental installation.

REAL_CODE_TO_CODENUM = {
    # Exams
    "D0120": 72,   # Periodic oral evaluation
    "D0140": 73,   # Limited oral evaluation
    "D0150": 75,   # Comprehensive oral evaluation
    "D0180": 79,   # Comprehensive periodontal evaluation
    # X-rays
    "D0210": 82,   # Intraoral - complete series
    "D0220": 83,   # Periapical first image
    "D0230": 84,   # Periapical each additional
    "D0274": 91,   # Bitewings - four images
    "D0330": 97,   # Panoramic
    "D0367": 104,  # Cone beam CT
    # Cleanings
    "D1110": 167,  # Prophylaxis - adult
    "D1120": 168,  # Prophylaxis - child
    "D1206": 169,  # Fluoride varnish
    "D1208": 170,  # Fluoride - excluding varnish
    # Perio
    "D4341": 360,  # SRP - 4+ teeth per quadrant
    "D4342": 361,  # SRP - 1-3 teeth per quadrant
    "D4910": 365,  # Periodontal maintenance
    "D4355": 363,  # Full mouth debridement
    # Fillings
    "D2140": 201,  # Amalgam - one surface
    "D2150": 202,  # Amalgam - two surfaces
    "D2391": 210,  # Composite - one surface, posterior
    "D2392": 211,  # Composite - two surfaces, posterior
    "D2393": 212,  # Composite - three surfaces, posterior
    "D2394": 213,  # Composite - four+ surfaces, posterior
    "D2330": 205,  # Composite - one surface, anterior
    "D2331": 206,  # Composite - two surfaces, anterior
    # Crown/Bridge
    "D2740": 240,  # Crown - porcelain/ceramic
    "D2750": 241,  # Crown - porcelain fused to high noble
    "D2950": 268,  # Core buildup
    "D2751": 242,  # Crown - porcelain fused to base metal
    "D6240": 558,  # Pontic - porcelain fused to high noble
    # Oral Surgery
    "D7140": 615,  # Extraction - simple
    "D7210": 616,  # Extraction - surgical
    "D7220": 617,  # Impacted tooth - soft tissue
    "D7230": 618,  # Impacted tooth - partially bony
    "D7240": 619,  # Impacted tooth - completely bony
    "D7953": 735,  # Bone graft for ridge preservation
    # Implants
    "D6010": 478,  # Implant placement
    "D6056": 486,  # Prefabricated abutment
    "D6058": 488,  # Abutment supported crown
    # Endo
    "D3310": 293,  # RCT - anterior
    "D3320": 294,  # RCT - premolar
    "D3330": 295,  # RCT - molar
    "D3346": 299,  # Retreatment - anterior
    # Ortho
    "D8080": 762,  # Comprehensive ortho - adolescent
    "D8090": 763,  # Comprehensive ortho - adult
    "D8670": 767,  # Periodic ortho visit
}

# Procedure code descriptions (for generating procedurecode records)
PROCEDURE_CODE_DESCRIPTIONS = {
    "D0120": "Periodic oral evaluation",
    "D0140": "Limited oral evaluation",
    "D0150": "Comprehensive oral evaluation",
    "D0180": "Comprehensive periodontal evaluation",
    "D0210": "Intraoral - complete series",
    "D0220": "Periapical first image",
    "D0230": "Periapical each additional",
    "D0274": "Bitewings - four images",
    "D0330": "Panoramic",
    "D0367": "Cone beam CT",
    "D1110": "Prophylaxis - adult",
    "D1120": "Prophylaxis - child",
    "D1206": "Fluoride varnish",
    "D1208": "Fluoride - excluding varnish",
    "D4341": "SRP - 4+ teeth per quadrant",
    "D4342": "SRP - 1-3 teeth per quadrant",
    "D4910": "Periodontal maintenance",
    "D4355": "Full mouth debridement",
    "D2140": "Amalgam - one surface, primary or permanent",
    "D2150": "Amalgam - two surfaces, primary or permanent",
    "D2391": "Resin-based composite - one surface, posterior",
    "D2392": "Resin-based composite - two surfaces, posterior",
    "D2393": "Resin-based composite - three surfaces, posterior",
    "D2394": "Resin-based composite - four+ surfaces, posterior",
    "D2330": "Resin-based composite - one surface, anterior",
    "D2331": "Resin-based composite - two surfaces, anterior",
    "D2740": "Crown - porcelain/ceramic substrate",
    "D2750": "Crown - porcelain fused to high noble metal",
    "D2950": "Core buildup, including any pins",
    "D2751": "Crown - porcelain fused to base metal",
    "D6240": "Pontic - porcelain fused to high noble metal",
    "D7140": "Extraction, erupted tooth or exposed root",
    "D7210": "Extraction, erupted tooth requiring elevation",
    "D7220": "Removal of impacted tooth - soft tissue",
    "D7230": "Removal of impacted tooth - partially bony",
    "D7240": "Removal of impacted tooth - completely bony",
    "D7953": "Bone replacement graft for ridge preservation",
    "D6010": "Surgical placement of implant body: endosteal",
    "D6056": "Prefabricated abutment",
    "D6058": "Abutment supported porcelain/ceramic crown",
    "D3310": "Endodontic therapy, anterior tooth",
    "D3320": "Endodontic therapy, premolar tooth",
    "D3330": "Endodontic therapy, molar tooth",
    "D3346": "Retreatment of previous root canal - anterior",
    "D8080": "Comprehensive orthodontic treatment - adolescent",
    "D8090": "Comprehensive orthodontic treatment - adult",
    "D8670": "Periodic orthodontic treatment visit",
}

# =============================================================================
# OPEN DENTAL DefNum MAPPINGS
# =============================================================================

# Category 4 - BillingType
BILLING_TYPE_DEFNUMS = {
    "Standard": 40,
    "BadDebt_Precollections": 41,
    "BadDebt_Collections": 42,
    "Insured": 313,
    "Uninsured": 314,
    "FriendsFamily": 315,
}
DEFAULT_BILLING_TYPE = 40  # Standard

# Category 10 - PaymentTypes
PAYMENT_TYPE_DEFNUMS = {
    "Check": 69,
    "Cash": 70,
    "CreditCard": 71,
    "Visa": 377,
    "Mastercard": 378,
    "AmericanExpress": 379,
    "CareCredit": 380,
    "Discover": 387,
    "DebitCard": 393,
    "EFT": 397,
}

# Category 11 - ProcCodeCats
PROC_CAT_DEFNUMS = {
    "ExamsXrays": 73,
    "Cleanings": 74,
    "Fillings": 75,
    "Endo": 76,
    "Perio": 77,
    "Dentures": 78,
    "Cosmetic": 79,
    "Implants": 80,
    "CrownBridge": 81,
    "OralSurgery": 82,
    "Ortho": 83,
    "Misc": 84,
    "Preventive": 329,
}

# Procedure codes with fees (min, avg, max) and treatment area
# area: 0=None, 1=Surf, 2=Tooth, 3=Mouth, 4=Quad, 5=Sextant, 6=Arch, 7=ToothRange
PROCEDURE_CODES = [
    # Exams
    {"code": "D0120", "cat": "exam", "area": 3, "fees": (28, 96, 250)},
    {"code": "D0140", "cat": "exam", "area": 3, "fees": (10, 82, 200)},
    {"code": "D0150", "cat": "exam", "area": 3, "fees": (12, 117, 200)},
    {"code": "D0180", "cat": "exam", "area": 3, "fees": (50, 95, 175)},

    # X-rays
    {"code": "D0210", "cat": "xray", "area": 3, "fees": (80, 175, 350)},
    {"code": "D0220", "cat": "xray", "area": 2, "fees": (6, 26, 75)},
    {"code": "D0230", "cat": "xray", "area": 2, "fees": (6, 20, 75)},
    {"code": "D0274", "cat": "xray", "area": 3, "fees": (13, 90, 300)},
    {"code": "D0330", "cat": "xray", "area": 3, "fees": (20, 140, 300)},
    {"code": "D0367", "cat": "xray", "area": 3, "fees": (150, 338, 650)},

    # Cleanings
    {"code": "D1110", "cat": "cleaning", "area": 3, "fees": (45, 157, 350)},
    {"code": "D1120", "cat": "cleaning", "area": 3, "fees": (35, 85, 150)},
    {"code": "D1206", "cat": "cleaning", "area": 3, "fees": (20, 45, 85)},
    {"code": "D1208", "cat": "cleaning", "area": 3, "fees": (15, 35, 65)},

    # Perio
    {"code": "D4341", "cat": "perio", "area": 4, "fees": (75, 226, 350)},
    {"code": "D4342", "cat": "perio", "area": 4, "fees": (50, 150, 250)},
    {"code": "D4910", "cat": "perio", "area": 3, "fees": (79, 185, 350)},
    {"code": "D4355", "cat": "perio", "area": 3, "fees": (100, 200, 350)},

    # Fillings
    {"code": "D2140", "cat": "filling", "area": 1, "fees": (75, 145, 275)},
    {"code": "D2150", "cat": "filling", "area": 1, "fees": (95, 185, 350)},
    {"code": "D2391", "cat": "filling", "area": 1, "fees": (58, 167, 450)},
    {"code": "D2392", "cat": "filling", "area": 1, "fees": (125, 234, 500)},
    {"code": "D2393", "cat": "filling", "area": 1, "fees": (150, 285, 550)},
    {"code": "D2394", "cat": "filling", "area": 1, "fees": (175, 335, 600)},
    {"code": "D2330", "cat": "filling", "area": 1, "fees": (55, 155, 400)},
    {"code": "D2331", "cat": "filling", "area": 1, "fees": (75, 195, 450)},

    # Crown/Bridge
    {"code": "D2740", "cat": "crown", "area": 2, "fees": (768, 1113, 1400)},
    {"code": "D2750", "cat": "crown", "area": 2, "fees": (800, 1150, 1450)},
    {"code": "D2950", "cat": "crown", "area": 2, "fees": (150, 285, 400)},
    {"code": "D2751", "cat": "crown", "area": 2, "fees": (700, 950, 1200)},
    {"code": "D6240", "cat": "crown", "area": 2, "fees": (750, 1050, 1350)},

    # Oral Surgery
    {"code": "D7140", "cat": "oralsurg", "area": 2, "fees": (75, 185, 350)},
    {"code": "D7210", "cat": "oralsurg", "area": 2, "fees": (69, 357, 650)},
    {"code": "D7220", "cat": "oralsurg", "area": 2, "fees": (150, 350, 550)},
    {"code": "D7230", "cat": "oralsurg", "area": 2, "fees": (200, 425, 650)},
    {"code": "D7240", "cat": "oralsurg", "area": 2, "fees": (250, 525, 750)},
    {"code": "D7953", "cat": "oralsurg", "area": 2, "fees": (220, 608, 800)},

    # Implants
    {"code": "D6010", "cat": "implant", "area": 2, "fees": (250, 1447, 2000)},
    {"code": "D6056", "cat": "implant", "area": 2, "fees": (300, 650, 900)},
    {"code": "D6058", "cat": "implant", "area": 2, "fees": (800, 1350, 1800)},

    # Endo
    {"code": "D3310", "cat": "endo", "area": 2, "fees": (450, 850, 1200)},
    {"code": "D3320", "cat": "endo", "area": 2, "fees": (550, 950, 1350)},
    {"code": "D3330", "cat": "endo", "area": 2, "fees": (700, 1150, 1600)},
    {"code": "D3346", "cat": "endo", "area": 2, "fees": (550, 950, 1400)},

    # Ortho (limited set)
    {"code": "D8080", "cat": "ortho", "area": 3, "fees": (4000, 5500, 7500)},
    {"code": "D8090", "cat": "ortho", "area": 3, "fees": (4500, 6000, 8000)},
    {"code": "D8670", "cat": "ortho", "area": 3, "fees": (0, 0, 0)},
]

# Category distribution for procedure generation
CATEGORY_WEIGHTS = {
    "exam": 0.26,
    "xray": 0.25,
    "cleaning": 0.11,
    "perio": 0.09,
    "filling": 0.07,
    "crown": 0.04,
    "oralsurg": 0.03,
    "implant": 0.02,
    "endo": 0.02,
    "ortho": 0.02,
}

# Appointment bundles (procedure codes grouped together)
APPOINTMENT_BUNDLES = {
    "new_patient": {
        "codes": ["D0150", "D0274", "D0330", "D1110"],
        "pattern": "XXXXXXXXXXXXXXX",  # 75 min
        "is_hygiene": 0,
        "weight": 0.08,
    },
    "recall_hygiene": {
        "codes": ["D0120", "D0274", "D1110", "D1206"],
        "pattern": "XXXXXXXXXXXX",  # 60 min
        "is_hygiene": 1,
        "weight": 0.35,
    },
    "perio_maintenance": {
        "codes": ["D0120", "D4910"],
        "pattern": "XXXXXXXXX",  # 45 min
        "is_hygiene": 1,
        "weight": 0.10,
    },
    "srp_quad": {
        "codes": ["D4341", "D0220", "D0230"],
        "pattern": "XXXXXXXXXXXXXXX",  # 75 min
        "is_hygiene": 1,
        "weight": 0.06,
    },
    "crown_prep": {
        "codes": ["D2740", "D2950", "D0220"],
        "pattern": "XXXXXXXXXXXXXXXXXXX",  # 95 min
        "is_hygiene": 0,
        "weight": 0.04,
    },
    "extraction_graft": {
        "codes": ["D7210", "D7953", "D0220"],
        "pattern": "XXXXXXXXXXXXXXXXXXXXXXX",  # 115 min
        "is_hygiene": 0,
        "weight": 0.03,
    },
    "implant_placement": {
        "codes": ["D6010", "D7953", "D0220"],
        "pattern": "XXXXXXXXXXXXXXXXXXXXXXX",  # 115 min
        "is_hygiene": 0,
        "weight": 0.02,
    },
    "emergency": {
        "codes": ["D0140", "D0220", "D0230"],
        "pattern": "XXXXXXXXXXXX",  # 60 min
        "is_hygiene": 0,
        "weight": 0.05,
    },
    "filling_single": {
        "codes": ["D2391", "D0220"],
        "pattern": "XXXXXXXXXX",  # 50 min
        "is_hygiene": 0,
        "weight": 0.08,
    },
    "filling_multi": {
        "codes": ["D2392", "D2391", "D0220"],
        "pattern": "XXXXXXXXXXXXXX",  # 70 min
        "is_hygiene": 0,
        "weight": 0.06,
    },
    "root_canal": {
        "codes": ["D3320", "D0220", "D0230"],
        "pattern": "XXXXXXXXXXXXXXXXXXXX",  # 100 min
        "is_hygiene": 0,
        "weight": 0.03,
    },
    "child_prophy": {
        "codes": ["D0120", "D1120", "D1208"],
        "pattern": "XXXXXXXX",  # 40 min
        "is_hygiene": 1,
        "weight": 0.05,
    },
    "limited_exam": {
        "codes": ["D0140", "D0220"],
        "pattern": "XXXXXX",  # 30 min
        "is_hygiene": 0,
        "weight": 0.05,
    },
}

# Note templates
PROC_NOTE_TEMPLATES = [
    "Pt presents for {procedure}. No concerns reported.",
    "Discussed treatment options. Pt to consider.",
    "Completed {procedure} without complications.",
    "Anesthesia: 2% lido 1:100k, 1.7mL. Procedure uneventful.",
    "Pt tolerated procedure well. Post-op instructions given.",
    "No complications. Pt dismissed in stable condition.",
    "Reviewed home care instructions with patient.",
    "{procedure} completed as treatment planned.",
    "Patient reported mild sensitivity. Will monitor.",
    "Routine {procedure}. No abnormal findings.",
]

APPOINTMENT_NOTE_TEMPLATES = [
    "",
    "",
    "",
    "Prefers morning appointments",
    "Prefers afternoon appointments",
    "Needs 2 carpules for numbing",
    "Spanish speaker - daughter translates",
    "Anxious patient - needs extra time",
    "May need premedication",
    "Works nights - flexible scheduling",
    "Insurance verification needed",
    "",
    "",
]

COMMLOG_NOTE_TEMPLATES = [
    "Reminder call - confirmed for {date}",
    "Left voicemail regarding overdue hygiene appointment",
    "Pt called to reschedule - new appt {date}",
    "Discussed treatment plan, pt will call back",
    "Sent appointment reminder via text",
    "Insurance benefits verified",
    "Pt confirmed via text message",
    "Unable to reach - no answer",
    "Pt requested morning callback",
    "Billing question resolved",
    "Pt cancelled appointment - will reschedule",
    "Treatment estimate sent to patient",
]

# Teeth for procedures
POSTERIOR_TEETH = ["2", "3", "4", "5", "12", "13", "14", "15", "18", "19", "20", "21", "28", "29", "30", "31"]
ANTERIOR_TEETH = ["6", "7", "8", "9", "10", "11", "22", "23", "24", "25", "26", "27"]
ALL_TEETH = POSTERIOR_TEETH + ANTERIOR_TEETH

SURFACES = ["M", "O", "D", "B", "L", "MO", "DO", "MOD", "MODBL"]

QUADRANTS = ["UR", "UL", "LR", "LL"]

# Metro areas for address generation
METRO_AREAS = [
    {"city": "New York", "state": "NY", "zips": ["10001", "10002", "10003", "10011", "10012", "10013", "10014", "10016", "10017", "10018", "10019", "10020", "10021", "10022", "10023", "10024", "10025", "10026", "10027", "10028", "10029", "10030"]},
    {"city": "Los Angeles", "state": "CA", "zips": ["90001", "90002", "90003", "90004", "90005", "90006", "90007", "90008", "90010", "90011", "90012", "90013", "90014", "90015", "90016", "90017", "90018", "90019", "90020", "90024"]},
    {"city": "Chicago", "state": "IL", "zips": ["60601", "60602", "60603", "60604", "60605", "60606", "60607", "60608", "60609", "60610", "60611", "60612", "60613", "60614", "60615", "60616", "60617", "60618", "60619", "60620"]},
    {"city": "Houston", "state": "TX", "zips": ["77001", "77002", "77003", "77004", "77005", "77006", "77007", "77008", "77009", "77010", "77011", "77012", "77013", "77014", "77015", "77016", "77017", "77018", "77019", "77020"]},
    {"city": "Phoenix", "state": "AZ", "zips": ["85001", "85002", "85003", "85004", "85005", "85006", "85007", "85008", "85009", "85012", "85013", "85014", "85015", "85016", "85017", "85018", "85019", "85020", "85021", "85022"]},
    {"city": "Philadelphia", "state": "PA", "zips": ["19102", "19103", "19104", "19106", "19107", "19109", "19111", "19114", "19115", "19116", "19118", "19119", "19120", "19121", "19122", "19123", "19124", "19125", "19126", "19127"]},
    {"city": "San Antonio", "state": "TX", "zips": ["78201", "78202", "78203", "78204", "78205", "78207", "78208", "78209", "78210", "78211", "78212", "78213", "78214", "78215", "78216", "78217", "78218", "78219", "78220", "78221"]},
    {"city": "San Diego", "state": "CA", "zips": ["92101", "92102", "92103", "92104", "92105", "92106", "92107", "92108", "92109", "92110", "92111", "92113", "92114", "92115", "92116", "92117", "92118", "92119", "92120", "92121"]},
    {"city": "Dallas", "state": "TX", "zips": ["75201", "75202", "75203", "75204", "75205", "75206", "75207", "75208", "75209", "75210", "75211", "75212", "75214", "75215", "75216", "75217", "75218", "75219", "75220", "75223"]},
    {"city": "Seattle", "state": "WA", "zips": ["98101", "98102", "98103", "98104", "98105", "98106", "98107", "98108", "98109", "98112", "98115", "98116", "98117", "98118", "98119", "98121", "98122", "98125", "98126", "98133"]},
]


# =============================================================================
# SQL GENERATION HELPERS
# =============================================================================

def sql_escape(value: Any) -> str:
    """Escape a value for SQL INSERT statement."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return f"'{value}'"
    # String - escape single quotes
    value = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{value}'"


def generate_insert(table: str, columns: list[str], values: list[Any]) -> str:
    """Generate a SQL INSERT statement."""
    cols = ", ".join(columns)
    vals = ", ".join(sql_escape(v) for v in values)
    return f"INSERT INTO `{table}` ({cols}) VALUES ({vals});"


# =============================================================================
# DATA GENERATOR CLASS
# =============================================================================

class SyntheticDataGenerator:
    def __init__(self, seed: int = DEFAULT_SEED, city: str = None, state: str = None, patient_count: int = DEFAULT_PATIENT_COUNT):
        self.seed = seed
        self.patient_count = patient_count
        random.seed(seed)
        Faker.seed(seed)
        self.fake = Faker('en_US')

        # Select metro area
        if city and state:
            # Try to find matching metro
            metro = next((m for m in METRO_AREAS if m["city"].lower() == city.lower() and m["state"].lower() == state.lower()), None)
            if not metro:
                # Create custom metro
                metro = {"city": city, "state": state, "zips": [f"{random.randint(10000, 99999)}" for _ in range(20)]}
        else:
            metro = random.choice(METRO_AREAS)

        self.metro = metro

        # Initialize counters for primary keys
        # Start high to avoid collisions with existing data
        self.next_pat_num = 10000
        self.next_apt_num = 10000
        self.next_proc_num = 10000
        self.next_procnote_num = 10000
        self.next_recall_num = 10000
        self.next_commlog_num = 10000
        self.next_payment_num = 10000
        self.next_paysplit_num = 10000
        self.next_claimproc_num = 10000
        self.next_carrier_num = 100
        self.next_insplan_num = 100
        self.next_inssub_num = 10000
        self.next_patplan_num = 10000

        # Data storage
        self.providers = []
        self.operatories = []
        self.carriers = []
        self.insplans = []
        self.patients = []
        self.inssubs = []
        self.patplans = []
        self.appointments = []
        self.procedures = []
        self.procnotes = []
        self.recalls = []
        self.commlogs = []
        self.payments = []
        self.paysplits = []
        self.claimprocs = []

        # Use real CodeNum mapping from existing OD database
        self.code_to_codenum = REAL_CODE_TO_CODENUM.copy()

        # Build procedure_codes list from PROCEDURE_CODES with real CodeNums
        self.procedure_codes = []
        for proc in PROCEDURE_CODES:
            code_num = self.code_to_codenum.get(proc["code"])
            if code_num:
                self.procedure_codes.append({
                    "CodeNum": code_num,
                    "ProcCode": proc["code"],
                    "cat": proc["cat"],
                    "fees": proc["fees"],
                    "area": proc["area"],
                })

        # SQL statements
        self.sql_statements = []

        # Date ranges
        self.today = date.today()
        self.history_start = self.today - timedelta(days=3*365)  # 3 years ago
        self.future_end = self.today + timedelta(days=90)  # 3 months ahead

    def generate_all(self) -> list[str]:
        """Generate all synthetic data and return SQL statements."""
        print(f"Generating synthetic data for {self.metro['city']}, {self.metro['state']}...")
        print(f"Seed: {self.seed}, Patients: {self.patient_count}")

        # Generate base reference data first (procedurecode, definition)
        # This makes the output self-contained - no external data needed
        self._generate_base_data()

        # Generate in FK order
        self._generate_providers()
        self._generate_operatories()
        self._generate_carriers()
        self._generate_insplans()
        self._generate_patients()
        self._generate_inssubs_and_patplans()
        self._generate_appointments_and_procedures()
        self._generate_recalls()
        self._generate_commlogs()
        self._generate_payments()

        # Print summary stats
        self._print_stats()

        return self.sql_statements

    def _generate_base_data(self):
        """Generate base reference data (procedurecode, definition) to make output self-contained."""
        print("  Generating base reference data...")

        # Generate definition records for BillingTypes (Category 4)
        for name, defnum in BILLING_TYPE_DEFNUMS.items():
            display_name = name.replace("_", " - ") if "_" in name else name
            self.sql_statements.append(generate_insert(
                "definition",
                ["DefNum", "Category", "ItemOrder", "ItemName", "ItemValue", "ItemColor", "IsHidden"],
                [defnum, 4, defnum, display_name, "", 0, 0]
            ))

        # Generate definition records for PaymentTypes (Category 10)
        for name, defnum in PAYMENT_TYPE_DEFNUMS.items():
            display_name = name.replace("_", " ")
            self.sql_statements.append(generate_insert(
                "definition",
                ["DefNum", "Category", "ItemOrder", "ItemName", "ItemValue", "ItemColor", "IsHidden"],
                [defnum, 10, defnum, display_name, "", 0, 0]
            ))

        # Generate definition records for ProcCodeCats (Category 11)
        for name, defnum in PROC_CAT_DEFNUMS.items():
            self.sql_statements.append(generate_insert(
                "definition",
                ["DefNum", "Category", "ItemOrder", "ItemName", "ItemValue", "ItemColor", "IsHidden"],
                [defnum, 11, defnum, name, "", 0, 0]
            ))

        # Generate procedurecode records for all codes we use
        # Map category names to ProcCat DefNums
        cat_to_proccat = {
            "exam": PROC_CAT_DEFNUMS.get("ExamsXrays", 73),
            "xray": PROC_CAT_DEFNUMS.get("ExamsXrays", 73),
            "cleaning": PROC_CAT_DEFNUMS.get("Cleanings", 74),
            "perio": PROC_CAT_DEFNUMS.get("Perio", 77),
            "filling": PROC_CAT_DEFNUMS.get("Fillings", 75),
            "crown": PROC_CAT_DEFNUMS.get("CrownBridge", 81),
            "oralsurg": PROC_CAT_DEFNUMS.get("OralSurgery", 82),
            "implant": PROC_CAT_DEFNUMS.get("Implants", 80),
            "endo": PROC_CAT_DEFNUMS.get("Endo", 76),
            "ortho": PROC_CAT_DEFNUMS.get("Ortho", 83),
        }

        for proc in PROCEDURE_CODES:
            code = proc["code"]
            code_num = REAL_CODE_TO_CODENUM.get(code)
            if not code_num:
                continue

            description = PROCEDURE_CODE_DESCRIPTIONS.get(code, code)
            proc_cat = cat_to_proccat.get(proc["cat"], 84)  # Default to Misc
            treat_area = proc["area"]

            self.sql_statements.append(generate_insert(
                "procedurecode",
                ["CodeNum", "ProcCode", "Descript", "AbbrDesc", "ProcTime", "ProcCat", "TreatArea",
                 "NoBillIns", "IsProsth", "IsHygiene", "GTypeNum", "IsTaxed", "PaintType",
                 "GraphicColor", "IsCanadianLab", "PreExisting", "BaseUnits", "SubstOnlyIf",
                 "IsMultiVisit", "DrugNDC", "RevenueCodeDefault", "ProvNumDefault",
                 "CanadaTimeUnits", "IsRadiology"],
                [code_num, code, description, code, "/X/", proc_cat, treat_area,
                 0, 0, 1 if proc["cat"] == "cleaning" else 0, 0, 0, 0,
                 0, 0, 0, 0, 0,
                 0, "", "", 0,
                 0.0, 1 if proc["cat"] == "xray" else 0]
            ))

        print(f"    Generated {len(BILLING_TYPE_DEFNUMS) + len(PAYMENT_TYPE_DEFNUMS) + len(PROC_CAT_DEFNUMS)} definition records")
        print(f"    Generated {len(PROCEDURE_CODES)} procedurecode records")

    def _generate_providers(self):
        """Generate provider records."""
        print("  Generating providers...")

        for i, prov in enumerate(PROVIDERS):
            prov_num = PROVIDER_START_NUM + i
            self.providers.append({
                "ProvNum": prov_num,
                "Abbr": prov["abbr"],
                "LName": prov["lname"],
                "FName": prov["fname"],
                "Suffix": prov["suffix"],
                "IsSecondary": prov["is_secondary"],
            })

            self.sql_statements.append(generate_insert(
                "provider",
                ["ProvNum", "Abbr", "LName", "FName", "MI", "Suffix", "IsSecondary", "IsHidden", "ProvStatus"],
                [prov_num, prov["abbr"], prov["lname"], prov["fname"], "", prov["suffix"], prov["is_secondary"], 0, 0]
            ))

    def _generate_operatories(self):
        """Generate operatory records."""
        print("  Generating operatories...")

        for i, op in enumerate(OPERATORIES):
            op_num = OPERATORY_START_NUM + i
            self.operatories.append({
                "OperatoryNum": op_num,
                "OpName": op["name"],
                "Abbrev": op["abbrev"],
                "IsHygiene": op["is_hygiene"],
                "ProvDentist": op["prov_dentist"],
                "ProvHygienist": op["prov_hygienist"],
            })

            self.sql_statements.append(generate_insert(
                "operatory",
                ["OperatoryNum", "OpName", "Abbrev", "ItemOrder", "IsHidden", "ProvDentist", "ProvHygienist", "IsHygiene"],
                [op_num, op["name"], op["abbrev"], op_num, 0, op["prov_dentist"], op["prov_hygienist"], op["is_hygiene"]]
            ))

    def _generate_carriers(self):
        """Generate carrier records."""
        print("  Generating carriers...")

        for name, _ in INSURANCE_CARRIERS:
            carrier_num = self.next_carrier_num
            self.next_carrier_num += 1

            # Generate corporate address
            address = self.fake.street_address()
            city = self.fake.city()
            state = self.fake.state_abbr()
            zip_code = self.fake.zipcode()
            phone = self.fake.phone_number()

            self.carriers.append({
                "CarrierNum": carrier_num,
                "CarrierName": name,
            })

            self.sql_statements.append(generate_insert(
                "carrier",
                ["CarrierNum", "CarrierName", "Address", "Address2", "City", "State", "Zip", "Phone", "NoSendElect"],
                [carrier_num, name, address, "", city, state, zip_code, phone, 0]
            ))

    def _generate_insplans(self):
        """Generate insurance plan records."""
        print("  Generating insurance plans...")

        plan_types = ["", "p", "p", ""]  # Mix of percentage and PPO

        for carrier in self.carriers:
            # Create 2-3 plans per carrier (different groups)
            for plan_idx in range(random.randint(2, 3)):
                plan_num = self.next_insplan_num
                self.next_insplan_num += 1

                group_name = f"{carrier['CarrierName']} - {self.fake.company()}"
                group_num = f"{random.randint(100000, 999999)}"
                plan_type = random.choice(plan_types)
                month_renew = random.choice([0, 1, 7])  # Calendar, January, or July

                self.insplans.append({
                    "PlanNum": plan_num,
                    "CarrierNum": carrier["CarrierNum"],
                    "GroupName": group_name,
                    "GroupNum": group_num,
                    "PlanType": plan_type,
                })

                self.sql_statements.append(generate_insert(
                    "insplan",
                    ["PlanNum", "GroupName", "GroupNum", "PlanType", "CarrierNum", "EmployerNum", "MonthRenew"],
                    [plan_num, group_name, group_num, plan_type, carrier["CarrierNum"], 0, month_renew]
                ))

    def _generate_birthdate(self) -> date:
        """Generate a birthdate based on age distribution."""
        # Select age range based on distribution
        r = random.random()
        cumulative = 0
        for min_age, max_age, prob in AGE_DISTRIBUTION:
            cumulative += prob
            if r <= cumulative:
                age = random.randint(min_age, max_age)
                break
        else:
            age = random.randint(25, 45)  # Default

        # Generate birthdate
        days_old = age * 365 + random.randint(0, 364)
        return self.today - timedelta(days=days_old)

    def _generate_phone(self) -> str:
        """Generate a formatted phone number."""
        area = random.randint(200, 999)
        prefix = random.randint(200, 999)
        line = random.randint(1000, 9999)
        return f"({area}) {prefix}-{line}"

    def _generate_patients(self):
        """Generate patient records."""
        print("  Generating patients...")

        # Calculate family vs solo split
        solo_count = int(self.patient_count * 0.94)
        family_patient_count = self.patient_count - solo_count

        # Generate solo patients first
        for _ in range(solo_count):
            self._create_patient(guarantor=None)

        # Generate family groups
        family_sizes = [2, 3, 4, 5]
        family_weights = [0.4, 0.35, 0.2, 0.05]

        remaining = family_patient_count
        while remaining > 0:
            # Pick family size
            size = min(random.choices(family_sizes, weights=family_weights)[0], remaining)

            # Create head of household (adult)
            guarantor = self._create_patient(guarantor=None, force_adult=True)
            remaining -= 1

            # Create family members
            for i in range(size - 1):
                if remaining <= 0:
                    break
                # Spouse or child
                is_child = i > 0 and random.random() < 0.7
                self._create_patient(guarantor=guarantor["PatNum"], is_child=is_child)
                remaining -= 1

        print(f"    Created {len(self.patients)} patients ({solo_count} solo, {family_patient_count} in families)")

    def _create_patient(self, guarantor: int = None, force_adult: bool = False, is_child: bool = False) -> dict:
        """Create a single patient record."""
        pat_num = self.next_pat_num
        self.next_pat_num += 1

        # Generate demographics
        gender = random.choice([0, 1])  # 0=Male, 1=Female
        if gender == 0:
            fname = self.fake.first_name_male()
        else:
            fname = self.fake.first_name_female()

        lname = self.fake.last_name()
        middle_i = random.choice(["", "", "", self.fake.random_letter().upper()])
        preferred = "" if random.random() < 0.85 else self.fake.first_name()

        # Birthdate
        if is_child:
            age = random.randint(2, 17)
            birthdate = self.today - timedelta(days=age * 365 + random.randint(0, 364))
        elif force_adult:
            age = random.randint(25, 55)
            birthdate = self.today - timedelta(days=age * 365 + random.randint(0, 364))
        else:
            birthdate = self._generate_birthdate()

        age = (self.today - birthdate).days // 365

        # Position (marital status)
        if age < 18:
            position = 2  # Child
        else:
            position = random.choices([0, 1, 3, 4], weights=[0.3, 0.5, 0.05, 0.15])[0]

        # SSN (fake)
        ssn = f"{random.randint(100, 999)}{random.randint(10, 99)}{random.randint(1000, 9999)}"

        # Address
        address = self.fake.street_address()
        city = self.metro["city"]
        state = self.metro["state"]
        zip_code = random.choice(self.metro["zips"])

        # Contact info
        hm_phone = self._generate_phone()
        wk_phone = self._generate_phone() if age >= 18 and random.random() < 0.6 else ""
        wireless = self._generate_phone() if age >= 13 else ""
        email = self.fake.email() if age >= 13 else ""

        # Provider assignment (using our synthetic providers 100-103)
        # 100, 101 are dentists; 102, 103 are hygienists
        pri_prov = random.choice([PROVIDER_START_NUM, PROVIDER_START_NUM + 1])  # Dentist
        sec_prov = random.choice([PROVIDER_START_NUM + 2, PROVIDER_START_NUM + 3]) if random.random() < 0.7 else 0  # Hygienist

        # Guarantor
        if guarantor is None:
            guarantor = pat_num  # Self-guarantor

        # Balances (will be calculated later based on procedures)
        est_balance = Decimal("0.00")
        bal_total = Decimal("0.00")

        # First visit date
        date_first_visit = self.history_start + timedelta(days=random.randint(0, 365))

        # Text message OK
        txt_msg_ok = random.choices([0, 1, 2], weights=[0.1, 0.7, 0.2])[0]

        patient = {
            "PatNum": pat_num,
            "LName": lname,
            "FName": fname,
            "MiddleI": middle_i,
            "Preferred": preferred,
            "PatStatus": 0,  # Active
            "Gender": gender,
            "Position": position,
            "Birthdate": birthdate,
            "SSN": ssn,
            "Address": address,
            "Address2": "",
            "City": city,
            "State": state,
            "Zip": zip_code,
            "HmPhone": hm_phone,
            "WkPhone": wk_phone,
            "WirelessPhone": wireless,
            "Email": email,
            "Guarantor": guarantor,
            "PriProv": pri_prov,
            "SecProv": sec_prov,
            "FeeSched": 0,
            "BillingType": DEFAULT_BILLING_TYPE,  # 40 = Standard
            "EstBalance": est_balance,
            "BalTotal": bal_total,
            "DateFirstVisit": date_first_visit,
            "ClinicNum": 0,
            "TxtMsgOk": txt_msg_ok,
            "Age": age,  # Not stored in DB, used for logic
        }

        self.patients.append(patient)

        self.sql_statements.append(generate_insert(
            "patient",
            ["PatNum", "LName", "FName", "MiddleI", "Preferred", "PatStatus", "Gender", "Position",
             "Birthdate", "SSN", "Address", "Address2", "City", "State", "Zip",
             "HmPhone", "WkPhone", "WirelessPhone", "Email", "Guarantor", "PriProv", "SecProv",
             "FeeSched", "BillingType", "EstBalance", "BalTotal", "DateFirstVisit", "ClinicNum", "TxtMsgOk"],
            [pat_num, lname, fname, middle_i, preferred, 0, gender, position,
             birthdate, ssn, address, "", city, state, zip_code,
             hm_phone, wk_phone, wireless, email, guarantor, pri_prov, sec_prov,
             0, DEFAULT_BILLING_TYPE, est_balance, bal_total, date_first_visit, 0, txt_msg_ok]
        ))

        return patient

    def _generate_inssubs_and_patplans(self):
        """Generate insurance subscriptions and patient plans."""
        print("  Generating insurance subscriptions...")

        # 53% of patients have insurance
        insured_patients = random.sample(self.patients, int(len(self.patients) * 0.53))

        # Build carrier weights for random selection
        carrier_names = [c[0] for c in INSURANCE_CARRIERS]
        carrier_weights = [c[1] for c in INSURANCE_CARRIERS]
        # Normalize weights
        total = sum(carrier_weights)
        carrier_weights = [w/total for w in carrier_weights]

        for patient in insured_patients:
            # Select carrier based on distribution
            carrier_name = random.choices(carrier_names, weights=carrier_weights)[0]
            carrier = next(c for c in self.carriers if c["CarrierName"] == carrier_name)

            # Find a plan for this carrier
            carrier_plans = [p for p in self.insplans if p["CarrierNum"] == carrier["CarrierNum"]]
            plan = random.choice(carrier_plans)

            # Create inssub
            inssub_num = self.next_inssub_num
            self.next_inssub_num += 1

            # Subscriber (usually self or guarantor)
            if patient["Guarantor"] == patient["PatNum"]:
                subscriber = patient["PatNum"]
            else:
                subscriber = patient["Guarantor"]

            subscriber_id = f"{subscriber:08d}"
            date_effective = patient["DateFirstVisit"] - timedelta(days=random.randint(0, 365))
            date_term = date(2099, 12, 31)  # Far future

            inssub = {
                "InsSubNum": inssub_num,
                "PlanNum": plan["PlanNum"],
                "Subscriber": subscriber,
                "SubscriberID": subscriber_id,
                "DateEffective": date_effective,
                "DateTerm": date_term,
            }
            self.inssubs.append(inssub)

            self.sql_statements.append(generate_insert(
                "inssub",
                ["InsSubNum", "PlanNum", "Subscriber", "SubscriberID", "DateEffective", "DateTerm"],
                [inssub_num, plan["PlanNum"], subscriber, subscriber_id, date_effective, date_term]
            ))

            # Create patplan
            patplan_num = self.next_patplan_num
            self.next_patplan_num += 1

            # Relationship
            if patient["PatNum"] == subscriber:
                relationship = 0  # Self
            elif patient["Position"] == 2:  # Child
                relationship = 2  # Child
            else:
                relationship = 1  # Spouse

            patplan = {
                "PatPlanNum": patplan_num,
                "PatNum": patient["PatNum"],
                "InsSubNum": inssub_num,
                "Ordinal": 1,  # Primary
                "Relationship": relationship,
                "PlanNum": plan["PlanNum"],
            }
            self.patplans.append(patplan)

            self.sql_statements.append(generate_insert(
                "patplan",
                ["PatPlanNum", "PatNum", "InsSubNum", "Ordinal", "Relationship"],
                [patplan_num, patient["PatNum"], inssub_num, 1, relationship]
            ))

        print(f"    Created {len(self.inssubs)} insurance subscriptions")

    def _get_patient_insurance(self, pat_num: int) -> dict | None:
        """Get patient's insurance info if any."""
        patplan = next((pp for pp in self.patplans if pp["PatNum"] == pat_num), None)
        return patplan

    def _generate_appointments_and_procedures(self):
        """Generate appointments and associated procedures."""
        print("  Generating appointments and procedures...")

        # Build bundle weights
        bundle_names = list(APPOINTMENT_BUNDLES.keys())
        bundle_weights = [APPOINTMENT_BUNDLES[b]["weight"] for b in bundle_names]

        # Track patients who need unscheduled treatment (target 76%)
        patients_needing_tp = set()

        for patient in self.patients:
            # Determine number of appointments for this patient (history)
            # Based on years since first visit
            years_active = (self.today - patient["DateFirstVisit"]).days / 365

            # Average 2-3 visits per year
            avg_visits = int(years_active * random.uniform(1.5, 3.5))
            num_appointments = max(1, min(avg_visits, 15))

            # Generate historical appointments (completed)
            appointment_dates = []
            for _ in range(num_appointments):
                apt_date = patient["DateFirstVisit"] + timedelta(
                    days=random.randint(0, (self.today - patient["DateFirstVisit"]).days)
                )
                if apt_date <= self.today:
                    appointment_dates.append(apt_date)

            appointment_dates.sort()

            # First appointment should often be new patient type
            first_apt = True

            for apt_date in appointment_dates:
                # Select bundle type
                if first_apt and patient["Age"] >= 18:
                    bundle_name = "new_patient"
                    first_apt = False
                elif patient["Age"] < 13:
                    bundle_name = random.choices(
                        ["child_prophy", "limited_exam", "filling_single"],
                        weights=[0.7, 0.2, 0.1]
                    )[0]
                else:
                    bundle_name = random.choices(bundle_names, weights=bundle_weights)[0]

                bundle = APPOINTMENT_BUNDLES[bundle_name]

                # Create completed appointment
                self._create_appointment(
                    patient=patient,
                    apt_date=apt_date,
                    bundle=bundle,
                    status=2,  # Complete
                )

            # Generate future scheduled appointments (20% of patients)
            if random.random() < 0.20:
                future_date = self.today + timedelta(days=random.randint(1, 90))
                bundle_name = random.choices(bundle_names, weights=bundle_weights)[0]
                bundle = APPOINTMENT_BUNDLES[bundle_name]

                self._create_appointment(
                    patient=patient,
                    apt_date=future_date,
                    bundle=bundle,
                    status=1,  # Scheduled
                )

            # Generate treatment planned procedures (76% target)
            if random.random() < 0.76:
                patients_needing_tp.add(patient["PatNum"])
                self._create_treatment_planned_procedures(patient)

        print(f"    Created {len(self.appointments)} appointments")
        print(f"    Created {len(self.procedures)} procedures")
        print(f"    {len(patients_needing_tp)} patients have unscheduled treatment ({100*len(patients_needing_tp)/len(self.patients):.1f}%)")

    def _create_appointment(self, patient: dict, apt_date: date, bundle: dict, status: int):
        """Create an appointment with associated procedures."""
        apt_num = self.next_apt_num
        self.next_apt_num += 1

        # Select operatory and provider based on bundle type
        if bundle["is_hygiene"]:
            op = random.choice([o for o in self.operatories if o["IsHygiene"]])
            prov_num = op["ProvHygienist"]
            prov_hyg = prov_num
        else:
            op = random.choice([o for o in self.operatories if not o["IsHygiene"]])
            prov_num = op["ProvDentist"] if op["ProvDentist"] else patient["PriProv"]
            prov_hyg = 0

        # Appointment time (business hours 8am-5pm)
        hour = random.randint(8, 16)
        minute = random.choice([0, 15, 30, 45])
        apt_datetime = datetime.combine(apt_date, datetime.min.time().replace(hour=hour, minute=minute))

        # Pattern
        pattern = bundle["pattern"]

        # Note
        note = random.choice(APPOINTMENT_NOTE_TEMPLATES)

        # Is new patient
        is_new = 1 if bundle == APPOINTMENT_BUNDLES.get("new_patient") else 0

        # Get insurance info
        patplan = self._get_patient_insurance(patient["PatNum"])
        insplan1 = patplan["PlanNum"] if patplan else 0

        # Procedure description
        proc_codes = bundle["codes"]
        proc_descript = ", ".join(proc_codes[:3])
        if len(proc_codes) > 3:
            proc_descript += f" +{len(proc_codes)-3}"

        appointment = {
            "AptNum": apt_num,
            "PatNum": patient["PatNum"],
            "AptStatus": status,
            "Pattern": pattern,
            "Confirmed": 0,
            "Op": op["OperatoryNum"],
            "Note": note,
            "ProvNum": prov_num,
            "ProvHyg": prov_hyg,
            "AptDateTime": apt_datetime,
            "IsNewPatient": is_new,
            "ProcDescript": proc_descript,
            "IsHygiene": bundle["is_hygiene"],
            "InsPlan1": insplan1,
            "InsPlan2": 0,
        }
        self.appointments.append(appointment)

        self.sql_statements.append(generate_insert(
            "appointment",
            ["AptNum", "PatNum", "AptStatus", "Pattern", "Confirmed", "Op", "Note",
             "ProvNum", "ProvHyg", "AptDateTime", "IsNewPatient", "ProcDescript", "IsHygiene",
             "InsPlan1", "InsPlan2"],
            [apt_num, patient["PatNum"], status, pattern, 0, op["OperatoryNum"], note,
             prov_num, prov_hyg, apt_datetime, is_new, proc_descript, bundle["is_hygiene"],
             insplan1, 0]
        ))

        # Create procedures for this appointment
        for proc_code in proc_codes:
            # Handle SRP quads (create multiple D4341)
            if proc_code == "D4341":
                num_quads = random.randint(2, 4)
                for q in range(num_quads):
                    self._create_procedure(
                        patient=patient,
                        apt_num=apt_num,
                        proc_code=proc_code,
                        proc_date=apt_date,
                        prov_num=prov_num,
                        status=2 if status == 2 else 1,  # Complete if apt is complete
                        quadrant=QUADRANTS[q],
                    )
            else:
                self._create_procedure(
                    patient=patient,
                    apt_num=apt_num,
                    proc_code=proc_code,
                    proc_date=apt_date,
                    prov_num=prov_num,
                    status=2 if status == 2 else 1,
                )

    def _create_procedure(self, patient: dict, apt_num: int, proc_code: str, proc_date: date,
                          prov_num: int, status: int, quadrant: str = None, tooth: str = None):
        """Create a single procedure."""
        proc_num = self.next_proc_num
        self.next_proc_num += 1

        # Get CodeNum
        code_num = self.code_to_codenum.get(proc_code)
        if not code_num:
            return  # Skip if code not found

        # Get procedure info
        proc_info = next((p for p in self.procedure_codes if p["CodeNum"] == code_num), None)
        if not proc_info:
            return

        # Calculate fee
        fee_min, fee_avg, fee_max = proc_info["fees"]
        # Use normal distribution around average
        if fee_avg > 0:
            fee = max(fee_min, min(fee_max, random.gauss(fee_avg, (fee_max - fee_min) / 4)))
            fee = Decimal(str(round(fee, 2)))
        else:
            fee = Decimal("0.00")

        # Determine tooth/surface based on treatment area
        surf = ""
        tooth_num = ""
        tooth_range = ""

        if proc_info["area"] == 1:  # Surface
            tooth_num = tooth or random.choice(POSTERIOR_TEETH)
            surf = random.choice(["MO", "DO", "MOD", "O", "M", "D"])
        elif proc_info["area"] == 2:  # Tooth
            tooth_num = tooth or random.choice(ALL_TEETH)
        elif proc_info["area"] == 4:  # Quadrant
            surf = quadrant or random.choice(QUADRANTS)

        procedure = {
            "ProcNum": proc_num,
            "PatNum": patient["PatNum"],
            "AptNum": apt_num if status == 2 else 0,  # Only link if complete
            "CodeNum": code_num,
            "ProcCode": proc_code,
            "ProcDate": proc_date,
            "ProcFee": fee,
            "Surf": surf,
            "ToothNum": tooth_num,
            "ToothRange": tooth_range,
            "ProcStatus": status,
            "ProvNum": prov_num,
            "PlannedAptNum": apt_num if status == 1 else 0,
            "ClinicNum": 0,
            "DateTP": proc_date if status == 1 else date(1, 1, 1),
        }
        self.procedures.append(procedure)

        self.sql_statements.append(generate_insert(
            "procedurelog",
            ["ProcNum", "PatNum", "AptNum", "CodeNum", "ProcDate", "ProcFee", "Surf",
             "ToothNum", "ToothRange", "ProcStatus", "ProvNum", "PlannedAptNum", "ClinicNum", "DateTP"],
            [proc_num, patient["PatNum"], procedure["AptNum"], code_num, proc_date, fee, surf,
             tooth_num, tooth_range, status, prov_num, procedure["PlannedAptNum"], 0,
             procedure["DateTP"] if procedure["DateTP"] != date(1, 1, 1) else "0001-01-01"]
        ))

        # Create procedure note for completed procedures
        if status == 2 and random.random() < 0.8:
            self._create_procnote(patient, procedure)

        # Create claimproc estimate for insured patients with completed procedures
        if status == 2:
            patplan = self._get_patient_insurance(patient["PatNum"])
            if patplan and random.random() < 0.9:
                self._create_claimproc(patient, procedure, patplan)

    def _create_treatment_planned_procedures(self, patient: dict):
        """Create unscheduled treatment planned procedures for a patient."""
        # Select random procedures that make sense for treatment planning
        tp_codes = [
            "D2391", "D2392", "D2393",  # Fillings
            "D2740", "D2750",  # Crowns
            "D7140", "D7210",  # Extractions
            "D3310", "D3320", "D3330",  # Root canals
        ]

        # 1-4 treatment planned procedures
        num_procs = random.randint(1, 4)
        selected_codes = random.choices(tp_codes, k=num_procs)

        # Date treatment was planned (sometime in the past)
        date_tp = self.today - timedelta(days=random.randint(30, 365))

        for proc_code in selected_codes:
            self._create_procedure(
                patient=patient,
                apt_num=0,
                proc_code=proc_code,
                proc_date=date_tp,
                prov_num=patient["PriProv"],
                status=1,  # TP
            )

    def _create_procnote(self, patient: dict, procedure: dict):
        """Create a procedure note."""
        procnote_num = self.next_procnote_num
        self.next_procnote_num += 1

        template = random.choice(PROC_NOTE_TEMPLATES)
        note = template.format(
            procedure=procedure["ProcCode"],
            tooth=procedure["ToothNum"] or "affected area",
        )

        entry_datetime = datetime.combine(
            procedure["ProcDate"],
            datetime.min.time().replace(hour=random.randint(9, 16), minute=random.randint(0, 59))
        )

        self.procnotes.append({
            "ProcNoteNum": procnote_num,
            "PatNum": patient["PatNum"],
            "ProcNum": procedure["ProcNum"],
            "Note": note,
            "EntryDateTime": entry_datetime,
        })

        self.sql_statements.append(generate_insert(
            "procnote",
            ["ProcNoteNum", "PatNum", "ProcNum", "Note", "EntryDateTime", "UserNum"],
            [procnote_num, patient["PatNum"], procedure["ProcNum"], note, entry_datetime, 1]
        ))

    def _create_claimproc(self, patient: dict, procedure: dict, patplan: dict):
        """Create a claimproc estimate."""
        claimproc_num = self.next_claimproc_num
        self.next_claimproc_num += 1

        fee = procedure["ProcFee"]

        # Estimate insurance payment (typically 50-80% of fee)
        ins_percent = random.uniform(0.5, 0.8)
        ins_pay_est = Decimal(str(round(float(fee) * ins_percent, 2)))

        # Some claims are received, most are estimates
        if random.random() < 0.7:
            status = 6  # Estimate
            ins_pay_amt = Decimal("0.00")
            write_off = Decimal("0.00")
        else:
            status = 1  # Received
            ins_pay_amt = ins_pay_est
            # Random small write-off
            write_off = Decimal(str(round(random.uniform(0, float(fee) * 0.1), 2)))

        claimproc = {
            "ClaimProcNum": claimproc_num,
            "ProcNum": procedure["ProcNum"],
            "ClaimNum": 0,
            "PatNum": patient["PatNum"],
            "ProvNum": procedure["ProvNum"],
            "FeeBilled": fee,
            "InsPayEst": ins_pay_est,
            "InsPayAmt": ins_pay_amt,
            "Status": status,
            "PlanNum": patplan["PlanNum"],
            "WriteOff": write_off,
            "InsSubNum": patplan["InsSubNum"],
        }
        self.claimprocs.append(claimproc)

        self.sql_statements.append(generate_insert(
            "claimproc",
            ["ClaimProcNum", "ProcNum", "ClaimNum", "PatNum", "ProvNum", "FeeBilled",
             "InsPayEst", "InsPayAmt", "Status", "PlanNum", "WriteOff", "InsSubNum"],
            [claimproc_num, procedure["ProcNum"], 0, patient["PatNum"], procedure["ProvNum"],
             fee, ins_pay_est, ins_pay_amt, status, patplan["PlanNum"], write_off, patplan["InsSubNum"]]
        ))

    def _generate_recalls(self):
        """Generate recall records."""
        print("  Generating recalls...")

        # Target: 26% overdue for hygiene (DateDue < today - 7 months)
        overdue_threshold = self.today - timedelta(days=7*30)

        overdue_count = 0
        target_overdue = int(len(self.patients) * 0.26)

        for patient in self.patients:
            if patient["Age"] < 3:
                continue

            recall_num = self.next_recall_num
            self.next_recall_num += 1

            # Standard 6-month recall interval
            interval = "0y6m0d"

            # Find last hygiene appointment
            patient_apts = [a for a in self.appointments
                          if a["PatNum"] == patient["PatNum"]
                          and a["AptStatus"] == 2
                          and a["IsHygiene"]]

            if patient_apts:
                last_apt = max(patient_apts, key=lambda a: a["AptDateTime"])
                date_previous = last_apt["AptDateTime"].date()
                date_due = date_previous + timedelta(days=180)  # 6 months
            else:
                # No previous hygiene
                date_previous = date(1, 1, 1)
                date_due = patient["DateFirstVisit"] + timedelta(days=180)

            # Force some to be overdue to hit target
            if overdue_count < target_overdue and random.random() < 0.3:
                date_due = overdue_threshold - timedelta(days=random.randint(1, 180))
                overdue_count += 1

            # Check if already scheduled
            future_hygiene = [a for a in self.appointments
                            if a["PatNum"] == patient["PatNum"]
                            and a["AptStatus"] == 1
                            and a["IsHygiene"]]
            date_scheduled = future_hygiene[0]["AptDateTime"].date() if future_hygiene else date(1, 1, 1)

            recall = {
                "RecallNum": recall_num,
                "PatNum": patient["PatNum"],
                "DateDue": date_due,
                "DatePrevious": date_previous,
                "RecallInterval": interval,
                "RecallStatus": 0,
                "IsDisabled": 0,
                "RecallTypeNum": 1,
                "DateScheduled": date_scheduled,
            }
            self.recalls.append(recall)

            self.sql_statements.append(generate_insert(
                "recall",
                ["RecallNum", "PatNum", "DateDue", "DatePrevious", "RecallInterval",
                 "RecallStatus", "IsDisabled", "RecallTypeNum", "DateScheduled"],
                [recall_num, patient["PatNum"], date_due,
                 date_previous if date_previous != date(1, 1, 1) else "0001-01-01",
                 interval, 0, 0, 1,
                 date_scheduled if date_scheduled != date(1, 1, 1) else "0001-01-01"]
            ))

        # Calculate actual overdue
        actual_overdue = len([r for r in self.recalls if r["DateDue"] < overdue_threshold])
        print(f"    Created {len(self.recalls)} recalls")
        print(f"    {actual_overdue} patients overdue for hygiene ({100*actual_overdue/len(self.recalls):.1f}%)")

    def _generate_commlogs(self):
        """Generate communication log entries."""
        print("  Generating communication logs...")

        for patient in self.patients:
            # 1-5 commlog entries per patient
            num_entries = random.randint(1, 5)

            for _ in range(num_entries):
                commlog_num = self.next_commlog_num
                self.next_commlog_num += 1

                # Random date in history
                comm_date = self.history_start + timedelta(
                    days=random.randint(0, (self.today - self.history_start).days)
                )
                comm_datetime = datetime.combine(
                    comm_date,
                    datetime.min.time().replace(hour=random.randint(8, 17), minute=random.randint(0, 59))
                )

                # Mode
                mode = random.choices([1, 2, 3, 4, 5], weights=[0.15, 0.05, 0.5, 0.1, 0.2])[0]

                # Template
                template = random.choice(COMMLOG_NOTE_TEMPLATES)
                note = template.format(date=(comm_date + timedelta(days=random.randint(1, 14))).strftime("%m/%d/%Y"))

                # Sent or received
                sent_or_received = random.choice([1, 2])

                self.commlogs.append({
                    "CommlogNum": commlog_num,
                    "PatNum": patient["PatNum"],
                    "CommDateTime": comm_datetime,
                    "CommType": 0,
                    "Note": note,
                    "Mode_": mode,
                    "SentOrReceived": sent_or_received,
                })

                self.sql_statements.append(generate_insert(
                    "commlog",
                    ["CommlogNum", "PatNum", "CommDateTime", "CommType", "Note", "Mode_", "SentOrReceived", "UserNum"],
                    [commlog_num, patient["PatNum"], comm_datetime, 0, note, mode, sent_or_received, 1]
                ))

        print(f"    Created {len(self.commlogs)} commlog entries")

    def _generate_payments(self):
        """Generate payment and paysplit records."""
        print("  Generating payments...")

        # Get completed procedures for patients
        patient_procs = defaultdict(list)
        for proc in self.procedures:
            if proc["ProcStatus"] == 2:
                patient_procs[proc["PatNum"]].append(proc)

        for patient in self.patients:
            procs = patient_procs.get(patient["PatNum"], [])
            if not procs:
                continue

            # 60% of patients with procedures have made payments
            if random.random() > 0.6:
                continue

            # 1-3 payments
            num_payments = random.randint(1, 3)

            for _ in range(num_payments):
                payment_num = self.next_payment_num
                self.next_payment_num += 1

                # Payment date (after some procedures)
                eligible_procs = [p for p in procs if p["ProcDate"] <= self.today]
                if not eligible_procs:
                    continue

                pay_date = random.choice(eligible_procs)["ProcDate"] + timedelta(days=random.randint(0, 30))
                if pay_date > self.today:
                    pay_date = self.today

                # Payment amount (partial or full)
                total_fees = sum(float(p["ProcFee"]) for p in eligible_procs)
                pay_amt = Decimal(str(round(random.uniform(20, min(total_fees, 500)), 2)))

                # Payment type using real DefNums
                pay_type_options = [
                    PAYMENT_TYPE_DEFNUMS["Cash"],        # 70
                    PAYMENT_TYPE_DEFNUMS["Check"],       # 69
                    PAYMENT_TYPE_DEFNUMS["CreditCard"],  # 71
                    PAYMENT_TYPE_DEFNUMS["Visa"],        # 377
                    PAYMENT_TYPE_DEFNUMS["Mastercard"],  # 378
                ]
                pay_type = random.choice(pay_type_options)

                check_num = str(random.randint(1000, 9999)) if pay_type == PAYMENT_TYPE_DEFNUMS["Check"] else ""

                self.payments.append({
                    "PayNum": payment_num,
                    "PayType": pay_type,
                    "PayDate": pay_date,
                    "PayAmt": pay_amt,
                    "CheckNum": check_num,
                    "PayNote": "",
                    "PatNum": patient["PatNum"],
                })

                self.sql_statements.append(generate_insert(
                    "payment",
                    ["PayNum", "PayType", "PayDate", "PayAmt", "CheckNum", "PayNote", "PatNum", "ClinicNum"],
                    [payment_num, pay_type, pay_date, pay_amt, check_num, "", patient["PatNum"], 0]
                ))

                # Create paysplit - allocate to procedures
                remaining = float(pay_amt)
                for proc in eligible_procs:
                    if remaining <= 0:
                        break

                    split_num = self.next_paysplit_num
                    self.next_paysplit_num += 1

                    split_amt = min(remaining, float(proc["ProcFee"]))
                    split_amt = Decimal(str(round(split_amt, 2)))
                    remaining -= float(split_amt)

                    self.paysplits.append({
                        "SplitNum": split_num,
                        "SplitAmt": split_amt,
                        "PatNum": patient["PatNum"],
                        "PayNum": payment_num,
                        "ProvNum": proc["ProvNum"],
                        "ProcNum": proc["ProcNum"],
                        "DatePay": pay_date,
                    })

                    self.sql_statements.append(generate_insert(
                        "paysplit",
                        ["SplitNum", "SplitAmt", "PatNum", "PayNum", "ProvNum", "ProcNum", "DatePay"],
                        [split_num, split_amt, patient["PatNum"], payment_num, proc["ProvNum"], proc["ProcNum"], pay_date]
                    ))

        print(f"    Created {len(self.payments)} payments")
        print(f"    Created {len(self.paysplits)} paysplits")

    def _print_stats(self):
        """Print summary statistics."""
        print("\n" + "="*60)
        print("GENERATION SUMMARY")
        print("="*60)
        print(f"Metro: {self.metro['city']}, {self.metro['state']}")
        print(f"Seed: {self.seed}")
        print("-"*60)
        print(f"Providers: {len(self.providers)}")
        print(f"Operatories: {len(self.operatories)}")
        print(f"Carriers: {len(self.carriers)}")
        print(f"Insurance Plans: {len(self.insplans)}")
        print(f"Patients: {len(self.patients)}")
        print(f"  - With insurance: {len(self.patplans)} ({100*len(self.patplans)/len(self.patients):.1f}%)")
        print(f"Insurance Subscriptions: {len(self.inssubs)}")
        print(f"Appointments: {len(self.appointments)}")
        print(f"  - Completed: {len([a for a in self.appointments if a['AptStatus'] == 2])}")
        print(f"  - Scheduled: {len([a for a in self.appointments if a['AptStatus'] == 1])}")
        print(f"Procedures: {len(self.procedures)}")
        print(f"  - Completed: {len([p for p in self.procedures if p['ProcStatus'] == 2])}")
        print(f"  - Treatment Planned: {len([p for p in self.procedures if p['ProcStatus'] == 1])}")
        print(f"Procedure Notes: {len(self.procnotes)}")
        print(f"Recalls: {len(self.recalls)}")
        print(f"Communication Logs: {len(self.commlogs)}")
        print(f"Payments: {len(self.payments)}")
        print(f"Pay Splits: {len(self.paysplits)}")
        print(f"Claim Procedures: {len(self.claimprocs)}")
        print("-"*60)
        print(f"Total SQL statements: {len(self.sql_statements)}")
        print("="*60)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic Open Dental database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate.py                                    # 750 patients, random city
  python generate.py --patients 500 --output data.sql   # Custom patient count
  python generate.py --city "Chicago" --state "IL"      # Specific metro area
  python generate.py --seed 12345                       # Reproducible output

More info: https://github.com/dentaljosh/synthetic-opendental
Built by the team at Luna (https://yourluna.co)
        """
    )
    parser.add_argument("--city", type=str, help="Target city for addresses (e.g., 'Chicago')")
    parser.add_argument("--state", type=str, help="Target state for addresses (e.g., 'IL')")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--patients", type=int, default=DEFAULT_PATIENT_COUNT, help="Number of patients to generate (default: 750)")
    parser.add_argument("--output", type=str, default="synthetic_data.sql", help="Output SQL file (default: synthetic_data.sql)")

    args = parser.parse_args()

    generator = SyntheticDataGenerator(
        seed=args.seed,
        city=args.city,
        state=args.state,
        patient_count=args.patients,
    )

    sql_statements = generator.generate_all()

    # Write output
    output_path = args.output
    print(f"\nWriting SQL to {output_path}...")

    with open(output_path, 'w') as f:
        f.write("-- =============================================================================\n")
        f.write("-- Synthetic Open Dental Database\n")
        f.write("-- =============================================================================\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n")
        f.write(f"-- Seed: {args.seed}\n")
        f.write(f"-- Metro: {generator.metro['city']}, {generator.metro['state']}\n")
        f.write(f"-- Patients: {len(generator.patients)}\n")
        f.write("-- \n")
        f.write("-- This is 100% synthetic data for testing and demo purposes.\n")
        f.write("-- All names, SSNs, addresses, and other details are computer-generated.\n")
        f.write("-- No real patient data is included.\n")
        f.write("-- \n")
        f.write("-- Generator: https://github.com/dentaljosh/synthetic-opendental\n")
        f.write("-- Built by Luna (https://yourluna.co)\n")
        f.write("-- =============================================================================\n\n")

        f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

        for statement in sql_statements:
            f.write(statement + "\n")

        f.write("\nSET FOREIGN_KEY_CHECKS = 1;\n")

    print(f"Done! Generated {len(sql_statements)} SQL statements.")


if __name__ == "__main__":
    main()
