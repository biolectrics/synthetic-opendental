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
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from collections import defaultdict

# Must run before importing faker or defining classes that use PEP 604 (X | None)
# type unions, both of which would otherwise fail with an obscure error on 3.9.
if sys.version_info < (3, 10):
    sys.exit("This generator requires Python 3.10+ (uses PEP 604 type unions).")

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
    # Perio surgery / adjuncts (synthetic CodeNums; output is self-contained)
    "D4260": 770,  # Osseous surgery - 4+ teeth per quadrant
    "D4261": 771,  # Osseous surgery - 1-3 teeth per quadrant
    "D4381": 772,  # Localized delivery of antimicrobial agent
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
    "D4260": "Osseous surgery - 4+ teeth per quadrant",
    "D4261": "Osseous surgery - 1-3 teeth per quadrant",
    "D4381": "Localized delivery of antimicrobial agents per tooth",
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
    {"code": "D4260", "cat": "perio", "area": 4, "fees": (350, 900, 1500)},   # osseous surgery 4+ teeth/quad
    {"code": "D4261", "cat": "perio", "area": 4, "fees": (250, 600, 1000)},   # osseous surgery 1-3 teeth/quad
    {"code": "D4381", "cat": "perio", "area": 2, "fees": (35, 90, 175)},      # localized antimicrobial, per tooth

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
    {"city": "Nashville", "state": "TN", "zips": ["37201", "37203", "37204", "37205", "37206", "37207", "37208", "37209", "37210", "37211", "37212", "37214", "37215", "37216", "37217", "37218", "37219", "37220", "37221", "37013"]},
    {"city": "Omaha", "state": "NE", "zips": ["68102", "68104", "68105", "68106", "68107", "68108", "68110", "68111", "68112", "68114", "68116", "68117", "68118", "68122", "68124", "68127", "68130", "68131", "68132", "68134"]},
    {"city": "Cleveland", "state": "OH", "zips": ["44102", "44103", "44104", "44105", "44106", "44107", "44108", "44109", "44110", "44111", "44113", "44114", "44115", "44119", "44120", "44121", "44125", "44127", "44128", "44135"]},
    {"city": "Columbus", "state": "OH", "zips": ["43201", "43202", "43203", "43204", "43205", "43206", "43207", "43209", "43210", "43211", "43212", "43214", "43215", "43219", "43220", "43221", "43222", "43223", "43224", "43227"]},
    {"city": "Cincinnati", "state": "OH", "zips": ["45202", "45203", "45204", "45205", "45206", "45207", "45208", "45209", "45211", "45212", "45213", "45214", "45215", "45216", "45217", "45219", "45220", "45223", "45224", "45225"]},
    {"city": "Boston", "state": "MA", "zips": ["02108", "02109", "02110", "02111", "02113", "02114", "02115", "02116", "02118", "02119", "02120", "02121", "02122", "02124", "02125", "02126", "02127", "02128", "02129", "02130"]},
    {"city": "Detroit", "state": "MI", "zips": ["48201", "48202", "48204", "48205", "48206", "48207", "48208", "48209", "48210", "48211", "48212", "48213", "48214", "48215", "48216", "48217", "48219", "48221", "48223", "48224"]},
    {"city": "The Woodlands", "state": "TX", "zips": ["77380", "77381", "77382", "77384", "77385", "77386", "77389", "77354", "77302", "77304"]},
    {"city": "Brentwood", "state": "TN", "zips": ["37027", "37024", "37046", "37064", "37067", "37069", "37135", "37179"]},
]


# =============================================================================
# PERIODONTAL CHARTING & TREATMENT MODEL
# =============================================================================
# Grounded in the 2017 World Workshop staging/grading (Tonetti/Papapanou 2018),
# NHANES/Eke prevalence, Cobb 2002 / Hung & Douglass 2002 SRP response, Loe 1986
# natural history, and Hirschfeld & Wasserman 1978 long-term maintenance outcomes.
# Probing/recession values are integer millimeters, matching the Open Dental
# perioexam/periomeasure schema. PerioSequenceType integers below are verbatim
# from the OpenDentBusiness source enum.

PERIO_SEQ_MOBILITY = 0    # grade in ToothValue; six surfaces -1
PERIO_SEQ_FURCATION = 1   # per-surface class (0-3); ToothValue -1; molars only
PERIO_SEQ_GINGMARGIN = 2  # recession, per-surface mm; negatives encoded as 100+|v|
PERIO_SEQ_MGJ = 3         # mucogingival junction, per-surface mm
PERIO_SEQ_PROBING = 4     # pocket depth, per-surface mm (the core reading)
PERIO_SEQ_SKIPTOOTH = 5   # ToothValue=1; surfaces -1
PERIO_SEQ_BLEEDING = 6    # per-surface bitmask (see flags below)
# SequenceType 7 (CAL) is never stored: Open Dental computes it as Probing+GingMargin.

PERIO_NO_MEASURE = -1      # "no measurement taken" sentinel

# Bleeding/Suppuration/Plaque/Calculus bit flags for SequenceType 6 surface values.
PERIO_FLAG_BLEED = 1
PERIO_FLAG_SUPP = 2
PERIO_FLAG_PLAQUE = 4
PERIO_FLAG_CALC = 8

PERIO_MIN_AGE = 18  # only adults are periodontally charted

# Universal numbering; exclude 3rd molars (1/16/17/32), usually absent.
PERIO_TEETH = [t for t in range(1, 33) if t not in (1, 16, 17, 32)]
MAXILLARY_TEETH = set(range(1, 17))           # 1-16 upper (MGJ lingual sites left -1)
MOLAR_TEETH = {2, 3, 14, 15, 18, 19, 30, 31}  # carry furcations
ANTERIOR_INT = {6, 7, 8, 9, 10, 11, 22, 23, 24, 25, 26, 27}  # incisors/canines (often spared)
# Six perio site columns in Open Dental order; mesial/distal = interproximal (deeper).
PERIO_SITE_COLS = ["MBvalue", "Bvalue", "DBvalue", "MLvalue", "Lvalue", "DLvalue"]
PERIO_INTERPROX_IDX = [0, 2, 3, 5]            # MB, DB, ML, DL

PERIO_STAGES = ["healthy", "I", "II", "III", "IV"]

# Universal-tooth -> quadrant (Open Dental Surf code) for SRP/surgery procedures.
def _tooth_quadrant(tooth: int) -> str:
    if tooth <= 8:
        return "UR"
    if tooth <= 16:
        return "UL"
    if tooth <= 24:
        return "LL"
    return "LR"

# Per-site CLINICAL ATTACHMENT LOSS (CAL) ranges by stage -- CAL is the 2017 staging
# determinant (interdental CAL at the site of greatest loss), NOT probing depth.
# "worst" = deepest interproximal/molar sites; "base" = typical/anterior sites;
# "bop" = baseline inflammation fraction; "missing" = teeth lost to periodontitis.
# Probing depth is DERIVED at charting time as PD = CAL - gingival margin, where the
# margin can sit coronal to the CEJ (inflammatory swelling / pseudopocket), so a
# lower-stage patient can still show isolated deep pockets. See _perio_baseline_chart.
STAGE_CAL_RANGES = {
    "healthy": {"base": (0, 1), "worst": (0, 1), "bop": 0.05, "missing": 0},
    "I":       {"base": (0, 2), "worst": (1, 2), "bop": 0.25, "missing": 0},
    "II":      {"base": (0, 3), "worst": (3, 4), "bop": 0.45, "missing": 0},
    "III":     {"base": (1, 5), "worst": (5, 7), "bop": 0.65, "missing": (1, 4)},
    "IV":      {"base": (2, 7), "worst": (6, 10), "bop": 0.80, "missing": (5, 8)},
}

# Age-stratified baseline stage prevalence (NHANES/Eke). Weights order = PERIO_STAGES.
AGE_STAGE_DISTRIBUTION = [
    (44,  [0.71, 0.04, 0.21, 0.03, 0.01]),
    (64,  [0.47, 0.06, 0.33, 0.10, 0.04]),
    (200, [0.32, 0.08, 0.45, 0.10, 0.05]),
]

# Grade distribution within each stage (drives progression speed).
STAGE_GRADE_DISTRIBUTION = {
    "healthy": [("A", 0.70), ("B", 0.28), ("C", 0.02)],
    "I":       [("A", 0.40), ("B", 0.50), ("C", 0.10)],
    "II":      [("A", 0.20), ("B", 0.60), ("C", 0.20)],
    "III":     [("A", 0.05), ("B", 0.40), ("C", 0.55)],
    "IV":      [("A", 0.00), ("B", 0.15), ("C", 0.85)],
}

# Per-3-month-visit site transition: (P_improve, P_stable, P_worsen) and the mm
# increment range when worsening. Calibrated to ~0.08/0.24/0.80 mm/yr (A/B/C).
GRADE_TRANSITION = {
    "A": {"p": (0.10, 0.85, 0.05), "worsen": (0.3, 0.5)},
    "B": {"p": (0.08, 0.80, 0.12), "worsen": (0.5, 0.8)},
    "C": {"p": (0.05, 0.75, 0.20), "worsen": (0.8, 1.5)},
}

# Per-stage treatment template (literature-anchored; [MODELED] where unmeasured).
# srp_prob = chance of SRP vs prophy-only; srp_quads = (lo,hi) quadrants scaled;
# fmd/antimic/surgery = probabilities; maint_per_year = D4910 visits/yr after therapy.
STAGE_TREATMENT = {
    "healthy": {"srp_prob": 0.0,  "srp_quads": (0, 0), "fmd": 0.0,  "antimic": 0.0,  "surgery": 0.0,   "maint_per_year": 0},
    "I":       {"srp_prob": 0.3,  "srp_quads": (1, 2), "fmd": 0.05, "antimic": 0.05, "surgery": 0.015, "maint_per_year": 2},
    "II":      {"srp_prob": 0.85, "srp_quads": (2, 3), "fmd": 0.10, "antimic": 0.15, "surgery": 0.05,  "maint_per_year": 3},
    "III":     {"srp_prob": 0.95, "srp_quads": (3, 4), "fmd": 0.15, "antimic": 0.32, "surgery": 0.12,  "maint_per_year": 4},
    "IV":      {"srp_prob": 0.95, "srp_quads": (4, 4), "fmd": 0.18, "antimic": 0.40, "surgery": 0.25,  "maint_per_year": 4},
}

PERIO_RECESSION_MM_PER_DECADE = 0.5  # recession grows ~0.5mm/decade after age 20

# CAL band per stage, used ONLY by the --stage corner-case test mode. Because the
# 2017 stage is set by interdental CAL (not probing depth), the lock bounds CAL: the
# upper value is the max interdental CAL allowed (II<=4 never reaches Stage III's >=5),
# and DEFMIN is the worst-site CAL that makes the case recognizably that stage.
# Probing depth is left FREE -- isolated deep pseudopockets are allowed at any stage.
STAGE_CAL_BAND = {
    "healthy": (0, 1),
    "I": (0, 2),
    "II": (0, 4),
    "III": (0, 9),
    "IV": (0, 13),
}
STAGE_CAL_DEFMIN = {"healthy": 0, "I": 1, "II": 3, "III": 5, "IV": 5}

# Radiographic bone loss (RBL), as % of root length -- the 2017 co-determinant of stage
# alongside CAL. 2017 thresholds: Stage I <15% (coronal third), II 15-33% (coronal third),
# III extends to the middle third, IV to the apical third. Within severe disease, whether
# RBL reaches the apical third (>= RBL_APICAL_THRESHOLD) DETERMINES Stage IV vs III (see
# _assign_perio_profiles). Open Dental's perio schema has no structured bone-loss field,
# so the value is recorded in the perioexam Note.
STAGE_BONE_LOSS = {"healthy": (0, 4), "I": (5, 14), "II": (15, 33), "III": (33, 59), "IV": (60, 90)}
RBL_APICAL_THRESHOLD = 60  # RBL >= apical third => Stage IV

# Risk-based periodontal-maintenance (D4910) recall interval, in MONTHS. The fixed
# "3 months for everyone" default is replaced by individualized intervals per the
# Lang & Tonetti Periodontal Risk Assessment and the AAP/EFP grade mapping
# (Grade A 6-12mo, Grade B 3-4mo, Grade C bimonthly until stable). The interval is
# re-decided at EVERY maintenance visit from the patient's CURRENT status (stage by
# worst-site CAL, grade, smoking/diabetes, residual >=5mm pockets, compliance), so it
# tightens as disease recurs and lengthens when stable. Tiers (high-risk-factor count):
#   >=2 high factors -> very high -> 2 mo;  1 -> high -> 3 mo;
#   else Grade B / diabetic -> moderate -> 4 mo;  else low -> 6 mo.
PERIO_RECALL_MONTHS = {"very_high": 2, "high": 3, "moderate": 4, "low": 6}
PERIO_FIRST_MAINT_MIN_DAYS = 84  # insurance floor: first D4910 >= ~12 weeks after SRP


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
    def __init__(self, seed: int = DEFAULT_SEED, city: str = None, state: str = None, patient_count: int = DEFAULT_PATIENT_COUNT,
                 gen_perio: bool = True, perio_stage: str = None, perio_grade: str = None):
        self.seed = seed
        self.patient_count = patient_count
        self.gen_perio = gen_perio
        # Corner-case test locks: force every periodontitis patient to a single stage
        # and/or grade. When perio_stage is set, exams are held strictly within that
        # stage's band (no progression to the next stage). See _generate_perio.
        self.perio_stage = perio_stage
        self.perio_grade = perio_grade
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
        self.next_perioexam_num = 10000
        self.next_periomeasure_num = 10000

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
        self.perioexams = []
        self.periomeasures = []

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
        if self.gen_perio:
            self._assign_perio_profiles()
        self._generate_inssubs_and_patplans()
        self._generate_appointments_and_procedures()
        if self.gen_perio:
            self._generate_perio()
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

        # Build bundle weights. When perio is enabled, the perio module owns SRP and
        # perio-maintenance procedures, so exclude those bundles from the random pool
        # (prevents healthy patients randomly receiving SRP, and double-booked cleanings).
        if self.gen_perio:
            bundle_names = [b for b in APPOINTMENT_BUNDLES if b not in ("srp_quad", "perio_maintenance")]
        else:
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

                # Perio patients in maintenance get their hygiene visits as D4910
                # periodontal maintenance, created by the perio module on a guaranteed
                # 3-month cadence. Skip the generic prophy recall here so the patient
                # isn't double-booked with both a D1110 and a D4910 cleaning.
                if bundle_name == "recall_hygiene" and self._patient_in_perio_maintenance(patient):
                    continue

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
                # Skip generic hygiene recalls for perio-maintenance patients (handled
                # by the perio module); other future visit types are scheduled normally.
                if not (bundle_name == "recall_hygiene" and self._patient_in_perio_maintenance(patient)):
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
        pct_tp = 100 * len(patients_needing_tp) / len(self.patients) if self.patients else 0
        print(f"    {len(patients_needing_tp)} patients have unscheduled treatment ({pct_tp:.1f}%)")

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

    # =========================================================================
    # PERIODONTAL CHARTING & TREATMENT
    # =========================================================================

    def _patient_in_perio_maintenance(self, patient: dict) -> bool:
        """True if the patient is a periodontitis case in active D4910 maintenance."""
        p = patient.get("perio")
        return bool(p and p.get("maintenance"))

    def _assign_perio_profiles(self):
        """Assign each adult a periodontal stage/grade/risk profile (in-memory only)."""
        print("  Assigning periodontal profiles...")
        counts = {s: 0 for s in PERIO_STAGES}
        for patient in self.patients:
            if patient["Age"] < PERIO_MIN_AGE:
                patient["perio"] = None
                continue

            smoker = random.random() < 0.17
            diabetic = random.random() < 0.10
            stage = self._perio_sample_stage(patient, smoker, diabetic)
            # --stage lock: keep healthy patients healthy, force every diseased patient
            # to the target stage (so the cohort is healthy + a single periodontitis stage).
            if self.perio_stage and stage != "healthy":
                stage = self.perio_stage
            # Radiographic bone loss. For severe disease (not under a stage lock), RBL is
            # the 2017 determinant of Stage IV vs III: apical-third loss -> IV, else III.
            # Otherwise RBL is sampled consistent with the (possibly forced) stage.
            if stage in ("III", "IV") and not self.perio_stage:
                bone_loss = round(random.triangular(33, 90, 45))
                stage = "IV" if bone_loss >= RBL_APICAL_THRESHOLD else "III"
            else:
                bone_loss = random.randint(*STAGE_BONE_LOSS[stage])
            grade = self._perio_sample_grade(stage, smoker, diabetic)
            # --grade lock: force the grade of diseased patients only (healthy keep theirs).
            if self.perio_grade and stage != "healthy":
                grade = self.perio_grade
            tx = STAGE_TREATMENT[stage]
            treated = (stage != "healthy") and (random.random() < tx["srp_prob"])
            compliant = random.random() < 0.7

            teeth = list(PERIO_TEETH)
            missing = STAGE_CAL_RANGES[stage]["missing"]
            if missing:
                teeth = self._perio_remove_teeth(teeth, random.randint(*missing))

            patient["perio"] = {
                "stage": stage, "grade": grade, "smoker": smoker, "diabetic": diabetic,
                "treated": treated, "compliant": compliant, "maintenance": treated,
                "teeth": teeth, "bone_loss": bone_loss,
            }
            counts[stage] += 1

        total = sum(counts.values())
        perio_ct = total - counts["healthy"]
        locks = []
        if self.perio_stage:
            locks.append(f"stage={self.perio_stage} (held in-band, no progression)")
        if self.perio_grade:
            locks.append(f"grade={self.perio_grade}")
        if locks:
            print("    TEST LOCK active: " + ", ".join(locks))
        print(f"    Profiled {total} adults: " + ", ".join(f"{s}={counts[s]}" for s in PERIO_STAGES))
        if total:
            print(f"    Periodontitis (any stage): {perio_ct} ({100*perio_ct/total:.1f}%)")

    def _perio_sample_stage(self, patient: dict, smoker: bool, diabetic: bool) -> str:
        age = patient["Age"]
        weights = None
        for max_age, w in AGE_STAGE_DISTRIBUTION:
            if age <= max_age:
                weights = list(w)
                break
        if weights is None:
            weights = list(AGE_STAGE_DISTRIBUTION[-1][1])
        if patient["Gender"] == 0:  # males have higher severe prevalence
            weights = [weights[0]*0.95, weights[1], weights[2]*1.05, weights[3]*1.2, weights[4]*1.2]
        if smoker:
            weights = [weights[0]*0.6, weights[1]*0.9, weights[2]*1.1, weights[3]*2.0, weights[4]*2.0]
        if diabetic:
            weights = [weights[0]*0.8, weights[1]*0.95, weights[2]*1.15, weights[3]*1.6, weights[4]*1.6]
        return random.choices(PERIO_STAGES, weights=weights)[0]

    def _perio_sample_grade(self, stage: str, smoker: bool, diabetic: bool) -> str:
        opts = STAGE_GRADE_DISTRIBUTION[stage]
        grade = random.choices([g for g, _ in opts], weights=[w for _, w in opts])[0]
        order = ["A", "B", "C"]
        if (smoker and random.random() < 0.6) or (diabetic and random.random() < 0.5):
            grade = order[min(2, order.index(grade) + 1)]
        return grade

    def _perio_remove_teeth(self, teeth: list, n: int) -> list:
        """Remove n teeth, preferentially molars then posterior (periodontitis pattern)."""
        ordered = sorted(teeth, key=lambda t: (t not in MOLAR_TEETH, t in ANTERIOR_INT, random.random()))
        drop = set(ordered[:n])
        return [t for t in teeth if t not in drop]

    # Per-site model: CAL is the staging severity; the gingival margin = recession
    # (apical, +) minus inflammatory swelling (coronal, -). Probing depth is DERIVED:
    #   margin = rec - swell ;  PD = CAL - margin = CAL - rec + swell  (clamped 1..12)
    # Open Dental then recomputes CAL = Probing + GingMargin. Keeping rec <= CAL-1 makes
    # PD >= 1 so the stored CAL equals the modeled CAL. Swelling > recession yields a
    # coronal margin (pseudopocket): a deep pocket whose CAL stays in a lower stage.
    @staticmethod
    def _site_pd(t: dict, i: int) -> int:
        # CAL is tracked as a float (sub-mm progression); round to whole mm for charting.
        return max(1, min(12, int(round(t["cal"][i])) - t["rec"][i] + t["swell"][i]))

    @staticmethod
    def _chart_worst_cal(chart: dict) -> int:
        """Worst interdental (mesial/distal) CAL across the chart, in whole mm -- the
        2017 staging severity driver."""
        worst = 0
        for t in chart.values():
            for i in PERIO_INTERPROX_IDX:
                worst = max(worst, int(round(t["cal"][i])))
        return worst

    @staticmethod
    def _stage_from_cal(worst_cal: int) -> str:
        """Map worst-site interdental CAL to the 2017 stage (severity axis). III vs IV is
        not separable by CAL alone -- callers that need it keep the profile's III/IV."""
        if worst_cal <= 0:
            return "healthy"
        if worst_cal <= 2:
            return "I"
        if worst_cal <= 4:
            return "II"
        if worst_cal <= 7:
            return "III"
        return "IV"

    @staticmethod
    def _rbl_descriptor(pct: int) -> str:
        third = "coronal third" if pct < 33 else "middle third" if pct < RBL_APICAL_THRESHOLD else "apical third"
        return f"~{pct}% of root length ({third})"

    def _perio_recall_days(self, chart: dict, profile: dict) -> int:
        """Individualized D4910 recall interval (days), re-decided from the patient's
        CURRENT status. The RECOMMENDED interval is risk-based (worst-site CAL stage,
        grade, smoking, residual >=6mm pockets, diabetes). The REALIZED interval then
        stretches for non-compliant patients, who skip/delay visits -- the literature
        shows regular compliers cluster at ~3-4 months while non-compliers average
        ~6.3 months. Returns the realized interval with scheduling jitter."""
        cur_stage = self._stage_from_cal(self._chart_worst_cal(chart))
        residual_deep = sum(1 for t in chart.values() for i in range(6) if self._site_pd(t, i) >= 6)
        high = 0
        if cur_stage in ("III", "IV"):
            high += 1
        if profile["grade"] == "C":
            high += 1
        if profile["smoker"]:
            high += 1
        if residual_deep >= 4:
            high += 1
        if high >= 3:
            tier = "very_high"          # e.g. Stage IV + Grade C + smoker -> bimonthly
        elif high >= 1:
            tier = "high"               # any single high risk factor -> ~3 months (AAP default)
        elif profile["grade"] == "B" or profile["diabetic"]:
            tier = "moderate"           # Grade B / diabetic -> ~4 months
        else:
            tier = "low"                # Grade A, Stage I/II, compliant, no risk -> ~6 months
        months = PERIO_RECALL_MONTHS[tier]
        if not profile["compliant"]:
            months *= random.uniform(1.5, 2.2)   # irregular compliers stretch/skip recall
        # +/-10-20% scheduling jitter; clamp to plausible booking bounds (up to ~18 mo).
        days = months * 30.4 * random.uniform(0.9, 1.2)
        return int(max(45, min(540, days)))

    def _perio_baseline_chart(self, profile: dict, age: int) -> dict:
        """Build the baseline chart: sample per-site CAL (severity) by stage, then a
        recession component and a localized inflammatory-swelling component; probing
        depth is derived from these at charting time."""
        stage = profile["stage"]
        rng = STAGE_CAL_RANGES[stage]
        base, worst = rng["base"], rng["worst"]
        age_rec = max(0, int(round((age - 20) / 10.0 * PERIO_RECESSION_MM_PER_DECADE)))

        chart = {}
        for tooth in profile["teeth"]:
            is_molar = tooth in MOLAR_TEETH
            is_ant = tooth in ANTERIOR_INT
            cal, rec, swell = [], [], []
            for i in range(6):
                interprox = i in PERIO_INTERPROX_IDX
                # --- CAL (the staging determinant): worst at interproximal molar sites ---
                if stage == "healthy":
                    c = random.randint(*base)
                elif is_molar and interprox:
                    c = random.randint(*worst)
                elif is_molar or interprox:
                    lo = (base[0] + worst[0]) // 2
                    hi = (base[1] + worst[1]) // 2
                    c = random.randint(min(lo, hi), max(lo, hi))
                elif is_ant:
                    c = random.randint(*base)
                else:
                    c = random.randint(base[0], base[1])
                c = max(0, min(12, c))
                cal.append(c)
                # --- recession component (<= CAL-1 so PD stays >=1 and CAL is exact) ---
                if c <= 0:
                    r = 0
                else:
                    r = min(c - 1, age_rec + (1 if (c >= 4 and random.random() < 0.4) else 0))
                    r = max(0, r)
                rec.append(r)
                # --- inflammatory swelling (coronal margin / pseudopocket), localized ---
                if stage == "healthy":
                    s = random.choice([0, 0, 0, 1])
                elif interprox and c >= 3:
                    s = random.choices([0, 1, 2, 3], [0.45, 0.25, 0.2, 0.1])[0]
                elif c >= 3:
                    s = random.choices([0, 1, 2], [0.6, 0.3, 0.1])[0]
                else:
                    s = random.choice([0, 0, 1])
                swell.append(s)

            maxcal = max(cal)
            mob = 0
            if stage == "III" and maxcal >= 5:
                mob = random.choices([0, 1, 2], [0.5, 0.35, 0.15])[0]
            elif stage == "IV" and maxcal >= 5:
                mob = random.choices([0, 1, 2, 3], [0.2, 0.3, 0.35, 0.15])[0]

            furc = None
            if is_molar and stage in ("III", "IV"):
                furc = [random.choices([0, 1, 2, 3], [0.3, 0.3, 0.3, 0.1])[0]
                        if (i in PERIO_INTERPROX_IDX and cal[i] >= 5) else 0 for i in range(6)]

            chart[tooth] = {"cal": cal, "base_cal": list(cal), "rec": rec, "swell": swell,
                            "mgj": random.randint(2, 5), "mob": mob, "furc": furc}
        return chart

    def _perio_apply_srp(self, chart: dict):
        """Post-SRP improvement = small attachment gain + resolution of inflammatory
        swelling (Cobb 2002: PD drop ~= CAL gain + gingival shrinkage)."""
        for t in chart.values():
            for i in range(6):
                c = t["cal"][i]
                if c >= 5:        # mean ~1.2mm attachment gain on deep pockets (Cobb)
                    t["cal"][i] = max(1.0, c - random.uniform(0.8, 1.5))
                elif c >= 3:      # mean ~0.55mm attachment gain on moderate pockets
                    t["cal"][i] = max(1.0, c - random.uniform(0.3, 0.8))
                t["swell"][i] = max(0, t["swell"][i] - random.randint(1, 3))  # edema resolves
                if random.random() < 0.3:                   # margin recedes as swelling drops
                    t["rec"][i] = min(max(0, int(t["cal"][i]) - 1), t["rec"][i] + 1)
            if t["mob"] > 0 and random.random() < 0.4:
                t["mob"] -= 1

    def _perio_apply_surgery(self, chart: dict):
        """Osseous surgery resolves residual deep pockets (eliminates swelling, gains
        some attachment at sites still deep after re-evaluation)."""
        for t in chart.values():
            for i in range(6):
                if self._site_pd(t, i) >= 6:
                    if t["cal"][i] >= 6:
                        t["cal"][i] = max(2.0, t["cal"][i] - random.uniform(1.0, 2.0))
                    t["swell"][i] = 0
                    if random.random() < 0.5:
                        t["rec"][i] = min(max(0, int(t["cal"][i]) - 1), t["rec"][i] + 1)

    def _perio_advance_chart(self, chart: dict, grade: str, worsen_mult: float):
        """Evolve one maintenance step (~3 months): worsening = real attachment loss
        (CAL up, the irreversible progression that grade governs); improving/stable just
        move the reversible inflammatory swelling that drives pocket depth."""
        tp = GRADE_TRANSITION[grade]
        p_imp, _, p_wor0 = tp["p"]
        gmob = {"A": 0.3, "B": 1.0, "C": 2.0}[grade]
        for t in chart.values():
            for i in range(6):
                # Attachment loss concentrates at already-diseased sites; shallow/healthy
                # sites rarely break down, so whole-mouth progression stays realistic.
                sev = min(1.0, 0.05 + 0.15 * t["cal"][i])
                p_wor = min(0.9, p_wor0 * worsen_mult * sev)
                p_stab = max(0.0, 1 - p_imp - p_wor)
                r = random.random()
                if r < p_imp:                               # inflammation control: pocket shrinks
                    t["swell"][i] = max(0, t["swell"][i] - 1)
                elif r < p_imp + p_stab:                    # noise in inflammation
                    t["swell"][i] = max(0, min(3, t["swell"][i] + random.choice([-1, 0, 0, 1])))
                else:                                       # progression: real attachment loss
                    t["cal"][i] = min(12.0, t["cal"][i] + random.uniform(*tp["worsen"]))
                    if random.random() < 0.5:
                        t["rec"][i] = min(max(0, int(t["cal"][i]) - 1), t["rec"][i] + 1)
                    t["swell"][i] = min(3, t["swell"][i] + 1)
            maxcal = max(t["cal"])
            if maxcal >= 6 and t["mob"] < 3 and random.random() < 0.05 * gmob:
                t["mob"] += 1
            elif maxcal <= 3 and t["mob"] > 0 and random.random() < 0.2:
                t["mob"] -= 1

    def _perio_jitter_healthy(self, chart: dict):
        """Periodontally healthy patients do not progress (no attachment loss); only the
        reversible inflammation jitters slightly, so charts stay shallow over time."""
        for t in chart.values():
            for i in range(6):
                t["swell"][i] = max(0, min(1, t["swell"][i] + random.choice([-1, 0, 0, 1])))

    def _perio_stage_jitter(self, chart: dict, stage: str):
        """--stage test mode: hold CAL (the staging quantity) mean-reverting in the
        stage's CAL band so the case never crosses stages, while jittering the
        inflammatory swelling so probing depth still varies (incl. deep pseudopockets)."""
        lo, hi = STAGE_CAL_BAND.get(stage, (0, 12))
        for t in chart.values():
            for i in range(6):
                t["cal"][i] = max(lo, min(hi, t["base_cal"][i] + random.choice([-1, 0, 0, 1])))
                t["rec"][i] = min(max(0, int(t["cal"][i]) - 1), t["rec"][i])
                t["swell"][i] = max(0, min(3, t["swell"][i] + random.choice([-1, 0, 0, 1])))

    def _perio_evolve(self, chart: dict, grade: str, worsen_mult: float, stage: str):
        """Advance the chart one visit: realistic grade progression normally, or
        CAL-bounded jitter when a --stage test lock is active."""
        if self.perio_stage:
            self._perio_stage_jitter(chart, stage)
        else:
            self._perio_advance_chart(chart, grade, worsen_mult)

    def _perio_bleed_surfaces(self, t: dict, inflammation: float, bop: float) -> list:
        """Per-site Bleeding bitmask -- bleeding rises with the stage's baseline BOP
        burden (bop), current inflammatory swelling, and depth, modulated by the
        inflammation factor (treatment lowers it). SequenceType 6 encoding."""
        out = []
        for i in range(6):
            s = t["swell"][i]
            pd = self._site_pd(t, i)
            p = min(0.95, (0.3 * bop + 0.15 * s + 0.03 * max(0, pd - 4)) * inflammation)
            flag = 0
            if random.random() < p:
                flag |= PERIO_FLAG_BLEED
                if pd >= 6 and s >= 2 and random.random() < 0.2:
                    flag |= PERIO_FLAG_SUPP
            if random.random() < 0.25:
                flag |= PERIO_FLAG_PLAQUE
            if pd >= 5 and random.random() < 0.3:
                flag |= PERIO_FLAG_CALC
            out.append(flag)
        return out

    def _perio_tooth_loss(self, patient: dict, chart: dict, profile: dict, grade: str, date_: date):
        """Probabilistically extract hopeless teeth (severe attachment loss) in maintenance."""
        gmult = {"A": 0.2, "B": 0.5, "C": 1.0}[grade]
        for tooth in list(chart.keys()):
            if max(chart[tooth]["cal"]) >= 8 and random.random() < 0.02 * gmult:
                del chart[tooth]
                profile["teeth"] = [t for t in profile["teeth"] if t != tooth]
                if date_ <= self.today:
                    self._create_perio_appointment(
                        patient, date_, [("D7140", None, tooth)], is_hygiene=False, prov_num=patient["PriProv"])

    def _create_periomeasure(self, exam_num: int, exam_dt: datetime, seq_type: int,
                             tooth: int, tooth_value: int, surfaces: list):
        m_num = self.next_periomeasure_num
        self.next_periomeasure_num += 1
        mb, b, db, ml, l, dl = surfaces
        self.periomeasures.append({
            "PerioMeasureNum": m_num, "PerioExamNum": exam_num,
            "SequenceType": seq_type, "IntTooth": tooth,
        })
        self.sql_statements.append(generate_insert(
            "periomeasure",
            ["PerioMeasureNum", "PerioExamNum", "SequenceType", "IntTooth", "ToothValue",
             "MBvalue", "Bvalue", "DBvalue", "MLvalue", "Lvalue", "DLvalue", "SecDateTEdit"],
            [m_num, exam_num, seq_type, tooth, tooth_value, mb, b, db, ml, l, dl, exam_dt]
        ))

    def _emit_perio_exam(self, patient: dict, exam_date: date, chart: dict, prov_num: int,
                         full: bool, inflammation: float):
        """Emit one perioexam plus its data-bearing periomeasure rows."""
        if not chart:
            return
        exam_num = self.next_perioexam_num
        self.next_perioexam_num += 1
        exam_dt = datetime.combine(
            exam_date,
            datetime.min.time().replace(hour=random.randint(8, 16), minute=random.choice([0, 15, 30, 45])))
        note = "Comprehensive periodontal charting." if full else "Periodontal maintenance charting."
        perio = patient.get("perio")
        if perio and perio["stage"] != "healthy":
            note += f" Radiographic bone loss {self._rbl_descriptor(perio['bone_loss'])}."

        self.perioexams.append({
            "PerioExamNum": exam_num, "PatNum": patient["PatNum"],
            "ExamDate": exam_date, "ProvNum": prov_num,
        })
        self.sql_statements.append(generate_insert(
            "perioexam",
            ["PerioExamNum", "PatNum", "ExamDate", "ProvNum", "DateTMeasureEdit", "Note"],
            [exam_num, patient["PatNum"], exam_date, prov_num, exam_dt, note]
        ))

        # Baseline bleeding burden tracks the CURRENT severity (worst-site CAL) of this exam.
        bop = STAGE_CAL_RANGES[self._stage_from_cal(self._chart_worst_cal(chart))]["bop"]

        for tooth in sorted(chart.keys()):
            t = chart[tooth]
            # Probing depth, then derive the gingival margin so that the CAL Open Dental
            # recomputes (CAL = Probing + GingMargin) EXACTLY equals the modeled CAL,
            # regardless of the 1..12 probing clamp. margin = round(CAL) - PD.
            pd = [self._site_pd(t, i) for i in range(6)]
            margin = [int(round(t["cal"][i])) - pd[i] for i in range(6)]
            # Probing depth (always)
            self._create_periomeasure(exam_num, exam_dt, PERIO_SEQ_PROBING, tooth, PERIO_NO_MEASURE, pd)
            # Gingival margin (always); coronal/negative (pseudopocket) encodes as 100+|v|
            ging_enc = [v if v >= 0 else 100 + (-v) for v in margin]
            self._create_periomeasure(exam_num, exam_dt, PERIO_SEQ_GINGMARGIN, tooth, PERIO_NO_MEASURE, ging_enc)
            # Bleeding/suppuration/plaque/calculus (always)
            self._create_periomeasure(exam_num, exam_dt, PERIO_SEQ_BLEEDING, tooth, PERIO_NO_MEASURE,
                                      self._perio_bleed_surfaces(t, inflammation, bop))
            if full:
                # Mucogingival junction; maxillary lingual sites left -1
                m = t["mgj"]
                if tooth in MAXILLARY_TEETH:
                    mgj = [max(1, m + random.choice([-1, 0, 0, 1])), m,
                           max(1, m + random.choice([-1, 0, 0, 1])),
                           PERIO_NO_MEASURE, PERIO_NO_MEASURE, PERIO_NO_MEASURE]
                else:
                    mgj = [max(1, m + random.choice([-1, 0, 0, 1])) for _ in range(6)]
                self._create_periomeasure(exam_num, exam_dt, PERIO_SEQ_MGJ, tooth, PERIO_NO_MEASURE, mgj)
                # Furcation (molars with involvement)
                if t["furc"] is not None and any(f > 0 for f in t["furc"]):
                    self._create_periomeasure(exam_num, exam_dt, PERIO_SEQ_FURCATION, tooth, PERIO_NO_MEASURE, t["furc"])
            # Mobility whenever present
            if t["mob"] > 0:
                self._create_periomeasure(exam_num, exam_dt, PERIO_SEQ_MOBILITY, tooth, t["mob"],
                                          [PERIO_NO_MEASURE] * 6)

    def _create_perio_appointment(self, patient: dict, apt_date: date, proc_specs: list,
                                  is_hygiene: bool, prov_num: int):
        """Create a completed appointment for perio treatment with explicit procedures.

        proc_specs is a list of (proc_code, quadrant_or_None, tooth_or_None).
        """
        apt_num = self.next_apt_num
        self.next_apt_num += 1

        if is_hygiene:
            op = random.choice([o for o in self.operatories if o["IsHygiene"]])
            prov_hyg = prov_num
        else:
            op = random.choice([o for o in self.operatories if not o["IsHygiene"]])
            prov_hyg = 0

        hour = random.randint(8, 16)
        minute = random.choice([0, 15, 30, 45])
        apt_datetime = datetime.combine(apt_date, datetime.min.time().replace(hour=hour, minute=minute))
        pattern = "XXXXXXXXX" if is_hygiene else "XXXXXXXXXXXXXXX"
        note = random.choice(APPOINTMENT_NOTE_TEMPLATES)
        patplan = self._get_patient_insurance(patient["PatNum"])
        insplan1 = patplan["PlanNum"] if patplan else 0

        codes = [s[0] for s in proc_specs]
        proc_descript = ", ".join(codes[:3]) + (f" +{len(codes)-3}" if len(codes) > 3 else "")

        self.appointments.append({
            "AptNum": apt_num, "PatNum": patient["PatNum"], "AptStatus": 2, "Pattern": pattern,
            "Confirmed": 0, "Op": op["OperatoryNum"], "Note": note, "ProvNum": prov_num,
            "ProvHyg": prov_hyg, "AptDateTime": apt_datetime, "IsNewPatient": 0,
            "ProcDescript": proc_descript, "IsHygiene": 1 if is_hygiene else 0,
            "InsPlan1": insplan1, "InsPlan2": 0,
        })
        self.sql_statements.append(generate_insert(
            "appointment",
            ["AptNum", "PatNum", "AptStatus", "Pattern", "Confirmed", "Op", "Note",
             "ProvNum", "ProvHyg", "AptDateTime", "IsNewPatient", "ProcDescript", "IsHygiene",
             "InsPlan1", "InsPlan2"],
            [apt_num, patient["PatNum"], 2, pattern, 0, op["OperatoryNum"], note,
             prov_num, prov_hyg, apt_datetime, 0, proc_descript, 1 if is_hygiene else 0,
             insplan1, 0]
        ))

        for code, quadrant, tooth in proc_specs:
            self._create_procedure(
                patient=patient, apt_num=apt_num, proc_code=code, proc_date=apt_date,
                prov_num=prov_num, status=2, quadrant=quadrant,
                tooth=str(tooth) if tooth is not None else None)

    def _generate_perio(self):
        """Generate longitudinal perio exams and the matching treatment course per adult."""
        print("  Generating periodontal exams and treatment...")
        dentists = [PROVIDER_START_NUM, PROVIDER_START_NUM + 1]
        hygienists = [PROVIDER_START_NUM + 2, PROVIDER_START_NUM + 3]

        for patient in self.patients:
            profile = patient.get("perio")
            if not profile:
                continue
            if (self.today - patient["DateFirstVisit"]).days < 30:
                continue

            stage, grade = profile["stage"], profile["grade"]
            first = patient["DateFirstVisit"]
            dentist = random.choice(dentists)
            hygienist = random.choice(hygienists)
            inflammation = 1.0 if profile["compliant"] else 1.3
            chart = self._perio_baseline_chart(profile, patient["Age"])
            # --stage test lock: clamp the baseline CAL (and its mean-revert anchor) into
            # the stage's CAL band so even the first exam can never reach the next stage's
            # severity. Probing depth is left free (deep pseudopockets remain possible).
            if self.perio_stage:
                lo, hi = STAGE_CAL_BAND[stage]
                for t in chart.values():
                    t["cal"] = [max(lo, min(hi, v)) for v in t["cal"]]
                    t["base_cal"] = list(t["cal"])
                    t["rec"] = [min(max(0, int(t["cal"][i]) - 1), t["rec"][i]) for i in range(6)]

            # Healthy adults: occasional screening charting only (not everyone is charted).
            if stage == "healthy":
                if random.random() < 0.45:
                    continue
                d = first + timedelta(days=random.randint(0, 150))
                first_exam = True
                while d <= self.today:
                    self._perio_jitter_healthy(chart)
                    self._emit_perio_exam(patient, d, chart, hygienist, full=first_exam, inflammation=1.0)
                    first_exam = False
                    d = d + timedelta(days=random.randint(330, 420))
                continue

            tx = STAGE_TREATMENT[stage]

            # 1) Comprehensive periodontal evaluation + radiographs (+ optional debridement).
            eval_date = first + timedelta(days=random.randint(0, 45))
            eval_specs = [("D0180", None, None), ("D0274", None, None)]
            if random.random() < tx["fmd"]:
                eval_specs.append(("D4355", None, None))
            self._create_perio_appointment(patient, eval_date, eval_specs, is_hygiene=False, prov_num=dentist)
            self._emit_perio_exam(patient, eval_date, chart, dentist, full=True, inflammation=inflammation)
            last_date = eval_date

            if not profile["treated"]:
                # Diagnosed but prophy-only (mostly Stage I): periodic charting, slow drift.
                d = eval_date + timedelta(days=random.randint(150, 210))
                while d <= self.today:
                    self._perio_evolve(chart, grade, 1.0, stage)
                    self._emit_perio_exam(patient, d, chart, hygienist, full=False, inflammation=inflammation)
                    d = d + timedelta(days=random.randint(170, 210))
                continue

            # 2) Scaling & root planing by quadrant (<=2 quadrants/visit).
            present_quads = [q for q in QUADRANTS if any(_tooth_quadrant(t) == q for t in profile["teeth"])]
            random.shuffle(present_quads)
            n_quads = min(random.randint(*tx["srp_quads"]), len(present_quads))
            srp_quads = present_quads[:max(1, n_quads)]
            srp_code = "D4342" if stage == "I" else "D4341"
            for i in range(0, len(srp_quads), 2):
                srp_date = last_date + timedelta(days=random.randint(7, 21))
                if srp_date > self.today:
                    break
                batch = srp_quads[i:i + 2]
                specs = [(srp_code, q, None) for q in batch]
                if random.random() < tx["antimic"]:
                    qt = [t for t in profile["teeth"] if _tooth_quadrant(t) == batch[0]]
                    if qt:
                        specs.append(("D4381", None, random.choice(qt)))
                self._create_perio_appointment(patient, srp_date, specs, is_hygiene=True, prov_num=hygienist)
                last_date = srp_date

            # 3) Re-evaluation ~6 weeks after SRP applies the one-time improvement.
            # (In --stage test mode the chart is held in-band, so the SRP drop is
            # suppressed -- the treatment procedures are still recorded.)
            reeval_date = last_date + timedelta(days=random.randint(35, 49))
            if not self.perio_stage:
                self._perio_apply_srp(chart)
            if reeval_date <= self.today:
                self._create_perio_appointment(patient, reeval_date, [("D0120", None, None)],
                                               is_hygiene=False, prov_num=dentist)
                self._emit_perio_exam(patient, reeval_date, chart, dentist, full=True,
                                      inflammation=inflammation * 0.7)
                last_date = reeval_date

            # 4) A fraction proceed to osseous surgery for residual deep pockets.
            if random.random() < tx["surgery"]:
                surg_date = reeval_date + timedelta(days=random.randint(30, 90))
                if surg_date <= self.today:
                    if not self.perio_stage:
                        self._perio_apply_surgery(chart)
                    surg_code = "D4260" if stage in ("III", "IV") else "D4261"
                    deep_quads = srp_quads[:max(1, len(srp_quads) // 2)]
                    specs = [(surg_code, q, None) for q in deep_quads]
                    self._create_perio_appointment(patient, surg_date, specs, is_hygiene=False, prov_num=dentist)
                    self._emit_perio_exam(patient, surg_date, chart, dentist, full=True,
                                          inflammation=inflammation * 0.6)
                    last_date = surg_date

            # 5) Periodontal maintenance (D4910). The perio module owns these visits (the
            # generic recall stream skips routine prophy for maintenance patients). The
            # recall interval is INDIVIDUALIZED and re-decided each visit from current
            # status (see _perio_recall_days): low-risk stable cases stretch toward 6
            # months, high-risk/recurrent cases tighten toward 2-3 months. Maintenance is
            # protective: compliant patients progress far slower than untreated rates, so
            # most stay stable (Hirschfeld & Wasserman ~83% well-maintained); non-compliant
            # patients drive the downhill/tooth-loss tail. If disease recurs to a higher
            # stage with deep residual pockets, the patient RE-ENTERS active therapy.
            worsen_mult = 0.25 if profile["compliant"] else 0.7
            orig_idx = PERIO_STAGES.index(stage)
            gap = random.randint(PERIO_FIRST_MAINT_MIN_DAYS, 105)
            step = last_date + timedelta(days=gap)
            i = 0
            while step <= self.today and chart:
                # Attachment loss accrues with TIME, so apply roughly one ~3-month
                # progression step per 90 days of the gap since the last visit (longer
                # gaps from skipped recalls -> more interval progression).
                for _ in range(max(1, round(gap / 90))):
                    self._perio_evolve(chart, grade, worsen_mult, stage)
                if not self.perio_stage:
                    self._perio_tooth_loss(patient, chart, profile, grade, step)

                cur_idx = PERIO_STAGES.index(self._stage_from_cal(self._chart_worst_cal(chart)))
                deep_teeth = [t for t in chart if max(self._site_pd(chart[t], k) for k in range(6)) >= 6]
                recurrence = (not self.perio_stage and cur_idx > orig_idx and len(deep_teeth) >= 3
                              and random.random() < (0.3 if grade == "C" else 0.12))
                if recurrence:
                    # Re-enter active therapy: re-evaluation + localized re-SRP on the
                    # worst quadrants, which then reduces inflammation/pockets again.
                    aff_quads = sorted({_tooth_quadrant(t) for t in deep_teeth})[:2]
                    specs = [("D0180", None, None)] + [("D4341", q, None) for q in aff_quads]
                    self._create_perio_appointment(patient, step, specs, is_hygiene=False, prov_num=dentist)
                    self._perio_apply_srp(chart)
                    self._emit_perio_exam(patient, step, chart, dentist, full=True, inflammation=inflammation)
                else:
                    self._create_perio_appointment(
                        patient, step, [("D0120", None, None), ("D4910", None, None)],
                        is_hygiene=True, prov_num=hygienist)
                    if i % 2 == 0:
                        self._emit_perio_exam(patient, step, chart, hygienist, full=False, inflammation=inflammation)
                gap = self._perio_recall_days(chart, profile)
                step = step + timedelta(days=gap)
                i += 1

        print(f"    Created {len(self.perioexams)} perio exams, {len(self.periomeasures)} measurements")

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
        pct_overdue = 100 * actual_overdue / len(self.recalls) if self.recalls else 0
        print(f"    {actual_overdue} patients overdue for hygiene ({pct_overdue:.1f}%)")

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
        pct_ins = 100 * len(self.patplans) / len(self.patients) if self.patients else 0
        print(f"  - With insurance: {len(self.patplans)} ({pct_ins:.1f}%)")
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
        if self.gen_perio:
            perio_pats = len([p for p in self.patients if p.get("perio") and p["perio"]["stage"] != "healthy"])
            print(f"Perio Exams: {len(self.perioexams)}")
            print(f"Perio Measurements: {len(self.periomeasures)}")
            print(f"  - Periodontitis patients (Stage I-IV): {perio_pats}")
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
  python generate.py --stage II                         # TEST: only Stage II periodontitis
  python generate.py --grade A                          # TEST: all periodontitis Grade A
  python generate.py --stage III --grade C              # TEST: Stage III, Grade C only

More info: https://github.com/dentaljosh/synthetic-opendental
Built by the team at Luna (https://yourluna.co)
        """
    )
    parser.add_argument("--city", type=str, help="Target city for addresses (e.g., 'Chicago')")
    parser.add_argument("--state", type=str, help="Target state for addresses (e.g., 'IL')")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--patients", type=int, default=DEFAULT_PATIENT_COUNT, help="Number of patients to generate (default: 750)")
    parser.add_argument("--output", type=str, default="synthetic_data.sql", help="Output SQL file (default: synthetic_data.sql)")
    parser.add_argument("--no-perio", action="store_true", help="Skip periodontal charting and treatment generation")
    parser.add_argument("--stage", type=str, choices=["I", "II", "III", "IV", "1", "2", "3", "4"],
                        help="TEST corner case: force every periodontitis patient to this single 2017 stage "
                             "(held strictly in-band, no progression to the next stage). Healthy patients are kept.")
    parser.add_argument("--grade", type=str, choices=["A", "B", "C", "a", "b", "c"],
                        help="TEST corner case: force every periodontitis patient to this single 2017 grade.")

    args = parser.parse_args()

    # Input validation.
    if args.patients < 1:
        parser.error("--patients must be a positive integer (>= 1).")
    if bool(args.city) != bool(args.state):
        parser.error("--city and --state must be used together (a city needs its state).")

    # Normalize the test-lock flags.
    stage_map = {"1": "I", "2": "II", "3": "III", "4": "IV"}
    perio_stage = stage_map.get(args.stage, args.stage) if args.stage else None
    perio_grade = args.grade.upper() if args.grade else None
    if args.no_perio and (perio_stage or perio_grade):
        print("Warning: --stage/--grade have no effect with --no-perio; ignoring them.")
        perio_stage = perio_grade = None

    generator = SyntheticDataGenerator(
        seed=args.seed,
        city=args.city,
        state=args.state,
        patient_count=args.patients,
        gen_perio=not args.no_perio,
        perio_stage=perio_stage,
        perio_grade=perio_grade,
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
