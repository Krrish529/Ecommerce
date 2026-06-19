from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Categoria(db.Model):
    __tablename__ = "categorias"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False, unique=True)
    descripcion = db.Column(db.String(200))
    icono = db.Column(db.String(10), default="📦")
    activa = db.Column(db.Boolean, default=True)

    productos = db.relationship("Producto", backref="categoria", lazy=True)


class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    telefono = db.Column(db.String(20))
    es_vendedor = db.Column(db.Boolean, default=False)
    rol = db.Column(db.Enum('cliente', 'vendedor', 'admin'), default='cliente')
    avatar_url = db.Column(db.String(255))
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"
    
    @property
    def es_admin(self):
        return self.rol == 'admin'

class Producto(db.Model):
    __tablename__ = "productos"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    marca = db.Column(db.String(100))
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id"), nullable=False)
    vendedor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    imagen_url = db.Column(db.String(255))
    activo = db.Column(db.Boolean, default=True)
    fecha_publicacion = db.Column(db.DateTime, default=datetime.utcnow)

    resenas = db.relationship("Resena", backref="producto", lazy=True, cascade="all, delete-orphan")
    @property
    def promedio_estrellas(self):
        if not self.resenas:
            return 0.0
        return round(sum(r.estrellas for r in self.resenas) / len(self.resenas), 1)

    @property
    def total_resenas(self):
        return len(self.resenas)


class Resena(db.Model):
    __tablename__ = "resenas"
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    estrellas = db.Column(db.SmallInteger, nullable=False)
    titulo = db.Column(db.String(150))
    comentario = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)


class Carrito(db.Model):
    __tablename__ = "carritos"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    estado = db.Column(db.Enum('activo','convertido','abandonado'), default='activo')
    fecha_creado = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizado = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship("CarritoItem", backref="carrito", lazy=True, cascade="all, delete-orphan")


class CarritoItem(db.Model):
    __tablename__ = "carrito_items"
    id = db.Column(db.Integer, primary_key=True)
    carrito_id = db.Column(db.Integer, db.ForeignKey("carritos.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    cantidad = db.Column(db.Integer, default=1)

    producto = db.relationship("Producto")


class Pedido(db.Model):
    __tablename__ = "pedidos"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    metodo_pago = db.Column(db.Enum('Yape','Plin','Tarjeta'), nullable=False)
    estado = db.Column(db.Enum('pendiente','pagado','enviado','entregado','cancelado'), default='pendiente')
    direccion_entrega = db.Column(db.String(300))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("DetallePedido", backref="pedido", lazy=True, cascade="all, delete-orphan")
    envio = db.relationship("Envio", backref="pedido", uselist=False)


class DetallePedido(db.Model):
    __tablename__ = "detalle_pedido"
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    producto = db.relationship("Producto")


class Envio(db.Model):
    __tablename__ = "envios"
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), nullable=False, unique=True)
    transportista = db.Column(db.String(100))
    numero_tracking = db.Column(db.String(100))
    costo_envio = db.Column(db.Numeric(10, 2), default=0.00)
    estado = db.Column(db.Enum('preparando','en_camino','entregado','fallido'), default='preparando')
    fecha_envio = db.Column(db.DateTime)
    fecha_entrega_est = db.Column(db.Date)


class TokenRecuperacion(db.Model):
    __tablename__ = "tokens_recuperacion"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    fecha_creado = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_expira = db.Column(db.DateTime, nullable=False)
    usado = db.Column(db.Boolean, default=False)