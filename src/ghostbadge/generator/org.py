"""The synthetic org: departments, physical zones, and fake-name tables.

Everything identifying is hardcoded and fictional (hard project boundary: no
real personal data). The zone topology is deliberately small — six zones is
enough to make zone-mismatch and tailgating detections meaningful without
turning the demo dataset into a maze nobody can eyeball.
"""

# Physical zones. SRV-ROOM is the "crown jewels" zone: hosts there are tagged
# sensitive, which is what after-hours pairing (GB-004) keys on.
LOBBY = "LOBBY"
ZONES = ["LOBBY", "1F-OPS", "2F-SALES", "3F-ENG", "4F-EXEC", "SRV-ROOM"]

# department -> (home zone, extra permitted zones beyond LOBBY + home).
# Weights skew toward Engineering so the dataset looks like a tech company.
DEPARTMENTS: dict[str, tuple[str, list[str]]] = {
    "Engineering": ("3F-ENG", []),
    "Sales": ("2F-SALES", []),
    "IT Operations": ("1F-OPS", ["SRV-ROOM"]),
    "Finance": ("4F-EXEC", []),
    "Executive": ("4F-EXEC", []),
    "Facilities": ("1F-OPS", ["SRV-ROOM", "2F-SALES", "3F-ENG", "4F-EXEC"]),
}
DEPARTMENT_WEIGHTS: dict[str, int] = {
    "Engineering": 40,
    "Sales": 20,
    "IT Operations": 15,
    "Finance": 10,
    "Executive": 5,
    "Facilities": 10,
}

# City-level geo tables for VPN logins (city, lat, lon). Real city
# coordinates are fine — city-level is not identifiable — and the distances
# between the two tables are what makes impossible-presence (GB-002) math
# meaningful. BENIGN cities are all within commute range of the fictional
# Bay Area HQ; DISTANT cities are all >2000 km away, reserved for injectors.
BENIGN_CITIES: dict[str, tuple[float, float]] = {
    "San Francisco": (37.7749, -122.4194),
    "Oakland": (37.8044, -122.2712),
    "Berkeley": (37.8715, -122.2730),
    "San Jose": (37.3382, -121.8863),
}
DISTANT_CITIES: dict[str, tuple[float, float]] = {
    "New York": (40.7128, -74.0060),
    "London": (51.5074, -0.1278),
    "Tokyo": (35.6762, 139.6503),
    "Sydney": (-33.8688, 151.2093),
    "Berlin": (52.5200, 13.4050),
}

# Fake-name pools. 40 x 40 pairs comfortably covers the default 50-employee
# roster without repeats; sampling is without replacement on full names.
FIRST_NAMES = [
    "Avery",
    "Blake",
    "Casey",
    "Dana",
    "Ellis",
    "Frankie",
    "Gray",
    "Harper",
    "Indigo",
    "Jules",
    "Kai",
    "Lane",
    "Marlow",
    "Noor",
    "Oakley",
    "Parker",
    "Quinn",
    "Reese",
    "Sage",
    "Tatum",
    "Uma",
    "Vale",
    "Wren",
    "Xen",
    "Yael",
    "Zephyr",
    "Arden",
    "Briar",
    "Cove",
    "Devin",
    "Ember",
    "Finch",
    "Gale",
    "Hollis",
    "Isla",
    "Juno",
    "Koda",
    "Lyric",
    "Merit",
    "Nova",
]
LAST_NAMES = [
    "Ashford",
    "Barrow",
    "Coldwell",
    "Danvers",
    "Eastwick",
    "Fenmore",
    "Garrick",
    "Hale",
    "Ironwood",
    "Jessop",
    "Kestrel",
    "Larkspur",
    "Marchbanks",
    "Northgate",
    "Oakhurst",
    "Pemberly",
    "Quillon",
    "Ravenel",
    "Silverton",
    "Thornbury",
    "Umberly",
    "Vandermeer",
    "Westerly",
    "Xanders",
    "Yarrow",
    "Zellwood",
    "Aldermere",
    "Briarcliff",
    "Crowhurst",
    "Dunmore",
    "Elmsworth",
    "Fairwater",
    "Greystone",
    "Hollowell",
    "Ivorson",
    "Juneberry",
    "Kingsmere",
    "Lockridge",
    "Mistvale",
    "Nightingale",
]
