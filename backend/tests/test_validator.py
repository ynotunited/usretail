import pytest
from app.ingestion.validator import validate_geometry

def test_validate_geometry_out_of_bounds():
    # Outside US (e.g., Europe)
    geojson_feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [2.3522, 48.8566] # Paris
        },
        "properties": {}
    }
    
    issues, corrected_wkt = validate_geometry(geojson_feature, index=0)
    assert len(issues) == 1
    assert issues[0]["rule_name"] == "out_of_bounds"
    assert issues[0]["severity"] == "error"

def test_validate_geometry_valid():
    # Inside US (e.g., Austin TX)
    geojson_feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [-97.7431, 30.2672]
        },
        "properties": {}
    }
    
    issues, corrected_wkt = validate_geometry(geojson_feature, index=0)
    assert len(issues) == 0
    assert corrected_wkt is not None
    assert "POINT" in corrected_wkt

def test_validate_geometry_invalid_topology():
    # Self-intersecting polygon
    geojson_feature = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [0, 0], [2, 0], [0, 2], [2, 2], [0, 0]
            ]]
        },
        "properties": {}
    }
    
    issues, corrected_wkt = validate_geometry(geojson_feature, index=0)
    # The validator will log invalid topology but shapely make_valid might fix it or it stays an error.
    # In our implementation it logs 'invalid_topology' error
    assert any(i["rule_name"] == "invalid_topology" for i in issues)

def test_validate_geometry_no_geom():
    geojson_feature = {
        "type": "Feature",
        "properties": {}
    }
    
    issues, corrected_wkt = validate_geometry(geojson_feature, index=0)
    assert len(issues) == 1
    assert issues[0]["rule_name"] == "missing_geometry"
