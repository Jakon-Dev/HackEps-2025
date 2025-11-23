"""
Motor de recomanació personalitzat basat en preferències de l'usuari
Usa barrios_procesados_para_recomendacion.csv con scores normalizados
Algoritmo mejorado con sistema de scoring inteligente y árbol de decisiones
"""

import csv
import json
import os
from typing import Dict, List, Optional, Tuple
import math

def round_standard(value: float) -> int:
    """
    Redondeo estándar: 7.5 → 8, 7.4 → 7
    Usa math.floor(x + 0.5) para asegurar redondeo estándar (no banker's rounding)
    """
    return int(math.floor(value + 0.5))

class CustomRecommendationEngine:
    """Motor de recomanació personalitzat con algoritmo mejorado"""
    
    # Caché de datos para evitar cargar múltiples veces
    _cached_data = None
    _cache_path = None
    
    def __init__(self, csv_path: str = None, json_path: str = None):
        """
        Inicialitzar amb dades del CSV de barrios procesados con scores normalizados
        y JSON con métricas para obtener parks_google_places
        
        Args:
            csv_path: Ruta al CSV con scores. Si es None, busca en data/
            json_path: Ruta al JSON con métricas. Si es None, busca en data/
        """
        if csv_path is None:
            # Intentar múltiples rutas posibles
            possible_paths = []
            
            print(f"DEBUG: Buscando CSV de barrios...")
            
            # 0. Usar Django settings si está disponible (Mejor opción)
            try:
                from django.conf import settings
                base_dir = settings.BASE_DIR
                print(f"DEBUG: settings.BASE_DIR = {base_dir}")
                path = os.path.join(base_dir, 'data', 'barrios_procesados_para_recomendacion.csv')
                possible_paths.append(path)
            except ImportError:
                print("DEBUG: No se pudo importar django.conf.settings")
            except Exception as e:
                print(f"DEBUG: Error accediendo a settings.BASE_DIR: {e}")

            # 1. Desde el directorio del archivo actual
            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                print(f"DEBUG: current_dir = {current_dir}")
                path = os.path.join(current_dir, '..', 'data', 'barrios_procesados_para_recomendacion.csv')
                possible_paths.append(path)
            except Exception as e:
                print(f"DEBUG: Error con current_dir: {e}")
            
            # 2. Desde el directorio de trabajo actual
            cwd = os.getcwd()
            print(f"DEBUG: cwd = {cwd}")
            possible_paths.append(os.path.join(cwd, 'data', 'barrios_procesados_para_recomendacion.csv'))
            
            # Buscar la primera ruta que exista
            csv_path = None
            for path in possible_paths:
                abs_path = os.path.abspath(path)
                exists = os.path.exists(abs_path)
                print(f"DEBUG: Probando ruta: {abs_path} - Existe: {exists}")
                if exists:
                    csv_path = abs_path
                    print(f"DEBUG: ¡Archivo encontrado en {csv_path}!")
                    break
            
            if csv_path is None:
                print(f"❌ No se encontró el CSV en ninguna de las rutas probadas: {possible_paths}")
                # Fallback to the first path just in case
                csv_path = possible_paths[0] if possible_paths else 'data/barrios_procesados_para_recomendacion.csv'
        
        # Usar caché si el archivo no ha cambiado
        abs_csv_path = os.path.abspath(csv_path)
        if (CustomRecommendationEngine._cached_data is not None and 
            CustomRecommendationEngine._cache_path == abs_csv_path):
            self.neighborhood_data = CustomRecommendationEngine._cached_data
        else:
            self.neighborhood_data = self._load_csv_data(csv_path)
            CustomRecommendationEngine._cached_data = self.neighborhood_data
            CustomRecommendationEngine._cache_path = abs_csv_path
        
        # Cargar JSON para obtener parks_google_places
        if json_path is None:
            # Intentar múltiples rutas posibles para el JSON
            possible_json_paths = []
            
            print(f"DEBUG: Buscando JSON de métricas...")
            
            # 0. Usar Django settings si está disponible
            try:
                from django.conf import settings
                path = os.path.join(settings.BASE_DIR, 'data', 'neighborhood_metrics.json')
                possible_json_paths.append(path)
            except ImportError:
                pass

            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                path = os.path.join(current_dir, '..', 'data', 'neighborhood_metrics.json')
                possible_json_paths.append(path)
            except:
                pass
            
            cwd = os.getcwd()
            possible_json_paths.append(os.path.join(cwd, 'data', 'neighborhood_metrics.json'))
            
            json_path = None
            for path in possible_json_paths:
                abs_path = os.path.abspath(path)
                exists = os.path.exists(abs_path)
                print(f"DEBUG: Probando ruta JSON: {abs_path} - Existe: {exists}")
                if exists:
                    json_path = abs_path
                    print(f"DEBUG: ¡JSON encontrado en {json_path}!")
                    break
            
            if json_path is None:
                print(f"❌ No se encontró el JSON en ninguna de las rutas probadas: {possible_json_paths}")
                json_path = possible_json_paths[0] if possible_json_paths else 'data/neighborhood_metrics.json'
        
        # Cargar JSON con métricas
        self.json_metrics = self._load_json_metrics(json_path)
    
    def _load_csv_data(self, csv_path: str) -> Dict:
        """Cargar datos del CSV con scores normalizados"""
        neighborhood_data = {}
        
        if not os.path.exists(csv_path):
            print(f"⚠️  CSV no encontrado: {csv_path}")
            return neighborhood_data
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    barrio_name = row['Barrio'].strip()
                    if not barrio_name:
                        continue
                    
                    # Guardar todos los scores del CSV (actualizado con nuevas columnas)
                    neighborhood_data[barrio_name] = {
                        'score_coste_vida': float(row.get('score_coste_vida', 0)),
                        'score_edad': float(row.get('score_edad', 0)),
                        'score_seguridad': float(row.get('score_seguridad', 0)),
                        'score_sanidad': float(row.get('score_sanidad', 0)),
                        'score_educacion': float(row.get('score_educacion', 0)),
                        'score_vida_nocturna': float(row.get('score_vida_nocturna', 0)),
                        'score_cultura': float(row.get('score_cultura', 0)),
                        'score_tiendas': float(row.get('score_tiendas', 0)),
                        'score_hosteleria': float(row.get('score_hosteleria', 0)),
                        'score_calma': float(row.get('score_calma', 0)),
                        'score_naturaleza': float(row.get('score_naturaleza', 0)),
                        'score_walkability': float(row.get('score_walkability', 0)),
                        'score_transporte': float(row.get('score_transporte', 0)),
                    }
            
            print(f"✅ CSV cargado: {len(neighborhood_data)} barrios")
        except Exception as e:
            print(f"❌ Error cargando CSV: {e}")
        
        return neighborhood_data
    
    def _load_json_metrics(self, json_path: str) -> Dict:
        """Cargar métricas del JSON para obtener parks_google_places"""
        json_metrics = {}
        
        if not os.path.exists(json_path):
            print(f"⚠️  JSON no encontrado: {json_path}")
            return json_metrics
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_metrics = json.load(f)
            print(f"✅ JSON de métricas cargado: {len(json_metrics)} barrios")
        except Exception as e:
            print(f"❌ Error cargando JSON: {e}")
        
        return json_metrics
    
    def _calculate_percentiles(self):
        """Calcular percentiles de todos los barrios para normalización inteligente"""
        if hasattr(self, '_percentiles_cached'):
            return self._percentiles_cached
        
        percentiles = {}
        
        # Recopilar todos los valores del CSV (actualizado con nuevas columnas)
        campos_numericos = {
            'score_coste_vida': [],
            'score_edad': [],
            'score_seguridad': [],
            'score_sanidad': [],
            'score_educacion': [],
            'score_vida_nocturna': [],
            'score_cultura': [],
            'score_tiendas': [],
            'score_hosteleria': [],
            'score_calma': [],
            'score_naturaleza': [],
            'score_walkability': [],
            'score_transporte': [],
        }
        
        for name, metrics in self.neighborhood_data.items():
            for campo in campos_numericos.keys():
                if campo in metrics:
                    valor = metrics[campo]
                    if isinstance(valor, (int, float)):
                        campos_numericos[campo].append(valor)
        
        # Calcular percentiles (25, 50, 75, 95)
        import statistics
        for campo, valores in campos_numericos.items():
            if valores:
                valores_sorted = sorted(valores)
                n = len(valores_sorted)
                percentiles[campo] = {
                    'min': min(valores),
                    'p25': valores_sorted[int(n * 0.25)] if n > 0 else 0,
                    'p50': valores_sorted[int(n * 0.50)] if n > 0 else 0,
                    'p75': valores_sorted[int(n * 0.75)] if n > 0 else 0,
                    'p95': valores_sorted[int(n * 0.95)] if n > 0 else 0,
                    'max': max(valores),
                    'mean': statistics.mean(valores),
                }
        
        self._percentiles_cached = percentiles
        return percentiles
    
    def normalize_to_10_percentile(self, value: float, campo: str) -> int:
        """
        Normalizar usando percentiles para mejor distribución.
        Usa percentiles para mapear valores a escala 0-10 de forma más inteligente.
        """
        percentiles = self._calculate_percentiles()
        
        if campo not in percentiles:
            # Fallback a normalización simple
            return self.normalize_to_10(value, 1.0)
        
        p = percentiles[campo]
        
        # Mapear usando percentiles
        if value <= p['p25']:
            # 0-25%: mapear a 0-2.5
            if p['p25'] > p['min']:
                ratio = (value - p['min']) / (p['p25'] - p['min'])
                return round_standard(ratio * 2.5)  # Redondear: 7.5→8, 7.4→7
            else:
                return 0
        elif value <= p['p50']:
            # 25-50%: mapear a 2.5-5
            if p['p50'] > p['p25']:
                ratio = (value - p['p25']) / (p['p50'] - p['p25'])
                return round_standard(2.5 + ratio * 2.5)  # Redondear: 7.5→8, 7.4→7
            else:
                return 2
        elif value <= p['p75']:
            # 50-75%: mapear a 5-7.5
            if p['p75'] > p['p50']:
                ratio = (value - p['p50']) / (p['p75'] - p['p50'])
                return round_standard(5 + ratio * 2.5)  # Redondear: 7.5→8, 7.4→7
            else:
                return 5
        elif value <= p['p95']:
            # 75-95%: mapear a 7.5-9.5
            if p['p95'] > p['p75']:
                ratio = (value - p['p75']) / (p['p95'] - p['p75'])
                return round_standard(7.5 + ratio * 2.0)  # Redondear: 7.5→8, 7.4→7
            else:
                return 7
        else:
            # 95-100%: mapear a 9.5-10
            if p['max'] > p['p95']:
                ratio = (value - p['p95']) / (p['max'] - p['p95'])
                return round_standard(9.5 + ratio * 0.5)  # Redondear: 7.5→8, 7.4→7
            else:
                return 10
    
    def normalize_to_10(self, value: float, max_val: float = 1.0) -> int:
        """Normalitzar valor 0-1 a escala 0-10 con redondeo estándar"""
        if max_val == 0:
            return 5
        normalized = min(10, max(0, round_standard((value / max_val) * 10)))  # Redondear: 7.5→8, 7.4→7
        return normalized
    
    def get_neighborhood_scores(self, neighborhood_name: str) -> Dict:
        """
        Obtenir scores normalitzats (0-10) per a un barri desde el CSV.
        
        Mapea los scores del CSV a los scores internos del algoritmo.
        """
        if neighborhood_name not in self.neighborhood_data:
            return {}
        
        metrics = self.neighborhood_data[neighborhood_name]
        scores = {}
        
        # Presupuesto: score_coste_vida invertido (coste bajo = presupuesto alto/buen precio)
        # score_coste_vida alto (1.0) = coste alto = presupuesto bajo (0/10)
        # score_coste_vida bajo (0.0) = coste bajo = presupuesto alto (10/10)
        score_coste = metrics.get('score_coste_vida', 0.5)
        score_presupuesto = 1.0 - score_coste  # Invertir
        scores['presupuesto'] = self.normalize_to_10_percentile(score_presupuesto, 'score_coste_vida')
        
        # Seguridad: score_seguridad ya está normalizado (0-1)
        score_seguridad = metrics.get('score_seguridad', 0.5)
        scores['seguridad'] = self.normalize_to_10_percentile(score_seguridad, 'score_seguridad')
        
        # Vida nocturna: score_vida_nocturna tiene valores muy bajos, escalar mejor
        score_nocturna = metrics.get('score_vida_nocturna', 0.0)
        # Escalar para mejor diferenciación (multiplicar por 10)
        nocturna_escalada = min(1.0, score_nocturna * 10)
        scores['vida_nocturna'] = self.normalize_to_10_percentile(nocturna_escalada, 'score_vida_nocturna')
        
        # Cultura: score_cultura tiene valores muy bajos, escalar mejor
        score_cultura = metrics.get('score_cultura', 0.0)
        # Escalar para mejor diferenciación (multiplicar por 10)
        cultura_escalada = min(1.0, score_cultura * 10)
        scores['cultura'] = self.normalize_to_10_percentile(cultura_escalada, 'score_cultura')
        
        # Caminabilidad: usar score_walkability (ya separado)
        score_walkability = metrics.get('score_walkability', 0.0)
        scores['caminabilidad'] = self.normalize_to_10_percentile(score_walkability, 'score_walkability')
        
        # Transporte: usar score_transporte (ya separado)
        score_transporte = metrics.get('score_transporte', 0.0)
        scores['transporte'] = self.normalize_to_10_percentile(score_transporte, 'score_transporte')
        
        # Movilidad: combinación de caminabilidad y transporte
        movilidad_score = (scores['caminabilidad'] / 10.0 * 0.6 + scores['transporte'] / 10.0 * 0.4)
        scores['movilidad'] = round_standard(movilidad_score * 10)  # Redondear: 7.5→8, 7.4→7
        
        # Actividad/Bullicio: usar score_calma directamente (calma alta = actividad baja)
        # Invertir score_calma para obtener nivel de actividad (0 = muy tranquilo, 10 = muy activo)
        score_calma = metrics.get('score_calma', 0.5)
        # Primero normalizar score_calma a 0-10, luego invertir
        calma_normalizada = self.normalize_to_10_percentile(score_calma, 'score_calma')
        scores['actividad'] = 10 - calma_normalizada  # Invertir: calma 10 = actividad 0, calma 0 = actividad 10
        
        # Densidad: usar score_calma como indicador (calma alta = densidad baja)
        # Mantener para compatibilidad con el selector de densidad
        if score_calma > 0.80:
            scores['densidad'] = 'baja'  # Muy tranquilo
        elif score_calma > 0.50:
            scores['densidad'] = 'media'  # Moderadamente tranquilo
        else:
            scores['densidad'] = 'alta'  # Poco tranquilo
        
        # Naturaleza: usar score_naturaleza del CSV normalizado a 0-10
        score_naturaleza = metrics.get('score_naturaleza', 0.0)
        nature_score = self.normalize_to_10_percentile(score_naturaleza, 'score_naturaleza')
        scores['naturaleza'] = nature_score  # Score numérico 0-10
        
        # Sanidad: score_sanidad tiene valores muy bajos, escalar mejor
        score_sanidad = metrics.get('score_sanidad', 0.0)
        # Escalar para mejor diferenciación (multiplicar por 5)
        sanidad_escalada = min(1.0, score_sanidad * 5)
        scores['farmacias'] = self.normalize_to_10_percentile(sanidad_escalada, 'score_sanidad')
        scores['hospitales'] = self.normalize_to_10_percentile(sanidad_escalada, 'score_sanidad')
        
        # Educación: score_educacion tiene mejor distribución (agrupa escuelas y universidades)
        score_educacion = metrics.get('score_educacion', 0.0)
        scores['educacion'] = self.normalize_to_10_percentile(score_educacion, 'score_educacion')
        # Mantener escuelas y universidades para compatibilidad con el modal
        scores['escuelas'] = scores['educacion']
        scores['universidades'] = scores['educacion']
        
        # Edad demográfica: score_edad (0-1) donde 0 = joven/vibrante, 1 = maduro/tranquilo
        score_edad = metrics.get('score_edad', 0.5)
        scores['edad_demografica'] = self.normalize_to_10_percentile(score_edad, 'score_edad')
        
        return scores
    
    def _calculate_importance_weights(self, preferences: Dict) -> Dict[str, float]:
        """
        Calcular pesos de importancia basados en las preferencias del usuario.
        Valores extremos (muy altos o muy bajos) indican mayor importancia.
        """
        weights = {}
        
        numeric_criteria = [
            'presupuesto', 'seguridad', 'vida_nocturna', 'cultura',
            'caminabilidad', 'transporte', 'edad_demografica',
            'farmacias', 'hospitales', 'educacion'
        ]
        
        for criterion in numeric_criteria:
            value = preferences.get(criterion, 5)
            # Calcular importancia: valores extremos = más importante
            if value <= 2 or value >= 8:
                weight = 3.0  # Muy importante
            elif value <= 3 or value >= 7:
                weight = 2.0  # Importante
            elif value <= 4 or value >= 6:
                weight = 1.5  # Moderadamente importante
            else:
                weight = 1.0  # Normal
            
            weights[criterion] = weight
        
        # Criterios booleanos
        if preferences.get('naturaleza'):
            weights['naturaleza'] = 2.5
        if preferences.get('privacidad'):
            weights['privacidad'] = 3.0
        
        return weights
    
    def _apply_smart_filters(self, preferences: Dict, barrio_scores: Dict) -> Tuple[bool, float]:
        """
        Aplicar filtros inteligentes con sistema de penalización.
        
        Estrategia:
        - Deal breakers: Seguridad mínima, Privacidad, Naturaleza, Densidad
        - Penalizaciones graduales: Otros criterios penalizan pero no eliminan
        
        Returns:
            (pasa_filtros, penalizacion): True si pasa, False si se elimina, y penalización (0-1)
        """
        penalizacion = 0.0
        
        # DEAL BREAKERS (eliminan directamente)
        
        # FILTRO 1: Seguridad (DEAL BREAKER - debe cumplir mínimo)
        seguridad_solicitada = preferences.get('seguridad', 0)
        seguridad_barrio = barrio_scores.get('seguridad', 0)
        if seguridad_barrio < seguridad_solicitada:
            return (False, 1.0)
        
        # FILTRO 2: Privacidad (DEAL BREAKER)
        if preferences.get('privacidad') and barrio_scores.get('densidad') != 'baja':
            return (False, 1.0)
        
        # FILTRO 3: Naturaleza (DEAL BREAKER)
        # Naturaleza ahora es numérico, verificar si el barrio cumple el mínimo solicitado
        naturaleza_solicitada = preferences.get('naturaleza', 0)
        naturaleza_barrio = barrio_scores.get('naturaleza', 0)
        if naturaleza_solicitada >= 3 and naturaleza_barrio < (naturaleza_solicitada - 1):
            return (False, 1.0)
        
        # FILTRO 4: Densidad (DEAL BREAKER)
        densidad_solicitada = preferences.get('densidad', 'media')
        densidad_barrio = barrio_scores.get('densidad', 'media')
        if densidad_solicitada != densidad_barrio:
            return (False, 1.0)
        
        # FILTROS CON PENALIZACIÓN GRADUAL (no eliminan, pero penalizan)
        
        # Presupuesto: preferir igual o mejor (más barato = presupuesto más alto)
        presupuesto_solicitado = preferences.get('presupuesto', 5)
        presupuesto_barrio = barrio_scores.get('presupuesto', 5)
        if presupuesto_barrio < (presupuesto_solicitado - 3):
            penalizacion += 0.2  # Muy caro
        elif presupuesto_barrio < (presupuesto_solicitado - 1):
            penalizacion += 0.1  # Algo caro
        
        # Vida nocturna: lógica especial
        vida_nocturna_solicitada = preferences.get('vida_nocturna', 5)
        vida_nocturna_barrio = barrio_scores.get('vida_nocturna', 5)
        if vida_nocturna_solicitada <= 2:
            # Pide poca, penalizar mucho si hay mucha
            if vida_nocturna_barrio >= 7:
                penalizacion += 0.25
            elif vida_nocturna_barrio >= 5:
                penalizacion += 0.15
        elif vida_nocturna_solicitada >= 8:
            # Pide mucha, penalizar poco si hay poca (pero no eliminar)
            if vida_nocturna_barrio < (vida_nocturna_solicitada - 3):
                penalizacion += 0.1
        
        # Caminabilidad, Transporte: preferir igual o mejor
        # Ser más flexible: permitir hasta 3 puntos menos sin penalizar mucho
        for criterion in ['caminabilidad', 'transporte']:
            solicitado = preferences.get(criterion, 5)
            barrio = barrio_scores.get(criterion, 5)
            diff = solicitado - barrio
            if diff > 4:  # Mucho peor
                penalizacion += 0.15
            elif diff > 2:  # Algo peor
                penalizacion += 0.08
            elif diff > 0:  # Un poco peor
                penalizacion += 0.03
        
        # Cultura: más estricto - si pide cultura, no mostrar 0
        cultura_solicitada = preferences.get('cultura', 5)
        cultura_barrio = barrio_scores.get('cultura', 5)
        if cultura_solicitada >= 3:  # Si pide cultura media o alta
            if cultura_barrio == 0:
                # Eliminar barrios con cultura 0 si el usuario pide cultura
                return (False, 1.0)
            elif cultura_barrio < (cultura_solicitada - 2):
                penalizacion += 0.2  # Penalizar mucho si está muy lejos
            elif cultura_barrio < cultura_solicitada:
                penalizacion += 0.1  # Penalizar si está un poco menos
        
        # Servicios: preferir igual o mejor, pero menos crítico
        for criterion in ['farmacias', 'hospitales', 'educacion']:
            # Si el usuario configuró escuelas o universidades, usar educacion
            if criterion == 'educacion':
                solicitado = preferences.get('escuelas', preferences.get('universidades', preferences.get('educacion', 5)))
            else:
                solicitado = preferences.get(criterion, 5)
            barrio = barrio_scores.get(criterion, 5)
            if barrio < (solicitado - 3):
                penalizacion += 0.05
        
        return (True, min(0.5, penalizacion))  # Máximo 50% de penalización
    
    def _calculate_match_score(self, preferences: Dict, barrio_scores: Dict, weights: Dict, penalizacion: float) -> float:
        """
        Calcular score de match usando algoritmo mejorado.
        
        Considera:
        1. Similitud en criterios importantes
        2. Bonificaciones por superar expectativas
        3. Penalizaciones por no cumplir
        """
        base_score = 0.0
        total_weight = 0.0
        
        numeric_criteria = [
            'presupuesto', 'seguridad', 'vida_nocturna', 'cultura',
            'caminabilidad', 'transporte', 'edad_demografica',
            'farmacias', 'hospitales', 'educacion'
        ]
        
        for criterion in numeric_criteria:
            user_val = preferences.get(criterion, 5)
            barrio_val = barrio_scores.get(criterion, 5)
            weight = weights.get(criterion, 1.0)
            
            # Calcular similitud (0-1)
            diff = abs(user_val - barrio_val)
            similarity = 1.0 - (diff / 10.0)  # Normalizar diferencia
            
            # Bonificación por superar expectativas (hacia arriba)
            if barrio_val > user_val:
                bonus = (barrio_val - user_val) / 10.0 * 0.3  # Bonus hasta 30%
                similarity = min(1.0, similarity + bonus)
            
            base_score += similarity * weight
            total_weight += weight
        
        # Normalizar
        if total_weight > 0:
            base_score = base_score / total_weight
        
        # Aplicar penalización
        base_score = base_score * (1.0 - penalizacion)
        
        # Bonificaciones especiales
        bonus = 0.0
        
        # Bonificación por coincidencias exactas en criterios importantes
        for criterion in numeric_criteria:
            if weights.get(criterion, 1.0) >= 2.0:  # Criterio importante
                if abs(preferences.get(criterion, 5) - barrio_scores.get(criterion, 5)) <= 1:
                    bonus += 0.05
        
        # Bonificación por naturaleza si coincide o supera lo solicitado
        naturaleza_user = preferences.get('naturaleza', 5)
        naturaleza_barrio = barrio_scores.get('naturaleza', 0)
        if abs(naturaleza_user - naturaleza_barrio) <= 1:
            bonus += 0.1
        elif naturaleza_barrio > naturaleza_user:
            bonus += 0.15  # Supera expectativas
        
        # Bonificación por densidad si coincide
        if preferences.get('densidad') == barrio_scores.get('densidad'):
            bonus += 0.05
        
        final_score = min(100, (base_score * 100) + (bonus * 100))
        
        return final_score
    
    def _calculate_uniform_match_score(self, preferences: Dict, barrio_scores: Dict, tolerance: float = 1.0) -> float:
        """
        Calcular score de match con todos los parámetros igual de importantes.
        
        Args:
            preferences: Preferencias del usuario
            barrio_scores: Scores del barrio
            tolerance: Tolerancia para diferencias (1.0 = estricto, 2.0 = flexible)
        
        Returns:
            Score de match (0-100)
        """
        numeric_criteria = [
            'presupuesto', 'seguridad', 'vida_nocturna', 'cultura',
            'caminabilidad', 'transporte', 'edad_demografica',
            'farmacias', 'hospitales', 'educacion'
        ]
        
        total_score = 0.0
        total_weight = 0.0
        
        for criterion in numeric_criteria:
            user_val = preferences.get(criterion, 5)
            barrio_val = barrio_scores.get(criterion, 5)
            
            # Calcular diferencia
            diff = abs(user_val - barrio_val)
            
            # Score basado en diferencia con tolerancia
            if diff <= tolerance:
                # Coincidencia perfecta o muy cercana
                score = 1.0
            elif diff <= tolerance * 2:
                # Coincidencia aceptable
                score = 1.0 - (diff - tolerance) / tolerance * 0.25  # Penalizar hasta 25%
            elif diff <= tolerance * 3:
                # Coincidencia moderada
                score = 0.75 - (diff - tolerance * 2) / tolerance * 0.25  # Penalizar hasta 50%
            elif diff <= tolerance * 4:
                # Coincidencia baja
                score = 0.5 - (diff - tolerance * 3) / tolerance * 0.3  # Penalizar hasta 80%
            else:
                # Coincidencia muy pobre
                score = max(0.0, 0.2 - (diff - tolerance * 4) / tolerance * 0.2)  # Penalizar hasta 100%
            
            # Bonificación si supera expectativas (hacia arriba) - solo si está cerca
            if barrio_val > user_val and diff <= tolerance * 2:
                bonus = min(0.15, (barrio_val - user_val) / 10.0 * 0.15)
                score = min(1.0, score + bonus)
            
            total_score += score
            total_weight += 1.0
        
        # Naturaleza: comparar valores numéricos (0-10)
        naturaleza_user = preferences.get('naturaleza', 5)
        naturaleza_barrio = barrio_scores.get('naturaleza', 0)
        # Calcular diferencia y penalizar si es muy diferente
        diff_naturaleza = abs(naturaleza_user - naturaleza_barrio)
        if diff_naturaleza <= 1:
            score = 1.0  # Muy cercano
        elif diff_naturaleza <= 2:
            score = 0.7  # Cercano
        elif diff_naturaleza <= 3:
            score = 0.4  # Moderado
        else:
            score = 0.1  # Lejano
        total_score += score
        total_weight += 1.0
        
        if preferences.get('densidad') == barrio_scores.get('densidad', 'media'):
            total_score += 1.0
        total_weight += 1.0
        
        # Normalizar a 0-100
        if total_weight > 0:
            match_ratio = (total_score / total_weight) * 100
        else:
            match_ratio = 0.0
        
        return match_ratio
    
    def _check_individual_scores_match(self, preferences: Dict, barrio_scores: Dict, min_match_percentage: float = 80.0) -> Tuple[bool, Dict]:
        """
        Verificar que CADA score individual tenga al menos el porcentaje de matching especificado.
        
        Args:
            preferences: Preferencias del usuario
            barrio_scores: Scores del barrio
            min_match_percentage: Porcentaje mínimo de matching requerido (0-100)
        
        Returns:
            Tuple (cumple_todos, detalles_por_score)
            - cumple_todos: True si TODOS los scores cumplen el mínimo
            - detalles_por_score: Dict con el match percentage de cada score
        """
        # 80% de matching significa diferencia máxima de 2 puntos (20% de 10)
        # Fórmula: match_percentage = (10 - diff) / 10 * 100
        # Si queremos 80%: (10 - diff) / 10 >= 0.8 => diff <= 2
        
        numeric_criteria = [
            'presupuesto', 'seguridad', 'vida_nocturna', 'cultura',
            'caminabilidad', 'transporte', 'naturaleza', 'actividad',
            'edad_demografica', 'farmacias', 'hospitales', 'educacion'
        ]
        
        detalles = {}
        cumple_todos = True
        
        for criterion in numeric_criteria:
            user_val = preferences.get(criterion, 5)
            barrio_val = barrio_scores.get(criterion, 5)
            
            # Calcular diferencia
            diff = abs(user_val - barrio_val)
            
            # Calcular porcentaje de matching para este score
            # match = (10 - diff) / 10 * 100
            match_percentage = max(0.0, (10.0 - diff) / 10.0 * 100.0)
            
            detalles[criterion] = {
                'user_val': user_val,
                'barrio_val': barrio_val,
                'diff': diff,
                'match_percentage': match_percentage,
                'cumple': match_percentage >= min_match_percentage
            }
            
            # Si algún score no cumple el mínimo, el barrio no pasa el filtro
            # EXCEPCIÓN: Para seguridad, mantener siempre el 80% mínimo si el usuario pide 5
            # (esto se maneja en get_recommendations antes de llamar a esta función)
            if match_percentage < min_match_percentage:
                cumple_todos = False
        
        # Verificar densidad (debe coincidir exactamente)
        densidad_user = preferences.get('densidad', 'media')
        densidad_barrio = barrio_scores.get('densidad', 'media')
        densidad_cumple = densidad_user == densidad_barrio
        detalles['densidad'] = {
            'user_val': densidad_user,
            'barrio_val': densidad_barrio,
            'cumple': densidad_cumple
        }
        
        if not densidad_cumple:
            cumple_todos = False
        
        return cumple_todos, detalles
    
    def get_recommendations(self, preferences: Dict, min_safety: int = 3) -> List[Dict]:
        """
        Obtener recomendaciones usando árbol de decisiones con matching progresivo.
        
        Sistema de matching por niveles (matching mínimo del 80%):
        1. Nivel 1: Matching exacto (match >= 95%)
        2. Nivel 2: Matching muy alto (match >= 90%)
        3. Nivel 3: Matching alto (match >= 80%)
        4. Nivel 4: Matching medio (match >= 70%)
        5. Nivel 5: Matching bajo (match >= 60%)
        6. Nivel 6: Matching mínimo (match >= 50%)
        
        Todos los parámetros tienen igual importancia inicialmente.
        """
        # Asegurar seguridad mínima
        seguridad_minima = max(preferences.get('seguridad', min_safety), min_safety)
        preferences['seguridad'] = seguridad_minima
        
        # Niveles de matching progresivos basados en porcentaje mínimo por score individual
        # Cada score debe cumplir el porcentaje mínimo individualmente
        # El sistema reducirá progresivamente hasta encontrar al menos 5 resultados
        matching_levels = [
            {'min_match_percentage': 95.0, 'name': 'Exacto'},   # Diferencia máxima: 0.5 puntos
            {'min_match_percentage': 90.0, 'name': 'Muy Alto'}, # Diferencia máxima: 1 punto
            {'min_match_percentage': 80.0, 'name': 'Alto'},       # Diferencia máxima: 2 puntos (NIVEL BASE)
            {'min_match_percentage': 75.0, 'name': 'Medio-Alto'},    # Diferencia máxima: 2.5 puntos
            {'min_match_percentage': 70.0, 'name': 'Medio'},    # Diferencia máxima: 3 puntos
            {'min_match_percentage': 60.0, 'name': 'Bajo'},     # Diferencia máxima: 4 puntos
            {'min_match_percentage': 50.0, 'name': 'Muy Bajo'},     # Diferencia máxima: 5 puntos
            {'min_match_percentage': 40.0, 'name': 'Mínimo'},     # Diferencia máxima: 6 puntos
            {'min_match_percentage': 30.0, 'name': 'Muy Mínimo'},     # Diferencia máxima: 7 puntos
        ]
        
        resultados = []
        
        # Aplicar deal breakers primero (seguridad, privacidad, naturaleza, densidad)
        barrios_candidatos = []
        for neighborhood_name in self.neighborhood_data.keys():
            barrio_scores = self.get_neighborhood_scores(neighborhood_name)
            
            if not barrio_scores:
                continue
            
            # Aplicar deal breakers
            seguridad_solicitada = preferences.get('seguridad', 0)
            if barrio_scores.get('seguridad', 0) < seguridad_solicitada:
                continue
            
            if preferences.get('privacidad') and barrio_scores.get('densidad') != 'baja':
                continue
            
            # FILTRO NATURALEZA: Comparar valores numéricos (0-10)
            # Si el usuario solicita naturaleza >= 3, filtrar barrios con naturaleza < 3
            naturaleza_solicitada = preferences.get('naturaleza', 5)
            naturaleza_barrio = barrio_scores.get('naturaleza', 0)
            # Permitir barrios con naturaleza igual o mayor a la solicitada (con tolerancia de -1)
            if naturaleza_solicitada >= 3 and naturaleza_barrio < (naturaleza_solicitada - 1):
                continue
            
            densidad_solicitada = preferences.get('densidad', 'media')
            if densidad_solicitada != barrio_scores.get('densidad', 'media'):
                continue
            
            # Filtro especial de cultura
            cultura_solicitada = preferences.get('cultura', 5)
            if cultura_solicitada >= 3 and barrio_scores.get('cultura', 0) == 0:
                continue
            
            barrios_candidatos.append((neighborhood_name, barrio_scores))
        
        # Aplicar matching progresivo por niveles
        # Reducir progresivamente el matching hasta encontrar al menos 5 resultados
        # Empezar con 80% y reducir gradualmente (70%, 60%, 50%, etc.) hasta encontrar mínimo 5
        # IMPORTANTE: Cada criterio individual mantiene SIEMPRE el 80% mínimo
        # Esto asegura que si pides cualquier valor, solo verás barrios dentro del rango 80% (diferencia <= 2)
        resultados = []
        
        # Criterios numéricos que deben mantener el 80% mínimo
        numeric_criteria = [
            'presupuesto', 'seguridad', 'vida_nocturna', 'cultura',
            'caminabilidad', 'transporte', 'naturaleza', 'actividad',
            'edad_demografica', 'farmacias', 'hospitales', 'educacion'
        ]
        
        # FASE 1: Intentar matching individual estricto (80% por criterio)
        for level in matching_levels:
            if len(resultados) >= 5:
                break
            
            min_match_percentage = level['min_match_percentage']
            
            for neighborhood_name, barrio_scores in barrios_candidatos:
                # Verificar que CADA criterio individual mantenga el 80% mínimo
                cumple_criterios_individuales = True
                
                for criterion in numeric_criteria:
                    user_val = preferences.get(criterion, 5)
                    barrio_val = barrio_scores.get(criterion, 5)
                    diff = abs(user_val - barrio_val)
                    match_pct = max(0.0, (10.0 - diff) / 10.0 * 100.0)
            
                    # Mantener 80% mínimo para cada criterio individual
                    if match_pct < 80.0:
                        cumple_criterios_individuales = False
                        break
                
                if not cumple_criterios_individuales:
                    continue
                
                # Si todos cumplen 80%, verificar matching general
                cumple_todos, detalles_scores = self._check_individual_scores_match(
                    preferences, barrio_scores, min_match_percentage
                )
                
                if cumple_todos:
                    if not any(r['barrio']['nombre'] == neighborhood_name for r in resultados):
                        match_score_promedio = self._calculate_uniform_match_score(preferences, barrio_scores)
                        justificacion = self._generate_justification_simple(preferences, barrio_scores, match_score_promedio)
                        
                        resultados.append({
                            'barrio': {
                                'nombre': neighborhood_name,
                                'scores': barrio_scores,
                                'densidad': barrio_scores.get('densidad', 'media'),
                                'naturaleza': barrio_scores.get('naturaleza', 0),
                                'img': None
                            },
                            'match_ratio': round_standard(match_score_promedio),
                            'justificacion': justificacion,
                            'matching_level': level['name'],
                            'score_details': detalles_scores
                        })
            
            if len(resultados) >= 5:
                break
        
        # FASE 2: Si no hay suficientes resultados, usar matching general (promedio) más flexible
        if len(resultados) < 5:
            for level in matching_levels:
                if len(resultados) >= 5:
                    break
                
                min_match_percentage = level['min_match_percentage']
                
                for neighborhood_name, barrio_scores in barrios_candidatos:
                    if len(resultados) >= 5:
                        break
                    
                    # Calcular matching general (promedio de todos los criterios)
                    match_scores = []
                    for criterion in numeric_criteria:
                        user_val = preferences.get(criterion, 5)
                        barrio_val = barrio_scores.get(criterion, 5)
                        diff = abs(user_val - barrio_val)
                        match_pct = max(0.0, (10.0 - diff) / 10.0 * 100.0)
                        match_scores.append(match_pct)
                    
                    # Matching general = promedio de todos los criterios
                    match_general = sum(match_scores) / len(match_scores) if match_scores else 0.0
                    
                    # Aplicar el nivel de matching al promedio general
                    if match_general >= min_match_percentage:
                        if not any(r['barrio']['nombre'] == neighborhood_name for r in resultados):
                            # Calcular detalles para cada score
                            detalles_scores = {}
                            for criterion in numeric_criteria:
                                user_val = preferences.get(criterion, 5)
                                barrio_val = barrio_scores.get(criterion, 5)
                                diff = abs(user_val - barrio_val)
                                match_pct = max(0.0, (10.0 - diff) / 10.0 * 100.0)
                                detalles_scores[criterion] = {
                                    'user_val': user_val,
                                    'barrio_val': barrio_val,
                                    'diff': diff,
                                    'match_percentage': match_pct,
                                    'cumple': match_pct >= min_match_percentage
                                }
                            
                            match_score_promedio = match_general
                            justificacion = self._generate_justification_simple(preferences, barrio_scores, match_score_promedio)
                            
                            resultados.append({
                                'barrio': {
                                    'nombre': neighborhood_name,
                                    'scores': barrio_scores,
                                    'densidad': barrio_scores.get('densidad', 'media'),
                                    'naturaleza': barrio_scores.get('naturaleza', 0),
                                    'img': None
                                },
                                'match_ratio': round_standard(match_score_promedio),
                                'justificacion': justificacion,
                                'matching_level': f"{level['name']} (General)",
                                'score_details': detalles_scores
                            })
        
        # Ordenar por match_ratio (descendente)
        resultados.sort(key=lambda x: x['match_ratio'], reverse=True)
        
        return resultados

    def _generate_justification_simple(self, preferences: Dict, barrio_scores: Dict, match_score: float) -> str:
        """Generar justificación simple basada en el match score"""
        if match_score >= 90:
            return "Coincidencia excelente en todos los criterios."
        elif match_score >= 80:
            return "Coincidencia muy buena en la mayoría de criterios."
        elif match_score >= 70:
            return "Coincidencia buena, aunque difiere en algunos aspectos."
        elif match_score >= 60:
            return "Coincidencia aceptable, con algunas diferencias."
        else:
            return "Coincidencia básica, con diferencias significativas en varios aspectos."
    
    def _generate_justification(self, user_prefs: Dict, barrio_scores: Dict, weights: Dict) -> str:
        """
        Generar justificación inteligente basada en las mejores coincidencias.
        """
        justificaciones = []
        
        numeric_criteria = [
            ('presupuesto', 'Buen precio'),
            ('seguridad', 'Seguridad óptima'),
            ('vida_nocturna', 'Vida nocturna vibrante'),
            ('cultura', 'Zona cultural'),
            ('caminabilidad', 'Excelente caminabilidad'),
            ('transporte', 'Buen transporte público'),
            ('naturaleza', 'Zonas verdes y naturaleza'),  # Ahora es numérico
            ('edad_demografica', 'Ambiente demográfico ideal'),
            ('farmacias', 'Cerca de farmacias'),
            ('hospitales', 'Cerca de hospitales'),
            ('educacion', 'Educación (escuelas y universidades)'),
        ]
        
        for criterion, label in numeric_criteria:
            user_val = user_prefs.get(criterion, 5)
            barrio_val = barrio_scores.get(criterion, 5)
            diff = abs(user_val - barrio_val)
            weight = weights.get(criterion, 1.0)
            
            # Incluir si es importante y hay buena coincidencia o supera expectativas
            if weight >= 1.5:
                if diff <= 1:
                    justificaciones.append(label)
                elif barrio_val > user_val:
                    justificaciones.append(f"{label} (supera expectativas)")
        
        if user_prefs.get('densidad') == barrio_scores.get('densidad'):
            if barrio_scores.get('densidad') == 'baja':
                justificaciones.append("Tranquilidad y privacidad")
            elif barrio_scores.get('densidad') == 'alta':
                justificaciones.append("Ambiente urbano activo")
        
        if justificaciones:
            return f"Coincidencia fuerte en: {', '.join(justificaciones[:4])}."
        else:
            return "Coincidencia aceptable, aunque difiere en algunos aspectos."
