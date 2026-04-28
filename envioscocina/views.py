import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone

from .models import Envio, DetalleEnvio, Producto, Salon, StockSalon, ConsumoSalon, Departamento, TipoProducto


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('central')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('central')
        else:
            messages.error(request, "Usuario o contraseña incorrectos")

    return render(request, 'login.html')


@login_required(login_url='/envioscocina/login/')
def logout_view(request):
    logout(request)
    return redirect('login')


# ─────────────────────────────────────────────
# CENTRAL DE APLICACIONES
# ─────────────────────────────────────────────

APPS_DISPONIBLES = [
    {
        'id': 'envios',
        'nombre': 'Envíos a salones',
        'descripcion': 'Crear y gestionar envíos de productos entre cocina y salones.',
        'url_name': 'lista_envios',
        'icono': 'envios',
        'roles': ['admin', 'departamento', 'salon'],
    },
    {
        'id': 'stock',
        'nombre': 'Control de stock',
        'descripcion': 'Ver el stock actual de productos por salón.',
        'url_name': 'ver_stock',
        'icono': 'stock',
        'roles': ['admin', 'departamento', 'salon'],
    },
    {
        'id': 'consumo',
        'nombre': 'Registrar consumo',
        'descripcion': 'Registrar consumo de productos en el salón.',
        'url_name': 'ver_stock',
        'icono': 'consumo',
        'roles': ['salon'],
    },
    {
        'id': 'historial',
        'nombre': 'Historial y reportes',
        'descripcion': 'Reportes de envíos, promedios y actividad por período.',
        'url_name': 'reporte_consumo',
        'icono': 'historial',
        'roles': ['admin'],
    },
]

@login_required(login_url='/envioscocina/login/')
def central(request):
    user = request.user
    rol = user.perfil.rol

    apps = [a.copy() for a in APPS_DISPONIBLES if rol in a['roles']]

    for app in apps:
        app['badge'] = 0

        if app['id'] == 'envios':
            if rol in ('departamento', 'admin'):
                envios = Envio.objects.filter(estado='pendiente')
                if rol == 'departamento':
                    envios = envios.filter(origen=user.perfil.departamento)
                app['badge'] = envios.count()
            elif rol == 'salon':
                app['badge'] = Envio.objects.filter(
                    destino=user.perfil.salon,
                    estado='enviado'
                ).count()

    return render(request, 'central.html', {'apps': apps})


# ─────────────────────────────────────────────
# API: stock de un salón
# ─────────────────────────────────────────────
# Primero, actualizá tu API para que devuelva el tipo (solo esto agregás):
# Primero, actualizá tu API para que devuelva el tipo (solo esto agregás):
@login_required(login_url='/envioscocina/login/')
def api_stock_salon(request, salon_id):
    if request.user.perfil.rol not in ('departamento', 'admin'):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    salon = get_object_or_404(Salon, id=salon_id)
    
    if request.user.perfil.rol == 'admin':
        productos = Producto.objects.all()
    else:
        productos = Producto.objects.filter(departamento=request.user.perfil.departamento)
    
    data = []
    for p in productos:
        stock = StockSalon.objects.filter(salon=salon, producto=p).first()
        data.append({
            'id': p.id,
            'nombre': str(p),
            'es_devolvible': p.es_devolvible,
            'se_puede_reusar': p.se_puede_reusar,
            'stock_salon': stock.cantidad if stock else '0',
            'tipo_nombre': p.tipo.nombre if p.tipo else 'OTROS',  # 🔥 AGREGÁ ESTA LÍNEA
        })
    
    return JsonResponse({'salon': salon.nombre, 'productos': data})
# ─────────────────────────────────────────────
# LISTA DE ENVÍOS
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def lista_envios(request):
    user = request.user
    rol = user.perfil.rol

    if rol == 'admin':
        envios = Envio.objects.all()
    elif rol == 'departamento':
        envios = Envio.objects.filter(origen=user.perfil.departamento)
    elif rol == 'salon':
        # Salón ve todos los envíos de su destino
        envios = Envio.objects.filter(destino=user.perfil.salon)
    else:
        envios = Envio.objects.none()

    # 🔥 NUEVO: Para salón, si no hay filtro, mostrar SOLO 'enviado' por defecto
    estado = request.GET.get('estado')
    if rol == 'salon' and not estado:
        # Por defecto filtrar solo enviados
        envios = envios.filter(estado='enviado')
        estado_activo = 'enviado'
    elif estado:
        envios = envios.filter(estado=estado)
        estado_activo = estado
    else:
        estado_activo = 'todos'

    envios = envios.order_by('-fecha_creacion')

    estados = [
        ('', 'Todos'),
        ('pendiente', 'Pendientes'),
        ('enviado', 'Enviados'),
        ('aceptado', 'Aceptados'),
        ('rechazado', 'Rechazados'),
        ('entregado', 'Entregados'),
    ]

    return render(request, 'envios/lista.html', {
        'envios': envios,
        'estado_activo': estado_activo,
        'estados': estados,
    })
# CREAR ENVÍO (ACTUALIZADO)
# ─────────────────────────────────────────────
@login_required(login_url='/envioscocina/login/')
def crear_envio(request):
    if request.user.perfil.rol != 'departamento':
        messages.error(request, "Solo departamento puede crear envíos")
        return redirect('lista_envios')

    salones = Salon.objects.all()
    productos = Producto.objects.filter(departamento=request.user.perfil.departamento)

    if request.method == 'POST':
        destino_id = request.POST.get('destino')
        descripcion = request.POST.get('descripcion', '')
        fecha_evento = request.POST.get('fecha_evento')

        envio = Envio.objects.create(
            origen=request.user.perfil.departamento,
            destino_id=destino_id,
            descripcion=descripcion,
            creado_por=request.user,
        )
        
        if fecha_evento:
            envio.fecha_evento = fecha_evento
            envio.save()

        salon = get_object_or_404(Salon, id=destino_id)
        productos_del_departamento = Producto.objects.filter(departamento=request.user.perfil.departamento)

        for producto in productos_del_departamento:
            # Obtener cantidad a USAR DEL STOCK
            usar_stock_str = request.POST.get(f'usar_stock_{producto.id}', '0')
            # Obtener cantidad a ENVIAR NUEVOS
            enviar_nuevos_str = request.POST.get(f'enviar_{producto.id}', '0')
            
            usar_stock_num = int(usar_stock_str) if usar_stock_str.isdigit() else 0
            enviar_nuevos_num = int(enviar_nuevos_str) if enviar_nuevos_str.isdigit() else 0
            
            # Si no hay nada, saltar
            if usar_stock_num == 0 and enviar_nuevos_num == 0:
                continue
            
            # 🔥 1. PROCESAR USO DE STOCK EXISTENTE (DESCONTAR)
            if usar_stock_num > 0:
                stock, created = StockSalon.objects.get_or_create(
                    salon=salon,
                    producto=producto,
                    defaults={'cantidad': '0'}
                )
                
                # Extraer número actual del stock
                stock_actual_num = extraer_numero(stock.cantidad) if stock.cantidad else 0
                stock_unidad = extraer_unidad(stock.cantidad) if stock.cantidad else 'unidades'
                
                if stock_actual_num >= usar_stock_num:
                    nuevo_stock_num = stock_actual_num - usar_stock_num
                    stock.cantidad = f"{nuevo_stock_num} {stock_unidad}".strip()
                    stock.save()
                    messages.info(request, f"✅ Reservado {usar_stock_num} de {producto.nombre} del stock existente. Stock restante: {stock.cantidad}")
                else:
                    messages.warning(request, f"⚠️ No hay suficiente stock de {producto.nombre}. Tenés {stock.cantidad}, querés usar {usar_stock_num}.")
            
            # 🔥 2. PROCESAR ENVÍO DE NUEVOS PRODUCTOS
            if enviar_nuevos_num > 0:
                DetalleEnvio.objects.create(
                    envio=envio,
                    producto=producto,
                    cantidad=str(enviar_nuevos_num),
                    check_incluido=True,
                )
                messages.info(request, f"📦 Enviando {enviar_nuevos_num} nuevos de {producto.nombre}")

        if envio.detalles.count() == 0 and usar_stock_num == 0:
            messages.warning(request, "No se agregaron productos al envío.")
        else:
            messages.success(request, "Envío creado correctamente")
            
        return redirect('lista_envios')

    return render(request, 'envios/crear.html', {
        'salones': salones,
        'productos': productos,
    })

# ─────────────────────────────────────────────
# DETALLE DE UN ENVÍO
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def detalle_envio(request, envio_id):
    envio = get_object_or_404(Envio, id=envio_id)
    return render(request, 'envios/detalle.html', {'envio': envio})


# ─────────────────────────────────────────────
# ENVIAR (departamento)
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def enviar_envio(request, envio_id):
    envio = get_object_or_404(Envio, id=envio_id)

    if request.user.perfil.rol != 'departamento':
        messages.error(request, "No permitido")
        return redirect('lista_envios')

    if envio.estado != 'pendiente':
        messages.error(request, "Solo se pueden enviar envíos pendientes")
        return redirect('lista_envios')

    envio.enviar()
    messages.success(request, "Envío marcado como enviado")
    return redirect('lista_envios')


# ─────────────────────────────────────────────
# ACEPTAR (salón) - ACTUALIZADO
# ─────────────────────────────────────────────


@login_required(login_url='/envioscocina/login/')
def aceptar_envio(request, envio_id):
    envio = get_object_or_404(Envio, id=envio_id)

    if request.user.perfil.rol != 'salon':
        messages.error(request, "Solo el salón puede aceptar")
        return redirect('lista_envios')

    if envio.estado != 'enviado':
        messages.error(request, "Solo se pueden aceptar envíos en estado 'enviado'")
        return redirect('lista_envios')

    # Sumar al stock del salón
    for detalle in envio.detalles.all():
        if not detalle.check_incluido:
            continue
            
        stock, created = StockSalon.objects.get_or_create(
            salon=envio.destino,
            producto=detalle.producto,
            defaults={'cantidad': '0'}
        )
        
        # 🔥 SUMAR la cantidad del envío al stock existente
        if created or stock.cantidad == '0':
            stock.cantidad = detalle.cantidad
        else:
            stock.cantidad = sumar_cantidades(stock.cantidad, detalle.cantidad)
        stock.save()

    envio.aceptar()
    messages.success(request, "Envío aceptado y stock actualizado")
    return redirect('lista_envios')

# ─────────────────────────────────────────────
# RECHAZAR (salón)
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def rechazar_envio(request, envio_id):
    envio = get_object_or_404(Envio, id=envio_id)

    if request.user.perfil.rol != 'salon':
        messages.error(request, "Solo el salón puede rechazar")
        return redirect('lista_envios')

    if envio.estado != 'enviado':
        messages.error(request, "Solo se pueden rechazar envíos en estado 'enviado'")
        return redirect('lista_envios')

    envio.rechazar()
    messages.warning(request, "Envío rechazado")
    return redirect('lista_envios')


# ─────────────────────────────────────────────
# CONSUMIR PRODUCTO - ACTUALIZADO
# ─────────────────────────────────────────────
@login_required(login_url='/envioscocina/login/')
def consumir_producto(request):
    if request.user.perfil.rol != 'salon':
        messages.error(request, "Solo salones pueden registrar consumo")
        return redirect('lista_envios')

    if request.method == 'POST':
        producto_id = request.POST.get('producto')
        cantidad_sobrante = request.POST.get('sobrante', '').strip()
        comentario = request.POST.get('comentario', '')

        if not cantidad_sobrante:
            messages.error(request, "Ingresá cuánto SOBRÓ")
            return redirect('ver_stock')

        salon = request.user.perfil.salon
        producto = get_object_or_404(Producto, id=producto_id)

        stock, created = StockSalon.objects.get_or_create(
            salon=salon,
            producto=producto,
            defaults={'cantidad': '0'}
        )

        # 🔥 LÓGICA: reusable vs no reusable
        if producto.se_puede_reusar:
            stock.cantidad = cantidad_sobrante
            messages.success(request, f"✅ {producto.nombre}: sobró {cantidad_sobrante}. Queda en stock.")
        else:
            stock.cantidad = "0"
            messages.warning(request, f"⚠️ {producto.nombre}: comida sobrante se descartó.")

        stock.save()

        ConsumoSalon.objects.create(
            salon=salon,
            producto=producto,
            cantidad=cantidad_sobrante,
            comentario=comentario
        )

        return redirect('ver_stock')
    
    return redirect('ver_stock')

# ─────────────────────────────────────────────
# VER STOCK - ACTUALIZADO
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def ver_stock(request):
    if request.user.perfil.rol == 'salon':
        # Mostrar SOLO productos marcados como reutilizables
        stock = StockSalon.objects.filter(
            salon=request.user.perfil.salon,
            producto__se_puede_reusar=True
        ).select_related('producto')

        template = 'consumir.html'

    elif request.user.perfil.rol in ('admin', 'departamento'):
        stock = StockSalon.objects.all().select_related(
            'salon',
            'producto'
        )
        template = 'stock/lista.html'

    else:
        return redirect('central')

    return render(request, template, {
        'stock': stock,
    })

# ─────────────────────────────────────────────
# REPORTE DE CONSUMO
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def reporte_consumo(request):
    consumos = ConsumoSalon.objects.all().order_by('-fecha')
    
    # Filtros por fecha
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if fecha_desde:
        consumos = consumos.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        consumos = consumos.filter(fecha__date__lte=fecha_hasta)
    
    return render(request, 'envios/reporte.html', {
        'consumos': consumos,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    })



def parse_cantidad(cantidad_str):
    """Parsea una cantidad como '200g', '5 unidades', '3kg' y devuelve (valor, unidad)"""
    import re
    cantidad_str = str(cantidad_str).strip().lower()
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([a-záéíóúñ]+)?', cantidad_str)
    if match:
        valor = float(match.group(1))
        unidad = match.group(2) if match.group(2) else 'unidades'
        return valor, unidad
    return 0, ''


def sumar_cantidades(cantidad1, cantidad2):
    """Suma dos cantidades en texto (ej: '200g' + '300g' = '500g')"""
    val1, uni1 = parse_cantidad(cantidad1)
    val2, uni2 = parse_cantidad(cantidad2)
    
    if uni1 != uni2:
        # Si las unidades son diferentes, concatenar
        return f"{cantidad1} + {cantidad2}"
    
    resultado = val1 + val2
    if resultado.is_integer():
        resultado = int(resultado)
    return f"{resultado}{uni1}"


def restar_cantidades(cantidad_total, cantidad_restar):
    """Resta dos cantidades en texto (ej: '500g' - '200g' = '300g')"""
    val_total, uni_total = parse_cantidad(cantidad_total)
    val_restar, uni_restar = parse_cantidad(cantidad_restar)
    
    if uni_total != uni_restar and uni_restar != '':
        return cantidad_total  # No se puede restar, devolver el total original
    
    resultado = val_total - val_restar
    if resultado <= 0:
        return "0"
    
    if resultado.is_integer():
        resultado = int(resultado)
    return f"{resultado}{uni_total}"

def extraer_numero(texto):
    import re
    texto = str(texto).strip()
    match = re.search(r'(\d+(?:[.,]\d+)?)', texto)
    if match:
        return float(match.group(1).replace(',', '.'))
    return 0

def extraer_unidad(texto):
    import re
    texto = str(texto).strip().lower()
    match = re.search(r'\d+(?:[.,]\d+)?\s*([a-záéíóúñ]+)', texto)
    if match:
        return match.group(1)
    return 'unidades'
