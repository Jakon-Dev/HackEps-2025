from django.shortcuts import render

def inicio(request):
    if request.method == 'POST':
        # --- 1. CAPTURA DE DATOS ---
        try:
            prefs = {
                'presupuesto': int(request.POST.get('presupuesto', 5)),
                'seguridad': int(request.POST.get('seguridad', 5)),
                'vida_nocturna': int(request.POST.get('vida_nocturna', 5)),
                # NUEVOS CAMPOS
                'cultura': int(request.POST.get('cultura', 5)),
                'bici': int(request.POST.get('bici', 5)),
                
                'silencio': int(request.POST.get('silencio', 5)),
                'caminabilidad': int(request.POST.get('caminabilidad', 5)),
                'transporte': int(request.POST.get('transporte', 5)),
                
                # Checkboxes / Selects
                'privacidad': request.POST.get('privacidad') == 'on',
                'naturaleza': request.POST.get('naturaleza') == 'on',
                'accesibilidad': request.POST.get('accesibilidad') == 'on',
                'densidad': request.POST.get('densidad'), # 'baja', 'media', 'alta'
            }
        except ValueError:
            return render(request, 'principal/formulario_cliente.html', {'error': 'Datos numéricos inválidos'})

        # --- 2. BASE DE DATOS SIMULADA ACTUALIZADA ---
        # Añadimos puntuaciones de Cultura y Bici a los barrios
        barrios_db = [
            {
                'nombre': 'Downtown L.A. (Arts District)',
                'img': 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Echo_Park_Lake_with_Downtown_Los_Angeles_Skyline.jpg/640px-Echo_Park_Lake_with_Downtown_Los_Angeles_Skyline.jpg',
                'scores': {
                    'presupuesto': 7, 
                    'seguridad': 4, 
                    'vida_nocturna': 10, 
                    'cultura': 9,      # Mucha cultura
                    'bici': 6,         # Medio
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
                    'bici': 10,        # Excelente para bici (playa)
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
                    'bici': 4,         # Muchas cuestas
                    'silencio': 6, 
                    'caminabilidad': 7, 
                    'transporte': 5
                },
                'densidad': 'media',
                'tiene_naturaleza': True,
                'es_accesible': False # No apto para Bran Stark
            },
        ]

        # --- 3. ALGORITMO DE MATCHING MEJORADO ---
        resultados = []
        
        for barrio in barrios_db:
            score = 100
            
            # 1. Filtros "Deal Breakers" (Eliminan directamente)
            if prefs['accesibilidad'] and not barrio['es_accesible']:
                continue 
            
            if prefs['privacidad'] and barrio['densidad'] == 'alta':
                continue # Si quiere privacidad, odia el centro

            # 2. Cálculo de Diferencias (Penalizaciones)
            diff_seguridad = abs(prefs['seguridad'] - barrio['scores']['seguridad'])
            diff_presupuesto = abs(prefs['presupuesto'] - barrio['scores']['presupuesto'])
            diff_vida = abs(prefs['vida_nocturna'] - barrio['scores']['vida_nocturna'])
            
            # Nuevas penalizaciones
            diff_cultura = abs(prefs['cultura'] - barrio['scores']['cultura'])
            diff_bici = abs(prefs['bici'] - barrio['scores']['bici'])
            
            # Aplicar pesos (Weighting)
            score -= (diff_seguridad * 2.5)
            score -= (diff_presupuesto * 2.0)
            score -= (diff_vida * 1.0)
            score -= (diff_cultura * 1.0)
            score -= (diff_bici * 1.5) # Bici pesa bastante
            
            # 3. Bonificaciones
            if prefs['naturaleza'] and barrio['tiene_naturaleza']:
                score += 8
            
            if prefs['densidad'] == barrio['densidad']:
                score += 5

            # Generar Justificación Dinámica
            justificacion = []
            if diff_seguridad <= 1: justificacion.append("Seguridad óptima")
            if diff_presupuesto <= 1: justificacion.append("Buen precio")
            if diff_bici <= 2 and prefs['bici'] > 6: justificacion.append("Gran red ciclista")
            if diff_cultura <= 2 and prefs['cultura'] > 6: justificacion.append("Zona cultural")
            
            texto_justificacion = f"Coincidencia fuerte en: {', '.join(justificacion)}." if justificacion else "Coincidencia aceptable, aunque difiere en algunos servicios."

            # Guardar
            if score > 0:
                resultados.append({
                    'barrio': barrio,
                    'match_ratio': int(score), # Redondear a entero
                    'justificacion': texto_justificacion
                })

        # Ordenar
        resultados.sort(key=lambda x: x['match_ratio'], reverse=True)

        return render(request, 'principal/resultados.html', {'resultados': resultados})

    return render(request, 'principal/formulario_cliente.html')