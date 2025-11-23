"""
Mòdul per mapejar barris del LA Times als Neighborhood Councils
"""

import pandas as pd
import json
from typing import Dict, List, Set, Optional
from difflib import SequenceMatcher

class NeighborhoodMapper:
    """Classe per mapejar noms de barris entre diferents sistemes"""
    
    def __init__(self, la_times_csv_path: str, geojson_path: str):
        self.la_times_csv_path = la_times_csv_path
        self.geojson_path = geojson_path
        self.la_times_df = None
        self.geojson_data = None
        self.mapping = {}  # la_times_name -> council_name
        self.reverse_mapping = {}  # council_name -> [la_times_names]
        
    def load_data(self):
        """Carregar dades del LA Times i GeoJSON"""
        try:
            print(f"📊 Carregant dades del LA Times de {self.la_times_csv_path}...")
            self.la_times_df = pd.read_csv(self.la_times_csv_path)
            print(f"✅ {len(self.la_times_df)} barris del LA Times carregats")
            
            print(f"📊 Carregant GeoJSON de {self.geojson_path}...")
            with open(self.geojson_path, 'r') as f:
                self.geojson_data = json.load(f)
            print(f"✅ {len(self.geojson_data.get('features', []))} Neighborhood Councils carregats")
            
            return True
        except Exception as e:
            print(f"❌ Error carregant dades: {e}")
            return False
    
    def similarity(self, str1: str, str2: str) -> float:
        """Calcular similitud entre dos strings"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def create_mapping(self, similarity_threshold: float = 0.6):
        """Crear mapeig entre barris del LA Times i Neighborhood Councils"""
        if not self.la_times_df or not self.geojson_data:
            if not self.load_data():
                return
        
        print("🔍 Creant mapeig entre barris...")
        
        # Obtenir noms únics
        la_times_names = set(self.la_times_df['name'].str.strip().dropna())
        council_names = [
            f.get('properties', {}).get('Name', '').strip()
            for f in self.geojson_data.get('features', [])
        ]
        council_names = [n for n in council_names if n]
        
        # Crear mapeig
        for la_name in la_times_names:
            best_match = None
            best_score = 0
            
            la_upper = la_name.upper()
            
            for council_name in council_names:
                council_upper = council_name.upper()
                
                # Coincidència exacta
                if la_upper == council_upper:
                    best_match = council_name
                    best_score = 1.0
                    break
                
                # Conté o està contingut
                if la_upper in council_upper or council_upper in la_upper:
                    score = min(len(la_upper), len(council_upper)) / max(len(la_upper), len(council_upper))
                    if score > best_score:
                        best_match = council_name
                        best_score = score
                
                # Similitud
                sim = self.similarity(la_name, council_name)
                if sim > best_score and sim >= similarity_threshold:
                    best_match = council_name
                    best_score = sim
            
            if best_match:
                self.mapping[la_name] = best_match
                if best_match not in self.reverse_mapping:
                    self.reverse_mapping[best_match] = []
                self.reverse_mapping[best_match].append(la_name)
        
        print(f"✅ Mapeig creat: {len(self.mapping)} barris mapejats")
    
    def get_la_times_names_for_council(self, council_name: str) -> List[str]:
        """Obtenir noms del LA Times per a un Neighborhood Council"""
        return self.reverse_mapping.get(council_name, [])
    
    def get_council_for_la_times_name(self, la_times_name: str) -> Optional[str]:
        """Obtenir Neighborhood Council per a un nom del LA Times"""
        return self.mapping.get(la_times_name)
    
    def get_mapping_stats(self) -> Dict:
        """Obtenir estadístiques del mapeig"""
        total_la_times = len(self.la_times_df['name'].unique()) if self.la_times_df is not None else 0
        mapped = len(self.mapping)
        mapping_rate = (mapped / total_la_times * 100) if total_la_times > 0 else 0
        
        return {
            'total_la_times': total_la_times,
            'mapped': mapped,
            'unmapped': total_la_times - mapped,
            'mapping_rate': mapping_rate
        }

