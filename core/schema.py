"""
SeisComP XML schema version detection and namespace mapping.
Supports all known versions 0.5–0.14 and forward-compatible unknown versions.
"""

# Namespace URI → version string
NAMESPACE_TO_VERSION: dict[str, str] = {
    "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.5":  "0.5",
    "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.6":  "0.6",
    "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.7":  "0.7",
    "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.8":  "0.8",
    "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.9":  "0.9",
    "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.10": "0.10",
    "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.11": "0.11",
    "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.12": "0.12",
    "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.13": "0.13",
    "http://geofon.gfz.de/ns/seiscomp-schema/0.14":          "0.14",
}

VERSION_TO_NAMESPACE: dict[str, str] = {v: k for k, v in NAMESPACE_TO_VERSION.items()}


def detect_namespace(root_element) -> tuple[str, str]:
    """
    Extract namespace URI and schema version from the root XML element tag.

    Returns:
        (ns_uri, version_string)  — version is 'unknown' for unrecognised URIs,
        but the raw URI is still returned for forward-compatible parsing.
    """
    tag = root_element.tag
    ns_uri = tag[1 : tag.index("}")] if tag.startswith("{") else ""

    version = NAMESPACE_TO_VERSION.get(ns_uri, "unknown")

    if version == "unknown" and ns_uri:
        # Forward-compatible: try to extract version from URI pattern
        for pattern in ("seiscomp3-schema/", "seiscomp-schema/"):
            if pattern in ns_uri:
                candidate = ns_uri.split(pattern)[-1]
                if candidate:
                    version = candidate
                break

    return ns_uri, version


def get_version_features(version: str) -> dict[str, bool]:
    """
    Return feature-presence flags for a schema version.
    Older versions may lack certain XML fields; the parser checks these
    before reporting missing data as an error.
    """
    try:
        v = float(version)
    except (ValueError, TypeError):
        v = 0.12  # assume modern capabilities for unknown future versions

    return {
        "has_creation_info":           v >= 0.7,
        "has_evaluation_status":       v >= 0.8,
        "has_depth_phase_count":       v >= 0.9,
        "has_secondary_azimuthal_gap": v >= 0.9,
        "has_slowness_used_flags":     v >= 0.10,
        "has_backazimuth_used":        v >= 0.10,
        "has_take_off_angle_used":     v >= 0.10,
    }
