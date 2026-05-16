import json
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Envio, DetalleEnvio, Producto, Salon, StockSalon, ConsumoSalon, Departamento, TipoProducto


# ─────────────────────────────────────────────
# FUNCIONES AUXILIARES
# ─────────────────────────────────────────────

def extraer_numero(texto):
    """Extrae un número de un texto como '10 unidades' -> 10"""
    if not texto:
        return 0
    texto = str(texto).strip()
    match = re.search(r'(\d+(?:[.,]\d+)?)', texto)
    if match:
        return float(match.group(1).replace(',', '.'))
    return 0

def extraer_unidad(texto):
    """Extrae la unidad de un texto como '10 unidades' -> 'unidades'"""
    if not texto:
        return 'unidades'
    texto = str(texto).strip().lower()
    match = re.search(r'\d+(?:[.,]\d+)?\s*([a-záéíóúñ]+)', texto)
    if match:
        return match.group(1)
    return 'unidades'

def parse_cantidad(cantidad_str):
    """Parsea una cantidad como '200g', '5 unidades', '3kg' y devuelve (valor, unidad)"""
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
        return cantidad_total
    
    resultado = val_total - val_restar
    if resultado <= 0:
        return "0"
    
    if resultado.is_integer():
        resultado = int(resultado)
    return f"{resultado}{uni_total}"


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
        'roles': ['admin', 'departamento', 'empaquetado', 'salon'],
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
            if rol == 'departamento':
                app['badge'] = Envio.objects.filter(
                    estado='pendiente',
                    origen=user.perfil.departamento
                ).count()
            elif rol == 'empaquetado':
                app['badge'] = Envio.objects.filter(estado='pendiente').count()
            elif rol == 'admin':
                app['badge'] = Envio.objects.filter(estado='pendiente').count()
            elif rol == 'salon':
                app['badge'] = Envio.objects.filter(
                    destino=user.perfil.salon,
                    estado='enviado'
                ).count()

    return render(request, 'central.html', {'apps': apps})


# ─────────────────────────────────────────────
# API: stock de un salón
# ─────────────────────────────────────────────

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
            'nombre': p.nombre,
            'comportamiento_stock': p.comportamiento_stock,
            'stock_salon': stock.cantidad if stock else '0',
            'tipo_nombre': p.tipo.nombre if p.tipo else 'OTROS',
            'cantidad_gramos': p.cantidad_gramos or '',
        })
    
    return JsonResponse({'salon': salon.nombre, 'productos': data})


# ─────────────────────────────────────────────
# LISTA DE ENVÍOS
# ─────────────────────────────────────────────
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

@login_required(login_url='/envioscocina/login/')
def lista_envios(request):
    user = request.user
    rol = user.perfil.rol

    # 🔥 FILTRAR ENVÍOS SEGÚN ROL
    if rol == 'admin':
        envios = Envio.objects.all()
    elif rol == 'departamento':
        envios = Envio.objects.filter(origen=user.perfil.departamento)
    elif rol == 'empaquetado':
        # ✅ CORREGIDO: SOLO su propio departamento
        envios = Envio.objects.filter(
            origen=user.perfil.departamento,
            estado__in=['pendiente', 'preparado']
        )
    elif rol == 'salon':
        envios = Envio.objects.filter(
            destino=user.perfil.salon,
            estado__in=['enviado', 'entregado', 'aceptado', 'rechazado']
        )
    else:
        envios = Envio.objects.none()

    estado = request.GET.get('estado')
    
    # 🔥 VISTA POR DEFECTO SEGÚN ROL
    if rol == 'salon' and not estado:
        estado_activo = 'todos'
    elif rol == 'empaquetado' and not estado:
        envios = envios.filter(estado='pendiente')
        estado_activo = 'pendiente'
    elif rol == 'departamento' and not estado:
        estado_activo = 'todos'
    elif estado:
        envios = envios.filter(estado=estado)
        estado_activo = estado
    else:
        estado_activo = 'todos'

    envios = envios.order_by('-fecha_creacion')

    # ✅ PAGINACIÓN: 15 ENVÍOS POR PÁGINA
    paginator = Paginator(envios, 15)
    page = request.GET.get('page', 1)

    try:
        envios_page = paginator.page(page)
    except PageNotAnInteger:
        envios_page = paginator.page(1)
    except EmptyPage:
        envios_page = paginator.page(paginator.num_pages)

    # 🔥 FILTROS DISPONIBLES SEGÚN ROL
    if rol == 'empaquetado':
        estados = [
            ('', 'Todos'),
            ('pendiente', '⏳ Pendientes'),
            ('preparado', '📦 Preparados'),
        ]
    elif rol == 'salon':
        estados = [
            ('', '📋 Todos'),
            ('enviado', '🚚 Enviados'),
            ('entregado', '📬 Entregados'),
            ('aceptado', '✅ Aceptados'),
            ('rechazado', '❌ Rechazados'),
        ]
    else:
        estados = [
            ('', '📋 Todos'),
            ('pendiente', '⏳ Pendientes'),
            ('preparado', '📦 Preparados'),
            ('enviado', '🚚 Enviados'),
            ('entregado', '📬 Entregados'),
            ('aceptado', '✅ Aceptados'),
            ('rechazado', '❌ Rechazados'),
        ]

    puede_preparar = rol in ['empaquetado', 'admin']
    puede_enviar = rol in ['departamento', 'admin']
    puede_responder = rol == 'salon'

    return render(request, 'envios/lista.html', {
        'envios': envios_page,
        'estado_activo': estado_activo,
        'estados': estados,
        'puede_preparar': puede_preparar,
        'puede_enviar': puede_enviar,
        'puede_responder': puede_responder,
        'rol': rol,
        'pagina': envios_page,
    })
# ─────────────────────────────────────────────
# CREAR ENVÍO
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def crear_envio(request):
    if request.user.perfil.rol != 'departamento':
        messages.error(request, "Solo departamento puede crear envíos")
        return redirect('lista_envios')

    salones = Salon.objects.all()

    if request.method == 'POST':
        destino_id = request.POST.get('destino')
        descripcion = request.POST.get('descripcion', '').strip()
        fecha_evento = request.POST.get('fecha_evento')
        tipo_evento = request.POST.get('tipo_evento')
        plan_evento = request.POST.get('plan_evento')
        cantidad_invitados = request.POST.get('cantidad_invitados')

        if not destino_id:
            messages.error(request, "Debe seleccionar un salón destino")
            return redirect('crear_envio')

        salon = get_object_or_404(Salon, id=destino_id)

        envio = Envio.objects.create(
            origen=request.user.perfil.departamento,
            destino=salon,
            descripcion=descripcion,
            creado_por=request.user,
            estado='pendiente',
            tipo_evento=tipo_evento or '',
            plan_evento=plan_evento or '',
        )

        if fecha_evento:
            envio.fecha_evento = parse_datetime(fecha_evento)

        if cantidad_invitados:
            try:
                envio.cantidad_invitados = int(cantidad_invitados)
            except ValueError:
                envio.cantidad_invitados = None

        envio.save()

        productos = Producto.objects.filter(
            departamento=request.user.perfil.departamento
        )

        productos_agregados = False

        for producto in productos:
            usar_stock_str = request.POST.get(f'usar_stock_{producto.id}', '0')
            enviar_nuevos_str = request.POST.get(f'enviar_{producto.id}', '').strip()
            usar_stock_num = int(usar_stock_str) if usar_stock_str.isdigit() else 0

            if usar_stock_num == 0 and not enviar_nuevos_str:
                continue

            productos_agregados = True
            cantidad_usada = '0'

            if usar_stock_num > 0:
                stock, _ = StockSalon.objects.get_or_create(
                    salon=salon,
                    producto=producto,
                    defaults={'cantidad': '0'}
                )
                stock_actual_num = extraer_numero(stock.cantidad or '0')
                stock_unidad = extraer_unidad(stock.cantidad or '0 unidades')

                if stock_actual_num >= usar_stock_num:
                    nuevo_stock = stock_actual_num - usar_stock_num
                    stock.cantidad = f"{nuevo_stock} {stock_unidad}".strip()
                    stock.save()
                    cantidad_usada = f"{usar_stock_num} {stock_unidad}".strip()
                else:
                    messages.warning(request, f"⚠️ No hay suficiente stock de {producto.nombre}")

            DetalleEnvio.objects.create(
                envio=envio,
                producto=producto,
                cantidad=enviar_nuevos_str if enviar_nuevos_str else '',
                cantidad_usada_stock=cantidad_usada,
                check_incluido=True,
            )

        if not productos_agregados:
            envio.delete()
            messages.warning(request, "No se agregaron productos al envío.")
        else:
            messages.success(request, f"✅ Envío #{envio.id} creado (pendiente de preparación)")

        return redirect('lista_envios')

    return render(request, 'envios/crear.html', {'salones': salones})


# ─────────────────────────────────────────────
# PREPARAR ENVÍO (empaquetado)
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def preparar_envio(request, envio_id):
    envio = get_object_or_404(Envio, id=envio_id)
    
    if request.user.perfil.rol not in ['empaquetado', 'admin']:
        messages.error(request, "No tienes permiso para preparar envíos")
        return redirect('lista_envios')
    
    if envio.estado != 'pendiente':
        messages.error(request, "Solo se pueden preparar envíos en estado 'pendiente'")
        return redirect('lista_envios')
    
    envio.preparar()
    messages.success(request, f"✅ Envío #{envio.id} marcado como PREPARADO")
    return redirect('lista_envios')


# ─────────────────────────────────────────────
# DETALLE DE UN ENVÍO
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def detalle_envio(request, envio_id):
    envio = get_object_or_404(Envio, id=envio_id)
    user = request.user
    rol = user.perfil.rol
    
    # 🔥 VERIFICACIÓN DE PERMISOS (igual que en preparar_envio)
    if rol == 'admin':
        pass  # Admin puede ver todo
    
    elif rol == 'departamento':
        # Solo puede ver envíos de su propio departamento
        if envio.origen != user.perfil.departamento:
            messages.error(request, "No tienes permiso para ver este envío")
            return redirect('lista_envios')
    
    elif rol == 'empaquetado':
        # Solo puede ver envíos en estado pendiente o preparado
        if envio.estado not in ['pendiente', 'preparado']:
            messages.error(request, "Solo puedes ver envíos en estado 'pendiente' o 'preparado'")
            return redirect('lista_envios')
    
    elif rol == 'salon':
        # Solo puede ver envíos destinados a su salón
        if envio.destino != user.perfil.salon:
            messages.error(request, "No tienes permiso para ver este envío")
            return redirect('lista_envios')
    
    else:
        messages.error(request, "Rol no reconocido")
        return redirect('central')
    
    # Si pasa todas las validaciones, mostrar el detalle
    return render(request, 'envios/detalle.html', {'envio': envio})
# ─────────────────────────────────────────────
# ENVIAR (departamento)
# ─────────────────────────────────────────────
@login_required(login_url='/envioscocina/login/')
def enviar_envio(request, envio_id):
    envio = get_object_or_404(Envio, id=envio_id)

    if request.user.perfil.rol not in ['departamento', 'admin']:
        messages.error(request, "No permitido")
        return redirect('lista_envios')

    # Permitir enviar desde pendiente o preparado
    if envio.estado == 'preparado':
        envio.enviar()
        messages.success(request, f"✅ Envío #{envio.id} marcado como ENVIADO")
        
    elif envio.estado == 'pendiente':
        envio.enviar()
        messages.warning(request, f"⚠️ Envío #{envio.id} enviado SIN preparación previa de empaquetado.")
        
    else:
        messages.error(request, f"❌ No se puede enviar el envío en estado '{envio.get_estado_display()}'")
        return redirect('lista_envios')

    return redirect('lista_envios')

# ─────────────────────────────────────────────
# ACEPTAR (salón)
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def aceptar_envio(request, envio_id):
    envio = get_object_or_404(Envio, id=envio_id)

    if request.user.perfil.rol != 'salon':
        messages.error(request, "Solo el salón puede aceptar")
        return redirect('lista_envios')

    # ✅ CORREGIDO: ahora permite aceptar en estado 'entregado'
    if envio.estado != 'entregado':
        messages.error(request, "Solo se pueden aceptar envíos en estado 'entregado'")
        return redirect('lista_envios')

    for detalle in envio.detalles.all():
        if not detalle.check_incluido:
            continue

        comportamiento = detalle.producto.comportamiento_stock

        if comportamiento == 'stock':
            stock, created = StockSalon.objects.get_or_create(
                salon=envio.destino,
                producto=detalle.producto,
                defaults={'cantidad': '0'}
            )
            if created or stock.cantidad == '0':
                stock.cantidad = detalle.cantidad
            else:
                stock.cantidad = sumar_cantidades(stock.cantidad, detalle.cantidad)
            stock.save()

        elif comportamiento == 'devuelve':
            stock, created = StockSalon.objects.get_or_create(
                salon=envio.destino,
                producto=detalle.producto,
                defaults={'cantidad': '0'}
            )
            if created or stock.cantidad == '0':
                stock.cantidad = detalle.cantidad
            else:
                stock.cantidad = sumar_cantidades(stock.cantidad, detalle.cantidad)
            stock.save()

    envio.aceptar()

    observacion = request.POST.get('observacion', '')
    if observacion:
        envio.observacion = observacion
        envio.save()

    messages.success(request, f"✅ Envío #{envio.id} aceptado y stock actualizado")
    return redirect('lista_envios')


# ─────────────────────────────────────────────
# RECHAZAR (salón) - CORREGIDO para estado 'entregado'
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def rechazar_envio(request, envio_id):
    envio = get_object_or_404(Envio, id=envio_id)

    if request.user.perfil.rol != 'salon':
        messages.error(request, "Solo el salón puede rechazar")
        return redirect('lista_envios')

    # ✅ CORREGIDO: ahora permite rechazar en estado 'entregado'
    if envio.estado != 'entregado':
        messages.error(request, "Solo se pueden rechazar envíos en estado 'entregado'")
        return redirect('lista_envios')

    observacion = request.POST.get('observacion', '')
    if observacion:
        envio.observacion = observacion
        envio.save()

    envio.rechazar()
    messages.warning(request, f"❌ Envío #{envio.id} rechazado")
    return redirect('lista_envios')

# ─────────────────────────────────────────────
# CONSUMIR PRODUCTO
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

        if producto.comportamiento_stock == 'stock':
            stock.cantidad = cantidad_sobrante
            messages.success(request, f"✅ {producto.nombre}: sobró {cantidad_sobrante}. Queda en stock.")
        elif producto.comportamiento_stock == 'devuelve':
            stock.cantidad = cantidad_sobrante
            messages.success(request, f"🔄 {producto.nombre}: sobró {cantidad_sobrante}. Se espera devolución a cocina.")
        else:
            stock.cantidad = "0"
            messages.warning(request, f"⚠️ {producto.nombre}: sobrante se descartó.")

        stock.save()

        ConsumoSalon.objects.create(
            salon=salon,
            producto=producto,
            cantidad=cantidad_sobrante,
            comentario=comentario
        )

        return redirect('ver_stock')

    return redirect('ver_stock')


@login_required(login_url='/envioscocina/login/')
def ver_stock(request):
    if request.user.perfil.rol == 'salon':
        stock = StockSalon.objects.filter(
            salon=request.user.perfil.salon,
            producto__comportamiento_stock__in=['stock', 'devuelve']
        ).select_related('producto')
        template = 'consumir.html'
    elif request.user.perfil.rol in ('admin', 'departamento'):
        stock = StockSalon.objects.all().select_related('salon', 'producto')
        template = 'stock/lista.html'
    else:
        return redirect('central')

    return render(request, template, {'stock': stock})


# ─────────────────────────────────────────────
# REPORTE DE CONSUMO
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def reporte_consumo(request):
    consumos = ConsumoSalon.objects.all().order_by('-fecha_registro')
    
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if fecha_desde:
        consumos = consumos.filter(fecha_evento__date__gte=fecha_desde)
    if fecha_hasta:
        consumos = consumos.filter(fecha_evento__date__lte=fecha_hasta)
    
    return render(request, 'envios/reporte.html', {
        'consumos': consumos,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    })

# ─────────────────────────────────────────────
# ELIMINAR ENVÍO (departamento: pendiente, preparado, enviado)
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def eliminar_envio(request, envio_id):
    envio = get_object_or_404(Envio, id=envio_id)
    
    user_rol = request.user.perfil.rol
    
    # Admin puede eliminar cualquier envío
    if user_rol == 'admin':
        pass
    
    # Departamento puede eliminar sus envíos en: pendiente, preparado, enviado
    elif user_rol == 'departamento':
        # Verificar que sea su departamento
        if envio.origen != request.user.perfil.departamento:
            messages.error(request, "No puedes eliminar envíos de otro departamento")
            return redirect('lista_envios')
        
        # Solo puede eliminar en estos estados
        if envio.estado not in ['pendiente', 'preparado', 'enviado']:
            messages.error(request, f"No puedes eliminar envíos en estado '{envio.get_estado_display()}'. Solo pendiente, preparado o enviado.")
            return redirect('lista_envios')
    
    # Empaquetado solo puede eliminar en estado pendiente
    elif user_rol == 'empaquetado':
        if envio.estado != 'pendiente':
            messages.error(request, "Solo puedes eliminar envíos en estado 'pendiente'")
            return redirect('lista_envios')
    
    # Salón no puede eliminar
    else:
        messages.error(request, "No tienes permiso para eliminar envíos")
        return redirect('lista_envios')
    
    # Guardar ID para el mensaje
    envio_id_temp = envio.id
    
    # Eliminar el envío (los detalles se eliminan en cascada)
    envio.delete()
    
    messages.success(request, f"✅ Envío #{envio_id_temp} eliminado correctamente")
    return redirect('lista_envios')


# ─────────────────────────────────────────────
# ELIMINAR ENVÍO (versión específica para departamento)
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# ELIMINAR ENVÍO (solo departamento)
# ─────────────────────────────────────────────

@login_required(login_url='/envioscocina/login/')
def eliminar_envio(request, envio_id):
    envio = get_object_or_404(Envio, id=envio_id)
    
    # SOLO departamento puede eliminar
    if request.user.perfil.rol != 'departamento':
        messages.error(request, "No tienes permiso para eliminar envíos")
        return redirect('lista_envios')
    
    # Verificar que sea su departamento
    if envio.origen != request.user.perfil.departamento:
        messages.error(request, "No puedes eliminar envíos de otro departamento")
        return redirect('lista_envios')
    
    # Solo puede eliminar en estos estados
    if envio.estado not in ['pendiente', 'preparado', 'enviado']:
        messages.error(request, "Solo puedes eliminar envíos en estado 'pendiente', 'preparado' o 'enviado'")
        return redirect('lista_envios')
    
    # Eliminar
    envio_id_temp = envio.id
    envio.delete()
    
    messages.success(request, f"✅ Envío #{envio_id_temp} eliminado correctamente")
    return redirect('lista_envios')

from django.urls import reverse

@login_required(login_url='/envioscocina/login/')
def entregar_envio(request, envio_id):
    """Marca el envío como entregado físicamente en el salón"""
    envio = get_object_or_404(Envio, id=envio_id)
    
    if request.user.perfil.rol not in ['salon', 'admin']:
        messages.error(request, "Solo el salón puede confirmar la recepción física")
        return redirect('detalle_envio', envio_id=envio.id)
    
    if envio.estado != 'enviado':
        messages.error(request, "Solo se pueden entregar envíos en estado 'enviado'")
        return redirect('detalle_envio', envio_id=envio.id)
    
    envio.estado = 'entregado'
    envio.save()
    
    messages.success(request, f"✅ Envío #{envio.id} marcado como ENTREGADO")
    
    # 🔥 QUEDA EN EL MISMO DETALLE, NO SE VA A LISTA
    return redirect('detalle_envio', envio_id=envio.id)