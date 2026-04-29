from django.contrib import admin
from .models import (
    Departamento, Salon, Producto, TipoProducto, 
    Envio, DetalleEnvio, StockSalon, PerfilUsuario, ConsumoSalon
)


class DetalleEnvioInline(admin.TabularInline):
    model = DetalleEnvio
    extra = 1


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)


@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ('nombre',)


@admin.register(TipoProducto)
class TipoProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'departamento')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'departamento', 'tipo', 'es_devolvible')


@admin.register(Envio)
class EnvioAdmin(admin.ModelAdmin):
    list_display = ('id', 'origen', 'destino', 'estado')
    inlines = [DetalleEnvioInline]


@admin.register(StockSalon)
class StockSalonAdmin(admin.ModelAdmin):
    list_display = ('salon', 'producto', 'cantidad')


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'rol')


@admin.register(ConsumoSalon)
class ConsumoSalonAdmin(admin.ModelAdmin):
    # ✅ CORREGIDO: usa fecha_registro en lugar de fecha
    list_display = ('salon', 'producto', 'cantidad', 'fecha_registro', 'fecha_evento')
    list_filter = ('salon', 'fecha_evento')
    search_fields = ('salon__nombre', 'producto__nombre')