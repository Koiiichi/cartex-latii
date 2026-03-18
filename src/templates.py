from enum import Enum

class TemplateType(Enum):
    STANDARD_TAKEOFF = "standard_takeoff"
    STANDARD_TAKEOFF_TDL = "standard_takeoff_tdl"
    GLASS_SCHEDULE = "glass_schedule"
    SHOP_DETAILS = "shop_details"

TEMPLATES = {
    TemplateType.STANDARD_TAKEOFF: [
        "Product", "Operability", "Width", "Height", "Quantity", "Location", "Material", "Rough Opening Measurements", "Special Notes"
    ],
    TemplateType.STANDARD_TAKEOFF_TDL: [
        "Product", "Operability", "Width", "Height", "Quantity", "Location", "Material",
        "Dividers SDL Type", "Dividers TDL Type", "Special Notes"
    ],
    TemplateType.GLASS_SCHEDULE: [
        "Quantity", "Glass Width", "Glass Height", "Glass Layer", "Glass Brand", "Glass Type", "Glass Arrangement Configuration", "Glass Arrangement Spacer Type", "Glass Arrangement Space Filling", "Special Notes"
    ],
    TemplateType.SHOP_DETAILS: [
        "Product", "Product Type", "Operability", "Width", "Height", "Frame Brand", "Frame Profile","Frame Material", 
        "Hardware Style", 
        "Hardware Finish",
        "Finish",
        "Installation Location",
        "Installation Method",
        "Energy Rating",
        "Perimeter",
        "Area",
        "Weight",
        "Special Notes"
    ]
}

FIELD_LIBRARY = [
    "Generalities", "Label", "Sub-Label", "Product", "Product Type", "Operability", "Width", "Height", "Quantity", "Location",
    "Material",
    "Rough Opening Measurements",
    "Dividers TDL Type",
    "Dividers SDL Type",
    "Glass Width",
    "Glass Height",
    "Glass Layer",
    "Glass Brand",
    "Glass Type",
    "Glass Arrangement Configuration",
    "Glass Arrangement Spacer Type",
    "Glass Arrangement Space Filling",
    "Glass Arrangement Capilaty Tubes",
    "Frame Brand",
    "Frame Profile",
    "Frame Material",
    "Hardware Style",
    "Hardware Finish",
    "Finish",
    "Installation Location",
    "Installation Method",
    "Installation Glazed",
    "Energy Rating",
    "Perimeter",
    "Area",
    "Hardware Material",
    "Special Notes",
    "Source Type"
]