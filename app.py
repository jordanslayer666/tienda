from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'tienda_jordan_super_secreta' # Necesario para las sesiones

# Configuración de la base de datos
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = ''
DB_NAME = 'tienda_jordan'

def get_db_connection():
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection

# --- RUTAS PÚBLICAS ---
@app.route('/')
def index():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM productos')
        productos = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        productos = []
        print(f"Error de base de datos: {e}")
        
    return render_template('index.html', productos=productos)

@app.route('/add_cart/<int:id_producto>', methods=['POST'])
def add_cart(id_producto):
    if 'carrito' not in session:
        session['carrito'] = []
    
    session['carrito'].append(id_producto)
    session.modified = True
    flash('Producto agregado al carrito.', 'success')
    return redirect(url_for('index'))

@app.route('/carrito')
def carrito():
    productos_en_carrito = []
    total_precio = 0
    if 'carrito' in session and session['carrito']:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            from collections import Counter
            conteos = Counter(session['carrito'])
            
            for id_prod, cantidad in conteos.items():
                cursor.execute('SELECT * FROM productos WHERE id_producto = %s', (id_prod,))
                producto = cursor.fetchone()
                if producto:
                    producto['cantidad_comprada'] = cantidad
                    producto['subtotal'] = producto['precio'] * cantidad
                    total_precio += producto['subtotal']
                    productos_en_carrito.append(producto)
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error carrito: {e}")
            
    return render_template('carrito.html', productos=productos_en_carrito, total=total_precio)

@app.route('/procesar_compra', methods=['POST'])
def procesar_compra():
    if 'carrito' not in session or not session['carrito']:
        return redirect(url_for('index'))
        
    nombre = request.form['nombre']
    apellido = request.form['apellido']
    telefono = request.form['telefono']
    correo = request.form['correo']
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Registrar al cliente nuevo
        cursor.execute('INSERT INTO clientes (nombre, apellido, telefono, correo) VALUES (%s, %s, %s, %s)', 
                       (nombre, apellido, telefono, correo))
        id_cliente = cursor.lastrowid
        
        # 2. Registrar las ventas (una por cada producto diferente en el carrito)
        from collections import Counter
        conteos = Counter(session['carrito'])
        fecha = datetime.now().strftime('%Y-%m-%d')
        
        for id_prod, cantidad in conteos.items():
            cursor.execute('SELECT precio FROM productos WHERE id_producto = %s', (id_prod,))
            res = cursor.fetchone()
            if res:
                precio = res['precio']
                total = precio * cantidad
                
                # Insertar en ventas
                cursor.execute('INSERT INTO ventas (id_cliente, id_producto, fecha_venta, cantidad, total) VALUES (%s, %s, %s, %s, %s)', 
                               (id_cliente, id_prod, fecha, cantidad, total))
                
                # Descontar el stock
                cursor.execute('UPDATE productos SET stock = stock - %s WHERE id_producto = %s', (cantidad, id_prod))
        
        conn.commit()
        session.pop('carrito', None) # Vaciar carrito
        flash('¡Tu compra se ha realizado con éxito! Tus datos han sido guardados.', 'success')
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error procesando compra: {e}")
        flash('Hubo un error al procesar tu compra.', 'danger')
        
    return redirect(url_for('index'))

# --- RUTAS ADMINISTRATIVAS ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['username']
        contrasena = request.form['password']
        
        # Para demostración, usaremos credenciales fijas. 
        # En producción, esto debería validar contra una tabla 'usuarios'.
        if usuario == 'admin' and contrasena == '123456':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
            
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
        
    # Estadísticas para el dashboard
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as total FROM productos')
        total_productos = cursor.fetchone()['total']
        
        cursor.execute('SELECT COUNT(*) as total FROM clientes')
        total_clientes = cursor.fetchone()['total']
        
        cursor.execute('SELECT COUNT(*) as total FROM ventas')
        total_ventas = cursor.fetchone()['total']
        
        cursor.execute('SELECT * FROM productos LIMIT 5')
        ultimos_productos = cursor.fetchall()
        
        cursor.close()
        conn.close()
    except Exception as e:
        total_productos = total_clientes = total_ventas = 0
        ultimos_productos = []
        print(f"Error: {e}")

    return render_template('admin_dashboard.html', 
                           total_productos=total_productos, 
                           total_clientes=total_clientes,
                           total_ventas=total_ventas,
                           ultimos_productos=ultimos_productos)

@app.route('/admin/productos', methods=['GET', 'POST'])
def admin_productos():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Si se envía un formulario para agregar producto
    if request.method == 'POST':
        nombre = request.form['nombre']
        categoria = request.form['categoria']
        precio = request.form['precio']
        stock = request.form['stock']
        
        cursor.execute('INSERT INTO productos (nombre_producto, categoria, precio, stock) VALUES (%s, %s, %s, %s)', 
                       (nombre, categoria, precio, stock))
        conn.commit()
        flash('Producto agregado correctamente', 'success')
        return redirect(url_for('admin_productos'))
        
    # Obtener todos los productos
    cursor.execute('SELECT * FROM productos')
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('admin_productos.html', productos=productos)

@app.route('/admin/productos/delete/<int:id>')
def delete_producto(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM productos WHERE id_producto = %s', (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Producto eliminado correctamente', 'success')
    return redirect(url_for('admin_productos'))

@app.route('/admin/clientes')
def admin_clientes():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clientes ORDER BY id_cliente DESC')
    clientes = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('admin_clientes.html', clientes=clientes)

@app.route('/admin/ventas')
def admin_ventas():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT v.id_venta, v.fecha_venta, v.cantidad, v.total, 
               p.nombre_producto, c.nombre, c.apellido 
        FROM ventas v
        JOIN productos p ON v.id_producto = p.id_producto
        JOIN clientes c ON v.id_cliente = c.id_cliente
        ORDER BY v.id_venta DESC
    ''')
    ventas = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('admin_ventas.html', ventas=ventas)

if __name__ == '__main__':
    app.run(debug=True)
