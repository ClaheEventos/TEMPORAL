from django.urls import path
from . import views

urlpatterns = [
    path('', views.central, name='central'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('envios/', views.lista_envios, name='lista_envios'),
    path('envios/crear/', views.crear_envio, name='crear_envio'),
    path('envios/<int:envio_id>/', views.detalle_envio, name='detalle_envio'),
    path('envios/<int:envio_id>/enviar/', views.enviar_envio, name='enviar_envio'),
    path('envios/<int:envio_id>/aceptar/', views.aceptar_envio, name='aceptar_envio'),
    path('envios/<int:envio_id>/rechazar/', views.rechazar_envio, name='rechazar_envio'),
    path('api/stock/<int:salon_id>/', views.api_stock_salon, name='api_stock_salon'),
    path('consumir/', views.consumir_producto, name='consumir_producto'),
    path('stock/', views.ver_stock, name='ver_stock'),
    path('reporte/', views.reporte_consumo, name='reporte_consumo'),
    path('envio/<int:envio_id>/preparar/', views.preparar_envio, name='preparar_envio'),  # ← AGREGAR ESTA LÍNEA
    path('envio/<int:envio_id>/eliminar/', views.eliminar_envio, name='eliminar_envio'),

    path('envio/<int:envio_id>/entregar/', views.entregar_envio, name='entregar_envio'),

]