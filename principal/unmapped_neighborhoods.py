"""
Mòdul per gestionar barris del LA Times no mapejats i obtenir les seves coordenades
"""

import pandas as pd
import json
import requests
import time
from typing import Dict, List, Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

class UnmappedNeighborhoodsGeocoder:
    """Classe per geocodificar barris no mapejats del LA Times"""
    
    def __init__(self, la_times_csv_path: str, geojson_path: str):
        self.la_times_csv_path = la_times_csv_path
        self.geojson_path = geojson_path
        self.unmapped_neighborhoods = []
        self.geocoded_data = {}  # name -> {lat, lon, bounds}
        
    def find_unmapped_neighborhoods(self):
        """Trobar barris del LA Times que no estan mapejats"""
        try:
            # Carregar dades
            la_times_df = pd.read_csv(self.la_times_csv_path)
            la_times_names = set(la_times_df['name'].str.strip())
            
            with open(self.geojson_path, 'r') as f:
                geojson_data = json.load(f)
            
            geojson_names = [f.get('properties', {}).get('Name', '').strip() 
                            for f in geojson_data.get('features', [])]
            
            # Crear mapeig simple
            mapping = {}
            for la_name in la_times_names:
                la_upper = la_name.upper()
                best_match = None
                
                for geo_name in geojson_names:
                    geo_upper = geo_name.upper()
                    if la_upper == geo_upper or la_upper in geo_upper or geo_upper in la_upper:
                        best_match = geo_name
                        break
                
                mapping[la_name] = best_match
            
            # Barris NO mapejats
            self.unmapped_neighborhoods = [name for name, mapped in mapping.items() if mapped is None]
            
            print(f"✅ Trobats {len(self.unmapped_neighborhoods)} barris no mapejats")
            return self.unmapped_neighborhoods
        except FileNotFoundError:
            print(f"ℹ️  Fitxers no trobats, saltant geocodificació de barris no mapejats")
            self.unmapped_neighborhoods = []
            return []
        except Exception as e:
            print(f"⚠️  Error trobant barris no mapejats: {e}")
            self.unmapped_neighborhoods = []
            return []
    
    def geocode_neighborhood(self, neighborhood_name: str, city: str = "Los Angeles, CA") -> Optional[Dict]:
        """
        Geocodificar un barri per obtenir coordenades
        
        Args:
            neighborhood_name: Nom del barri
            city: Ciutat (per defecte Los Angeles, CA)
        
        Returns:
            Diccionari amb lat, lon, bounds o None si falla
        """
        try:
            geolocator = Nominatim(user_agent="la_neighborhoods_mapper")
            query = f"{neighborhood_name}, {city}"
            
            location = geolocator.geocode(query, timeout=10)
            
            if location:
                return {
                    'lat': location.latitude,
                    'lon': location.longitude,
                    'address': location.address,
                    'bounds': None  # Nominatim no sempre retorna bounds
                }
            else:
                # Intentar sense la ciutat
                location = geolocator.geocode(f"{neighborhood_name}, Los Angeles", timeout=10)
                if location:
                    return {
                        'lat': location.latitude,
                        'lon': location.longitude,
                        'address': location.address,
                        'bounds': None
                    }
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"⚠️  Error geocodificant {neighborhood_name}: {e}")
            return None
        except Exception as e:
            print(f"⚠️  Error inesperat geocodificant {neighborhood_name}: {e}")
            return None
        
        return None
    
    def geocode_all_unmapped(self, delay: float = 1.0):
        """
        Geocodificar tots els barris no mapejats
        
        Args:
            delay: Temps d'espera entre peticions (per evitar rate limiting)
        """
        if not self.unmapped_neighborhoods:
            self.find_unmapped_neighborhoods()
        
        print(f"\n🌍 Geocodificant {len(self.unmapped_neighborhoods)} barris no mapejats...")
        print("   (Això pot trigar uns minuts per evitar rate limiting)")
        
        for i, neighborhood in enumerate(self.unmapped_neighborhoods, 1):
            print(f"   [{i}/{len(self.unmapped_neighborhoods)}] Geocodificant: {neighborhood}...", end=" ")
            
            result = self.geocode_neighborhood(neighborhood)
            
            if result:
                self.geocoded_data[neighborhood] = result
                print(f"✅ ({result['lat']:.4f}, {result['lon']:.4f})")
            else:
                print("❌ No trobat")
            
            # Esperar entre peticions per evitar rate limiting
            if i < len(self.unmapped_neighborhoods):
                time.sleep(delay)
        
        print(f"\n✅ Geocodificació completada: {len(self.geocoded_data)}/{len(self.unmapped_neighborhoods)} barris geocodificats")
        
        return self.geocoded_data
    
    def save_geocoded_data(self, output_path: str = "data/unmapped_neighborhoods_geocoded.json"):
        """Guardar dades geocodificades a un fitxer JSON"""
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.geocoded_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Dades guardades a {output_path}")
    
    def load_geocoded_data(self, input_path: str = "data/unmapped_neighborhoods_geocoded.json"):
        """Carregar dades geocodificades des d'un fitxer JSON"""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                self.geocoded_data = json.load(f)
            print(f"✅ Dades carregades de {input_path}: {len(self.geocoded_data)} barris")
            return True
        except FileNotFoundError:
            print(f"ℹ️  Fitxer {input_path} no trobat. Cal geocodificar primer.")
            return False
        except Exception as e:
            print(f"⚠️  Error carregant dades: {e}")
            return False
