from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

# ── 1. DEPARTAMENTOS (ISLAS: Cheddar, Sushi, Pasta, etc.) ─────────────
class Departamento(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre


# ── 2. SALONES ───────────────────────────────────────────────
class Salon(models.Model):
    nombre = models.CharField(max_length=100)
    ubicacion = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return self.nombre


# ── 3. TIPOS DE PRODUCTO (POR DEPARTAMENTO) ─────────────────────────────
class TipoProducto(models.Model):
    """Los tipos de producto pertenecen a un departamento específico"""
    nombre = models.CharField(max_length=50)  # ej: "pesable", "unidad", "piezas", "rolls", "recepción"
    departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE, related_name='tipos')
    
    def __str__(self):
        return f"{self.nombre} ({self.departamento.nombre})"
    
    class Meta:
        unique_together = ('nombre', 'departamento')
        verbose_name = "Tipo de Producto"
        verbose_name_plural = "Tipos de Productos"


# ── 4. PRODUCTOS (CORREGIDO) ─────────────────────────────────────────────
class Producto(models.Model):
    # Datos principales
    nombre = models.CharField(max_length=200, verbose_name="Nombre del producto")
    departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE, related_name='productos', verbose_name="Departamento/Isla")
    
    # Tipo de producto (ligado al departamento)
    tipo = models.ForeignKey(TipoProducto, on_delete=models.CASCADE, related_name='productos', verbose_name="Tipo")
    
    # Cantidad/gramos (texto libre para ej: "200g", "10 unidades", "1 bandeja")
    cantidad_gramos = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cantidad o gramos", 
                                       help_text="Ej: 200g, 10 unidades, 1 bandeja, 8 piezas")
    
    # Check 1 (del listado)
    check_1 = models.BooleanField(default=False, verbose_name="Check 1")
    
    # Si se puede devolver o no
    es_devolvible = models.BooleanField(default=True)
    
    # Detalle adicional
    detalle = models.TextField(blank=True, null=True, verbose_name="Detalle adicional")
    se_puede_reusar = models.BooleanField(
        default=False,
        verbose_name="Se puede reusar",
        help_text="True para bebidas, False para comida")
    def clean(self):
        # Validar que el tipo pertenezca al mismo departamento que el producto
        if self.tipo and self.tipo.departamento != self.departamento:
            raise ValidationError(f"El tipo '{self.tipo.nombre}' no pertenece al departamento '{self.departamento.nombre}'")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        base = self.nombre
        if self.cantidad_gramos:
            base += f" ({self.cantidad_gramos})"
        if self.tipo:
            base += f" [{self.tipo.nombre}]"
        return base


# ── 5. ENVÍOS (CON FECHA DE EVENTO) ────────────────────────────────
class Envio(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('enviado', 'Enviado'),
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
        ('entregado', 'Entregado'),
    ]

    origen = models.ForeignKey(Departamento, on_delete=models.CASCADE, related_name='envios_salientes')
    destino = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='envios_recibidos')

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    
    # Fecha del evento
    fecha_evento = models.DateTimeField(null=True, blank=True, verbose_name="Fecha del Evento", 
                                        help_text="Fecha y hora del evento para el cual se solicita este envío")

    descripcion = models.TextField(blank=True)

    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='envios_creados')

    # Fechas del sistema
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    fecha_entregado = models.DateTimeField(null=True, blank=True)

    def enviar(self):
        self.estado = 'enviado'
        self.fecha_envio = timezone.now()
        self.save()

    def aceptar(self):
        self.estado = 'aceptado'
        self.fecha_respuesta = timezone.now()
        self.save()

    def rechazar(self):
        self.estado = 'rechazado'
        self.fecha_respuesta = timezone.now()
        self.save()
    
    def entregar(self):
        self.estado = 'entregado'
        self.fecha_entregado = timezone.now()
        self.save()

    def __str__(self):
        evento = f" [Evento: {self.fecha_evento.strftime('%d/%m/%Y %H:%M')}]" if self.fecha_evento else ""
        return f"Envío {self.id} → {self.destino.nombre} [{self.estado}]{evento}"


# ── 6. DETALLE DEL ENVÍO (CORREGIDO) ────────────────────────────────
class DetalleEnvio(models.Model):
    envio = models.ForeignKey(Envio, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    
    # Cantidad específica para ESTE envío (puede diferir del producto base)
    cantidad = models.CharField(max_length=100, blank=True, null=True, 
                                verbose_name="Cantidad para este envío",
                                help_text="Ej: 200g, 5 unidades, 2 bandejas")
    
    # Check incluido en este envío
    check_incluido = models.BooleanField(default=True, verbose_name="Incluido en envío")
    
    # Observaciones específicas de esta línea
    observacion = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        check = "✓" if self.check_incluido else "✗"
        cantidad_str = f" - {self.cantidad}" if self.cantidad else ""
        producto_str = self.producto.cantidad_gramos if self.producto.cantidad_gramos else self.producto.nombre
        return f"{check} {producto_str}{cantidad_str}"


# ── 7. STOCK POR SALÓN ─────────────────────────────────────────────
class StockSalon(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='stock')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.CharField(max_length=100, default='0', 
                                verbose_name="Stock actual",
                                help_text="Ej: 10 unidades, 2kg, 5 bandejas")

    class Meta:
        unique_together = ('salon', 'producto')

    def __str__(self):
        return f"{self.salon.nombre} | {self.producto.nombre}: {self.cantidad}"


# ── 8. PERFIL DE USUARIO ────────────────────────────────────────────
class PerfilUsuario(models.Model):
    ROL_CHOICES = [
        ('admin', 'Administrador'),
        ('departamento', 'Departamento'),
        ('salon', 'Salón'),
    ]

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol = models.CharField(max_length=20, choices=ROL_CHOICES)
    departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE, null=True, blank=True)
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, null=True, blank=True)

    def clean(self):
        if self.rol == 'departamento' and not self.departamento:
            raise ValidationError("Debe tener un departamento")
        if self.rol == 'salon' and not self.salon:
            raise ValidationError("Debe tener un salón")
        if self.rol == 'admin':
            if self.departamento or self.salon:
                raise ValidationError("El admin no debe tener departamento ni salón")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.usuario.username} ({self.rol})"


# ── 9. CONSUMO POR SALÓN ────────────────────────────────────────────
class ConsumoSalon(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='consumos')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.CharField(max_length=100, verbose_name="Cantidad consumida",
                                help_text="Ej: 200g, 5 unidades, 2 porciones")
    
    # Referencia al envío que originó este consumo
    envio = models.ForeignKey(Envio, on_delete=models.SET_NULL, null=True, blank=True, related_name='consumos')
    
    fecha = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField(blank=True, null=True)

    def __str__(self):
        producto_str = self.producto.cantidad_gramos if self.producto.cantidad_gramos else self.producto.nombre
        return f"{self.salon.nombre} - {producto_str} ({self.cantidad})"