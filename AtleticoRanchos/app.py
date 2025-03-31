import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from openpyxl import Workbook
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from dotenv import load_dotenv
from flask_migrate import Migrate

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

app = Flask(__name__)

# Configuración de la app usando variables de entorno
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.secret_key = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicialización de extensiones
db = SQLAlchemy(app)
mail = Mail(app)
migrate = Migrate(app, db)

# Modelos
class Socio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    apellido = db.Column(db.String(50), nullable=False)
    telefono = db.Column(db.String(20))
    correo = db.Column(db.String(100))
    direccion = db.Column(db.String(200))
    fecha_ingreso = db.Column(db.Date, default=datetime.utcnow)
    es_jugador = db.Column(db.Boolean, default=False)
    categoria = db.Column(db.String(20))
    activo = db.Column(db.Boolean, default=True)
    pagos = db.relationship('Pago', backref='socio', lazy=True)
    ficha_medica = db.Column(db.Boolean, default=False)
    fecha_ultima_revision_medica = db.Column(db.Date, nullable=True)
    fecha_proxima_revision_medica = db.Column(db.Date, nullable=True)
    

class Pago(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    socio_id = db.Column(db.Integer, db.ForeignKey('socio.id'))
    monto = db.Column(db.Float)
    fecha = db.Column(db.Date, default=datetime.utcnow)
    mes_pagado = db.Column(db.String(20))
    metodo_pago = db.Column(db.String(20))


# Crear tablas si no existen
with app.app_context():
    db.create_all()

# Rutas

@app.route('/')
def dashboard():
    total_socios = Socio.query.filter_by(activo=True).count()
    total_jugadores = Socio.query.filter_by(es_jugador=True, activo=True).count()
    
    mes_actual = datetime.now().strftime("%Y-%m")
    socios_con_pago = [p.socio_id for p in Pago.query.filter_by(mes_pagado=mes_actual)]
    socios_morosos = Socio.query.filter(
        Socio.activo == True,
        ~Socio.id.in_(socios_con_pago)
    ).count()
    
    return render_template('dashboard.html',
                           total_socios=total_socios,
                           total_jugadores=total_jugadores,
                           socios_morosos=socios_morosos)

@app.route('/socios')
def listar_socios():
    try:
        filtro = request.args.get('filtro', 'todos')
        
        query = Socio.query.filter_by(activo=True)
        
        if filtro == 'jugadores':
            query = query.filter_by(es_jugador=True)
        elif filtro == 'no-jugadores':
            query = query.filter_by(es_jugador=False)
        
        socios = query.order_by(Socio.apellido).all()
        
        # Debug: Verifica qué datos se están enviando
        app.logger.debug(f"Socios encontrados: {len(socios)}")
        
        return render_template('socios.html', 
                               socios=socios, 
                               filtro_actual=filtro)
    except Exception as e:
        app.logger.error(f"Error en listar_socios: {str(e)}")
        flash("Ocurrió un error al cargar los socios", "error")
        return redirect(url_for('dashboard'))

@app.route('/socio/nuevo', methods=['GET', 'POST'])
def nuevo_socio():
    if request.method == 'POST':
        try:
            # Procesar campos de jugador y ficha médica
            es_jugador = 'es_jugador' in request.form
            categoria = request.form.get('categoria') if es_jugador else None
            
            # Procesar ficha médica
            ficha_medica = 'ficha_medica' in request.form and es_jugador
            fecha_ultima_revision = request.form.get('fecha_ultima_revision') if ficha_medica else None
            fecha_proxima_revision = request.form.get('fecha_proxima_revision') if ficha_medica else None
            
            socio = Socio(
                nombre=request.form['nombre'],
                apellido=request.form['apellido'],
                telefono=request.form.get('telefono'),
                correo=request.form.get('correo'),
                direccion=request.form.get('direccion'),
                es_jugador=es_jugador,
                categoria=categoria,
                ficha_medica=ficha_medica,
                fecha_ultima_revision_medica=datetime.strptime(fecha_ultima_revision, '%Y-%m-%d') if fecha_ultima_revision else None,
                fecha_proxima_revision_medica=datetime.strptime(fecha_proxima_revision, '%Y-%m-%d') if fecha_proxima_revision else None
            )
            
            db.session.add(socio)
            db.session.commit()
            flash('Socio agregado correctamente', 'success')
            return redirect(url_for('listar_socios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    return render_template('nuevo_socio.html')

@app.route('/socio/editar/<int:id>', methods=['GET', 'POST'])
def editar_socio(id):
    socio = Socio.query.get_or_404(id)
    if request.method == 'POST':
        try:
            socio.nombre = request.form['nombre']
            socio.apellido = request.form['apellido']
            socio.telefono = request.form.get('telefono')
            socio.correo = request.form.get('correo')
            socio.direccion = request.form.get('direccion')
            
            socio.es_jugador = 'es_jugador' in request.form
            socio.categoria = request.form.get('categoria') if socio.es_jugador else None
            
            socio.ficha_medica = 'ficha_medica' in request.form and socio.es_jugador
            socio.fecha_ultima_revision_medica = (
                datetime.strptime(request.form.get('fecha_ultima_revision'), '%Y-%m-%d')
                if request.form.get('fecha_ultima_revision') else None
            )
            socio.fecha_proxima_revision_medica = (
                datetime.strptime(request.form.get('fecha_proxima_revision'), '%Y-%m-%d')
                if request.form.get('fecha_proxima_revision') else None
            )
            
            db.session.commit()
            flash('Socio actualizado correctamente', 'success')
            return redirect(url_for('listar_socios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar socio: {str(e)}', 'error')
    
    return render_template('editar_socio.html', socio=socio)

@app.route('/socio/eliminar/<int:id>')
def eliminar_socio(id):
    socio = Socio.query.get_or_404(id)
    socio.activo = False
    db.session.commit()
    flash('Socio marcado como inactivo', 'warning')
    return redirect(url_for('listar_socios'))

@app.route('/buscar_socios', methods=['GET'])
def buscar_socios():
    termino = request.args.get('q', '').strip()
    categoria = request.args.get('categoria', '')
    estado_pago = request.args.get('estado_pago', '')
    
    query = Socio.query.filter_by(activo=True)
    
    if termino:
        query = query.filter(
            db.or_(
                Socio.nombre.ilike(f'%{termino}%'),
                Socio.apellido.ilike(f'%{termino}%'),
                Socio.telefono.ilike(f'%{termino}%'),
                Socio.correo.ilike(f'%{termino}%')
            )
        )
    
    if categoria:
        query = query.filter_by(categoria=categoria)
    
    if estado_pago == 'morosos':
        mes_actual = datetime.now().strftime("%Y-%m")
        socios_con_pago = [p.socio_id for p in Pago.query.filter_by(mes_pagado=mes_actual)]
        query = query.filter(~Socio.id.in_(socios_con_pago))
    elif estado_pago == 'al_dia':
        mes_actual = datetime.now().strftime("%Y-%m")
        socios_con_pago = [p.socio_id for p in Pago.query.filter_by(mes_pagado=mes_actual)]
        query = query.filter(Socio.id.in_(socios_con_pago))
    
    socios = query.order_by(Socio.apellido).all()
    
    return render_template('socios.html', 
                           socios=socios,
                           termino_busqueda=termino,
                           filtro_categoria=categoria,
                           filtro_estado_pago=estado_pago)

@app.route('/pagos')
def listar_pagos():
    mes = request.args.get('mes', datetime.now().strftime("%Y-%m"))
    pagos = Pago.query.filter_by(mes_pagado=mes).order_by(Pago.fecha.desc()).all()
    
    total_mes = sum(p.monto for p in pagos)
    total_socios = Socio.query.filter_by(activo=True).count()
    socios_pagados = len({p.socio_id for p in pagos})
    
    return render_template('pagos.html', 
                           pagos=pagos, 
                           mes_actual=mes,
                           total_mes=total_mes,
                           total_socios=total_socios,
                           socios_pagados=socios_pagados)

@app.route('/pago/nuevo', methods=['GET', 'POST'])
def nuevo_pago():
    if request.method == 'POST':
        try:
            # Validar que no exista un pago para el mismo socio en el mismo mes
            existe_pago = Pago.query.filter_by(
                socio_id=request.form['socio_id'],
                mes_pagado=request.form['mes_pagado']
            ).first()
            
            if existe_pago:
                flash('Este socio ya tiene un pago registrado para este mes', 'warning')
                return redirect(url_for('nuevo_pago'))
            
            # Crear nuevo pago
            nuevo_pago = Pago(
                socio_id=request.form['socio_id'],
                monto=float(request.form['monto']),
                mes_pagado=request.form['mes_pagado'],
                metodo_pago=request.form['metodo_pago'],
                fecha=datetime.strptime(request.form['fecha_pago'], '%Y-%m-%d')
            )
            
            db.session.add(nuevo_pago)
            db.session.commit()
            
            # Enviar factura por email si el socio tiene correo
            socio = Socio.query.get(nuevo_pago.socio_id)
            if socio and socio.correo:
                enviar_factura(nuevo_pago, socio)
            
            flash('Pago registrado exitosamente!', 'success')
            return redirect(url_for('listar_pagos'))
            
        except ValueError:
            db.session.rollback()
            flash('Error: El monto debe ser un número válido', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar el pago: {str(e)}', 'error')
    
    socios = Socio.query.filter_by(activo=True).order_by(Socio.apellido).all()
    hoy = datetime.now().strftime('%Y-%m-%d')
    return render_template('nuevo_pago.html', 
                           socios=socios,
                           mes_actual=datetime.now().strftime("%Y-%m"),
                           hoy=hoy)

def generar_factura_pdf(pago, socio):
    """
    Genera un PDF de factura con un diseño profesional y devuelve la ruta del archivo.
    """
    ruta_factura = f"facturas/factura_{socio.id}_{pago.mes_pagado}.pdf"
    
    # Crear la carpeta de facturas si no existe
    if not os.path.exists("facturas"):
        os.makedirs("facturas")
    
    # Configuración del documento
    doc = SimpleDocTemplate(
        ruta_factura,
        pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )
    styles = getSampleStyleSheet()
    elements = []
    
    # Estilos personalizados
    title_style = styles["Title"]
    normal_style = styles["Normal"]
    heading_style = styles["Heading2"]
    
    # Logo y datos del club
    logo_path = "static/logo.png"  # Asegúrate de tener el logo en esta ruta
    if os.path.exists(logo_path):
        im = Image(logo_path, width=120, height=60)
        im.hAlign = 'LEFT'
        elements.append(im)
    
    company_details = """
    <para align=right>
    <font size=14><b>Club Atlético Ranchos</b></font><br/>
    Dirección: Calle Estanislao Garay, Ranchos<br/>
    Tel: +54 9 224155555<br/>
    Email: clubranchos@gmail.com
    </para>
    """
    elements.append(Paragraph(company_details, normal_style))
    elements.append(Spacer(1, 20))
    
    # Título de la factura
    elements.append(Paragraph("Factura de Pago", title_style))
    elements.append(Spacer(1, 12))
    
    # Información de la factura
    invoice_info_data = [
        ["Fecha de Emisión:", pago.fecha.strftime('%d/%m/%Y')],
        ["Número de Factura:", f"{socio.id}-{pago.mes_pagado}"]
    ]
    invoice_table = Table(invoice_info_data, colWidths=[150, 300])
    invoice_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))
    elements.append(invoice_table)
    elements.append(Spacer(1, 20))
    
    # Datos del socio (cliente)
    elements.append(Paragraph("Datos del Socio", heading_style))
    socio_info = f"""
    <b>Nombre:</b> {socio.nombre} {socio.apellido}<br/>
    <b>Correo:</b> {socio.correo}<br/>
    <b>Teléfono:</b> {socio.telefono if socio.telefono else 'No disponible'}<br/>
    """
    elements.append(Paragraph(socio_info, normal_style))
    elements.append(Spacer(1, 20))
    
    # Detalles del pago
    elements.append(Paragraph("Detalle del Pago", heading_style))
    payment_data = [
        ["Descripción", "Detalle"],
        ["Mes Pagado", pago.mes_pagado],
        ["Monto", f"${pago.monto:.2f}"],
        ["Método de Pago", pago.metodo_pago],
    ]
    payment_table = Table(payment_data, colWidths=[150, 300])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    elements.append(payment_table)
    elements.append(Spacer(1, 30))
    
    # Mensaje final formal
    footer = """
    <para align=center>
    <font size=12>Le agradecemos por confiar en nuestros servicios.</font><br/>
    <font size=10>Atentamente,<br/>Equipo Administrativo<br/>Club Atlético Ranchos</font>
    </para>
    """
    elements.append(Paragraph(footer, normal_style))
    
    # Genera el PDF
    doc.build(elements)
    return ruta_factura

def enviar_factura(pago, socio):
    try:
        ruta_factura = generar_factura_pdf(pago, socio)  # Genera el PDF de la factura

        msg = Message(
            subject=f"Factura de Pago - {pago.mes_pagado}",
            sender=app.config['MAIL_USERNAME'],
            recipients=[socio.correo],
            body=f"""Estimado/a {socio.nombre} {socio.apellido},

Adjunto encontrará la factura correspondiente al pago realizado para el mes {pago.mes_pagado}.

Le agradecemos por su confianza y puntualidad. Si tiene alguna consulta o requiere asistencia, no dude en contactarnos.

Atentamente,
Club Atlético Ranchos
            """
        )

        # Adjunta el PDF al mensaje
        with open(ruta_factura, "rb") as pdf:
            msg.attach(f"Factura_{pago.mes_pagado}.pdf", "application/pdf", pdf.read())

        mail.send(msg)
        return True

    except Exception as e:
        app.logger.error(f"Error enviando factura a {socio.correo}: {str(e)}")
        return False

@app.route('/reporte/morosos')
def reporte_morosos():
    mes_actual = datetime.now().strftime("%Y-%m")
    socios_con_pago = [p.socio_id for p in Pago.query.filter_by(mes_pagado=mes_actual)]
    
    morosos = Socio.query.filter(
        Socio.activo == True,
        ~Socio.id.in_(socios_con_pago)
    ).order_by(Socio.apellido).all()
    
    return render_template('reporte_morosos.html',
                           morosos=morosos,
                           mes_actual=mes_actual)

def enviar_recordatorio(socio, mes):
    try:
        msg = Message(
            subject=f"Recordatorio de Pago - {mes}",
            sender=app.config['MAIL_USERNAME'],
            recipients=[socio.correo],
            body=f"""Hola {socio.nombre} {socio.apellido},

Notamos que aún no has realizado el pago correspondiente al mes de {mes}.
Te recordamos que regularizar tu situación es importante para seguir disfrutando de los beneficios del club.

Si ya realizaste el pago, por favor ignora este mensaje.

Saludos,
Club Atlético Ranchos
            """
        )
        mail.send(msg)
        return True
    except Exception as e:
        app.logger.error(f"Error enviando recordatorio a {socio.correo}: {str(e)}")
        return False

@app.route('/verificar_morosos')
def verificar_morosos():
    mes_actual = datetime.now().strftime("%Y-%m")
    fecha_limite = datetime.now() - timedelta(days=15)
    
    morosos = Socio.query.filter(
        Socio.activo == True,
        ~Socio.id.in_(
            db.session.query(Pago.socio_id).filter_by(mes_pagado=mes_actual)
        ),
        Socio.fecha_ingreso <= fecha_limite
    ).all()
    
    for socio in morosos:
        if socio.correo:
            enviar_recordatorio(socio, mes_actual)
    
    return f"Notificaciones enviadas a {len(morosos)} socios morosos."

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
