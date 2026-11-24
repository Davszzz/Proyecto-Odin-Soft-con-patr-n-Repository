"""Pruebas sin Supabase: datos sintéticos, fórmulas, 55 reportes y XLSX."""
import unittest
import sys
import types
import copy
import json
import zipfile
from pathlib import Path
from datetime import date
from decimal import Decimal
from uuid import UUID
from jinja2 import Environment, FileSystemLoader

# Aislar el paquete para no inicializar Flask/Supabase ni leer .env en pruebas unitarias.
ROOT=Path(__file__).resolve().parents[1]
if 'app' not in sys.modules:
    module=types.ModuleType('app'); module.__path__=[str(ROOT/'app')]; sys.modules['app']=module
from app.services.report_service import ReportService, REPORTS, GROUPS, SNAPSHOTS, period
from app.repositories.report_repository import SOURCES, ReportRepository
from app.utils.report_xlsx import export_report

T='2026-11-02T03:00:00+00:00' # En Lima aún es 1 de noviembre.
U='11111111-1111-4111-8111-111111111111'; A='22222222-2222-4222-8222-222222222222'; P='33333333-3333-4333-8333-333333333333'; I='44444444-4444-4444-8444-444444444444'; J='55555555-5555-4555-8555-555555555555'; S='66666666-6666-4666-8666-666666666666'
FIX={k:[] for k in SOURCES}
FIX.update(users=[{'id':U,'full_name':'Cliente prueba','email':'cliente@example.invalid','role':'CLIENT','active':True,'department':None,'location':'Lima','segment':'Persona','created_at':T},{'id':A,'full_name':'Admin prueba','email':'admin@example.invalid','role':'ADMIN','active':False,'department':'Técnico','location':None,'segment':None,'created_at':T}],suppliers=[{'id':P,'name':'Proveedor prueba','tax_id':'111','active':True,'category':'Repuestos','location':'Lima','created_at':T}],inventory_items=[{'id':I,'name':'SSD','sku':'SSD-1','item_type':'REPUESTO','supplier_id':P,'stock_quantity':4,'min_stock':5,'unit_cost':60,'sale_price':100,'active':True,'created_at':T},{'id':J,'name':'Pasta','sku':'P-1','item_type':'INSUMO','supplier_id':P,'stock_quantity':0,'min_stock':1,'unit_cost':10,'sale_price':None,'active':True,'created_at':T}],service_types=[{'id':S,'name':'Reparación','active':True,'sale_price':80,'estimated_unit_cost':30}],sales_requests=[{'id':'req1','user_id':U,'service_order_id':'ord1'},{'id':'req2','user_id':U,'service_order_id':'ord2'},{'id':'req3','user_id':U,'service_order_id':'ord3'}],sales_request_details=[{'id':'reqd1','item_kind':'PRODUCTO','inventory_item_id':I,'service_type_id':None},{'id':'reqd2','item_kind':'SERVICIO','inventory_item_id':None,'service_type_id':S},{'id':'reqd3','item_kind':'SERVICIO','inventory_item_id':None,'service_type_id':S}],sales=[{'id':'sale1','sale_number':1,'request_id':'req1','status':'CONFIRMADA','seller_id':A,'seller_name':'Admin prueba','payment_tracking':True,'created_at':T},{'id':'sale2','sale_number':2,'request_id':'req2','status':'CONFIRMADA','seller_id':None,'seller_name':None,'payment_tracking':False,'created_at':T},{'id':'sale3','sale_number':3,'request_id':'req3','status':'CANCELADA','seller_id':A,'seller_name':'Admin prueba','payment_tracking':True,'created_at':T}],sale_details=[{'id':'d1','sale_id':'sale1','source_request_detail_id':'reqd1','description':'SSD histórico','quantity':2,'unit_price':100,'line_total':200,'report_unit_cost':60,'report_cost_basis':'orden'},{'id':'d2','sale_id':'sale1','source_request_detail_id':'reqd2','description':'Reparación','quantity':1,'unit_price':80,'line_total':80,'report_unit_cost':30,'report_cost_basis':'estimado'},{'id':'d3','sale_id':'sale2','source_request_detail_id':'reqd3','description':'Reparación','quantity':1,'unit_price':80,'line_total':80,'report_unit_cost':None,'report_cost_basis':None},{'id':'d4','sale_id':'sale3','source_request_detail_id':'reqd3','description':'Reparación','quantity':1,'unit_price':80,'line_total':80,'report_unit_cost':30,'report_cost_basis':'estimado'}],sale_documents=[{'id':'doc1','sale_id':'sale1','status':'EMITIDO','document_type':'BOLETA','issued_at':T}],sale_payments=[{'id':1,'sale_id':'sale1','amount':100,'method':'EFECTIVO','created_at':T},{'id':2,'sale_id':'sale1','amount':30,'method':'TRANSFERENCIA','created_at':T}],supplier_purchases=[{'id':'p1','supplier_id':P,'item_id':I,'quantity':5,'unit_cost':60,'ordered_on':'2026-10-31','expected_on':'2026-11-01','received_at':T,'created_at':T}],supplier_purchase_payments=[{'id':1,'purchase_id':'p1','amount':200,'created_at':T}],supplier_evaluations=[{'id':1,'supplier_id':P,'score':4,'notes':None,'created_at':T}],access_events=[{'id':1,'user_id':U,'user_name':'Cliente prueba','outcome':'EXITOSO','created_at':T},{'id':2,'user_id':U,'user_name':'Cliente prueba','outcome':'FALLIDO','created_at':T},{'id':3,'user_id':U,'user_name':'Cliente prueba','outcome':'BLOQUEO','created_at':T}],audit_events=[{'id':1,'actor_id':A,'actor_name':'Admin prueba','entity':'users','entity_id':U,'action':'UPDATE','changed_fields':'active','created_at':T}],inventory_movements=[{'id':1,'item_id':I,'item_name':'SSD','quantity_delta':5,'stock_after':5,'reason':'RECEPCIÓN COMPRA','created_at':T},{'id':2,'item_id':I,'item_name':'SSD','quantity_delta':-2,'stock_after':3,'reason':'CONSUMO ORDEN','created_at':T},{'id':3,'item_id':I,'item_name':'SSD','quantity_delta':1,'stock_after':4,'reason':'REVERSIÓN ORDEN','created_at':T}])

class FakeRepo:
    def __init__(self, data=FIX):self.data=data
    def rows(self,table,start=None,end=None):
        from app.services.report_service import day
        field=SOURCES[table][2]; data=copy.deepcopy(self.data[table])
        if not field:return data
        return [r for r in data if (not start or day(r[field])>=start) and (not end or day(r[field])<=end)]

class ReportsTests(unittest.TestCase):
    def setUp(self):self.service=ReportService(FakeRepo())
    def test_55_reports_nonempty_and_empty(self):
        self.assertEqual(len(REPORTS),55)
        empty=ReportService(FakeRepo({k:[] for k in SOURCES}))
        for code in REPORTS:
            with self.subTest(code=code):
                for svc in (self.service,empty):
                    r=svc.generate(code)
                    self.assertTrue(r.columns)
                    self.assertTrue(all(len(row)==len(r.columns) for row in r.rows))
                    self.assertEqual(len(r.chart['labels']),len(r.chart['values']))
                    json.dumps({'rows':r.rows,'chart':r.chart},allow_nan=False)
                    b=export_report(r)
                    with zipfile.ZipFile(b) as z:
                        self.assertIsNone(z.testzip());self.assertIn('xl/worksheets/sheet1.xml',z.namelist())
    def test_sale_total_not_duplicated_by_lines(self):
        r=self.service.generate('ventas-2');self.assertEqual(r.rows,[['2026-11',360.0]])
    def test_ticket_mean(self):
        r=self.service.generate('ventas-13');self.assertEqual(r.rows,[['2026-11',2,360.0,180.0]])
    def test_sales_pending_unknown_history(self):
        r=self.service.generate('ventas-11'); self.assertEqual(r.rows[0][4],150.0);self.assertEqual(r.rows[1][4],'Sin dato')
    def test_payments_and_revenue(self):
        self.assertEqual(self.service.generate('ventas-12').rows,[['2026-11',130.0]])
        self.assertEqual(sum(self.service.generate('ventas-9').chart['values']),130)
    def test_profit_missing_cost(self):
        r=self.service.generate('ventas-14'); repair=next(x for x in r.rows if 'Reparación' in x[0]); self.assertEqual(repair[1:], [160.0,80.0,30.0,50.0,62.5,1])
    def test_stock_valuation_and_exhaustion(self):
        self.assertEqual(sum(self.service.generate('productos-12').chart['values']),240)
        r=self.service.generate('productos-7'); self.assertEqual(len(r.rows),1);self.assertEqual(r.chart['values'],[1.0])
    def test_stock_net_and_supply(self):
        r=self.service.generate('productos-3');self.assertEqual(r.rows[0][1],1.0)
        self.assertEqual(self.service.generate('proveedores-6').chart['values'],[5.0])
    def test_supplier_pending_and_delivery(self):
        self.assertEqual(self.service.generate('proveedores-8').rows[0][-1],100.0)
        self.assertEqual(self.service.generate('proveedores-9').rows[0][-1],100.0)
    def test_lima_dates_and_snapshot(self):
        self.assertEqual(period(T,'dia'),'2026-11-01')
        self.assertEqual(self.service.generate('ventas-1',date(2026,11,2)).rows,[])
        self.assertTrue(self.service.generate('ventas-1',date(2026,11,1),date(2026,11,1)).rows)
        self.assertTrue(self.service.generate('productos-5',date(2030,1,1)).rows)
    def test_filter_errors(self):
        for args in [('no-existe',),('ventas-1',date(2026,11,2),date(2026,11,1)),('ventas-1',None,None,'otra')]:
            with self.assertRaises(ValueError):self.service.generate(*args)
    def test_xlsx_no_formula_injection(self):
        from app.services.report_service import Report
        r=Report('Prueba',['Texto'],[['=1+2']],{'labels':[],'values':[]},'nota',False)
        with zipfile.ZipFile(export_report(r)) as z:
            self.assertNotIn(b'<f>',z.read('xl/worksheets/sheet1.xml'))
            self.assertIn(b'=1+2',z.read('xl/sharedStrings.xml'))
    def test_jinja_render_all_reports(self):
        env=Environment(loader=FileSystemLoader(ROOT/'app/templates'),autoescape=True)
        env.filters.update(date_pe=str,datetime_pe=str,commercial_money=str)
        env.globals.update(url_for=lambda endpoint,**kw:'/test/'+endpoint,get_flashed_messages=lambda **kw:[])
        t=env.get_template('admin/reports.html')
        for code in REPORTS:
            html=t.render(groups=GROUPS,code=code,report=self.service.generate(code),snapshot_ids=sorted(SNAPSHOTS),section='reports',tracking=T,session={'user_name':'Demo'},request=types.SimpleNamespace(args={}))
            self.assertIn('Descargar Excel',html);self.assertIn('echarts@5.6.0',html);self.assertIn('reportPayload',html)
    def test_operations_validation_and_rpcs(self):
        from app.services.report_operations_service import ReportOperationsService, money
        class Operations(FakeRepo):
            def operation(self,name,params):return name,params
        svc=ReportOperationsService(Operations(),sales=object())
        name,params=svc.create_purchase({'supplier_id':P,'item_id':I,'quantity':'2','unit_cost':'10.25','ordered_on':'2026-10-31','expected_on':'2026-11-01'})
        self.assertEqual(name,'odin_purchase_create');self.assertEqual(params['p_qty'],2)
        for amount in ['NaN','Infinity','-1','0','1.234']:
            with self.assertRaises(ValueError):money(amount)
        with self.assertRaises(ValueError):svc.pay_sale(U,{'method':'INVALIDO','amount':'1'})
        self.assertEqual(svc.pay_sale(U,{'method':'EFECTIVO','amount':'1.50','reviewed':'1'})[1]['p_reviewed'],True)
    def test_keyset_pagination(self):
        class Query:
            def __init__(self,items):self.items=items;self.cursor=0;self.size=500
            def select(self,*args):return self
            def order(self,*args):return self
            def limit(self,size):self.size=size;return self
            def gt(self,key,cursor):self.cursor=cursor;return self
            def execute(self):return types.SimpleNamespace(data=[r for r in self.items if r['id']>self.cursor][:self.size])
        class DB:
            def table(self,*args):return Query([{'id':i} for i in range(1,1201)])
        repo=ReportRepository(DB());self.assertEqual(len(repo.rows('access_events')),1200)
        repo.LIMIT=1000
        with self.assertRaises(ValueError):repo.rows('access_events')
    def test_all_templates_compile(self):
        env=Environment(loader=FileSystemLoader(ROOT/'app/templates'))
        env.filters.update(date_pe=str,datetime_pe=str,commercial_money=str)
        for n in env.list_templates():env.get_template(n)

if __name__=='__main__':unittest.main()
