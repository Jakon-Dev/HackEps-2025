"""
Mòdul per agregar dades de múltiples fonts i calcular mètriques pels barris
"""

import json
import requests
import time
from typing import Dict, List, Optional
from shapely.geometry import shape, Point, LineString
from shapely.prepared import prep

# Importar CensusDataLoader si está disponible
try:
    from census_data_loader import CensusDataLoader
    CENSUS_AVAILABLE = True
except ImportError:
    CENSUS_AVAILABLE = False
    CensusDataLoader = None

# Importar GooglePlacesLoader si está disponible
try:
    from google_places_loader import GooglePlacesLoader
    GOOGLE_PLACES_AVAILABLE = True
except ImportError:
    GOOGLE_PLACES_AVAILABLE = False
    GooglePlacesLoader = None

class DataAggregator:
    """Classe per agregar dades de múltiples fonts"""
    
    def __init__(self, geojson_path: str):
        self.geojson_path = geojson_path
        self.geojson_data = None
        self.neighborhood_polygons = {}  # name -> (polygon, prepared_polygon, area)
        self.neighborhood_metrics = {}   # name -> {métricas}
        
        # Inicializar CensusDataLoader si está disponible
        self.census_loader = None
        if CENSUS_AVAILABLE:
            try:
                self.census_loader = CensusDataLoader()
            except Exception as e:
                print(f"⚠️  No se pudo inicializar CensusDataLoader: {e}")
        
        # Inicializar GooglePlacesLoader si está disponible
        self.google_places_loader = None
        if GOOGLE_PLACES_AVAILABLE:
            try:
                self.google_places_loader = GooglePlacesLoader()
            except Exception as e:
                print(f"⚠️  No se pudo inicializar GooglePlacesLoader: {e}")
        
    def load_geojson(self):
        """Carregar GeoJSON"""
        try:
            with open(self.geojson_path, 'r') as f:
                self.geojson_data = json.load(f)
            
            # Preparar polígons
            for feature in self.geojson_data.get('features', []):
                name = feature.get('properties', {}).get('Name', '').strip()
                if not name:
                    continue
                
                geometry = feature.get('geometry')
                try:
                    polygon = shape(geometry)
                    prepared = prep(polygon)
                    area_km2 = polygon.area * (111.32 ** 2) / 1000000  # Aproximació a km²
                    
                    self.neighborhood_polygons[name] = (polygon, prepared, area_km2)
                    self.neighborhood_metrics[name] = {}
                except Exception as e:
                    print(f"⚠️  Error processant polígon per {name}: {e}")
            
            print(f"✅ {len(self.neighborhood_polygons)} barris carregats")
            return True
        except Exception as e:
            print(f"❌ Error carregant GeoJSON: {e}")
            return False
    
    def query_overpass_api(self, query: str, timeout: int = 180, retries: int = 3) -> Optional[List[Dict]]:
        """Fer consulta a Overpass API amb reintents i servidors alternatius"""
        # Llista de servidors Overpass API (rotar si un falla)
        servers = [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.openstreetmap.ru/api/interpreter"
        ]
        
        for attempt in range(retries):
            for server_url in servers:
                try:
                    response = requests.post(server_url, data={'data': query}, timeout=timeout)
                    
                    # Si és 429 (Too Many Requests), esperar i provar altre servidor
                    if response.status_code == 429:
                        wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                        print(f"      ⏳ Rate limit (429), esperant {wait_time}s...", end=" ")
                        time.sleep(wait_time)
                        continue
                    
                    response.raise_for_status()
                    data = response.json()
                    return data.get('elements', [])
                    
                except requests.exceptions.Timeout:
                    print(f"      ⏳ Timeout, provant altre servidor...", end=" ")
                    continue
                except requests.exceptions.RequestException as e:
                    if "429" in str(e) or "Too Many Requests" in str(e):
                        wait_time = (attempt + 1) * 10
                        print(f"      ⏳ Rate limit, esperant {wait_time}s...", end=" ")
                        time.sleep(wait_time)
                        continue
                    # Per altres errors, provar següent servidor
                    continue
        
        print(f"      ❌ Error després de {retries} reintents")
        return None
    
    def get_pois_in_neighborhood(self, neighborhood_name: str, poi_type: str) -> int:
        """Obtenir nombre de POIs d'un tipus en un barri"""
        if neighborhood_name not in self.neighborhood_polygons:
            return 0
        
        polygon, prepared, area = self.neighborhood_polygons[neighborhood_name]
        
        # Obtenir bounds del polígon
        bounds = polygon.bounds  # (minx, miny, maxx, maxy)
        
        # Construir query Overpass
        # Ajustar segons el tipus de POI
        query = f"""
        [out:json][timeout:25];
        (
          node["amenity"="{poi_type}"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["amenity"="{poi_type}"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          relation["amenity"="{poi_type}"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
        );
        out center;
        """
        
        elements = self.query_overpass_api(query)
        if not elements:
            return 0
        
        # Comptar quants estan dins del polígon
        count = 0
        for element in elements:
            if 'lat' in element and 'lon' in element:
                point = Point(element['lon'], element['lat'])
                if prepared.contains(point):
                    count += 1
            elif 'center' in element:
                center = element['center']
                point = Point(center['lon'], center['lat'])
                if prepared.contains(point):
                    count += 1
        
        return count
    
    def calculate_walkability(self, neighborhood_name: str) -> float:
        """Calcular walkability score (simplificat)"""
        if neighborhood_name not in self.neighborhood_polygons:
            return 0.0
        
        # Factors per walkability:
        # - Densitat de restaurants
        # - Densitat de serveis
        # - Densitat de parades de transport
        # - Qualitat de voreres (simplificat)
        
        restaurants = self.neighborhood_metrics[neighborhood_name].get('restaurants', 0)
        services = self.neighborhood_metrics[neighborhood_name].get('services', 0)
        public_transport = self.neighborhood_metrics[neighborhood_name].get('public_transport_stops', 0)
        
        polygon, prepared, area = self.neighborhood_polygons[neighborhood_name]
        
        # Normalitzar per àrea
        restaurants_density = restaurants / area if area > 0 else 0
        services_density = services / area if area > 0 else 0
        transport_density = public_transport / area if area > 0 else 0
        
        # Score combinat (0-1)
        score = min(1.0, (restaurants_density * 0.4 + services_density * 0.3 + transport_density * 0.3) / 10)
        return score
    
    def load_crimes_from_summary(self, summary_csv_path: str) -> Dict:
        """Carregar dades de crims des del CSV resumit"""
        import pandas as pd
        import os
        
        if not os.path.exists(summary_csv_path):
            print(f"⚠️  CSV resumit de crims no trobat: {summary_csv_path}")
            return {}
        
        try:
            df = pd.read_csv(summary_csv_path)
            crimes_dict = {}
            
            for _, row in df.iterrows():
                neighborhood = str(row.get('Neighborhood', '')).strip()
                total_crimes = float(row.get('Total Crimes', 0))
                
                if neighborhood and neighborhood != 'nan':
                    crimes_dict[neighborhood] = {
                        'total_crimes': int(total_crimes),
                        'crime_types': {}  # No tenim detall de tipus al resum
                    }
            
            print(f"✅ Carregats {len(crimes_dict)} barris des del CSV resumit")
            return crimes_dict
        except Exception as e:
            print(f"❌ Error carregant CSV resumit: {e}")
            return {}
    
    def aggregate_from_crimes(self, crimes_by_neighborhood: Dict):
        """Agregar dades de crims"""
        for neighborhood_name, crime_data in crimes_by_neighborhood.items():
            if neighborhood_name not in self.neighborhood_metrics:
                continue
            
            total_crimes = crime_data.get('total_crimes', 0)
            population = self.neighborhood_metrics[neighborhood_name].get('population', 0)
            
            # Obtenir àrea del barri
            if neighborhood_name in self.neighborhood_polygons:
                polygon, prepared, area = self.neighborhood_polygons[neighborhood_name]
            else:
                area = 1.0  # Valor per defecte si no tenim àrea
            
            # Calcular crime_rate per km² (per compatibilitat)
            crime_rate = total_crimes / area if area > 0 else 0
            
            # Calcular seguretat basada en població: 1 crim per cada 100,000 habitants
            if population > 0:
                # Crims ideals (1 crim per cada 100,000 habitants)
                ideal_crimes = population / 100000.0
                
                if ideal_crimes > 0:
                    # Ratio de seguretat: menys crims que l'ideal = més segur
                    # Escala millorada per diferenciar millor els barris
                    crime_ratio = total_crimes / ideal_crimes
                    
                    # Usar escala logarítmica per millor diferenciació
                    import math
                    
                    # Usar escala logarítmica per millor diferenciació
                    # Això permet diferenciar millor fins i tot amb ratios molt alts
                    
                    if crime_ratio <= 1.0:
                        # Té menys o igual crims que l'ideal: 100% segur (excel·lent)
                        safety_score = 1.0
                    elif crime_ratio <= 2.0:
                        # 1-2x l'ideal: 95-100% segur (molt bo)
                        safety_score = 1.0 - ((crime_ratio - 1.0) / 1.0) * 0.05
                    elif crime_ratio <= 5.0:
                        # 2-5x l'ideal: 85-95% segur (bo)
                        safety_score = 0.95 - ((crime_ratio - 2.0) / 3.0) * 0.10
                    elif crime_ratio <= 10.0:
                        # 5-10x l'ideal: 70-85% segur (acceptable)
                        safety_score = 0.85 - ((crime_ratio - 5.0) / 5.0) * 0.15
                    elif crime_ratio <= 20.0:
                        # 10-20x l'ideal: 55-70% segur (moderat, no recomanable)
                        safety_score = 0.70 - ((crime_ratio - 10.0) / 10.0) * 0.15
                    elif crime_ratio <= 50.0:
                        # 20-50x l'ideal: 40-55% segur (poc segur, no recomanable)
                        safety_score = 0.55 - ((crime_ratio - 20.0) / 30.0) * 0.15
                    elif crime_ratio <= 100.0:
                        # 50-100x l'ideal: 25-40% segur (molt poc segur, no recomanable)
                        safety_score = 0.40 - ((crime_ratio - 50.0) / 50.0) * 0.15
                    elif crime_ratio <= 500.0:
                        # 100-500x l'ideal: 15-25% segur (extremadament poc segur, no recomanable)
                        safety_score = 0.25 - ((crime_ratio - 100.0) / 400.0) * 0.10
                    elif crime_ratio <= 1000.0:
                        # 500-1000x l'ideal: 10-15% segur (molt perillós, no recomanable)
                        safety_score = 0.15 - ((crime_ratio - 500.0) / 500.0) * 0.05
                    else:
                        # >1000x l'ideal: 5-10% segur (extremadament perillós, no recomanable)
                        # Usar escala logarítmica per ratios extremadament alts
                        log_ratio = math.log10(crime_ratio / 1000.0)
                        safety_score = max(0.05, 0.10 - log_ratio * 0.05)
                else:
                    safety_score = 1.0  # Si no hi ha població, assumir segur
            else:
                # Fallback: usar mètode anterior basat en densitat si no tenim població
                if crime_rate == 0:
                    safety_score = 1.0
                elif crime_rate < 20:
                    safety_score = 1.0 - (crime_rate / 20.0) * 0.3
                elif crime_rate < 100:
                    safety_score = 0.7 - ((crime_rate - 20) / 80.0) * 0.5
                elif crime_rate < 200:
                    safety_score = 0.2 - ((crime_rate - 100) / 100.0) * 0.15
                else:
                    safety_score = max(0.02, 0.05 - ((crime_rate - 200) / 500.0) * 0.03)
            
            self.neighborhood_metrics[neighborhood_name]['total_crimes'] = total_crimes
            self.neighborhood_metrics[neighborhood_name]['crime_rate'] = crime_rate
            self.neighborhood_metrics[neighborhood_name]['safety'] = safety_score
            
            # Guardar també ideal_crimes si tenim població
            if population > 0:
                self.neighborhood_metrics[neighborhood_name]['ideal_crimes'] = population / 100000.0
            
            # Guardar també els tipus de crims si estan disponibles
            if 'crime_types' in crime_data:
                self.neighborhood_metrics[neighborhood_name]['crime_types'] = crime_data['crime_types']
    
    def aggregate_from_google_places(self, neighborhood_name: str, include_all: bool = False):
        """
        Agregar dades de Google Places API per a un barri
        
        Args:
            neighborhood_name: Nombre del barrio
            include_all: Si True, incluye todos los tipos (Fase 1 completa: escuelas, salud, vida nocturna, etc.)
        """
        if neighborhood_name not in self.neighborhood_polygons or not self.google_places_loader:
            return
        
        polygon, prepared, area = self.neighborhood_polygons[neighborhood_name]
        bounds = polygon.bounds
        
        try:
            places_metrics = self.google_places_loader.load_places_for_neighborhood(
                neighborhood_name, polygon, prepared, bounds, include_all=include_all
            )
            # Actualizar métricas con datos de Google Places
            if neighborhood_name not in self.neighborhood_metrics:
                self.neighborhood_metrics[neighborhood_name] = {}
            self.neighborhood_metrics[neighborhood_name].update(places_metrics)
        except Exception as e:
            print(f"   ⚠️  Error cargando Google Places: {e}")
    
    def aggregate_from_overpass(self, neighborhood_name: str):
        """Agregar dades de Overpass API per a un barri"""
        if neighborhood_name not in self.neighborhood_polygons:
            return
        
        polygon, prepared, area = self.neighborhood_polygons[neighborhood_name]
        bounds = polygon.bounds
        
        # Query combinada per obtenir múltiples tipus de POIs
        # FASE 1: Ampliada amb gimnasios, cultura, bici, autopistes i accessibilitat
        query = f"""
        [out:json][timeout:90];
        (
          node["amenity"~"restaurant|cafe|fast_food"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["amenity"~"restaurant|cafe|fast_food"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          node["leisure"~"park|playground"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["leisure"~"park|playground"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          node["shop"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["shop"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          node["public_transport"="platform"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["public_transport"="platform"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          // Gimnasios
          node["leisure"="fitness_centre"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          node["amenity"="gym"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["leisure"="fitness_centre"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          // Cultura
          node["amenity"="theatre"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          node["amenity"="cinema"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          node["tourism"="museum"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          node["amenity"="arts_centre"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["amenity"="theatre"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["amenity"="cinema"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["tourism"="museum"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          // Carriles bici
          node["highway"="cycleway"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["highway"="cycleway"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["highway"="path"]["bicycle"="yes"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          // Autopistas
          node["highway"="motorway"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          node["highway"="motorway_link"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["highway"="motorway"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["highway"="motorway_link"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          // Accesibilidad
          node["kerb"="lowered"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          node["wheelchair"="yes"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["wheelchair"="yes"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["highway"="footway"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
        );
        out geom;
        """
        
        elements = self.query_overpass_api(query)
        if not elements:
            return
        
        # Intentar obtenir població de Overpass API
        population = self.get_population_from_overpass(neighborhood_name, bounds, prepared)
        
        # Comptar per tipus
        restaurants = 0
        cafes = 0
        parks = 0
        shops = 0
        public_transport_stops = 0
        local_businesses = 0  # Negocis locals (no cadenes)
        
        # FASE 1: Nous comptadors
        gyms = 0
        theatres = 0
        cinemas = 0
        museums = 0
        bike_lanes_km = 0.0  # Longitud de carrils bici en km
        highway_access_points = 0  # Punts d'accés a autopistes
        accessible_points = 0  # Punts accessibles (ramps, wheelchair=yes)
        sidewalks_km = 0.0  # Longitud d'aceres en km
        
        for element in elements:
            tags = element.get('tags', {})
            amenity = tags.get('amenity', '')
            leisure = tags.get('leisure', '')
            shop = tags.get('shop', '')
            public_transport = tags.get('public_transport', '')
            
            # Obtenir coordenades (per nodes)
            lat = None
            lon = None
            
            if element.get('type') == 'node':
                if 'lat' in element and 'lon' in element:
                    lat, lon = element['lat'], element['lon']
                elif 'center' in element:
                    center = element['center']
                    lat, lon = center['lat'], center['lon']
                elif 'geometry' in element:
                    # Si tenim geometria, usar-la
                    geom = element.get('geometry', {})
                    if geom.get('type') == 'Point':
                        coords = geom.get('coordinates', [])
                        if len(coords) >= 2:
                            lon, lat = coords[0], coords[1]
            
            if lat and lon:
                point = Point(lon, lat)
                if not prepared.contains(point):
                    continue
                
                # Comptar per tipus
                if amenity in ['restaurant', 'fast_food']:
                    restaurants += 1
                elif amenity == 'cafe':
                    cafes += 1
                
                if leisure in ['park', 'playground']:
                    parks += 1
                
                if shop:
                    shops += 1
                    # Detectar negocis locals (simplificat: no tenir tag de brand)
                    if 'brand' not in tags and 'chain' not in tags:
                        local_businesses += 1
                
                if public_transport == 'platform' or 'public_transport' in tags:
                    public_transport_stops += 1
                
                # FASE 1: Processar nous elements
                # Gimnasios
                if leisure == 'fitness_centre' or amenity == 'gym':
                    gyms += 1
                
                # Cultura
                if amenity == 'theatre':
                    theatres += 1
                elif amenity == 'cinema':
                    cinemas += 1
                elif tags.get('tourism') == 'museum' or amenity == 'arts_centre':
                    museums += 1
                
                # Accesibilidad (nodes)
                if tags.get('kerb') == 'lowered' or tags.get('wheelchair') == 'yes':
                    accessible_points += 1
            
            # Processar ways per calcular longituds (carrils bici, aceres, autopistes)
            if element.get('type') == 'way' and 'geometry' in element:
                geometry = element.get('geometry', {})
                # geometry pot ser un dict o una llista
                if isinstance(geometry, dict) and geometry.get('type') == 'LineString':
                    coords = geometry.get('coordinates', [])
                elif isinstance(geometry, list) and len(geometry) >= 2:
                    # Si geometry és una llista directa de coordenades
                    coords = geometry
                else:
                    coords = []
                
                if len(coords) >= 2:
                        # Crear LineString i calcular longitud
                        try:
                            line_coords = [(coord[0], coord[1]) for coord in coords]
                            line = LineString(line_coords)
                            
                            # Verificar si el way intersecta amb el polígon
                            if polygon.intersects(line):
                                # Calcular longitud en km (aproximació)
                                # 1 grau ≈ 111.32 km
                                length_km = line.length * 111.32
                                
                                way_tags = element.get('tags', {})
                                highway = way_tags.get('highway', '')
                                
                                # Carriles bici
                                if highway == 'cycleway' or (highway == 'path' and way_tags.get('bicycle') == 'yes'):
                                    bike_lanes_km += length_km
                                
                                # Aceras
                                if highway == 'footway':
                                    sidewalks_km += length_km
                                
                                # Autopistas (contar accesos)
                                if highway in ['motorway', 'motorway_link']:
                                    highway_access_points += 1
                                
                                # Accesibilidad (ways)
                                if way_tags.get('wheelchair') == 'yes':
                                    accessible_points += 1
                        except Exception as e:
                            # Ignorar errors de geometria
                            pass
        
        # Guardar mètriques (valors reals, no normalitzats)
        # IMPORTANT: Guardar sempre el valor real abans de qualsevol normalització
        self.neighborhood_metrics[neighborhood_name]['restaurants'] = restaurants
        self.neighborhood_metrics[neighborhood_name]['cafes'] = cafes
        self.neighborhood_metrics[neighborhood_name]['parks'] = int(parks)  # Valor real (nombre de parcs) - SIEMPRE enter
        self.neighborhood_metrics[neighborhood_name]['parks_count'] = int(parks)  # Guardar també com a count per a visualització
        self.neighborhood_metrics[neighborhood_name]['shops'] = shops
        self.neighborhood_metrics[neighborhood_name]['local_businesses'] = local_businesses
        self.neighborhood_metrics[neighborhood_name]['public_transport_stops'] = public_transport_stops
        
        # FASE 1: Guardar noves mètriques
        self.neighborhood_metrics[neighborhood_name]['gyms'] = gyms
        self.neighborhood_metrics[neighborhood_name]['theatres'] = theatres
        self.neighborhood_metrics[neighborhood_name]['cinemas'] = cinemas
        self.neighborhood_metrics[neighborhood_name]['museums'] = museums
        self.neighborhood_metrics[neighborhood_name]['bike_lanes_km'] = round(bike_lanes_km, 2)
        self.neighborhood_metrics[neighborhood_name]['highway_access_points'] = highway_access_points
        self.neighborhood_metrics[neighborhood_name]['accessible_points'] = accessible_points
        self.neighborhood_metrics[neighborhood_name]['sidewalks_km'] = round(sidewalks_km, 2)
        
        # Guardar població si s'ha obtingut
        if population > 0:
            self.neighborhood_metrics[neighborhood_name]['population'] = population
        else:
            # Estimar població basada en densitat mitjana de LA (~3200 hab/km²)
            # Però només si no tenim dades reals
            estimated_population = int(area * 3200) if area > 0 else 0
            self.neighborhood_metrics[neighborhood_name]['population'] = estimated_population
            self.neighborhood_metrics[neighborhood_name]['population_estimated'] = True
        
        # Calcular densitats
        if area > 0:
            self.neighborhood_metrics[neighborhood_name]['restaurants_density'] = restaurants / area
            self.neighborhood_metrics[neighborhood_name]['parks_density'] = parks / area
            self.neighborhood_metrics[neighborhood_name]['shops_density'] = shops / area
        
        # Calcular walkability
        walkability = self.calculate_walkability(neighborhood_name)
        self.neighborhood_metrics[neighborhood_name]['walkability'] = walkability
    
    def get_population_from_overpass(self, neighborhood_name: str, bounds: tuple, prepared) -> int:
        """Intentar obtenir població de Overpass API"""
        # Query per obtenir dades de població (place tags amb population)
        query = f"""
        [out:json][timeout:30];
        (
          node["population"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["population"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          relation["population"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          node["place"]["population"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
          way["place"]["population"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
        );
        out center;
        """
        
        elements = self.query_overpass_api(query)
        if not elements:
            return 0
        
        # Buscar població dins del polígon
        total_population = 0
        for element in elements:
            tags = element.get('tags', {})
            population_str = tags.get('population', '')
            
            if not population_str:
                continue
            
            # Obtenir coordenades
            lat = None
            lon = None
            if 'lat' in element and 'lon' in element:
                lat, lon = element['lat'], element['lon']
            elif 'center' in element:
                center = element['center']
                lat, lon = center['lat'], center['lon']
            
            if lat and lon:
                point = Point(lon, lat)
                if prepared.contains(point):
                    try:
                        # Intentar parsejar població (pot tenir formats com "10000" o "10,000")
                        pop_value = int(population_str.replace(',', '').replace('.', ''))
                        total_population += pop_value
                    except (ValueError, AttributeError):
                        continue
        
        return total_population
    
    def aggregate_from_census(self, neighborhood_name: str):
        """Agregar dades del Census per a un barri"""
        if not self.census_loader or neighborhood_name not in self.neighborhood_polygons:
            return
        
        polygon, prepared, area = self.neighborhood_polygons[neighborhood_name]
        census_metrics = self.census_loader.load_census_data_for_neighborhood(neighborhood_name, polygon)
        
        if census_metrics:
            # Fusionar con métricas existentes
            if neighborhood_name not in self.neighborhood_metrics:
                self.neighborhood_metrics[neighborhood_name] = {}
            
            self.neighborhood_metrics[neighborhood_name].update(census_metrics)
            
            # Si tenemos población del Census, usarla en lugar de la estimada
            if census_metrics.get('population_census'):
                self.neighborhood_metrics[neighborhood_name]['population'] = census_metrics['population_census']
                self.neighborhood_metrics[neighborhood_name]['population_estimated'] = False
    
    def aggregate_all_neighborhoods(self, limit: Optional[int] = None):
        """Agregar dades de tots els barris (pot trigar molt)"""
        neighborhoods = list(self.neighborhood_polygons.keys())
        
        if limit:
            neighborhoods = neighborhoods[:limit]
        
        print(f"📊 Agregant dades de {len(neighborhoods)} barris...")
        print("   (Això pot trigar uns minuts per evitar rate limiting)")
        
        for i, neighborhood_name in enumerate(neighborhoods, 1):
            print(f"   [{i}/{len(neighborhoods)}] Processant {neighborhood_name}...", end=" ")
            self.aggregate_from_overpass(neighborhood_name)
            print("✅")
            
            # Esperar entre peticions (més temps per evitar rate limiting)
            if i < len(neighborhoods):
                time.sleep(3)  # 3 segons entre peticions per evitar 429
        
        print(f"✅ Dades agregades per {len(neighborhoods)} barris")
    
    def get_metrics(self) -> Dict:
        """Obtenir totes les mètriques"""
        return self.neighborhood_metrics
    
    def get_neighborhood_center(self, neighborhood_name: str) -> Optional[Dict]:
        """Obtener coordenadas del centro de un barrio"""
        if neighborhood_name in self.neighborhood_polygons:
            polygon, _, _ = self.neighborhood_polygons[neighborhood_name]
            bounds = polygon.bounds
            # Calcular centro: (min_lon + max_lon) / 2, (min_lat + max_lat) / 2
            center_lon = (bounds[0] + bounds[2]) / 2
            center_lat = (bounds[1] + bounds[3]) / 2
            return {'lat': center_lat, 'lng': center_lon}
        
        # Si no está en los polígonos, buscar en el GeoJSON
        if self.geojson_data:
            for feature in self.geojson_data.get('features', []):
                name = feature.get('properties', {}).get('Name', '').strip()
                if name == neighborhood_name:
                    geometry = feature.get('geometry', {})
                    geometry_type = geometry.get('type', '')
                    
                    if geometry_type == 'Polygon':
                        coords = geometry.get('coordinates', [])
                        if coords and len(coords) > 0:
                            # Obtener todas las coordenadas del polígono
                            all_coords = coords[0]  # Primer anillo del polígono
                            lons = [coord[0] for coord in all_coords]
                            lats = [coord[1] for coord in all_coords]
                            if lons and lats:
                                center_lon = (min(lons) + max(lons)) / 2
                                center_lat = (min(lats) + max(lats)) / 2
                                return {'lat': center_lat, 'lng': center_lon}
                    
                    elif geometry_type == 'MultiPolygon':
                        # Para MultiPolygon, calcular el centro de todos los polígonos
                        all_lons = []
                        all_lats = []
                        for polygon_coords in geometry.get('coordinates', []):
                            if polygon_coords and len(polygon_coords) > 0:
                                ring_coords = polygon_coords[0]  # Primer anillo
                                all_lons.extend([coord[0] for coord in ring_coords])
                                all_lats.extend([coord[1] for coord in ring_coords])
                        
                        if all_lons and all_lats:
                            center_lon = (min(all_lons) + max(all_lons)) / 2
                            center_lat = (min(all_lats) + max(all_lats)) / 2
                            return {'lat': center_lat, 'lng': center_lon}
        
        return None
    
    def get_neighborhood_polygon_path(self, neighborhood_name: str) -> Optional[str]:
        """Obtener path del polígono del barrio para Google Maps Static API
        Retorna una cadena con formato: lat1,lng1|lat2,lng2|...|lat1,lng1
        """
        if self.geojson_data:
            for feature in self.geojson_data.get('features', []):
                name = feature.get('properties', {}).get('Name', '').strip()
                if name == neighborhood_name:
                    geometry = feature.get('geometry', {})
                    geometry_type = geometry.get('type', '')
                    
                    path_points = []
                    
                    if geometry_type == 'Polygon':
                        coords = geometry.get('coordinates', [])
                        if coords and len(coords) > 0:
                            # Obtener todas las coordenadas del polígono (primer anillo)
                            all_coords = coords[0]  # Primer anillo del polígono
                            for coord in all_coords:
                                # Formato: lat,lng (Google Maps usa lat,lng)
                                path_points.append(f"{coord[1]},{coord[0]}")
                    
                    elif geometry_type == 'MultiPolygon':
                        # Para MultiPolygon, usar el primer polígono
                        polygon_coords = geometry.get('coordinates', [])
                        if polygon_coords and len(polygon_coords) > 0:
                            first_polygon = polygon_coords[0]
                            if first_polygon and len(first_polygon) > 0:
                                ring_coords = first_polygon[0]  # Primer anillo del primer polígono
                                for coord in ring_coords:
                                    path_points.append(f"{coord[1]},{coord[0]}")
                    
                    if path_points:
                        # Cerrar el polígono añadiendo el primer punto al final
                        if path_points[0] != path_points[-1]:
                            path_points.append(path_points[0])
                        return '|'.join(path_points)
        
        return None
    
    def get_neighborhood_bounds(self, neighborhood_name: str) -> Optional[Dict]:
        """Obtener los límites (bounds) del barrio para ajustar el zoom
        Retorna un diccionario con: min_lat, max_lat, min_lng, max_lng
        """
        if self.geojson_data:
            for feature in self.geojson_data.get('features', []):
                name = feature.get('properties', {}).get('Name', '').strip()
                if name == neighborhood_name:
                    geometry = feature.get('geometry', {})
                    geometry_type = geometry.get('type', '')
                    
                    all_lats = []
                    all_lngs = []
                    
                    if geometry_type == 'Polygon':
                        coords = geometry.get('coordinates', [])
                        if coords and len(coords) > 0:
                            all_coords = coords[0]  # Primer anillo del polígono
                            for coord in all_coords:
                                all_lngs.append(coord[0])  # Longitud
                                all_lats.append(coord[1])  # Latitud
                    
                    elif geometry_type == 'MultiPolygon':
                        polygon_coords = geometry.get('coordinates', [])
                        for polygon_coord in polygon_coords:
                            if polygon_coord and len(polygon_coord) > 0:
                                ring_coords = polygon_coord[0]  # Primer anillo
                                for coord in ring_coords:
                                    all_lngs.append(coord[0])
                                    all_lats.append(coord[1])
                    
                    if all_lats and all_lngs:
                        return {
                            'min_lat': min(all_lats),
                            'max_lat': max(all_lats),
                            'min_lng': min(all_lngs),
                            'max_lng': max(all_lngs)
                        }
        
        return None
    
    def get_neighborhood_metrics(self, neighborhood_name: str) -> Optional[Dict]:
        """Obtenir mètriques d'un barri específic"""
        return self.neighborhood_metrics.get(neighborhood_name)
    
    def load_saved_metrics(self, file_path: str = "data/neighborhood_metrics.json"):
        """Carregar mètriques guardades prèviament"""
        try:
            import os
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    saved_metrics = json.load(f)
                    # Fusionar amb mètriques existents
                    for name, metrics in saved_metrics.items():
                        if name in self.neighborhood_metrics:
                            self.neighborhood_metrics[name].update(metrics)
                        else:
                            self.neighborhood_metrics[name] = metrics
                    print(f"✅ Mètriques carregades de {file_path}: {len(saved_metrics)} barris")
                    return True
            return False
        except Exception as e:
            print(f"⚠️  Error carregant mètriques guardades: {e}")
            return False
    
    def calculate_derived_metrics(self):
        """Calcular mètriques derivades per als clients"""
        for neighborhood_name, metrics in self.neighborhood_metrics.items():
            # Assegurar que tenim població (estimar si no existeix)
            if 'population' not in metrics or metrics.get('population', 0) == 0:
                if neighborhood_name in self.neighborhood_polygons:
                    polygon, prepared, area = self.neighborhood_polygons[neighborhood_name]
                    # Estimar població basada en densitat mitjana de LA (~3200 hab/km²)
                    estimated_population = int(area * 3200) if area > 0 else 0
                    metrics['population'] = estimated_population
                    metrics['population_estimated'] = True
            
            # Inicialitzar valors per defecte si no existeixen
            if 'restaurants' not in metrics:
                metrics['restaurants'] = 0
            if 'parks' not in metrics:
                metrics['parks'] = 0
            if 'shops' not in metrics:
                metrics['shops'] = 0
            if 'local_businesses' not in metrics:
                metrics['local_businesses'] = 0
            if 'cafes' not in metrics:
                metrics['cafes'] = 0
            if 'public_transport_stops' not in metrics:
                metrics['public_transport_stops'] = 0
            if 'safety' not in metrics:
                metrics['safety'] = 0.7  # Valor per defecte
            if 'walkability' not in metrics:
                metrics['walkability'] = 0.5  # Valor per defecte
            if 'crime_rate' not in metrics:
                metrics['crime_rate'] = 0
            
            # FASE 1: Inicialitzar noves mètriques
            if 'gyms' not in metrics:
                metrics['gyms'] = 0
            if 'theatres' not in metrics:
                metrics['theatres'] = 0
            if 'cinemas' not in metrics:
                metrics['cinemas'] = 0
            if 'museums' not in metrics:
                metrics['museums'] = 0
            if 'bike_lanes_km' not in metrics:
                metrics['bike_lanes_km'] = 0.0
            if 'highway_access_points' not in metrics:
                metrics['highway_access_points'] = 0
            if 'accessible_points' not in metrics:
                metrics['accessible_points'] = 0
            if 'sidewalks_km' not in metrics:
                metrics['sidewalks_km'] = 0.0
            
            # FASE 1 (Google Places): Inicializar nuevos datos
            if 'schools' not in metrics:
                metrics['schools'] = 0
            if 'universities' not in metrics:
                metrics['universities'] = 0
            if 'bars' not in metrics:
                metrics['bars'] = 0
            if 'nightclubs' not in metrics:
                metrics['nightclubs'] = 0
            if 'pharmacies' not in metrics:
                metrics['pharmacies'] = 0
            if 'hospitals' not in metrics:
                metrics['hospitals'] = 0
            if 'car_dealers' not in metrics:
                metrics['car_dealers'] = 0
            if 'car_repair' not in metrics:
                metrics['car_repair'] = 0
            if 'gas_stations' not in metrics:
                metrics['gas_stations'] = 0
            if 'supermarkets' not in metrics:
                metrics['supermarkets'] = 0
            if 'parks_google_places' not in metrics:
                metrics['parks_google_places'] = 0
            if 'cafes_google_places' not in metrics:
                metrics['cafes_google_places'] = 0
            
            # Mètriques per Daenerys
            metrics['local_businesses_score'] = min(1.0, metrics.get('local_businesses', 0) / 50.0)
            
            # Parcs: preservar valor real i crear versió normalitzada per a scoring
            # IMPORTANT: NO sobrescriure parks_count si ja existeix i és vàlid
            parks_count_existing = metrics.get('parks_count', None)
            parks_raw = metrics.get('parks', 0)
            
            # Determinar el valor real de parcs
            if parks_count_existing is not None and parks_count_existing >= 0 and parks_count_existing >= 1:
                # Ja tenim el valor real guardat correctament
                parks_real = int(parks_count_existing)
            elif isinstance(parks_raw, (int, float)) and parks_raw >= 1:
                # parks_raw és el valor real (abans de normalitzar)
                parks_real = int(parks_raw)
                metrics['parks_count'] = parks_real  # Guardar el valor real
            elif isinstance(parks_raw, (int, float)) and 0 < parks_raw < 0.01:
                # Valor normalitzat molt petit, probablement 0 parcs reals
                parks_real = 0
                if parks_count_existing is None:
                    metrics['parks_count'] = 0
            else:
                # Intentar recuperar o deixar com està
                parks_real = int(parks_count_existing) if parks_count_existing is not None and parks_count_existing >= 0 else 0
                if parks_count_existing is None:
                    metrics['parks_count'] = parks_real
            
            # Crear la versió normalitzada per a scoring (0-1)
            # PERÒ només si el valor real és vàlid
            if parks_real > 0:
                parks_normalized = min(1.0, parks_real / 10.0)
                metrics['parks'] = parks_normalized  # Per a scoring
            else:
                metrics['parks'] = 0.0
            
            metrics['community_sense'] = min(1.0, (parks_real + metrics.get('local_businesses', 0)) / 100.0)
            
            # Mètriques per Cersei
            metrics['luxury_shops'] = min(1.0, metrics.get('shops', 0) / 20.0)  # Simplificat
            metrics['privacy'] = 0.5  # Placeholder - necessitaria dades de densitat poblacional
            
            # FASE 2: Usar income_level del Census si está disponible
            if 'income_level' in metrics and metrics['income_level'] is not None:
                # Ya viene del Census, no hacer nada
                pass
            elif 'median_income' in metrics and metrics['median_income'] is not None:
                # Usar median_income del Census para calcular income_level
                median_income = metrics['median_income']
                metrics['income_level'] = min(1.0, max(0.0, median_income / 200000.0))
            else:
                # Fallback: correlació amb seguretat
                metrics['income_level'] = metrics.get('safety', 0.7) * 0.8
            
            # FASE 1 (Google Places): Calcular elite_schools basado en datos reales
            schools = metrics.get('schools', 0)
            universities = metrics.get('universities', 0)
            total_education = schools + universities
            # Normalizar: 20+ escuelas/universidades = 100%
            if total_education > 0:
                metrics['elite_schools'] = min(1.0, total_education / 20.0)
            else:
                # Fallback si no hay datos
                metrics['elite_schools'] = metrics.get('safety', 0.7) * 0.6
            
            # Mètriques per Bran
            # FASE 1: Calcular accessibilitat basada en dades reals
            accessible_points = metrics.get('accessible_points', 0)
            sidewalks_km = metrics.get('sidewalks_km', 0.0)
            area = 0
            if neighborhood_name in self.neighborhood_polygons:
                polygon, prepared, area = self.neighborhood_polygons[neighborhood_name]
            
            # Score d'accessibilitat: combinació de punts accessibles i aceres
            if area > 0:
                # Normalitzar: més punts accessibles i més aceres = millor accessibilitat
                accessible_score = min(1.0, accessible_points / 50.0)  # 50 punts = 100%
                sidewalks_score = min(1.0, sidewalks_km / 10.0)  # 10 km d'aceres = 100%
                metrics['accessibility'] = (accessible_score * 0.6 + sidewalks_score * 0.4)
            else:
                metrics['accessibility'] = min(1.0, accessible_points / 50.0) if accessible_points > 0 else 0.5
            
            metrics['quietness'] = max(0.0, min(1.0, 1.0 - (metrics.get('crime_rate', 0) / 50.0)))  # Simplificat
            metrics['internet_quality'] = 0.8  # Placeholder - necessitaria dades reals
            
            # Mètriques per Jon
            parks_count = metrics.get('parks_count', 0)
            metrics['nature_access'] = min(1.0, parks_count / 10.0)
            
            # FASE 2: Usar affordability del Census si está disponible
            if 'affordability' in metrics and metrics['affordability'] is not None:
                # Ya viene del Census (basado en median_rent), no hacer nada
                pass
            else:
                # Fallback: correlació amb seguretat
                metrics['affordability'] = max(0.0, min(1.0, 1.0 - (metrics.get('safety', 0.7) * 0.3)))
            
            metrics['authenticity'] = metrics.get('community_sense', 0.5)
            
            # Calcular ratio d'espais verds basat en població: 1 parc per cada 10000 habitants
            parks_count = metrics.get('parks_count', 0)
            population = metrics.get('population', 0)
            
            if population > 0:
                # Calcular parcs ideals (1 parc per cada 10000 habitants)
                ideal_parks = population / 10000.0
                
                if ideal_parks > 0:
                    # Ratio = (parcs reals / parcs ideals) * 100%
                    # Si té més parcs que l'ideal, és 100%
                    parks_ratio = min(100.0, (parks_count / ideal_parks) * 100.0)
                else:
                    parks_ratio = 0.0
            else:
                # Si no tenim població, usar escala basada en nombre de parcs
                # Escala: >50 parcs = 100%, >20 = 80%, >10 = 60%, >5 = 40%, >1 = 20%, 0 = 0%
                if parks_count >= 50:
                    parks_ratio = 100.0  # Excel·lent
                elif parks_count >= 20:
                    parks_ratio = 80.0 + ((parks_count - 20) / 30) * 20.0  # 80-100%
                elif parks_count >= 10:
                    parks_ratio = 60.0 + ((parks_count - 10) / 10) * 20.0  # 60-80%
                elif parks_count >= 5:
                    parks_ratio = 40.0 + ((parks_count - 5) / 5) * 20.0  # 40-60%
                elif parks_count >= 1:
                    parks_ratio = 20.0 + ((parks_count - 1) / 4) * 20.0  # 20-40%
                else:
                    parks_ratio = 0.0
            
            metrics['parks_ratio'] = min(100.0, parks_ratio)  # Percentatge d'espais verds
            # Guardar també parcs ideals per referència
            if population > 0:
                metrics['ideal_parks'] = population / 10000.0
            
            # Mètriques per Arya
            metrics['density'] = min(1.0, (metrics.get('restaurants', 0) + metrics.get('shops', 0)) / 100.0)
            metrics['public_transport_24h'] = min(1.0, metrics.get('public_transport_stops', 0) / 20.0)
            metrics['diversity_services'] = min(1.0, (metrics.get('restaurants', 0) + metrics.get('shops', 0) + metrics.get('cafes', 0)) / 150.0)
            metrics['anonymity'] = metrics.get('density', 0.5)
            
            # Mètriques per Tyrion
            metrics['restaurants_quality'] = min(1.0, metrics.get('restaurants', 0) / 30.0)
            
            # FASE 1: Calcular cultural_life basat en dades reals
            theatres = metrics.get('theatres', 0)
            cinemas = metrics.get('cinemas', 0)
            museums = metrics.get('museums', 0)
            cultural_total = theatres + cinemas + museums
            # Normalitzar: 10+ llocs culturals = 100%
            metrics['cultural_life'] = min(1.0, cultural_total / 10.0)
            
            # FASE 1 (Google Places): Calcular nightlife basado en datos reales
            bars = metrics.get('bars', 0)
            nightclubs = metrics.get('nightclubs', 0)
            nightlife_total = bars + nightclubs
            # Normalizar: 15+ lugares nocturnos = 100%
            if nightlife_total > 0:
                metrics['nightlife'] = min(1.0, nightlife_total / 15.0)
            else:
                # Fallback si no hay datos
                metrics['nightlife'] = min(1.0, metrics.get('cafes', 0) / 20.0)

