from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os

from models import db, Categoria, Usuario, Producto, Resena, Pedido, DetallePedido, Carrito, CarritoItem

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave-secreta-libreria-2026")

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


def login_requerido(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        if not session.get("usuario_id"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorada


def vendedor_requerido(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        if not session.get("es_vendedor"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorada


# ====================== CARRITO PERSISTENTE ======================
def obtener_o_crear_carrito(usuario_id):
    carrito = Carrito.query.filter_by(usuario_id=usuario_id, estado='activo').first()
    if not carrito:
        carrito = Carrito(usuario_id=usuario_id)
        db.session.add(carrito)
        db.session.commit()
    return carrito


@app.route("/")
def catalogo():
    categoria_id = request.args.get("categoria", type=int)
    busqueda = request.args.get("q", "").strip()
    precio_min = request.args.get("precio_min", type=float)
    precio_max = request.args.get("precio_max", type=float)

    categorias = Categoria.query.filter_by(activa=True).all()

    query = Producto.query.filter_by(activo=True)

    if categoria_id:
        query = query.filter_by(categoria_id=categoria_id)
    
    if busqueda:
        query = query.filter(
            db.or_(
                Producto.nombre.ilike(f"%{busqueda}%"),
                Producto.descripcion.ilike(f"%{busqueda}%"),
                Producto.marca.ilike(f"%{busqueda}%")
            )
        )
    
    if precio_min is not None:
        query = query.filter(Producto.precio >= precio_min)
    if precio_max is not None:
        query = query.filter(Producto.precio <= precio_max)

    productos = query.all()

    return render_template(
        "catalogo.html",
        productos=productos,
        categorias=categorias,
        categoria_activa=categoria_id,
        busqueda=busqueda,
        precio_min=precio_min,
        precio_max=precio_max
    )


@app.route("/producto/<int:producto_id>")
def detalle_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    resenas = Resena.query.filter_by(producto_id=producto_id).order_by(Resena.fecha.desc()).all()
    return render_template("producto.html", producto=producto, resenas=resenas)


@app.route("/producto/<int:producto_id>/resena", methods=["POST"])
@login_requerido
def agregar_resena(producto_id):
    ya_existe = Resena.query.filter_by(
        producto_id=producto_id, usuario_id=session["usuario_id"]
    ).first()

    if not ya_existe:
        nueva = Resena(
            producto_id=producto_id,
            usuario_id=session["usuario_id"],
            estrellas=int(request.form.get("estrellas")),
            titulo=request.form.get("titulo"),
            comentario=request.form.get("comentario")
        )
        db.session.add(nueva)
        db.session.commit()

    return redirect(url_for("detalle_producto", producto_id=producto_id))


@app.route("/registro", methods=["GET", "POST"])
def registro():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        existe = Usuario.query.filter_by(email=email).first()

        if existe:
            error = "Ese correo ya está registrado"
        else:
            nuevo = Usuario(
                nombre=request.form.get("nombre"),
                apellido=request.form.get("apellido"),
                email=email,
                password_hash=generate_password_hash(request.form.get("password")),
                telefono=request.form.get("telefono"),
                es_vendedor=bool(request.form.get("es_vendedor"))
            )
            db.session.add(nuevo)
            db.session.commit()
            return redirect(url_for("login"))

    return render_template("registro.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(usuario.password_hash, password):
            session["usuario_id"] = usuario.id
            session["usuario_nombre"] = usuario.nombre
            session["es_vendedor"] = usuario.es_vendedor

            siguiente = request.args.get("next")
            return redirect(siguiente or url_for("catalogo"))
        else:
            error = "Correo o contraseña incorrectos"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("catalogo"))


# ==================== RUTAS DEL CARRITO PERSISTENTE ====================
@app.route("/agregar/<int:producto_id>")
@login_requerido
def agregar_carrito(producto_id):
    carrito = obtener_o_crear_carrito(session["usuario_id"])
    
    item = CarritoItem.query.filter_by(carrito_id=carrito.id, producto_id=producto_id).first()
    
    if item:
        item.cantidad += 1
    else:
        item = CarritoItem(carrito_id=carrito.id, producto_id=producto_id, cantidad=1)
        db.session.add(item)
    
    db.session.commit()
    return redirect(request.referrer or url_for("catalogo"))


@app.route("/carrito")
@login_requerido
def ver_carrito():
    carrito = Carrito.query.filter_by(usuario_id=session["usuario_id"], estado='activo').first()
    items = []
    total = 0

    if carrito:
        for item in carrito.items:
            subtotal = float(item.producto.precio) * item.cantidad
            total += subtotal
            items.append({
                "id": item.id,
                "producto": item.producto,
                "cantidad": item.cantidad,
                "subtotal": subtotal
            })

    return render_template("carrito.html", items=items, total=total)


@app.route("/eliminar/<int:item_id>")
@login_requerido
def eliminar_carrito(item_id):
    item = CarritoItem.query.get_or_404(item_id)
    if item.carrito.usuario_id == session["usuario_id"]:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for("ver_carrito"))


@app.route("/actualizar_cantidad/<int:item_id>", methods=["POST"])
@login_requerido
def actualizar_cantidad(item_id):
    item = CarritoItem.query.get_or_404(item_id)
    if item.carrito.usuario_id == session["usuario_id"]:
        nueva_cantidad = int(request.form.get("cantidad", 1))
        if nueva_cantidad > 0 and nueva_cantidad <= item.producto.stock:
            item.cantidad = nueva_cantidad
            db.session.commit()
    return redirect(url_for("ver_carrito"))


# ==================== PAGO ====================
@app.route("/pago", methods=["GET", "POST"])
@login_requerido
def pago():
    carrito = Carrito.query.filter_by(usuario_id=session["usuario_id"], estado='activo').first()
    items = []
    total = 0

    if carrito:
        for item in carrito.items:
            if item.producto.activo and item.producto.stock >= item.cantidad:
                subtotal = float(item.producto.precio) * item.cantidad
                total += subtotal
                items.append({
                    "producto": item.producto,
                    "cantidad": item.cantidad,
                    "subtotal": subtotal
                })
            else:
                # Si no hay stock suficiente, eliminar del carrito
                db.session.delete(item)

        db.session.commit()

    if not items:
        return redirect(url_for("ver_carrito"))

    if request.method == "POST":
        metodo = request.form.get("metodo_pago")
        direccion = request.form.get("direccion")

        if not metodo or not direccion:
            # Puedes agregar flash message después
            return render_template("pago.html", items=items, total=total, error="Debe completar todos los campos")

        nuevo_pedido = Pedido(
            usuario_id=session["usuario_id"],
            total=total,
            metodo_pago=metodo,
            estado="pagado",
            direccion_entrega=direccion
        )
        db.session.add(nuevo_pedido)
        db.session.flush()

        for item in items:
            detalle = DetallePedido(
                pedido_id=nuevo_pedido.id,
                producto_id=item["producto"].id,
                cantidad=item["cantidad"],
                precio_unitario=item["producto"].precio,
                subtotal=item["subtotal"]       
            )
            item["producto"].stock -= item["cantidad"]
            db.session.add(detalle)

        # Marcar carrito como convertido
        carrito.estado = 'convertido'
        
        db.session.commit()

        return render_template("confirmacion.html", metodo=metodo, total=total, pedido_id=nuevo_pedido.id)

    return render_template("pago.html", items=items, total=total)


@app.route("/mis-pedidos")
@login_requerido
def mis_pedidos():
    pedidos = Pedido.query.filter_by(usuario_id=session["usuario_id"]).order_by(Pedido.fecha.desc()).all()
    return render_template("Pedidos.html", pedidos=pedidos)


# ==================== VENDEDOR ====================
@app.route("/vendedor")
@vendedor_requerido
def panel_vendedor():
    productos = Producto.query.filter_by(vendedor_id=session["usuario_id"]).all()
    return render_template("vendedor/dashboard.html", productos=productos)


@app.route("/vendedor/agregar", methods=["GET", "POST"])
@vendedor_requerido
def vendedor_agregar():
    categorias = Categoria.query.all()

    if request.method == "POST":
        nuevo = Producto(
            nombre=request.form.get("nombre"),
            descripcion=request.form.get("descripcion"),
            marca=request.form.get("marca"),
            precio=float(request.form.get("precio")),
            stock=int(request.form.get("stock")),
            categoria_id=int(request.form.get("categoria_id")),
            vendedor_id=session["usuario_id"],
            imagen_url=request.form.get("imagen_url")
        )
        db.session.add(nuevo)
        db.session.commit()
        return redirect(url_for("panel_vendedor"))

    return render_template("vendedor/form_producto.html", producto=None, categorias=categorias)


@app.route("/vendedor/editar/<int:producto_id>", methods=["GET", "POST"])
@vendedor_requerido
def vendedor_editar(producto_id):
    producto = Producto.query.get_or_404(producto_id)

    if producto.vendedor_id != session["usuario_id"]:
        return redirect(url_for("panel_vendedor"))

    categorias = Categoria.query.all()

    if request.method == "POST":
        producto.nombre = request.form.get("nombre")
        producto.descripcion = request.form.get("descripcion")
        producto.marca = request.form.get("marca")
        producto.precio = float(request.form.get("precio"))
        producto.stock = int(request.form.get("stock"))
        producto.categoria_id = int(request.form.get("categoria_id"))
        producto.imagen_url = request.form.get("imagen_url")
        db.session.commit()
        return redirect(url_for("panel_vendedor"))

    return render_template("vendedor/form_producto.html", producto=producto, categorias=categorias)


@app.route("/vendedor/eliminar/<int:producto_id>")
@vendedor_requerido
def vendedor_eliminar(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    if producto.vendedor_id == session["usuario_id"]:
        producto.activo = False
        db.session.commit()
    return redirect(url_for("panel_vendedor"))
@app.context_processor
def inject_carrito_count_and_user():
    context = {"carrito_items_count": 0}
    
    if session.get("usuario_id"):
        from models import Carrito, Usuario
        # Carrito
        carrito = Carrito.query.filter_by(usuario_id=session["usuario_id"], estado='activo').first()
        count = sum(item.cantidad for item in carrito.items) if carrito and carrito.items else 0
        context["carrito_items_count"] = count
        
        # Usuario actual para admin
        usuario = Usuario.query.get(session["usuario_id"])
        context["current_user"] = usuario
    
    return context

def admin_requerido(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        if not session.get("usuario_id"):
            return redirect(url_for("login"))
        usuario = Usuario.query.get(session["usuario_id"])
        if not usuario or usuario.rol != 'admin':
            return redirect(url_for("catalogo"))  # o página de acceso denegado
        return f(*args, **kwargs)
    return decorada

@app.route("/admin")
@admin_requerido
def panel_admin():
    usuarios = Usuario.query.all()
    productos = Producto.query.count()
    pedidos = Pedido.query.count()
    return render_template("admin/dashboard.html", 
                         usuarios=usuarios, 
                         total_productos=productos,
                         total_pedidos=pedidos)


@app.route("/admin/usuarios")
@admin_requerido
def admin_usuarios():
    usuarios = Usuario.query.all()
    return render_template("admin/usuarios.html", usuarios=usuarios)


@app.route("/admin/cambiar_rol/<int:usuario_id>", methods=["POST"])
@admin_requerido
def cambiar_rol(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    nuevo_rol = request.form.get("rol")
    if nuevo_rol in ['cliente', 'vendedor', 'admin']:
        usuario.rol = nuevo_rol
        usuario.es_vendedor = (nuevo_rol == 'vendedor')
        db.session.commit()
    return redirect(url_for("admin_usuarios"))


if __name__ == "__main__":
    with app.app_context():
        try:
            db.create_all()
            print("✅ Base de datos sincronizada correctamente")
        except Exception as e:
            print("⚠️ Error en BD:", e)
    
    app.run(debug=False, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))