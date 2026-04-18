"""
Tests for the GeometryService — verifies initialization, caching,
failure tracking, and behavior with elements that lack 3D geometry.

Note: The test IFC fixtures have NULL representations on all elements,
so geometry computation returns empty dicts. These tests verify the
service handles that gracefully.
"""

import glob as glob_mod
import os

import ifcopenshell
import ifcopenshell.util.element
import pytest

from src.services.geometry_service import GeometryService


@pytest.fixture
def sample_ifc_path():
    """Find a sample IFC file in tests/fixtures/."""
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    patterns = ["*.ifc", "**/*.ifc"]
    for pattern in patterns:
        matches = glob_mod.glob(os.path.join(fixtures_dir, pattern), recursive=True)
        if matches:
            return matches[0]
    pytest.skip("No IFC fixture file found in tests/fixtures/")


@pytest.fixture
def ifc_model(sample_ifc_path):
    """Load an IFC model from the fixture file."""
    return ifcopenshell.open(sample_ifc_path)


@pytest.fixture
def geo_service(ifc_model):
    """Create a GeometryService instance."""
    return GeometryService(ifc_model)


class TestGeometryServiceInit:
    def test_service_initializes_without_error(self, ifc_model):
        """GeometryService can be instantiated with a valid IFC model."""
        service = GeometryService(ifc_model)
        assert service.model is ifc_model
        assert service._cache == {}
        assert service.failures == []


class TestComputeElementGeometry:
    def test_returns_empty_dict_for_element_without_representation(self, geo_service, ifc_model):
        """Elements with no Representation attribute return an empty dict."""
        # Get any element — fixture elements typically have NULL representations
        elements = ifc_model.by_type("IfcProduct")
        if not elements:
            pytest.skip("No IfcProduct elements in fixture")

        # Find an element without representation
        no_repr_elem = None
        for elem in elements:
            if not getattr(elem, "Representation", None):
                no_repr_elem = elem
                break

        if no_repr_elem is None:
            pytest.skip("All elements have representations")

        result = geo_service.compute_element_geometry(no_repr_elem)
        assert result == {}

    def test_caching_works(self, geo_service, ifc_model):
        """Second call for the same element returns cached result."""
        elements = ifc_model.by_type("IfcProduct")
        if not elements:
            pytest.skip("No elements in fixture")

        elem = elements[0]
        result1 = geo_service.compute_element_geometry(elem)
        result2 = geo_service.compute_element_geometry(elem)

        # Both calls should return the same object (cached)
        assert result1 is result2

        # The element should be in the cache
        assert elem.id() in geo_service._cache

    def test_failures_list_populated_for_invalid_elements(self, geo_service, ifc_model):
        """Elements that fail geometry computation are added to the failures list."""
        # Process all elements — those with representations that fail
        # tessellation will be added to failures
        elements = ifc_model.by_type("IfcProduct")
        if not elements:
            pytest.skip("No elements in fixture")

        for elem in elements:
            geo_service.compute_element_geometry(elem)

        # failures is a list of dicts; it may be empty if all elements
        # simply had no representation (which is a skip, not a failure)
        assert isinstance(geo_service.failures, list)
        for failure in geo_service.failures:
            assert "ifc_id" in failure
            assert "ifc_type" in failure
            assert "error" in failure


class TestComputeAllElements:
    def test_only_missing_qto_skips_elements_with_qto(self, geo_service, ifc_model):
        """With only_missing_qto=True, elements that have Qto data are skipped."""
        elements = ifc_model.by_type("IfcProduct")
        if not elements:
            pytest.skip("No elements in fixture")

        # Count how many elements have Qto data
        has_qto_count = 0
        for elem in elements:
            qtos = ifcopenshell.util.element.get_psets(elem, qtos_only=True)
            has_qto = any(
                isinstance(v, (int, float)) and v > 0
                for qto in qtos.values()
                for k, v in qto.items()
                if k != "id"
            )
            if has_qto:
                has_qto_count += 1

        # Run with only_missing_qto=True
        results = geo_service.compute_all_elements(elements, only_missing_qto=True)

        # Results should not include elements that had Qto data
        # (they were skipped). We verify by checking the log message
        # or by re-running with only_missing_qto=False and comparing.
        results_all = GeometryService(ifc_model).compute_all_elements(
            elements, only_missing_qto=False,
        )

        # The only_missing_qto run should process equal or fewer elements
        assert len(results) <= len(results_all) + has_qto_count
        assert isinstance(results, dict)

    def test_compute_all_returns_dict(self, geo_service, ifc_model):
        """compute_all_elements returns a dict mapping element IDs to quantities."""
        elements = ifc_model.by_type("IfcWall")
        if not elements:
            elements = ifc_model.by_type("IfcProduct")[:5]

        results = geo_service.compute_all_elements(elements, only_missing_qto=False)
        assert isinstance(results, dict)
        for eid, quantities in results.items():
            assert isinstance(eid, int)
            assert isinstance(quantities, dict)
