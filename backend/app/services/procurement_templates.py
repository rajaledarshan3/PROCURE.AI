
from copy import deepcopy

PROCUREMENT_TEMPLATES = {
    "chairs": {
        "name": "Office Chairs",
        "constraints": [
            {
                "field": "price",
                "operator": "<=",
                "value": 2500,
                "severity": "mandatory",
            },
            {
                "field": "material",
                "operator": "in",
                "value": ["steel", "metal"],
                "severity": "mandatory",
            },
            {
                "field": "load_capacity_kg",
                "operator": ">=",
                "value": 120,
                "severity": "mandatory",
            },
            {
                "field": "warranty_years",
                "operator": ">=",
                "value": 2,
                "severity": "preferred",
            },
        ],
    },
    "laptops": {
        "name": "Laptops",
        "constraints": [
            {
                "field": "price",
                "operator": "<=",
                "value": 60000,
                "severity": "mandatory",
            },
            {
                "field": "ram_gb",
                "operator": ">=",
                "value": 16,
                "severity": "mandatory",
            },
            {
                "field": "ssd_gb",
                "operator": ">=",
                "value": 512,
                "severity": "mandatory",
            },
            {
                "field": "warranty_years",
                "operator": ">=",
                "value": 3,
                "severity": "preferred",
            },
        ],
    },
    "desktops": {
        "name": "Desktop Computers",
        "constraints": [
            {
                "field": "price",
                "operator": "<=",
                "value": 50000,
                "severity": "mandatory",
            },
            {
                "field": "ram_gb",
                "operator": ">=",
                "value": 16,
                "severity": "mandatory",
            },
            {
                "field": "ssd_gb",
                "operator": ">=",
                "value": 512,
                "severity": "mandatory",
            },
        ],
    },
    "generic": {
        "name": "Generic Procurement",
        "constraints": [
            {
                "field": "price",
                "operator": "<=",
                "value": 100000,
                "severity": "mandatory",
            },
        ],
    },
}


def list_templates() -> list[dict]:
    return [
        {
            "id": template_id,
            "name": template["name"],
        }
        for template_id, template in PROCUREMENT_TEMPLATES.items()
    ]


def get_template(template_id: str) -> dict | None:
    template = PROCUREMENT_TEMPLATES.get(template_id.lower())
    return deepcopy(template) if template else None
