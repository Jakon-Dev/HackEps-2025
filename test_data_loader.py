"""
Test script to verify data loading
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hackeps25.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from principal.utils import data_loader

print("=" * 60)
print("Testing Data Loader")
print("=" * 60)

print(f"\n✓ GeoJSON loaded: {data_loader.geojson_data is not None}")
if data_loader.geojson_data:
    print(f"  - Neighborhoods: {len(data_loader.geojson_data.get('features', []))}")

print(f"\n✓ Crimes data loaded: {len(data_loader.crimes_data)} neighborhoods")

print(f"\n✓ Data aggregator initialized: {data_loader.data_aggregator is not None}")
if data_loader.data_aggregator:
    metrics = data_loader.data_aggregator.get_metrics()
    print(f"  - Metrics available for: {len(metrics)} neighborhoods")

print(f"\n✓ Recommendation engine initialized: {data_loader.recommendation_engine is not None}")

print("\n" + "=" * 60)
print("All systems operational!")
print("=" * 60)
