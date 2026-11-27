"""Pantallas SB Admin, gráficos Apache ECharts y descarga XLSX por reporte."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from io import BytesIO
import hmac
import secrets
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, session, url_for
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.repositories.report_repository import ReportRepository
from app.services.report_service import GROUPS, REPORTS, SNAPSHOTS, ReportService
from app.services.report_operations_service import ReportOperationsService
from app.utils.report_xlsx import export_report
from app.utils.purchase_table import purchase_table

admin_report_bp = Blueprint('admin_report', __name__, url_prefix='/admin/reportes')

@admin_report_bp.before_request
def check_admin():
    if not session.get('user_id'):return redirect(url_for('auth.login'))
    user=UserRepository().find_by_id(session['user_id'])
    if not user or not user.get('active',True) or user.get('role')!='ADMIN':abort(403)
    if not session.get('admin_csrf_token'):session['admin_csrf_token']=secrets.token_urlsafe(32)
    if request.method=='POST' and not hmac.compare_digest(session['admin_csrf_token'],request.form.get('csrf_token','')):abort(400,description='Token de seguridad inválido.')

@admin_report_bp.after_request
def no_cache(response):
    response.headers['Cache-Control']='no-store, private'
    return response

def filters():
    start=request.args.get('desde',''); end=request.args.get('hasta',''); grain=request.args.get('agrupar','mes')
    try: return (date.fromisoformat(start) if start else None,date.fromisoformat(end) if end else None,grain)
    except ValueError:raise ValueError('Introduce fechas válidas (AAAA-MM-DD).') from None

@admin_report_bp.get('/')
def home():
    return render_template('admin/reports.html',groups=GROUPS,report=None,section='reports',code='',snapshot_ids=sorted(SNAPSHOTS))

@admin_report_bp.get('/<code>')
def view(code):
    if code not in REPORTS:abort(404)
    result=None; error=None; tracking=None
    try:
        start,end,grain=filters(); result=ReportService().generate(code,start,end,grain)
        tracking=next(iter(ReportRepository().rows('report_tracking')),{}).get('started_at')
    except ValueError as exc:error=str(exc)
    except Exception:
        current_app.logger.exception('Error al generar reporte %s',code)
        error='No se pudo consultar el reporte. Verifica la migración SQL 10 y los permisos de Supabase.'
    return render_template('admin/reports.html',groups=GROUPS,report=result,code=code,error=error,tracking=tracking,section='reports',snapshot_ids=sorted(SNAPSHOTS))

@admin_report_bp.get('/<code>/excel')
def excel(code):
    if code not in REPORTS:abort(404)
    try:
        start,end,grain=filters(); result=ReportService().generate(code,start,end,grain)
        buf=export_report(result, start,end,grain)
    except ValueError as exc:abort(400,description=str(exc))
    except Exception:
        current_app.logger.exception('Error al exportar reporte %s',code)
        abort(503,description='No se pudo exportar. Revisa la migración y el origen de datos.')
    return send_file(buf,as_attachment=True,download_name=f'odinsoft-{code}-{datetime.now(ZoneInfo("America/Lima")).date()}.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@admin_report_bp.get('/operacion/compras')
def purchases():
    data=ReportOperationsService().purchasing()
    data.update(purchase_table(data['purchases'], request.args.get('orden','ordered_on'),
        request.args.get('direccion','desc'), request.args.get('pagina',1,type=int),
        request.args.get('cantidad',10,type=int)))
    audit_by_id = AuditService().for_records('supplier_purchases', [p['id'] for p in data['purchases']])
    return render_template('admin/report_purchases.html',**data,audit_by_id=audit_by_id,today=datetime.now(ZoneInfo('America/Lima')).date().isoformat(),section='reports')

@admin_report_bp.post('/operacion/compras/<action>')
def purchase_action(action):
    service=ReportOperationsService()
    actions={'crear':lambda:service.create_purchase(request.form),'recibir':lambda:service.receive(request.form.get('id')),'pagar':lambda:service.pay_purchase(request.form.get('id'),request.form.get('amount')),'evaluar':lambda:service.evaluate(request.form)}
    if action not in actions:abort(404)
    try:
        actions[action](); flash('Operación registrada correctamente.','success')
    except ValueError as exc:flash(str(exc),'warning')
    except Exception:
        current_app.logger.exception('Error de compra/evaluación')
        flash('No se pudo registrar. Comprueba fechas, recepción previa, saldo y datos.','danger')
    return redirect(url_for('admin_report.purchases'))

@admin_report_bp.route('/operacion/venta/<sale_id>/pagos',methods=['GET','POST'])
def sale_payments(sale_id):
    service=ReportOperationsService()
    if request.method=='POST':
        try:service.pay_sale(sale_id,request.form); flash('Cobro registrado correctamente.','success')
        except ValueError as exc:flash(str(exc),'warning')
        except Exception:
            current_app.logger.exception('Error al registrar cobro')
            flash('No se pudo registrar el cobro. Verifica saldo, estado y seguimiento.','danger')
        return redirect(url_for('admin_report.sale_payments',sale_id=sale_id))
    try:data=service.sale_context(sale_id)
    except ValueError:abort(404)
    return render_template('admin/report_sale_payments.html',**data,section='reports')
