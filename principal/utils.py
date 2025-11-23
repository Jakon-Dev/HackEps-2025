"""
Utility functions for data loading and path management
"""
import os
import json
import pandas as pd
from django.conf import settings


def get_data_dir():
    """Get the data directory path"""
    return os.path.join(settings.BASE_DIR, 'data')


def get_geojson_path():
    """Get path to GeoJSON file"""
    return os.path.join(get_data_dir(), 'Neighborhood_Council_Boundaries_(2018).geojson')


def get_crimes_csv_path():
    """Get path to crimes CSV file"""
    return os.path.join(get_data_dir(), 'crime_summary.csv')


def get_la_times_csv_path():
    """Get path to LA Times CSV file"""
    return os.path.join(get_data_dir(), 'LA_Times_Neighborhood_Boundaries.csv')


def get_metrics_json_path():
    """Get path to neighborhood metrics JSON file"""
    return os.path.join(get_data_dir(), 'neighborhood_metrics.json')


def get_barrios_csv_path():
    """Get path to processed neighborhoods CSV file"""
    return os.path.join(get_data_dir(), 'barrios_procesados_para_recomendacion.csv')


class DataLoader:
    """Singleton class for loading and caching data"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataLoader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not DataLoader._initialized:
            self.geojson_data = None
            self.crimes_data = {}
            self.crime_processor = None
            self.neighborhood_mapper = None
            self.unmapped_geocoder = None
            self.data_aggregator = None
            self.recommendation_engine = None
            self._load_all_data()
            DataLoader._initialized = True
    
    def _load_all_data(self):
        """Load all data files and initialize processors"""
        print("🗺️  Initializing data loader...")
        
        # Load GeoJSON
        geojson_path = get_geojson_path()
        if os.path.exists(geojson_path):
            try:
                with open(geojson_path, 'r') as f:
                    self.geojson_data = json.load(f)
                print(f"✅ GeoJSON loaded: {len(self.geojson_data.get('features', []))} neighborhoods")
            except Exception as e:
                print(f"⚠️  Error loading GeoJSON: {e}")
        else:
            print(f"ℹ️  GeoJSON not found at: {geojson_path}")
        
        # Load crimes data from summary CSV
        crimes_csv_path = get_crimes_csv_path()
        if os.path.exists(crimes_csv_path):
            try:
                print(f"📊 Loading crime data from CSV...")
                df = pd.read_csv(crimes_csv_path)
                for _, row in df.iterrows():
                    neighborhood = str(row.get('Neighborhood', '')).strip()
                    total_crimes = float(row.get('Total Crimes', 0))
                    if neighborhood and neighborhood != 'nan':
                        self.crimes_data[neighborhood] = {
                            'total_crimes': int(total_crimes),
                            'crime_types': {}
                        }
                print(f"✅ {len(self.crimes_data)} neighborhoods loaded from crime CSV")
            except Exception as e:
                print(f"⚠️  Error loading crime CSV: {e}")
        
        # Initialize data aggregator and recommendation engine
        if self.geojson_data:
            try:
                from .data_aggregator import DataAggregator
                from .recommendation_engine import RecommendationEngine
                
                print(f"🔧 Initializing data aggregator...")
                self.data_aggregator = DataAggregator(geojson_path)
                self.data_aggregator.load_geojson()
                
                # Load saved metrics
                metrics_file = get_metrics_json_path()
                if os.path.exists(metrics_file):
                    self.data_aggregator.load_saved_metrics(metrics_file)
                
                # Aggregate crime data if available
                if self.crimes_data:
                    self.data_aggregator.aggregate_from_crimes(self.crimes_data)
                
                # Calculate derived metrics
                self.data_aggregator.calculate_derived_metrics()
                
                # Initialize recommendation engine
                print(f"🎯 Initializing recommendation engine...")
                self.recommendation_engine = RecommendationEngine()
                self.recommendation_engine.load_neighborhood_data(self.data_aggregator.get_metrics())
                print(f"✅ Recommendation engine initialized with {len(self.data_aggregator.get_metrics())} neighborhoods")
                
            except Exception as e:
                print(f"⚠️  Error initializing aggregator/engine: {e}")
                import traceback
                traceback.print_exc()


# Create singleton instance
data_loader = DataLoader()
