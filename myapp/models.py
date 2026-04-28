from django.db import models

class Cliente(models.Model):
    dni = models.CharField(max_length=20)
    nombre = models.CharField(max_length=100)
    fecha_evento = models.DateField()
    horario_evento = models.TimeField(null=True, blank=True)  # Nuevo campo
    horario_cierre = models.TimeField(null=True, blank=True)   # Nuevo campo (cierre)
    salon = models.CharField(max_length=100)
    tipo_evento = models.CharField(max_length=100)  # Campo ya existente

    def __str__(self):
        return f"{self.nombre} - {self.dni} - {self.tipo_evento} a las {self.horario_evento}"
    
class Telefono(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='telefonos')
    numero1 = models.CharField(max_length=20)
    numero2 = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return f"{self.numero1} / {self.numero2} ({self.cliente.nombre})"
    
class Plan(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='plan')
    nombre = models.CharField(max_length=100)  # Ej: "Plan 1", "Plan Premium"

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"

# ===== Bebidas =====
class EleccionBebidas(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='bebidas')
    nombre = models.CharField(max_length=100)  # Nombre de la bebida seleccionada

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"


# ===== Vinos =====
class EleccionVinos(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='vinos')
    nombre = models.CharField(max_length=50)
    observacion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"


# ===== Choperas =====
class EleccionChoperas(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='choperas')
    sabor = models.CharField(max_length=50)
    variante = models.CharField(max_length=20, blank=True, null=True)  # ej: 30, 40, 50 o personalizada
    observacion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.sabor} ({self.variante}) - {self.cliente.nombre}"
    
class Isla(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='islas')
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"
    
class IslaPremium(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='islas_premium')
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"
    


class Eleccion_Platos(models.Model):
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, related_name='elecciones')
    plato_principal = models.TextField(null=True, blank=True)
    plato_infantil = models.TextField(null=True, blank=True)
    aclaraciones_alimentarias = models.TextField(null=True, blank=True)
    
    # Cantidades de personas
    num_adultos = models.PositiveIntegerField(null=True, blank=True)
    num_ninos = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.cliente.nombre} - {self.plato_principal}"    
class Postre(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='postres')
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"

class MesaDulcePremium(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='mesa_dulce_premium')
    nombre = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"
    
class Extra(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='extras')
    nombre = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"
    
class Show(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='shows')
    nombre = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"
    
class EleccionFinDeFiesta(models.Model):
    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name='fin_de_fiesta')
    nombre = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"
   
class Cantidades(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='cantidades')
    cantidad = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.cantidad} personas"


class BarraTragos(models.Model):
    cliente = models.ForeignKey("Cliente", on_delete=models.CASCADE, related_name="barra_tragos")
    duracion = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.duracion} - {self.cliente.nombre}"

class EleccionRecepcion(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='recepcion')
    item = models.CharField(max_length=200)  # nombre del ítem
    cantidad = models.PositiveIntegerField(default=0)
    observacion = models.TextField(blank=True, null=True)  # nuevo campo

    def __str__(self):
        return f"{self.item} - {self.cantidad} personas ({self.cliente.nombre})"
    
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

class PerfilUsuario(models.Model):
    USUARIO_TIPOS = (
        ('audi', 'Usuario audiitoria'),
        ('intermedio', 'Usuario Intermedio'),
         
        ('limitado', 'Usuario Limitado'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=USUARIO_TIPOS, default='limitado')

    def __str__(self):
        return f"{self.user.username} - {self.tipo}"


@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        PerfilUsuario.objects.create(user=instance)

@receiver(post_save, sender=User)
def guardar_perfil_usuario(sender, instance, **kwargs):
    instance.perfilusuario.save()


class Personal(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='personal')
    nombre = models.CharField(max_length=50)
    cantidad = models.PositiveIntegerField(default=1)
    horas = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        if self.nombre == "Barman":
            return f"{self.nombre} x {self.cantidad} - {self.horas} horas - {self.cliente.nombre}"
        return f"{self.nombre} x {self.cantidad} - {self.cliente.nombre}"
    

class Boutique(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="boutique")
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.cliente.nombre} - {self.nombre}"


class FirmaEvento(models.Model):
    ESTADOS_FIRMA = (
        ('pendiente', 'Pendiente'),
        ('firmado', 'Firmado'),
        ('rechazado', 'Rechazado'),
    )

    cliente = models.OneToOneField(
        Cliente,
        on_delete=models.CASCADE,
        related_name='firma_evento'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_FIRMA,
        default='pendiente'
    )
    fecha_firma = models.DateTimeField(null=True, blank=True)
    observacion = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Firma {self.cliente.nombre} - {self.estado}"