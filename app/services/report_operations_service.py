"""Operaciones mínimas para alimentar la reportería sin crear un ERP paralelo."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID
from zoneinfo import ZoneInfo
from app.repositories.report_repository import ReportRepository
from app.services.sale_service import SaleService

METHODS = ('EFECTIVO','TARJETA','TRANSFERENCIA','BILLETERA','OTRO')

def uid(value):
    try: return str(UUID(str(value)))
    except (ValueError, TypeError): raise ValueError('Selecciona un registro válido.') from None

def money(value, maximum=Decimal('9999999999.99')):
    try: n=Decimal(str(value))
    except InvalidOperation: raise ValueError('Importe inválido.') from None
    if not n.is_finite() or n<=0 or n>maximum or n.as_tuple().exponent < -2:
        raise ValueError('Importe positivo, máximo dos decimales y dentro del rango permitido.')
    return str(n)

class ReportOperationsService:
    def __init__(self, repo=None, sales=None):
        self.repo=repo or ReportRepository(); self.sales=sales or SaleService()

    def purchasing(self):
        suppliers=self.repo.rows('suppliers'); items=self.repo.rows('inventory_items')
        purchases=self.repo.rows('supplier_purchases'); payments=self.repo.rows('supplier_purchase_payments')
        sp={r['id']:r['name'] for r in suppliers}; it={r['id']:r['name'] for r in items}; paid={}
        for p in payments:paid[p['purchase_id']]=paid.get(p['purchase_id'],Decimal(0))+Decimal(str(p['amount']))
        for p in purchases:
            p['supplier']=sp.get(p['supplier_id'],'Sin referencia'); p['item']=it.get(p['item_id'],'Sin referencia')
            p['total']=Decimal(str(p['unit_cost']))*p['quantity']; p['paid']=paid.get(p['id'],Decimal(0)); p['balance']=p['total']-p['paid']
        purchases.sort(key=lambda r:(r['created_at'],r['id']),reverse=True)
        return {'suppliers':[r for r in suppliers if r['active']], 'items':[r for r in items if r['active']], 'purchases':purchases}

    def create_purchase(self, form):
        try:
            qty=int(form.get('quantity','')); ordered=date.fromisoformat(form.get('ordered_on','')); expected=date.fromisoformat(form.get('expected_on',''))
        except (ValueError,TypeError): raise ValueError('Cantidad o fechas inválidas.') from None
        if not 1<=qty<=1000000 or expected<ordered or ordered>datetime.now(ZoneInfo('America/Lima')).date():
            raise ValueError('Cantidad o fechas de compra fuera de rango.')
        return self.repo.operation('odin_purchase_create',{'p_supplier':uid(form.get('supplier_id')),'p_item':uid(form.get('item_id')),'p_qty':qty,'p_cost':money(form.get('unit_cost')),'p_ordered':ordered.isoformat(),'p_expected':expected.isoformat()})

    def receive(self, key): return self.repo.operation('odin_purchase_receive',{'p_id':uid(key)})
    def pay_purchase(self,key,amount): return self.repo.operation('odin_purchase_pay',{'p_id':uid(key),'p_amount':money(amount, Decimal('9999999999999999.99'))})
    def evaluate(self,form):
        try: score=int(form.get('score',''))
        except (ValueError,TypeError): raise ValueError('Puntaje inválido.') from None
        notes=(form.get('notes') or '').strip()
        supplier=uid(form.get('supplier_id'))
        if not 1<=score<=5 or len(notes)>500:raise ValueError('Puntaje entre 1 y 5; observaciones hasta 500 caracteres.')
        if not any(str(s['id'])==supplier and s['active'] for s in self.repo.rows('suppliers')): raise ValueError('Proveedor no disponible.')
        return self.repo.evaluation({'supplier_id':supplier,'score':score,'notes':notes or None})
    def sale_context(self,key):
        sale=self.sales.get(uid(key))
        if not sale: raise ValueError('Venta no encontrada.')
        rows=[p for p in self.repo.rows('sale_payments') if p['sale_id']==sale['id']]
        total=sum((Decimal(str(r['line_total'])) for r in sale['details']),Decimal(0)); paid=sum((Decimal(str(p['amount'])) for p in rows),Decimal(0))
        return {'sale':sale,'payments':sorted(rows,key=lambda r:r['created_at'],reverse=True),'total':total,'paid':paid,'balance':total-paid,'methods':METHODS}
    def pay_sale(self,key,form):
        method=form.get('method')
        if method not in METHODS:raise ValueError('Selecciona una forma de pago válida.')
        return self.repo.operation('odin_sale_pay',{'p_id':uid(key),'p_amount':money(form.get('amount'),Decimal('999999999999.99')),'p_method':method,'p_reviewed':form.get('reviewed')=='1'})
