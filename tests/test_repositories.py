"""Tests for DB repositories: return shapes match trigger expectations."""

import os
import sys
import unittest
from pathlib import Path

# Set in-memory DB before any db import
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import init_db
from src.db.repositories import allocation_fetch, customer_fetch, inventory_fetch
from src.models.inputs import (
    ProductAccessInput,
    ProductAllocationInput,
    ProductSupplyInput,
)


class TestRepositoryReturnShapes(unittest.TestCase):
    """Assert repository fetch return dicts have keys and types triggers expect."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_inventory_fetch_shape(self):
        out = inventory_fetch(ProductSupplyInput(ndc="", distributor="", confidence=0.9))
        self.assertIn("records", out)
        self.assertIn("total_quantity_available", out)
        self.assertIn("source", out)
        self.assertIsInstance(out["records"], list)
        self.assertIsInstance(out["total_quantity_available"], int)
        self.assertEqual(out["source"], "db")
        for r in out["records"]:
            self.assertIn("ndc", r)
            self.assertIn("product_name", r)
            self.assertIn("location", r)
            self.assertIn("quantity_available", r)
            self.assertIn("distributor", r)

    def test_customer_fetch_shape(self):
        out = customer_fetch(ProductAccessInput(confidence=0.9))
        self.assertIn("class_of_trade", out)
        self.assertIn("rems_certified", out)
        self.assertIn("is_340b", out)
        self.assertIn("address", out)
        self.assertIn("customer_id", out)
        self.assertIn("source", out)
        self.assertIs(out["source"], "db")

    def test_allocation_fetch_shape(self):
        out = allocation_fetch(ProductAllocationInput(confidence=0.9))
        self.assertIn("allocation_records", out)
        self.assertIn("total_quantity_allocated", out)
        self.assertIn("total_quantity_used", out)
        self.assertIn("year_start", out)
        self.assertIn("year_end", out)
        self.assertIn("source", out)
        self.assertIsInstance(out["allocation_records"], list)
        self.assertEqual(out["source"], "db")

    def test_allocation_fetch_with_s3_context(self):
        out = allocation_fetch(
            ProductAllocationInput(confidence=0.9),
            s3_context={"ad1": {}, "ad2": {}},
        )
        self.assertIn("s3_scaffold", out)
        self.assertEqual(out["s3_scaffold"], {"ad1": {}, "ad2": {}})
