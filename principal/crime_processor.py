"""
Mòdul per processar dades de crims i assignar-los als barris
"""

import pandas as pd
import json
import math
from typing import Dict, List, Optional
from shapely.geometry import Point, shape, Polygon
from shapely.prepared import prep

class CrimeProcessor:
    """Classe per processar i assignar crims als barris"""
    
    def __init__(self, csv_path: str, geojson_path: str):
        self.csv_path = csv_path
        self.geojson_path = geojson_path
        self.crimes_df = None
        self.geojson_data = None
        self.neighborhood_polygons = {}  # name -> (polygon, prepared_polygon, area_km2)
        self.crimes_by_neighborhood = {}  # name -> {total_crimes, crime_types: {}, crime_rate: float}
        
    def load_data(self):
        """Carregar dades de crims i GeoJSON"""
        try:
            print(f"📊 Carregant dades de crims de {self.csv_path}...")
            self.crimes_df = pd.read_csv(self.csv_path)
            print(f"✅ {len(self.crimes_df)} crims carregats")
            
            print(f"📊 Carregant GeoJSON de {self.geojson_path}...")
            with open(self.geojson_path, 'r') as f:
                self.geojson_data = json.load(f)
            print(f"✅ {len(self.geojson_data.get('features', []))} barris carregats")
            
            return True
        except Exception as e:
            print(f"❌ Error carregant dades: {e}")
            return False
    
    def prepare_neighborhoods(self):
        """Preparar polígons dels barris per a consultes ràpides"""
        if not self.geojson_data:
            return
        
        print("🗺️  Preparant polígons dels barris...")
        for feature in self.geojson_data.get('features', []):
            name = feature.get('properties', {}).get('Name', '').strip()
            if not name:
                continue
            
            geometry = feature.get('geometry')
            try:
                polygon = shape(geometry)
                prepared = prep(polygon)
                # Calcular àrea: Shapely retorna àrea en graus², cal convertir a km²
                # Per coordenades geogràfiques, 1 grau ≈ 111 km
                # Àrea en m² = polygon.area * (111000 ** 2) per coordenades en graus
                # Però si el GeoJSON ja està en projecció plana, usar directament
                # Provar amb el mètodo correcte: assumir que les coordenades són en graus
                # Per LA (lat ~34°), 1 grau lat ≈ 111 km, 1 grau lon ≈ 88 km
                bounds = polygon.bounds
                lat_center = (bounds[1] + bounds[3]) / 2
                lon_deg_to_km = 111.32 * abs(math.cos(math.radians(lat_center)))
                lat_deg_to_km = 111.32
                # Àrea aproximada en km²
                area_deg2 = polygon.area
                area_km2 = area_deg2 * lat_deg_to_km * lon_deg_to_km
                self.neighborhood_polygons[name] = (polygon, prepared, area_km2)
            except Exception as e:
                print(f"⚠️  Error processant polígon per {name}: {e}")
        
        print(f"✅ {len(self.neighborhood_polygons)} barris preparats")
    
    def assign_crimes_to_neighborhoods(self):
        """Assignar cada crim al seu barri corresponent"""
        if self.crimes_df is None or not self.neighborhood_polygons:
            if not self.crimes_df:
                self.load_data()
            if not self.neighborhood_polygons:
                self.prepare_neighborhoods()
        
        if self.crimes_df is None or not self.neighborhood_polygons:
            print("❌ No es poden assignar crims: dades no disponibles")
            return
        
        print("🔍 Assignant crims als barris...")
        
        # Inicialitzar comptadors
        for name in self.neighborhood_polygons.keys():
            self.crimes_by_neighborhood[name] = {
                'total_crimes': 0,
                'crime_types': {}
            }
        
        # Columnes esperades al CSV (ajustar segons el format real)
        lat_col = None
        lon_col = None
        type_col = None
        
        # Detectar columnes (el CSV LAPD té 'lat', 'lon', 'crm_cd_desc')
        lat_col = 'lat'
        lon_col = 'lon'
        type_col = 'crm_cd_desc'  # Descripció del crim
        
        # Verificar que les columnes existeixen
        if lat_col not in self.crimes_df.columns or lon_col not in self.crimes_df.columns:
            print("⚠️  No s'han trobat columnes de coordenades al CSV")
            print(f"   Columnes disponibles: {list(self.crimes_df.columns)}")
            return
        
        # Filtrar només crims amb coordenades vàlides
        print(f"   Filtrant crims amb coordenades vàlides...")
        initial_count = len(self.crimes_df)
        self.crimes_df = self.crimes_df.dropna(subset=[lat_col, lon_col])
        valid_count = len(self.crimes_df)
        print(f"   Crims vàlids: {valid_count}/{initial_count} (eliminats {initial_count - valid_count} sense coordenades)")
        
        assigned = 0
        unassigned = 0
        
        for idx, row in self.crimes_df.iterrows():
            try:
                lat = float(row[lat_col])
                lon = float(row[lon_col])
                point = Point(lon, lat)  # Shapely usa (lon, lat)
                
                # Trobar el barri que conté aquest punt
                found = False
                for name, (polygon, prepared, area_km2) in self.neighborhood_polygons.items():
                    if prepared.contains(point):
                        self.crimes_by_neighborhood[name]['total_crimes'] += 1
                        
                        if type_col and type_col in row:
                            crime_type = str(row[type_col]).strip()
                            if crime_type and crime_type != 'nan':
                                if crime_type not in self.crimes_by_neighborhood[name]['crime_types']:
                                    self.crimes_by_neighborhood[name]['crime_types'][crime_type] = 0
                                self.crimes_by_neighborhood[name]['crime_types'][crime_type] += 1
                        
                        assigned += 1
                        found = True
                        break
                
                if not found:
                    unassigned += 1
                    
            except (ValueError, KeyError) as e:
                unassigned += 1
                continue
        
        # Calcular taxes de crims per km²
        print("📊 Calculant taxes de crims per barri...")
        for name, (polygon, prepared, area_km2) in self.neighborhood_polygons.items():
            total = self.crimes_by_neighborhood[name]['total_crimes']
            if area_km2 and area_km2 > 0:
                crime_rate = total / area_km2
                self.crimes_by_neighborhood[name]['crime_rate'] = crime_rate
            else:
                self.crimes_by_neighborhood[name]['crime_rate'] = 0
        
        print(f"✅ Crims assignats: {assigned}, No assignats: {unassigned}")
        print(f"   (Només s'assignen crims als {len(self.neighborhood_polygons)} barris mapejats)")
    
    def get_crimes_by_neighborhood(self) -> Dict:
        """Obtenir estadístiques de crims per barri"""
        return self.crimes_by_neighborhood
    
    def get_neighborhood_stats(self, neighborhood_name: str) -> Optional[Dict]:
        """Obtenir estadístiques d'un barri específic"""
        if neighborhood_name in self.crimes_by_neighborhood:
            return {
                'neighborhood': neighborhood_name,
                **self.crimes_by_neighborhood[neighborhood_name]
            }
        return None
    
    def get_crime_rate(self, neighborhood_name: str, area_km2: float = None) -> Optional[float]:
        """Obtenir taxa de crims per km²"""
        if neighborhood_name not in self.crimes_by_neighborhood:
            return None
        
        total = self.crimes_by_neighborhood[neighborhood_name]['total_crimes']
        if area_km2 and area_km2 > 0:
            return total / area_km2
        return total

