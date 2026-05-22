from django.contrib import admin
from .models import (
    Departamento, Salon, Producto, TipoProducto, 
    Envio, DetalleEnvio, StockSalon, PerfilUsuario, ConsumoSalon

    search_fields = ('salon__nombre', 'producto__nombre')
