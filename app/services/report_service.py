"""Reportería académica. Cálculos explícitos, sin inferir pagos ni costos históricos."""
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from app.repositories.report_repository import ReportRepository

LIMA = ZoneInfo('America/Lima')
GROUPS = {
 'usuarios': ('Usuarios', ['Usuarios registrados','Usuarios activos e inactivos','Usuarios por rol o perfil','Accesos al sistema','Actividades realizadas por usuario','Usuarios por área/departamento','Intentos de acceso y bloqueos','Cambios realizados por usuario']),
 'clientes': ('Clientes', ['Clientes registrados','Clientes activos e inactivos','Clientes por ubicación','Clientes nuevos por período','Clientes frecuentes','Clientes con mayor volumen de compras','Historial de compras por cliente','Clientes con pagos pendientes','Clientes por segmento o categoría','Evolución de clientes']),
 'proveedores': ('Proveedores', ['Proveedores registrados','Proveedores activos e inactivos','Proveedores por categoría','Proveedores por ubicación','Compras por proveedor','Proveedores con mayor volumen de suministro','Productos adquiridos por proveedor','Cuentas pendientes con proveedores','Cumplimiento de entregas','Evaluación de proveedores']),
 'productos': ('Productos / servicios', ['Productos registrados','Productos por categoría','Productos con mayor demanda','Productos con menor demanda','Stock disponible','Productos con stock mínimo','Productos agotados','Entradas y salidas de mercadería','Movimientos de inventario','Precios de productos/servicios','Productos dados de baja','Valorización del inventario']),
 'ventas': ('Ventas', ['Ventas por período','Ventas por día, semana, mes y año','Ventas por usuario/vendedor','Ventas por cliente','Ventas por producto/servicio','Ventas por categoría','Productos más vendidos','Productos menos vendidos','Ventas por forma de pago','Ventas anuladas/canceladas','Ventas pendientes de pago','Ingresos por período','Ticket promedio','Rentabilidad por producto/servicio','Evolución de ventas']),
}
REPORTS = {f'{g}-{i}': (g, name) for g, (_, names) in GROUPS.items() for i, name in enumerate(names,1)}
# Reportes de fotografía actual; no se filtran por fecha de creación.
SNAPSHOTS = {'usuarios-2','usuarios-3','usuarios-6','clientes-2','clientes-3','clientes-8','clientes-9','proveedores-2','proveedores-3','proveedores-4','proveedores-8','productos-2','productos-5','productos-6','productos-7','productos-10','productos-11','productos-12','ventas-11'}

def D(v): return Decimal(str(v if v is not None else 0))
def day(v):
    if not v: return None
    s = str(v)
    if len(s)==10: return date.fromisoformat(s)
    dt = datetime.fromisoformat(s.replace('Z','+00:00'))
    return (dt if dt.tzinfo else dt.replace(tzinfo=ZoneInfo('UTC'))).astimezone(LIMA).date()
def period(v, grain='mes'):
    d=day(v)
    if not d: return 'Sin fecha'
    if grain=='dia': return d.isoformat()
    if grain=='semana': return (d-timedelta(days=d.weekday())).isoformat()
    if grain=='anio': return str(d.year)
    return d.strftime('%Y-%m')
def clean(v):
    if isinstance(v, Decimal): return float(v)
    if v is None: return 'Sin dato'
    return v

def label(v): return v or 'Sin clasificar'
def state(r): return 'Activo' if r.get('active') else 'Inactivo'
def grouped(rows, key, val=lambda r:1):
    totals=defaultdict(Decimal)
    for r in rows: totals[key(r)] += D(val(r))
    return totals

def ordered(totals, ascending=False): return sorted(totals.items(), key=lambda x:(x[1] if ascending else -x[1], str(x[0])))

@dataclass
class Report:
    title: str
    columns: list
    rows: list
    chart: dict
    note: str
    snapshot: bool

class ReportService:
    def __init__(self, repo=None): self.repo=repo or ReportRepository()

    def generate(self, code, start=None, end=None, grain='mes'):
        if code not in REPORTS: raise ValueError('Reporte no reconocido.')
        if grain not in ('dia','semana','mes','anio'): raise ValueError('Agrupación no válida.')
        if start and end and start>end: raise ValueError('El inicio debe preceder al fin.')
        if end and end>=date(9999,12,31): raise ValueError('Fecha final fuera de rango.')
        cache={}
        snapshot=code in SNAPSHOTS
        def get(t, filtered=False):
            k=(t,filtered and not snapshot)
            if k not in cache:
                cache[k]=self.repo.rows(t,start if k[1] else None,end if k[1] else None)
            return cache[k]
        def index(t): return {r['id']:r for r in get(t)}
        def within(v):
            d=day(v); return bool(d and (not start or d>=start) and (not end or d<=end))
        def user_name(k):
            u=indexed_users().get(k)
            return f"{u['full_name']} · {u['email']}" if u else ('Sin usuario identificado' if not k else f'Usuario histórico · {str(k)[:8]}')
        def indexed_users():
            if 'u_idx' not in cache: cache['u_idx']=index('users')
            return cache['u_idx']
        def name(t,k):
            if (t,'idx') not in cache: cache[t,'idx']=index(t)
            return (cache[t,'idx'].get(k) or {}).get('name') or 'Sin referencia'
        def entity_name(t,k):
            n=name(t,k)
            return f'{n} · {str(k)[:8]}' if k else n
        def make(cols, rows, chart=None, note='', kind='bar', metric='Cantidad'):
            rows=[list(map(clean,r)) for r in rows]
            if chart is None: chart=Counter(str(r[0]) for r in rows)
            items=list(chart.items()) if hasattr(chart,'items') else list(chart)
            if kind!='line' and len(items)>15:
                items=items[:15] if isinstance(chart,list) else sorted(items,key=lambda x:abs(x[1]),reverse=True)[:15]
            chart={'type':kind,'labels':[str(k) for k,v in items], 'values':[float(v) for k,v in items], 'metric':metric}
            extra=' Fotografía actual; las fechas no se aplican.' if snapshot else ' Período aplicado a la fecha indicada en el reporte; si está vacío, se usa todo el historial disponible.'
            return Report(REPORTS[code][1],cols,rows,chart,note+extra,snapshot)
        def agg(keyname, totals, metric='Cantidad', note='', kind='bar', ascending=False, sort_time=False):
            items=sorted(totals.items()) if sort_time else ordered(totals,ascending)
            return make([keyname,metric],items,items,note,kind,metric)
        def access_label(r): return f"{r.get('user_name') or user_name(r['user_id'])} · {str(r['user_id'])[:8]}" if r.get('user_id') else 'Sin usuario identificado'
        def actor_label(r): return f"{r.get('actor_name') or user_name(r['actor_id'])} · {str(r['actor_id'])[:8]}" if r.get('actor_id') else 'Sin actor registrado (sistema/SQL)'
        def user_rows(rs): return [(r['full_name'],r['email'],r['role'],state(r),r.get('department'),r.get('location'),r.get('segment'),str(day(r['created_at']))) for r in rs]
        def cumulative(rs):
            totals=grouped(rs,lambda r:period(r['created_at'],grain)); running=Decimal(0); result={}
            for k,v in sorted(totals.items()): running+=v; result[k]=running
            return result
        group,n=code.split('-'); n=int(n)
        if group in ('usuarios','clientes'):
            is_client=group=='clientes'
            rs=[r for r in get('users', n in (1,4,10) and not snapshot) if not is_client or r['role']=='CLIENT'] if (group=='usuarios' and n in (1,2,3,6)) or (is_client and n in (1,2,3,4,9,10)) else []
            if n==1: return make(['Nombre','Correo','Rol','Estado','Área','Ubicación','Segmento','Registro'],user_rows(rs),grouped(rs,state),'Fecha de registro; estado actual.')
            if n==2: return agg('Estado',grouped(rs,state),note='Estado de habilitación de cuenta, no actividad reciente.',kind='pie')
            if group=='usuarios':
                if n==3:return agg('Rol',grouped(rs,lambda r:r['role']),kind='pie')
                if n==6:return agg('Área',grouped(rs,lambda r:label(r.get('department'))))
                if n in (4,7):
                    logs=get('access_events',True)
                    allowed={'EXITOSO','SALIDA','REGISTRO'} if n==4 else {'FALLIDO','BLOQUEO','BLOQUEADO','INACTIVO'}
                    logs=[r for r in logs if r['outcome'] in allowed]
                    return make(['Fecha y hora (UTC)','Usuario','Evento'],[(r['created_at'],access_label(r),r['outcome']) for r in reversed(logs)],grouped(logs,lambda r:r['outcome']), 'Bitácora desde la instalación. BLOQUEO es un evento adicional al tercer intento fallido; no sumar ambos como intentos.')
                logs=get('audit_events',True)
                if n==5:return agg('Usuario',grouped(logs,actor_label),metric='Operaciones de datos',note='Inserciones, actualizaciones y eliminaciones reales; una acción puede afectar varias filas. No incluye navegación.')
                return make(['Fecha y hora (UTC)','Actor','Entidad','Identificador','Acción','Campos modificados'],[(r['created_at'],actor_label(r),r['entity'],r.get('entity_id'),r['action'],r.get('changed_fields')) for r in reversed(logs)],grouped(logs,lambda r:r['action']),'Bitácora de cambios, no almacena valores sensibles ni contraseñas.')
            if n==3:return agg('Ubicación',grouped(rs,lambda r:label(r.get('location'))))
            if n==9:return agg('Segmento',grouped(rs,lambda r:label(r.get('segment'))))
            if n==4:return agg('Período',grouped(rs,lambda r:period(r['created_at'],grain)),kind='line',sort_time=True)
            if n==10:return agg('Período',cumulative(rs),metric='Altas acumuladas',note='Acumulado de cuentas CLIENT que aún existen, dentro del período seleccionado; no equivale a base activa histórica.',kind='line',sort_time=True)
        # Datos comerciales bajo demanda, se preserva el ID para no duplicar ventas por línea.
        def commerce():
            if 'commerce' in cache:return cache['commerce']
            sr=index('sales_requests'); refs=index('sales_request_details'); inv=index('inventory_items'); services=index('service_types')
            ss=get('sales'); docs={r['sale_id']:r for r in get('sale_documents')}; sales={r['id']:{**r,'client_id':(sr.get(r['request_id']) or {}).get('user_id'),'doc':docs.get(r['id']), 'total':Decimal(0)} for r in ss}
            details=[]
            for l in get('sale_details'):
                s=sales.get(l['sale_id']); ref=refs.get(l.get('source_request_detail_id')) or {}; kind=ref.get('item_kind')
                item=ref.get('inventory_item_id') if kind=='PRODUCTO' else ref.get('service_type_id'); cat=(inv.get(item) or {}).get('item_type') if kind=='PRODUCTO' else ('SERVICIO' if kind=='SERVICIO' else 'Sin clasificar')
                if not s:continue
                s['total']+=D(l['line_total']); details.append({**l,'sale':s,'kind':kind,'item_id':item,'category':cat or 'Sin clasificar','item_key':f"{((inv if kind=='PRODUCTO' else services).get(item) or {}).get('name') or l['description']} · {str(item)[:8]}" if item else l['description']})
            cache['commerce']=(sales,details,inv,services); return cache['commerce']
        def valid(s): return s['status']=='CONFIRMADA' and (s.get('doc') or {}).get('status')!='ANULADO'
        def selected(s):return valid(s) and (snapshot or within(s['created_at']))
        def balances():
            sales,_,_,_=commerce(); paid=grouped(get('sale_payments'),lambda p:p['sale_id'],lambda p:p['amount']); out=[]
            for s in sales.values():
                if not valid(s):continue
                p=paid[s['id']]; known=s.get('payment_tracking',False)
                if known and s['total']<=p:continue
                out.append((s,p,s['total']-p if known else None))
            return out
        if group=='clientes':
            sales,_,_,_=commerce(); ss=[s for s in sales.values() if selected(s)]
            if n==5:return agg('Cliente',grouped(ss,lambda s:user_name(s['client_id'])),metric='Ventas confirmadas',note='Frecuencia = número de ventas confirmadas no anuladas.')
            if n==6:return agg('Cliente',grouped(ss,lambda s:user_name(s['client_id']),lambda s:s['total']),metric='Importe S/ sin IGV')
            if n==7:return make(['Cliente','Venta','Fecha','Importe S/ sin IGV'],[(user_name(s['client_id']),s['sale_number'],str(day(s['created_at'])),s['total']) for s in ss],grouped(ss,lambda s:user_name(s['client_id']),lambda s:s['total']),'Ventas confirmadas no anuladas; fecha de venta.',metric='S/ sin IGV')
            if n==8:
                bal=balances(); totals=defaultdict(Decimal); unknown=Counter()
                for s,p,b in bal:
                    key=user_name(s['client_id'])
                    if b is None:unknown[key]+=1
                    else:totals[key]+=b
                return make(['Cliente','Saldo conocido S/ sin IGV','Ventas sin seguimiento histórico'],[(k,totals[k],unknown[k]) for k in sorted(set(totals)|set(unknown))],totals,'Solo saldo confirmado desde el inicio de seguimiento; ventas antiguas no se presumen impagas.',metric='Saldo S/')
        if group=='proveedores':
            if n<=4:
                rs=get('suppliers',n==1)
                if n==1:return make(['Proveedor','RUC','Estado','Categoría','Ubicación','Registro'],[(r['name'],r.get('tax_id'),state(r),r.get('category'),r.get('location'),str(day(r['created_at']))) for r in rs],grouped(rs,state),'Fecha de registro; estado actual.')
                if n==2:return agg('Estado',grouped(rs,state),kind='pie')
                field='category' if n==3 else 'location'; return agg('Categoría' if n==3 else 'Ubicación',grouped(rs,lambda r:label(r.get(field))))
            if n==10:
                ev=get('supplier_evaluations',True); g=defaultdict(list)
                for r in ev:g[entity_name('suppliers',r['supplier_id'])].append(r['score'])
                return make(['Proveedor','Evaluaciones','Promedio (1–5)'],[(k,len(v),round(sum(v)/len(v),2)) for k,v in sorted(g.items())],{k:sum(v)/len(v) for k,v in g.items()},'Calificaciones registradas manualmente; no representa una auditoría de calidad.',metric='Puntaje / 5')
            ps=get('supplier_purchases',n==5 or n==9); sup=lambda p:entity_name('suppliers',p['supplier_id'])
            if n==5:return make(['Proveedor','Artículo','Fecha pedido','Cantidad','Costo S/','Importe S/','Recepción'],[(sup(p),name('inventory_items',p['item_id']),p['ordered_on'],p['quantity'],D(p['unit_cost']),D(p['unit_cost'])*p['quantity'],str(day(p['received_at'])) if p['received_at'] else 'Pendiente') for p in ps],grouped(ps,sup,lambda p:D(p['unit_cost'])*p['quantity']),'Compras registradas (fecha de pedido), no pagos.',metric='S/')
            if n in (6,7):
                rec=[p for p in ps if within(p.get('received_at'))]
                if n==6:return agg('Proveedor',grouped(rec,sup,lambda p:p['quantity']),metric='Unidades recibidas',note='Fecha de recepción; solo compras recibidas.')
                return agg('Proveedor / artículo',grouped(rec,lambda p:f"{sup(p)} / {name('inventory_items',p['item_id'])}",lambda p:p['quantity']),metric='Unidades recibidas',note='Fecha de recepción. Odin Soft adquiere artículos, no contrata servicios de proveedores.')
            if n==8:
                paid=grouped(get('supplier_purchase_payments'),lambda p:p['purchase_id'],lambda p:p['amount']); rows=[]; totals=defaultdict(Decimal)
                for p in ps:
                    total=D(p['unit_cost'])*p['quantity']; balance=total-paid[p['id']]
                    if balance>0:rows.append((sup(p),str(p['id']),total,paid[p['id']],balance));totals[sup(p)]+=balance
                return make(['Proveedor','Compra','Importe S/','Pagado S/','Saldo S/'],rows,totals,'Compras registradas con saldo mayor a cero, incluidas las pendientes de recibir.',metric='Saldo S/')
            today=datetime.now(LIMA).date(); d=defaultdict(lambda:[0,0,0,0]);
            for p in ps:
                row=d[sup(p)]; received=day(p.get('received_at')); expected=day(p['expected_on']);
                if received:row[0 if received<=expected else 1]+=1
                else:row[2 if today>expected else 3]+=1
            return make(['Proveedor','A tiempo','Recibidas tarde','Pendientes vencidas','Pendientes en plazo','Cumplimiento % (recibidas)'],[(k,*v,round(100*v[0]/(v[0]+v[1]),2) if v[0]+v[1] else None) for k,v in sorted(d.items())],{k:100*v[0]/(v[0]+v[1]) for k,v in d.items() if v[0]+v[1]},'Fecha de pedido; cumplimiento = recibidas a tiempo / total recibidas. Pendientes se muestran aparte.',metric='%')
        if group=='productos':
            if n in (3,4,8,9):
                movements=get('inventory_movements',True)
                if n in (3,4):
                    rs=[r for r in movements if r['reason'] in ('CONSUMO ORDEN','REVERSIÓN ORDEN')]
                    items_by_id=index('inventory_items')
                    totals=grouped(rs,lambda r:f"{(items_by_id.get(r['item_id']) or {}).get('name') or r['item_name']} · {str(r['item_id'])[:8]}",lambda r:-r['quantity_delta'])
                    for r in get('inventory_items'):
                        if r['active']:totals.setdefault(f"{r['name']} · {str(r['id'])[:8]}",Decimal(0))
                    return agg('Artículo',totals,metric='Consumo neto (unidades)',ascending=n==4,note='Consumo técnico menos devoluciones del período; puede ser negativo si se revierte consumo anterior. Incluye activos sin movimientos.')
                if n==8:
                    by=defaultdict(lambda:[0,0]);
                    for r in movements:by[r['reason']][0 if r['quantity_delta']>0 else 1]+=abs(r['quantity_delta'])
                    rows=[(k,*v,v[0]-v[1]) for k,v in sorted(by.items())]; chart={f'{k} / {direction}':v[i] for k,v in by.items() for i,direction in enumerate(('Entrada','Salida')) if v[i]}
                    return make(['Motivo','Entradas','Salidas','Neto'],rows,chart,'Cambios de stock posteriores a la instalación. No se deduce histórico anterior.',metric='Unidades')
                return make(['Fecha y hora (UTC)','Artículo','Motivo','Variación','Stock posterior'],[(r['created_at'],r['item_name'],r['reason'],r['quantity_delta'],r['stock_after']) for r in reversed(movements)],grouped(movements,lambda r:r['reason'],lambda r:abs(r['quantity_delta'])),'Movimientos reales desde la instalación.',metric='Unidades movidas')
            rs=get('inventory_items',n==1)
            if n==2:return agg('Categoría',grouped(rs,lambda r:r['item_type']))
            if n==10:
                rows=[(r['name'],r['item_type'],r.get('sale_price'),r.get('unit_cost'),r['id']) for r in rs]+[(r['name'],'SERVICIO',r.get('sale_price'),r.get('estimated_unit_cost'),r['id']) for r in get('service_types')]
                return make(['Concepto','Tipo','Precio de venta S/','Costo S/'],[r[:4] for r in rows],{f'{r[0]} · {str(r[4])[:8]}':D(r[2]) for r in rows if r[2] is not None},'Precios actuales; costo de servicios estimado si fue configurado.',metric='Precio S/')
            if n==12:return make(['Artículo','Categoría','Stock','Costo unitario S/','Valor S/'],[(r['name'],r['item_type'],r['stock_quantity'],D(r['unit_cost']),r['stock_quantity']*D(r['unit_cost'])) for r in rs],grouped(rs,lambda r:r['item_type'],lambda r:r['stock_quantity']*D(r['unit_cost'])),'Stock actual × costo de catálogo; valoración referencial, no kardex contable.',metric='S/')
            if n==6:rs=[r for r in rs if r['active'] and r['stock_quantity']<=r['min_stock']]
            if n==7:rs=[r for r in rs if r['active'] and r['stock_quantity']==0]
            if n==11:rs=[r for r in rs if not r['active']]
            if n==5:rs=[r for r in rs if r['active']]
            return make(['SKU','Artículo','Categoría','Estado','Stock','Stock mínimo','Proveedor'],[(r.get('sku'),r['name'],r['item_type'],state(r),r['stock_quantity'],r['min_stock'],name('suppliers',r.get('supplier_id'))) for r in rs],grouped(rs,lambda r:r['item_type'],(lambda r:r['stock_quantity']) if n==5 else (lambda r:1)),'Stock y estado actuales. Stock mínimo incluye agotados.' if n==6 else 'Inventario actual; registros filtrados por alta solo en el reporte de registrados.',metric='Unidades' if n==5 else 'Artículos')
        if group=='ventas':
            sales,details,inv,svc=commerce(); ss=[s for s in sales.values() if selected(s)]; lines=[l for l in details if selected(l['sale'])]
            base_note='Ventas confirmadas no anuladas, fecha de creación de venta; importes sin IGV.'
            if n==1:return make(['Venta','Fecha','Cliente','Subtotal S/'],[(s['sale_number'],str(day(s['created_at'])),user_name(s['client_id']),s['total']) for s in ss],grouped(ss,lambda s:period(s['created_at'],grain),lambda s:s['total']),base_note,metric='S/')
            if n in (2,15):return agg('Período',grouped(ss,lambda s:period(s['created_at'],grain),lambda s:s['total']),metric='Ventas S/ sin IGV',note=base_note+' Semana = lunes de inicio.',kind='line',sort_time=True)
            if n==3:return agg('Vendedor',grouped(ss,lambda s: f"{s.get('seller_name') or user_name(s.get('seller_id'))} · {str(s['seller_id'])[:8]}" if s.get('seller_id') else s.get('seller_name') or 'Sin vendedor histórico',lambda s:s['total']),metric='Ventas S/',note=base_note+' Vendedor registrado al generar la venta; no se atribuyen ventas anteriores.')
            if n==4:return agg('Cliente',grouped(ss,lambda s:user_name(s['client_id']),lambda s:s['total']),metric='Ventas S/',note=base_note)
            if n==5:return agg('Concepto',grouped(lines,lambda l:l['item_key'],lambda l:l['line_total']),metric='Ventas S/',note=base_note)
            if n==6:return agg('Categoría',grouped(lines,lambda l:l['category'],lambda l:l['line_total']),metric='Ventas S/',note=base_note+' Clasificación de artículos del catálogo actual.')
            if n in (7,8):
                totals=grouped([l for l in lines if l['kind']=='PRODUCTO'],lambda l:l['item_key'],lambda l:l['quantity'])
                if n==8:
                    sold_ids={l['item_id'] for l in lines if l['kind']=='PRODUCTO'}
                    for k,r in inv.items():
                        if r['active'] and r['item_type']!='INSUMO' and k not in sold_ids:totals.setdefault(f"{r['name']} · {str(k)[:8]}",Decimal(0))
                return agg('Producto / repuesto',totals,metric='Unidades vendidas',note=base_note+' Menos vendidos incluye productos/repuestos activos sin venta.',ascending=n==8)
            if n in (9,12):
                pp=[p for p in get('sale_payments',True) if p['sale_id'] in sales and valid(sales[p['sale_id']])]
                if n==9:
                    amounts=grouped(pp,lambda p:p['method'],lambda p:p['amount']); counts=defaultdict(set)
                    for p in pp: counts[p['method']].add(p['sale_id'])
                    return make(['Forma de pago','Ventas distintas','Cobros S/ sin IGV'],[(k,len(counts[k]),v) for k,v in ordered(amounts)],amounts,'Fecha de pago, no fecha de venta. Una venta con pago mixto aparece en cada medio utilizado; los importes no se duplican. No se inventa la forma de pago histórica.',metric='Cobros S/ sin IGV')
                return agg('Período',grouped(pp,lambda p:period(p['created_at'],grain),lambda p:p['amount']),metric='Ingresos cobrados S/ sin IGV',note='Cobros efectivamente registrados, fecha de pago, sin impuestos simulados.',kind='line',sort_time=True)
            if n==10:
                cancelled=[s for s in sales.values() if within(s['created_at']) and (s['status']=='CANCELADA' or (s.get('doc') or {}).get('status')=='ANULADO')]; status=lambda s:'Venta cancelada' if s['status']=='CANCELADA' else 'Comprobante anulado'
                return make(['Venta','Fecha de venta','Cliente','Situación','Importe S/'],[(s['sale_number'],str(day(s['created_at'])),user_name(s['client_id']),status(s),s['total']) for s in cancelled],grouped(cancelled,status),'Fecha de creación de venta, no fecha de anulación; cada venta aparece una sola vez.')
            if n==11:
                bal=balances(); return make(['Venta','Cliente','Subtotal S/','Cobrado registrado S/','Saldo conocido S/','Seguimiento'],[(s['sale_number'],user_name(s['client_id']),s['total'],p,b,'Activo' if b is not None else 'Sin histórico') for s,p,b in bal],{str(s['sale_number']):b for s,p,b in bal if b is not None},'Importes sin IGV. Ventas sin seguimiento histórico no se presentan como deudas confirmadas.',metric='Saldo S/')
            if n==13:
                buckets=defaultdict(list)
                for s in ss:buckets[period(s['created_at'],grain)].append(s['total'])
                rows=[(k,len(v),sum(v),round(sum(v)/len(v),2)) for k,v in sorted(buckets.items())]
                return make(['Período','Ventas','Importe S/','Ticket promedio S/'],rows,{r[0]:r[3] for r in rows},base_note+' Ticket = subtotal / número de ventas.',kind='line',metric='S/')
            if n==14:
                buckets=defaultdict(lambda:[Decimal(0),Decimal(0),Decimal(0),0,0]);
                for l in lines:
                    b=buckets[l['item_key']]; b[0]+=D(l['line_total']);
                    if l.get('report_unit_cost') is None:b[4]+=1;continue
                    b[1]+=D(l['line_total']);b[2]+=D(l['report_unit_cost'])*D(l['quantity']);b[3]+=1
                rows=[(k,v[0],v[1],v[2],v[1]-v[2] if v[3] else None,round(100*(v[1]-v[2])/v[1],2) if v[1] else None,v[4]) for k,v in sorted(buckets.items())]
                return make(['Concepto','Venta total S/','Venta con costo S/','Costo conocido S/','Margen bruto conocido S/','Margen %','Líneas sin costo'],rows,{r[0]:r[4] for r in rows if r[4] is not None},base_note+' Margen bruto referencial, no utilidad neta; excluye líneas sin costo histórico. Costos de servicio estimados deben incluir insumos internos.',metric='Margen S/')
        raise ValueError('Reporte no implementado.')
