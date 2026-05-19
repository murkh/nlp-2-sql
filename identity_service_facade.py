"""
Identity Service Facade - Resolves named resources to database identifiers.

This module abstracts the interface to external identity service(s) which
map named resources in user input (e.g., product names, customer names)
to corresponding database IDs for use in SQL queries.

In production, this would call a database or microservice for lookups.
For this sales domain, named resource resolution is minimal since most
queries operate on aggregated data rather than specific named entities.
"""

# ─────────────────────────────────────────────
# Mock Identity Database
# In production, this would be backed by a real
# database or identity/lookup service
# ─────────────────────────────────────────────
IDENTITY_DATABASE = {
    # Products
    "wireless mouse": {"id": 1, "type": "product"},
    "mechanical keyboard": {"id": 2, "type": "product"},
    "office chair": {"id": 3, "type": "product"},
    "standing desk": {"id": 4, "type": "product"},
    "usb-c hub": {"id": 5, "type": "product"},
    "monitor arm": {"id": 6, "type": "product"},
    "webcam pro": {"id": 7, "type": "product"},
    "noise canceling headphones": {"id": 8, "type": "product"},
    "project management software": {"id": 9, "type": "product"},
    "cloud storage subscription": {"id": 10, "type": "product"},
    # Sales Reps
    "alice johnson": {"id": 1, "type": "sales_rep"},
    "bob smith": {"id": 2, "type": "sales_rep"},
    "carol williams": {"id": 3, "type": "sales_rep"},
    "david brown": {"id": 4, "type": "sales_rep"},
    # Customers
    "techcorp inc": {"id": 1, "type": "customer"},
    "globalsoft ltd": {"id": 2, "type": "customer"},
}


class IdentityServiceFacade:
    @staticmethod
    def resolve(named_resources: set) -> list:
        """
        Given a set of named resources, resolve them to database identifiers.
        Returns a list of dicts with 'id', 'type', and 'name' keys.
        """
        identifiers = []
        for named_resource in named_resources:
            if named_resource in IDENTITY_DATABASE:
                eid = IDENTITY_DATABASE[named_resource].copy()
                eid["name"] = named_resource
                identifiers.append(eid)
        return identifiers

    @staticmethod
    def is_named_resource(named_resource: str) -> bool:
        """Check if the given string is a recognized named resource."""
        return named_resource in IDENTITY_DATABASE
