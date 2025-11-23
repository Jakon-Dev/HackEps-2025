from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('', views.index, name='index'),
    path('inicio/', views.inicio, name='inicio'),
    path('formulario/', views.formulario, name='formulario'),
    path('formulario/resultados/', views.formulario_resultados, name='formulario_resultados'),
    
    # API endpoints
    path('api/geojson/', views.api_geojson, name='api_geojson'),
    path('api/config/', views.api_config, name='api_config'),
    path('api/crimes-by-neighborhood/', views.api_crimes_by_neighborhood, name='api_crimes_by_neighborhood'),
    path('api/neighborhood/<str:neighborhood_name>/crimes/', views.api_neighborhood_crimes, name='api_neighborhood_crimes'),
    path('api/clients/', views.api_clients, name='api_clients'),
    path('api/recommendations/<str:client_type>/', views.api_recommendations, name='api_recommendations'),
    path('api/neighborhood/<str:neighborhood_name>/metrics/', views.api_neighborhood_metrics, name='api_neighborhood_metrics'),
]