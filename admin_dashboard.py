# -*- coding: utf-8 -*-
"""
Admin Dashboard للتحكم في بيانات البوت
"""

import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from data import routes_data, neighborhood_data

# إعداد Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///admin_bot.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# إضافة مرشح JSON للقوالب
@app.template_filter('from_json')
def from_json_filter(value):
    """تحويل JSON string إلى Python object"""
    try:
        return json.loads(value)
    except:
        return []

# Models قاعدة البيانات
class Location(db.Model):
    """جدول الأماكن والمعالم"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    neighborhood = db.Column(db.String(100), nullable=False)
    coordinates = db.Column(db.String(50), nullable=True)
    # تصنيف المكان: محطة مباشرة أم قريبة
    location_type = db.Column(db.String(50), nullable=False, default='direct')  # 'direct' أو 'nearby'
    # المسافة المطلوبة للمشي (بالمتر) إذا كان المكان قريباً
    walking_distance = db.Column(db.Integer, nullable=True, default=0)
    # ملاحظات إضافية عن المكان
    location_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Location {self.name}>'

class Route(db.Model):
    """جدول الخطوط"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    fare = db.Column(db.Float, nullable=False)
    start_area = db.Column(db.String(200), nullable=True)
    end_area = db.Column(db.String(200), nullable=True)
    key_points = db.Column(db.Text, nullable=False)  # JSON string
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Route {self.name}>'

class RouteConnection(db.Model):
    """جدول الربط بين المواصلات"""
    id = db.Column(db.Integer, primary_key=True)
    from_route_id = db.Column(db.Integer, db.ForeignKey('route.id'), nullable=False)
    to_route_id = db.Column(db.Integer, db.ForeignKey('route.id'), nullable=False)
    connection_point = db.Column(db.String(200), nullable=False)  # نقطة التحويل
    walking_time = db.Column(db.Integer, nullable=False, default=5)  # وقت المشي بالدقائق
    connection_notes = db.Column(db.Text, nullable=True)  # ملاحظات إضافية
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # علاقات
    from_route = db.relationship('Route', foreign_keys=[from_route_id], backref='connections_from')
    to_route = db.relationship('Route', foreign_keys=[to_route_id], backref='connections_to')
    
    def __repr__(self):
        return f'<RouteConnection {self.from_route.name} → {self.to_route.name} at {self.connection_point}>'

def init_database():
    """تهيئة قاعدة البيانات بالبيانات الحالية"""
    with app.app_context():
        db.create_all()
        
        # تحقق إذا كانت البيانات موجودة بالفعل
        if Location.query.count() == 0:
            print("🔄 جاري تحميل البيانات الحالية...")
            
            # إضافة الأماكن من neighborhood_data
            for neighborhood, categories in neighborhood_data.items():
                for category, locations in categories.items():
                    for location in locations:
                        # التعامل مع البيانات المعقدة
                        location_name = location
                        if isinstance(location, dict):
                            location_name = location.get('name', str(location))
                        
                        new_location = Location(
                            name=str(location_name),
                            category=str(category),
                            neighborhood=str(neighborhood)
                        )
                        db.session.add(new_location)
            
            # إضافة الخطوط من routes_data
            for route in routes_data:
                new_route = Route(
                    name=route['routeName'],
                    fare=float(route['fare'].split()[0]) if 'fare' in route else 4.5,
                    start_area=route.get('startArea', ''),
                    end_area=route.get('endArea', ''),
                    key_points=json.dumps(route['keyPoints'], ensure_ascii=False),
                    notes=route.get('notes', '')
                )
                db.session.add(new_route)
            
            db.session.commit()
            print("✅ تم تحميل البيانات بنجاح!")

# Routes الصفحات
@app.route('/')
def index():
    """الصفحة الرئيسية"""
    routes_count = Route.query.count()
    locations_count = Location.query.count()
    connections_count = RouteConnection.query.count()
    neighborhoods = db.session.query(Location.neighborhood.distinct()).all()
    
    return render_template('index.html', 
                         routes_count=routes_count,
                         locations_count=locations_count,
                         connections_count=connections_count,
                         neighborhoods_count=len(neighborhoods))

@app.route('/routes')
def routes_list():
    """عرض جميع الخطوط"""
    routes = Route.query.order_by(Route.created_at.desc()).all()
    return render_template('routes_list.html', routes=routes)

@app.route('/routes/add', methods=['GET', 'POST'])
def add_route():
    """إضافة خط جديد"""
    if request.method == 'POST':
        name = request.form.get('name')
        fare = float(request.form.get('fare', 4.5))
        start_area = request.form.get('start_area', '')
        end_area = request.form.get('end_area', '')
        selected_locations = request.form.getlist('locations')
        notes = request.form.get('notes', '')
        
        # إنشاء الخط الجديد
        new_route = Route(
            name=name,
            fare=fare,
            start_area=start_area,
            end_area=end_area,
            key_points=json.dumps(selected_locations, ensure_ascii=False),
            notes=notes
        )
        
        db.session.add(new_route)
        db.session.commit()
        
        flash(f'تم إضافة الخط "{name}" بنجاح!', 'success')
        return redirect(url_for('routes_list'))
    
    # جلب جميع الأماكن مرتبة حسب الحي والتصنيف
    locations = Location.query.order_by(Location.neighborhood, Location.category, Location.name).all()
    neighborhoods = {}
    
    for location in locations:
        if location.neighborhood not in neighborhoods:
            neighborhoods[location.neighborhood] = {}
        if location.category not in neighborhoods[location.neighborhood]:
            neighborhoods[location.neighborhood][location.category] = []
        neighborhoods[location.neighborhood][location.category].append(location)
    
    return render_template('add_route.html', neighborhoods=neighborhoods)

@app.route('/locations')
def locations_list():
    """عرض جميع الأماكن"""
    locations = Location.query.order_by(Location.neighborhood, Location.category, Location.name).all()
    return render_template('locations_list.html', locations=locations)

@app.route('/locations/add', methods=['GET', 'POST'])
def add_location():
    """إضافة مكان جديد"""
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        neighborhood = request.form.get('neighborhood')
        coordinates = request.form.get('coordinates', '')
        
        # الحصول على الحقول الجديدة
        location_type = request.form.get('location_type', 'direct')
        walking_distance = int(request.form.get('walking_distance', 0))
        location_notes = request.form.get('location_notes', '')
        
        new_location = Location(
            name=name,
            category=category,
            neighborhood=neighborhood,
            coordinates=coordinates,
            location_type=location_type,
            walking_distance=walking_distance,
            location_notes=location_notes
        )
        
        db.session.add(new_location)
        db.session.commit()
        
        flash(f'تم إضافة المكان "{name}" بنجاح!', 'success')
        return redirect(url_for('locations_list'))
    
    # جلب الأحياء والتصنيفات الموجودة
    neighborhoods = db.session.query(Location.neighborhood.distinct()).all()
    categories = db.session.query(Location.category.distinct()).all()
    
    return render_template('add_location.html', 
                         neighborhoods=[n[0] for n in neighborhoods],
                         categories=[c[0] for c in categories])

@app.route('/api/export')
def export_data():
    """تصدير البيانات للبوت"""
    routes = Route.query.all()
    locations = Location.query.all()
    
    # تجهيز بيانات الخطوط
    routes_export = []
    for route in routes:
        routes_export.append({
            'routeName': route.name,
            'fare': f"{route.fare} جنيه مصري",
            'startArea': route.start_area,
            'endArea': route.end_area,
            'keyPoints': json.loads(route.key_points),
            'notes': route.notes
        })
    
    # تجهيز بيانات الأماكن
    neighborhoods_export = {}
    for location in locations:
        if location.neighborhood not in neighborhoods_export:
            neighborhoods_export[location.neighborhood] = {}
        if location.category not in neighborhoods_export[location.neighborhood]:
            neighborhoods_export[location.neighborhood][location.category] = []
        
        neighborhoods_export[location.neighborhood][location.category].append(location.name)
    
    return jsonify({
        'routes_data': routes_export,
        'neighborhood_data': neighborhoods_export
    })

@app.route('/routes/edit/<int:route_id>', methods=['GET', 'POST'])
def edit_route(route_id):
    """تعديل خط موجود"""
    route = Route.query.get_or_404(route_id)
    
    if request.method == 'POST':
        route.name = request.form.get('name')
        route.fare = float(request.form.get('fare', 4.5))
        route.start_area = request.form.get('start_area', '')
        route.end_area = request.form.get('end_area', '')
        selected_locations = request.form.getlist('locations')
        route.key_points = json.dumps(selected_locations, ensure_ascii=False)
        route.notes = request.form.get('notes', '')
        
        db.session.commit()
        
        flash(f'تم تحديث الخط "{route.name}" بنجاح!', 'success')
        return redirect(url_for('routes_list'))
    
    # جلب جميع الأماكن مرتبة
    locations = Location.query.order_by(Location.neighborhood, Location.category, Location.name).all()
    neighborhoods = {}
    
    for location in locations:
        if location.neighborhood not in neighborhoods:
            neighborhoods[location.neighborhood] = {}
        if location.category not in neighborhoods[location.neighborhood]:
            neighborhoods[location.neighborhood][location.category] = []
        neighborhoods[location.neighborhood][location.category].append(location)
    
    # الأماكن الحالية للخط
    try:
        current_locations = json.loads(route.key_points)
    except:
        current_locations = []
    
    return render_template('edit_route.html', 
                         route=route, 
                         neighborhoods=neighborhoods,
                         current_locations=current_locations)

@app.route('/routes/delete/<int:route_id>', methods=['POST'])
def delete_route(route_id):
    """حذف خط"""
    route = Route.query.get_or_404(route_id)
    route_name = route.name
    
    db.session.delete(route)
    db.session.commit()
    
    flash(f'تم حذف الخط "{route_name}" بنجاح!', 'success')
    return redirect(url_for('routes_list'))

@app.route('/locations/edit/<int:location_id>', methods=['GET', 'POST'])
def edit_location(location_id):
    """تعديل مكان موجود"""
    location = Location.query.get_or_404(location_id)
    
    if request.method == 'POST':
        location.name = request.form.get('name')
        location.category = request.form.get('category')
        location.neighborhood = request.form.get('neighborhood')
        location.coordinates = request.form.get('coordinates', '')
        
        # إضافة الحقول الجديدة
        location.location_type = request.form.get('location_type', 'direct')
        location.walking_distance = int(request.form.get('walking_distance', 0))
        location.location_notes = request.form.get('location_notes', '')
        
        db.session.commit()
        
        flash(f'تم تحديث المكان "{location.name}" بنجاح!', 'success')
        return redirect(url_for('locations_list'))
    
    # جلب الأحياء والتصنيفات الموجودة
    neighborhoods = db.session.query(Location.neighborhood.distinct()).all()
    categories = db.session.query(Location.category.distinct()).all()
    
    return render_template('edit_location.html', 
                         location=location,
                         neighborhoods=[n[0] for n in neighborhoods],
                         categories=[c[0] for c in categories])

@app.route('/locations/delete/<int:location_id>', methods=['POST'])
def delete_location(location_id):
    """حذف مكان"""
    location = Location.query.get_or_404(location_id)
    location_name = location.name
    
    db.session.delete(location)
    db.session.commit()
    
    flash(f'تم حذف المكان "{location_name}" بنجاح!', 'success')
    return redirect(url_for('locations_list'))

# --- مسارات الربط بين المواصلات ---
@app.route('/connections')
def connections_list():
    """عرض جميع روابط المواصلات"""
    connections = RouteConnection.query.order_by(RouteConnection.created_at.desc()).all()
    return render_template('connections_list.html', connections=connections)

@app.route('/connections/add', methods=['GET', 'POST'])
def add_connection():
    """إضافة ربط جديد بين المواصلات"""
    if request.method == 'POST':
        from_route_id = int(request.form.get('from_route_id'))
        to_route_id = int(request.form.get('to_route_id'))
        connection_point = request.form.get('connection_point')
        walking_time = int(request.form.get('walking_time', 5))
        connection_notes = request.form.get('connection_notes', '')
        
        new_connection = RouteConnection(
            from_route_id=from_route_id,
            to_route_id=to_route_id,
            connection_point=connection_point,
            walking_time=walking_time,
            connection_notes=connection_notes
        )
        
        db.session.add(new_connection)
        db.session.commit()
        
        flash(f'تم إضافة الربط بنجاح!', 'success')
        return redirect(url_for('connections_list'))
    
    # جلب جميع الخطوط المتاحة
    routes = Route.query.order_by(Route.name).all()
    return render_template('add_connection.html', routes=routes)

@app.route('/connections/edit/<int:connection_id>', methods=['GET', 'POST'])
def edit_connection(connection_id):
    """تعديل ربط موجود"""
    connection = RouteConnection.query.get_or_404(connection_id)
    
    if request.method == 'POST':
        connection.from_route_id = int(request.form.get('from_route_id'))
        connection.to_route_id = int(request.form.get('to_route_id'))
        connection.connection_point = request.form.get('connection_point')
        connection.walking_time = int(request.form.get('walking_time', 5))
        connection.connection_notes = request.form.get('connection_notes', '')
        
        db.session.commit()
        
        flash(f'تم تحديث الربط بنجاح!', 'success')
        return redirect(url_for('connections_list'))
    
    routes = Route.query.order_by(Route.name).all()
    return render_template('edit_connection.html', connection=connection, routes=routes)

@app.route('/connections/delete/<int:connection_id>', methods=['POST'])
def delete_connection(connection_id):
    """حذف ربط"""
    connection = RouteConnection.query.get_or_404(connection_id)
    
    db.session.delete(connection)
    db.session.commit()
    
    flash(f'تم حذف الربط بنجاح!', 'success')
    return redirect(url_for('connections_list'))

@app.route('/api/update_bot')
def update_bot_data():
    """تحديث بيانات البوت"""
    try:
        from database_helper import update_bot_data
        success = update_bot_data()
        
        if success:
            flash('تم تحديث بيانات البوت بنجاح!', 'success')
            return jsonify({'status': 'success', 'message': 'تم تحديث البيانات بنجاح'})
        else:
            flash('حدث خطأ أثناء تحديث بيانات البوت', 'error')
            return jsonify({'status': 'error', 'message': 'فشل في تحديث البيانات'})
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=True)