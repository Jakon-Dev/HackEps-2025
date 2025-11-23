"""
Motor de recomanació de barris per als clients de Joc de Trons
Actualizado para usar los nuevos scores del CSV
"""

import json
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from .custom_recommendation import CustomRecommendationEngine

class ClientType(Enum):
    """Tipus de clients"""
    DAENERYS = "daenerys"  # Emprendedora ètica
    CERSEI = "cersei"      # Reina corporativa
    BRAN = "bran"          # Analista total
    JON = "jon"            # Guardià de la comunitat
    ARYA = "arya"          # Nòmada urbana
    TYRION = "tyrion"      # Estratega urbà

@dataclass
class ClientProfile:
    """Perfil d'un client amb les seves necessitats"""
    name: str
    client_type: ClientType
    priorities: Dict[str, float]  # métrica -> pes (0-1)
    description: str

class RecommendationEngine:
    """Motor de recomanació de barris"""
    
    def __init__(self):
        self.clients = self._initialize_clients()
        self.neighborhood_data = {}  # name -> {métricas}
        # Usar CustomRecommendationEngine para obtener los nuevos scores normalizados
        self.custom_engine = CustomRecommendationEngine()
        
    def _initialize_clients(self) -> Dict[ClientType, ClientProfile]:
        """Inicialitzar perfils dels clients"""
        clients = {}
        
        # Daenerys Targaryen: L'Emprenedora Ètica
        clients[ClientType.DAENERYS] = ClientProfile(
            name="Daenerys Targaryen",
            client_type=ClientType.DAENERYS,
            priorities={
                'local_businesses': 0.25,      # Negocis locals
                'community_sense': 0.25,       # Sentit de comunitat
                'parks': 0.15,                 # Parcs (per als gossos)
                'walkability': 0.15,           # Caminabilitat
                'safety': 0.10,                # Seguretat
                'affordability': 0.10          # Preu assequible
            },
            description="Fundadora d'una startup sostenible, nova a la ciutat amb tres 'dracs' (gossos). Busca un barri amb ànima, ple de negocis locals i amb un fort sentit de comunitat."
        )
        
        # Cersei Lannister: La Reina Corporativa
        clients[ClientType.CERSEI] = ClientProfile(
            name="Cersei Lannister",
            client_type=ClientType.CERSEI,
            priorities={
                'safety': 0.30,                # Seguretat màxima
                'income_level': 0.25,         # Nivell d'ingressos alt
                'luxury_shops': 0.20,          # Botigues de luxe
                'elite_schools': 0.15,        # Escoles d'elit
                'privacy': 0.10                # Privacitat (menor densitat)
            },
            description="Executiva d'alt nivell que viu pel poder, el prestigi i la privacitat. Vol viure aïllada en una bombolla de màxima seguretat, escoles d'elit i botigues de luxe."
        )
        
        # Bran Stark: L'Analista Total
        clients[ClientType.BRAN] = ClientProfile(
            name="Bran Stark",
            client_type=ClientType.BRAN,
            priorities={
                'accessibility': 0.30,         # Accessibilitat (zero barreres)
                'quietness': 0.25,             # Silenci (baixa contaminació acústica)
                'internet_quality': 0.25,      # Qualitat d'internet
                'safety': 0.10,                # Seguretat
                'affordability': 0.10          # Preu assequible
            },
            description="Científic de dades que treballa 100% des de casa. Es mou en cadira de rodes, així que necessita zero barreres arquitectòniques. Busca un lloc tranquil, silenciós i amb la millor fibra òptica."
        )
        
        # Jon Snow: El Guardià de la Comunitat
        clients[ClientType.JON] = ClientProfile(
            name="Jon Snow",
            client_type=ClientType.JON,
            priorities={
                'nature_access': 0.30,         # Accés a la natura
                'community_sense': 0.25,       # Sentit de comunitat
                'affordability': 0.20,         # Preu assequible
                'authenticity': 0.15,          # Autenticitat
                'safety': 0.10                 # Seguretat
            },
            description="Treballa als serveis d'emergència i té un sou públic. Busca un barri autèntic, on els veïns es coneguin. Valora allò pràctic, no el luxe, i necessita tenir la natura a prop."
        )
        
        # Arya Stark: La Nòmada Urbana
        clients[ClientType.ARYA] = ClientProfile(
            name="Arya Stark",
            client_type=ClientType.ARYA,
            priorities={
                'public_transport_24h': 0.30,  # Transport públic 24/7
                'density': 0.25,               # Densitat poblacional
                'walkability': 0.20,           # Caminabilitat
                'diversity_services': 0.15,    # Diversitat de serveis
                'anonymity': 0.10              # Anonimat
            },
            description="Freelance independent que valora l'anonimat i la llibertat. Necessita una 'base' en una zona densa i moguda, on pugui barrejar-se amb la gent. Transport públic 24/7."
        )
        
        # Tyrion Lannister: L'Estratega Urbà
        clients[ClientType.TYRION] = ClientProfile(
            name="Tyrion Lannister",
            client_type=ClientType.TYRION,
            priorities={
                'walkability': 0.30,           # Caminabilitat (molt alta)
                'restaurants_quality': 0.25,   # Qualitat de restaurants
                'cultural_life': 0.20,        # Vida cultural
                'nightlife': 0.15,             # Vida nocturna
                'density': 0.10                # Densitat
            },
            description="Consultor brillant i molt social. El seu hàbitat és l'epicentre cultural i gastronòmic de la ciutat. Ho vol tot a peu: de la reunió al millor restaurant, i d'allà a un bar."
        )
        
        return clients
    
    def load_neighborhood_data(self, data: Dict):
        """Carregar dades dels barris"""
        self.neighborhood_data = data
    
    def normalize_score(self, value: float, min_val: float, max_val: float, reverse: bool = False) -> float:
        """Normalitzar un valor a l'interval [0, 1]"""
        if max_val == min_val:
            return 0.5
        
        normalized = (value - min_val) / (max_val - min_val)
        
        if reverse:
            normalized = 1 - normalized
        
        # Assegurar que està dins [0, 1]
        return max(0, min(1, normalized))
    
    def calculate_neighborhood_score(self, neighborhood_name: str, client_type: ClientType) -> Tuple[float, Dict]:
        """Calcular puntuació d'un barri per a un client usando los nuevos scores del CSV"""
        client = self.clients[client_type]
        
        # Obtener scores normalizados (0-10) del CSV usando CustomRecommendationEngine
        barrio_scores = self.custom_engine.get_neighborhood_scores(neighborhood_name)
        if not barrio_scores:
            return 0.0, {}
        
        # Obtener neighborhood_data si está disponible (para compatibilidad)
        neighborhood = self.neighborhood_data.get(neighborhood_name, {})
        
        score = 0.0
        justifications = {}
        
        # Mapear las prioridades del cliente a los nuevos scores del CSV
        metric_mapping = {
            'local_businesses': 'tiendas',  # Usar score_tiendas
            'community_sense': 'cultura',    # Usar score_cultura como proxy
            'parks': 'naturaleza',          # Usar score_naturaleza
            'walkability': 'caminabilidad', # Usar score_walkability
            'safety': 'seguridad',          # Usar score_seguridad
            'affordability': 'presupuesto', # Usar score_coste_vida invertido
            'income_level': 'presupuesto',  # Usar score_coste_vida invertido
            'luxury_shops': 'tiendas',      # Usar score_tiendas
            'elite_schools': 'educacion',   # Usar score_educacion
            'privacy': 'densidad',          # Usar densidad (baja = más privacidad)
            'accessibility': 'caminabilidad', # Usar caminabilidad como proxy
            'quietness': 'actividad',       # Usar score_calma invertido (actividad)
            'internet_quality': 'caminabilidad', # Proxy
            'nature_access': 'naturaleza',  # Usar score_naturaleza
            'authenticity': 'cultura',      # Usar score_cultura
            'public_transport_24h': 'transporte', # Usar score_transporte
            'density': 'densidad',          # Usar densidad
            'diversity_services': 'tiendas', # Usar score_tiendas
            'anonymity': 'densidad',        # Usar densidad (alta = más anonimato)
            'restaurants_quality': 'hosteleria', # Usar score_hosteleria (si existe)
            'cultural_life': 'cultura',    # Usar score_cultura
            'nightlife': 'vida_nocturna'    # Usar score_vida_nocturna
        }
        
        # Calcular puntuació per cada prioritat usando los nuevos scores
        for metric, weight in client.priorities.items():
            # Mapear la métrica del cliente al score del CSV
            mapped_metric = metric_mapping.get(metric, None)
            
            if mapped_metric:
                # Obtener el score normalizado (0-10) del CSV
                score_value = barrio_scores.get(mapped_metric, 0)
                
                # Para densidad, manejar el caso especial (baja/media/alta) primero
                if mapped_metric == 'densidad':
                    densidad_str = barrio_scores.get('densidad', 'media')
                    if metric == 'privacy':
                        # Privacidad: baja densidad = mejor
                        if densidad_str == 'baja':
                            normalized_value = 1.0
                        elif densidad_str == 'media':
                            normalized_value = 0.5
                        else:
                            normalized_value = 0.0
                    elif metric == 'anonymity' or metric == 'density':
                        # Anonimato/Densidad: alta densidad = mejor
                        if densidad_str == 'alta':
                            normalized_value = 1.0
                        elif densidad_str == 'media':
                            normalized_value = 0.5
                        else:
                            normalized_value = 0.0
                else:
                    # Convertir de 0-10 a 0-1 para mantener compatibilidad
                    # Asegurar que score_value es numérico
                    if isinstance(score_value, str):
                        # Si es string, intentar convertir o usar 0
                        try:
                            score_value = float(score_value)
                        except (ValueError, TypeError):
                            score_value = 0
                    normalized_value = float(score_value) / 10.0
                
                contribution = normalized_value * weight
                score += contribution
                
                justifications[metric] = {
                    'value': score_value,
                    'normalized': normalized_value,
                    'weight': weight,
                    'contribution': contribution,
                    'mapped_to': mapped_metric
                }
            else:
                # Si no hay mapeo, intentar obtener del neighborhood_data original
                metric_value = neighborhood.get(metric, 0)
                normalized_value = self._normalize_metric(metric, metric_value, neighborhood)
                contribution = normalized_value * weight
                score += contribution
                
                justifications[metric] = {
                    'value': metric_value,
                    'normalized': normalized_value,
                    'weight': weight,
                    'contribution': contribution
                }
        
        return score, justifications
    
    def _normalize_metric(self, metric: str, value: float, neighborhood: Dict) -> float:
        """Normalitzar una mètrica específica"""
        # Aquest mètode s'ajustarà segons les dades reals
        # Per ara, assumim valors normalitzats o els normalitzem bàsicament
        
        if isinstance(value, (int, float)):
            # Normalització simple: assumim que els valors venen normalitzats
            # o els normalitzem segons el tipus de mètrica
            if metric in ['safety', 'accessibility', 'quietness', 'internet_quality']:
                # Mètriques on més alt és millor
                return min(1.0, max(0.0, value / 100.0)) if value > 1 else value
            elif metric in ['crime_rate', 'noise_level']:
                # Mètriques on més baix és millor
                return max(0.0, min(1.0, 1.0 - (value / 100.0))) if value > 1 else (1.0 - value)
            else:
                # Altres mètriques: normalització simple
                return min(1.0, max(0.0, value))
        
        return 0.0
    
    def get_recommendations(self, client_type: ClientType, top_n: int = 5, min_safety: float = 0.30) -> List[Dict]:
        """Obtenir recomanacions per a un client
        
        Args:
            client_type: Tipus de client
            top_n: Nombre de recomanacions a retornar
            min_safety: Seguretat mínima requerida (0-1). Barris amb seguretat inferior no es recomanen.
                        Per defecte: 0.30 (30%) - no recomanar barris poc segurs
        """
        # Usar los barrios del custom_engine (que tiene los datos del CSV)
        if not self.custom_engine.neighborhood_data:
            return []
        
        scores = []
        
        # Iterar sobre los barrios del CSV
        for neighborhood_name in self.custom_engine.neighborhood_data.keys():
            # Obtener neighborhood_data si está disponible (para compatibilidad)
            neighborhood = self.neighborhood_data.get(neighborhood_name, {})
            
            # Obtener score de seguridad del CSV (0-10) y convertir a 0-1
            barrio_scores = self.custom_engine.get_neighborhood_scores(neighborhood_name)
            if not barrio_scores:
                # Si no hay scores del CSV, usar el valor original del neighborhood_data
                safety = neighborhood.get('safety', 0)
                if isinstance(safety, (int, float)) and safety > 1:
                    safety = safety / 100.0  # Convertir de 0-100 a 0-1
            else:
                seguridad_score = barrio_scores.get('seguridad', 0)
                safety = seguridad_score / 10.0  # Convertir de 0-10 a 0-1
            
            # Filtrar barris amb seguretat massa baixa
            if safety < min_safety:
                continue  # Saltar aquest barri
            
            score, justifications = self.calculate_neighborhood_score(neighborhood_name, client_type)
            scores.append({
                'neighborhood': neighborhood_name,
                'score': score,
                'justifications': justifications,
                'data': neighborhood,
                'safety': safety,
                'scores': barrio_scores if barrio_scores else {}  # Incluir los nuevos scores normalizados
            })
        
        # Ordenar per puntuació (descendent)
        scores.sort(key=lambda x: x['score'], reverse=True)
        
        # Retornar top N
        return scores[:top_n]
    
    def get_justification_text(self, recommendation: Dict, client_type: ClientType) -> str:
        """Generar text de justificació per a una recomanació"""
        client = self.clients[client_type]
        neighborhood = recommendation['neighborhood']
        justifications = recommendation['justifications']
        
        text = f"**{neighborhood}** és perfecte per a {client.name} perquè:\n\n"
        
        # Ordenar justificacions per contribució
        sorted_just = sorted(
            justifications.items(),
            key=lambda x: x[1]['contribution'],
            reverse=True
        )
        
        for metric, data in sorted_just[:5]:  # Top 5 raons
            metric_name = self._get_metric_display_name(metric)
            value = data['normalized']
            
            if value > 0.7:
                text += f"✅ **{metric_name}**: Excel·lent ({value*100:.0f}%)\n"
            elif value > 0.5:
                text += f"✓ **{metric_name}**: Bo ({value*100:.0f}%)\n"
            else:
                text += f"• **{metric_name}**: Acceptable ({value*100:.0f}%)\n"
        
        return text
    
    def _get_metric_display_name(self, metric: str) -> str:
        """Obtenir nom d'exhibició per a una mètrica"""
        names = {
            'local_businesses': 'Negocis Locals',
            'community_sense': 'Sentit de Comunitat',
            'parks': 'Parcs i Espais Verds',
            'walkability': 'Caminabilitat',
            'safety': 'Seguretat',
            'affordability': 'Preu Assequible',
            'income_level': 'Nivell d\'Ingressos',
            'luxury_shops': 'Botigues de Luxe',
            'elite_schools': 'Escoles d\'Elit',
            'privacy': 'Privacitat',
            'accessibility': 'Accessibilitat',
            'quietness': 'Silenci',
            'internet_quality': 'Qualitat d\'Internet',
            'nature_access': 'Accés a la Natura',
            'authenticity': 'Autenticitat',
            'public_transport_24h': 'Transport Públic 24/7',
            'density': 'Densitat Poblacional',
            'diversity_services': 'Diversitat de Serveis',
            'anonymity': 'Anonimat',
            'restaurants_quality': 'Qualitat de Restaurants',
            'cultural_life': 'Vida Cultural',
            'nightlife': 'Vida Nocturna'
        }
        return names.get(metric, metric.replace('_', ' ').title())
    
    def get_client_info(self, client_type: ClientType) -> Dict:
        """Obtenir informació d'un client"""
        client = self.clients[client_type]
        return {
            'name': client.name,
            'type': client_type.value,
            'description': client.description,
            'priorities': client.priorities
        }

