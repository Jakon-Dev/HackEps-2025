"""
Views for the principal app - Los Angeles neighborhood recommendation system
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
import json

from .utils import data_loader, get_barrios_csv_path
from .recommendation_engine import ClientType
from .custom_recommendation import CustomRecommendationEngine


def index(request):
    """Main page with Google Maps interface"""
    return render(request, 'principal/index.html')


def formulario(request):
    """Custom form page"""
    return render(request, 'principal/formulario_cliente.html')


@require_http_methods(["POST"])
def formulario_resultados(request):
    """Process custom form and show results"""
    try:
        # Validate that the system is available
        if data_loader.data_aggregator is None or data_loader.recommendation_engine is None:
            return render(request, 'principal/formulario_cliente.html', 
                         {'error': 'Sistema de recomendación no disponible. Por favor, inténtalo más tarde.'})
        
        # Validate and capture form preferences
        def safe_int(value, default=5, min_val=0, max_val=10):
            """Safely convert to int with range validation"""
            try:
                val = int(value) if value else default
                return max(min_val, min(max_val, val))
            except (ValueError, TypeError):
                return default
        
        prefs = {
            'presupuesto': safe_int(request.POST.get('presupuesto'), 5),
            'seguridad': safe_int(request.POST.get('seguridad'), 5),
            'vida_nocturna': safe_int(request.POST.get('vida_nocturna'), 5),
            'cultura': safe_int(request.POST.get('cultura'), 5),
            'caminabilidad': safe_int(request.POST.get('caminabilidad'), 5),
            'transporte': safe_int(request.POST.get('transporte'), 5),
            'privacidad': request.POST.get('privacidad') == 'on',
            'naturaleza': safe_int(request.POST.get('naturaleza'), 5),
            'actividad': safe_int(request.POST.get('actividad'), 5),
            'densidad': request.POST.get('densidad', 'media'),
            'farmacias': safe_int(request.POST.get('farmacias'), 5),
            'hospitales': safe_int(request.POST.get('hospitales'), 5),
            'escuelas': safe_int(request.POST.get('escuelas'), 5),
            'universidades': safe_int(request.POST.get('universidades'), 5),
            'edad_demografica': safe_int(request.POST.get('edad_demografica'), 5),
        }
        
        # Validate density
        if prefs['densidad'] not in ['baja', 'media', 'alta']:
            prefs['densidad'] = 'media'
        
    except Exception as e:
        return render(request, 'principal/formulario_cliente.html', 
                     {'error': f'Error procesando el formulario: {str(e)}. Por favor, inténtalo de nuevo.'})
    
    try:
        # Initialize custom recommendation engine
        custom_engine = CustomRecommendationEngine()
        
        if not custom_engine.neighborhood_data:
            return render(request, 'principal/formulario_cliente.html', 
                         {'error': 'No se pudieron cargar los datos de barrios. Por favor, contacta al administrador.'})
        
        # Get recommendations
        resultados = custom_engine.get_recommendations(prefs, min_safety=3)
        
        # Prepare neighborhood names for URL
        barrios_names = [item['barrio']['nombre'] for item in resultados]
        barrios_url = ','.join(barrios_names)
        
        # Get coordinates and polygon paths for each neighborhood
        for item in resultados:
            barrio_name = item['barrio']['nombre']
            
            # Get center coordinates from GeoJSON
            center_coords = data_loader.data_aggregator.get_neighborhood_center(barrio_name)
            if center_coords:
                item['barrio']['center_lat'] = center_coords['lat']
                item['barrio']['center_lng'] = center_coords['lng']
            else:
                # Fallback: use approximate LA coordinates
                item['barrio']['center_lat'] = 34.0522
                item['barrio']['center_lng'] = -118.2437
            
            # Get polygon path for drawing on map
            polygon_path = data_loader.data_aggregator.get_neighborhood_polygon_path(barrio_name)
            if polygon_path:
                item['barrio']['polygon_path'] = polygon_path
            
            # Get bounds for dynamic zoom
            bounds = data_loader.data_aggregator.get_neighborhood_bounds(barrio_name)
            if bounds:
                item['barrio']['bounds'] = bounds
                item['barrio']['visible'] = f"{bounds['min_lat']},{bounds['min_lng']}|{bounds['max_lat']},{bounds['max_lng']}"
            
            # Get all neighborhood metrics for modal
            metrics = data_loader.data_aggregator.get_neighborhood_metrics(barrio_name)
            if metrics:
                item['barrio']['metrics'] = metrics
                
                # Add normalized scores to metrics for consistency
                if 'scores' in item['barrio']:
                    metrics['normalized_scores'] = item['barrio']['scores']
                
                # Convert to JSON string for template
                item['barrio']['metrics_json'] = json.dumps(metrics).replace('"', '&quot;')
        
        # Calculate metrics list for display based on preferences
        metrics_config = [
            ('seguridad', 'Seguridad', 'fas fa-shield-alt', 'bg-danger'),
            ('presupuesto', 'Presupuesto', 'fas fa-piggy-bank', 'bg-success'),
            ('vida_nocturna', 'Vida Nocturna', 'fas fa-cocktail', 'bg-purple'),
            ('cultura', 'Cultura', 'fas fa-theater-masks', 'bg-info'),
            ('caminabilidad', 'Caminabilidad', 'fas fa-walking', 'bg-warning'),
            ('transporte', 'Transporte', 'fas fa-bus', 'bg-primary'),
            ('naturaleza', 'Naturaleza', 'fas fa-tree', 'bg-success'),
            ('actividad', 'Actividad', 'fas fa-running', 'bg-orange'),
            ('edad_demografica', 'Edad', 'fas fa-user-clock', 'bg-secondary'),
            ('farmacias', 'Farmacias', 'fas fa-clinic-medical', 'bg-danger'),
            ('hospitales', 'Hospitales', 'fas fa-hospital', 'bg-danger'),
            ('educacion', 'Educación', 'fas fa-graduation-cap', 'bg-info'),
        ]
        
        metrics_list = []
        for key, label, icon, color in metrics_config:
            if prefs.get(key):
                metrics_list.append({
                    'key': key,
                    'label': label,
                    'icon': icon,
                    'color': color
                })

        return render(request, 'principal/resultados.html', {
            'resultados': resultados,
            'barrios_url': barrios_url,
            'user_preferences': prefs,
            'metrics_list': metrics_list
        })
        
    except Exception as e:
        return render(request, 'principal/formulario_cliente.html', 
                     {'error': f'Error generando recomendaciones: {str(e)}. Por favor, inténtalo de nuevo.'})


# API Endpoints

def api_geojson(request):
    """API endpoint to get GeoJSON data"""
    if data_loader.geojson_data:
        return JsonResponse(data_loader.geojson_data, safe=False)
    else:
        return JsonResponse({'error': 'GeoJSON no disponible'}, status=404)


def api_config(request):
    """Get configuration"""
    return JsonResponse({
        'has_api_key': bool(settings.GOOGLE_MAPS_API_KEY),
        'has_geojson': data_loader.geojson_data is not None,
        'neighborhoods_count': len(data_loader.geojson_data.get('features', [])) if data_loader.geojson_data else 0,
        'crimes_loaded': data_loader.crime_processor is not None,
        'neighborhoods_with_crimes': len(data_loader.crimes_data) if data_loader.crimes_data else 0,
        'recommendation_engine_ready': data_loader.recommendation_engine is not None
    })


def api_crimes_by_neighborhood(request):
    """Get crimes grouped by neighborhood"""
    if not data_loader.crimes_data:
        return JsonResponse({
            'error': 'No hay crims carregats',
            'message': 'Els crims no s\'han pogut carregar o processar'
        }, status=400)
    
    return JsonResponse({
        'success': True,
        'neighborhoods': data_loader.crimes_data
    })


def api_neighborhood_crimes(request, neighborhood_name):
    """Get crimes for a specific neighborhood"""
    if not data_loader.crimes_data:
        return JsonResponse({'error': 'No hay crims carregats'}, status=400)
    
    stats = data_loader.crimes_data.get(neighborhood_name)
    
    if stats is None:
        return JsonResponse({'error': 'Barri no trobat'}, status=404)
    
    return JsonResponse(stats)


def api_clients(request):
    """Get list of available clients"""
    if data_loader.recommendation_engine is None:
        return JsonResponse({'error': 'Motor de recomanació no disponible'}, status=404)
    
    clients = []
    for client_type in ClientType:
        client_info = data_loader.recommendation_engine.get_client_info(client_type)
        clients.append(client_info)
    
    return JsonResponse({
        'success': True,
        'clients': clients
    })


def api_recommendations(request, client_type):
    """Get recommendations for a client"""
    if data_loader.recommendation_engine is None:
        return JsonResponse({'error': 'Motor de recomanació no disponible'}, status=404)
    
    try:
        client_type_enum = ClientType(client_type.lower())
    except ValueError:
        return JsonResponse({'error': f'Client no vàlid: {client_type}'}, status=400)
    
    top_n = int(request.GET.get('top_n', 5))
    min_safety = float(request.GET.get('min_safety', 0.30))
    
    recommendations = data_loader.recommendation_engine.get_recommendations(
        client_type_enum, top_n, min_safety=min_safety
    )
    
    # Add text justifications
    for rec in recommendations:
        rec['justification_text'] = data_loader.recommendation_engine.get_justification_text(
            rec, client_type_enum
        )
    
    return JsonResponse({
        'success': True,
        'client': data_loader.recommendation_engine.get_client_info(client_type_enum),
        'recommendations': recommendations
    })


def api_neighborhood_metrics(request, neighborhood_name):
    """Get metrics for a specific neighborhood"""
    if data_loader.data_aggregator is None:
        return JsonResponse({'error': 'Agregador de dades no disponible'}, status=404)
    
    metrics = data_loader.data_aggregator.get_neighborhood_metrics(neighborhood_name)
    
    if metrics is None:
        return JsonResponse({'error': 'Barri no trobat'}, status=404)
    
    return JsonResponse({
        'success': True,
        'neighborhood': neighborhood_name,
        'metrics': metrics
    })


def inicio(request):
    """Original inicio view - redirect to index"""
    if request.method == 'POST':
        # Keep original functionality for backward compatibility
        try:
            prefs = {
                'presupuesto': int(request.POST.get('presupuesto', 5)),
                'seguridad': int(request.POST.get('seguridad', 5)),
                'vida_nocturna': int(request.POST.get('vida_nocturna', 5)),
                'cultura': int(request.POST.get('cultura', 5)),
                'bici': int(request.POST.get('bici', 5)),
                'silencio': int(request.POST.get('silencio', 5)),
                'caminabilidad': int(request.POST.get('caminabilidad', 5)),
                'transporte': int(request.POST.get('transporte', 5)),
                'privacidad': request.POST.get('privacidad') == 'on',
                'naturaleza': request.POST.get('naturaleza') == 'on',
                'accesibilidad': request.POST.get('accesibilidad') == 'on',
                'densidad': request.POST.get('densidad'),
            }
        except ValueError:
            return render(request, 'principal/formulario_cliente.html', {'error': 'Datos numéricos inválidos'})

        # Original database
        barrios_db = [
            {
                'nombre': 'Downtown L.A. (Arts District)',
                'img': 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Echo_Park_Lake_with_Downtown_Los_Angeles_Skyline.jpg/640px-Echo_Park_Lake_with_Downtown_Los_Angeles_Skyline.jpg',
                'scores': {
                    'presupuesto': 7, 
                    'seguridad': 4, 
                    'vida_nocturna': 10, 
                    'cultura': 9,
                    'bici': 6,
                    'silencio': 1, 
                    'caminabilidad': 9, 
                    'transporte': 10
                },
                'densidad': 'alta',
                'tiene_naturaleza': False,
                'es_accesible': True
            },
            {
                'nombre': 'Santa Monica',
                'img': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Santa_Monica_Pier_at_Dusk.jpg/640px-Santa_Monica_Pier_at_Dusk.jpg',
                'scores': {
                    'presupuesto': 9, 
                    'seguridad': 7, 
                    'vida_nocturna': 8, 
                    'cultura': 6, 
                    'bici': 10,
                    'silencio': 5, 
                    'caminabilidad': 8, 
                    'transporte': 7
                },
                'densidad': 'media',
                'tiene_naturaleza': True,
                'es_accesible': True
            },
            {
                'nombre': 'Beverly Hills',
                'img': 'https://upload.wikimedia.org/wikipedia/commons/e/e0/Beverly_Hills_Hotel_2017.jpg',
                'scores': {
                    'presupuesto': 10, 
                    'seguridad': 9, 
                    'vida_nocturna': 4, 
                    'cultura': 7, 
                    'bici': 5, 
                    'silencio': 9, 
                    'caminabilidad': 5, 
                    'transporte': 2
                },
                'densidad': 'baja',
                'tiene_naturaleza': True,
                'es_accesible': True
            },
            {
                'nombre': 'Silver Lake',
                'img': 'https://upload.wikimedia.org/wikipedia/commons/6/6f/Silver_Lake_Reservoir_2019.jpg',
                'scores': {
                    'presupuesto': 6, 
                    'seguridad': 6, 
                    'vida_nocturna': 7, 
                    'cultura': 8, 
                    'bici': 4,
                    'silencio': 6, 
                    'caminabilidad': 7, 
                    'transporte': 5
                },
                'densidad': 'media',
                'tiene_naturaleza': True,
                'es_accesible': False
            },
        ]

        # Matching algorithm
        resultados = []
        
        for barrio in barrios_db:
            score = 100
            
            # Deal breakers
            if prefs['accesibilidad'] and not barrio['es_accesible']:
                continue 
            
            if prefs['privacidad'] and barrio['densidad'] == 'alta':
                continue

            # Calculate differences
            diff_seguridad = abs(prefs['seguridad'] - barrio['scores']['seguridad'])
            diff_presupuesto = abs(prefs['presupuesto'] - barrio['scores']['presupuesto'])
            diff_vida = abs(prefs['vida_nocturna'] - barrio['scores']['vida_nocturna'])
            diff_cultura = abs(prefs['cultura'] - barrio['scores']['cultura'])
            diff_bici = abs(prefs['bici'] - barrio['scores']['bici'])
            
            # Apply weights
            score -= (diff_seguridad * 2.5)
            score -= (diff_presupuesto * 2.0)
            score -= (diff_vida * 1.0)
            score -= (diff_cultura * 1.0)
            score -= (diff_bici * 1.5)
            
            # Bonuses
            if prefs['naturaleza'] and barrio['tiene_naturaleza']:
                score += 8
            
            if prefs['densidad'] == barrio['densidad']:
                score += 5

            # Generate justification
            justificacion = []
            if diff_seguridad <= 1: justificacion.append("Seguridad óptima")
            if diff_presupuesto <= 1: justificacion.append("Buen precio")
            if diff_bici <= 2 and prefs['bici'] > 6: justificacion.append("Gran red ciclista")
            if diff_cultura <= 2 and prefs['cultura'] > 6: justificacion.append("Zona cultural")
            
            texto_justificacion = f"Coincidencia fuerte en: {', '.join(justificacion)}." if justificacion else "Coincidencia aceptable, aunque difiere en algunos servicios."

            # Save
            if score > 0:
                resultados.append({
                    'barrio': barrio,
                    'match_ratio': int(score),
                    'justificacion': texto_justificacion
                })

        # Sort
        resultados.sort(key=lambda x: x['match_ratio'], reverse=True)

        return render(request, 'principal/resultados.html', {'resultados': resultados})

    return render(request, 'principal/formulario_cliente.html')