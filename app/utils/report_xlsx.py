"""Exportación real XLSX, no CSV renombrado. Protege contra fórmulas en texto."""
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
import xlsxwriter


def export_report(report, start=None, end=None, grain='mes'):
    buf=BytesIO()
    with xlsxwriter.Workbook(buf,{'in_memory':True,'strings_to_formulas':False,'strings_to_urls':False}) as book:
        sheet=book.add_worksheet('Datos'); info=book.add_worksheet('Metadatos')
        head=book.add_format({'bold':True,'bg_color':'#12375B','font_color':'white','text_wrap':True,'valign':'vcenter'})
        text=book.add_format({'valign':'top','text_wrap':True}); number=book.add_format({'num_format':'#,##0.##'})
        sheet.write_row(0,0,report.columns,head);sheet.set_row(0,32);sheet.freeze_panes(1,0)
        for i,row in enumerate(report.rows,1):
            for j,v in enumerate(row):
                if isinstance(v,(float,int)) and not isinstance(v,bool):sheet.write_number(i,j,v,number)
                else:sheet.write_string(i,j,str(v if v is not None else ''),text)
        for j,c in enumerate(report.columns):
            sample=max([len(str(row[j])) for row in report.rows[:100]]+[len(c)])
            sheet.set_column(j,j,min(48,max(15,sample+2)))
        if report.rows:sheet.autofilter(0,0,len(report.rows),len(report.columns)-1)
        info.set_column(0,0,24);info.set_column(1,1,90);info.write_row(0,0,['Campo','Detalle'],head)
        fields=[('Reporte',report.title),('Desde',str(start or 'Todo el historial')),('Hasta',str(end or 'Todo el historial')),('Agrupación',grain),('Generado (Lima)',datetime.now(ZoneInfo('America/Lima')).isoformat(timespec='seconds')),('Filas',len(report.rows)),('Definición',report.note)]
        for i,(k,v) in enumerate(fields,1):info.write_string(i,0,k,text);info.write_string(i,1,str(v),text)
        info.set_row(len(fields),74)
    buf.seek(0);return buf
