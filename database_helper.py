# -*- coding: utf-8 -*-
"""
مساعد قاعدة البيانات لقراءة البيانات للبوت
"""

import sqlite3
import json

def get_routes_from_db():
    """قراءة جميع الخطوط من قاعدة البيانات"""
    try:
        conn = sqlite3.connect('instance/admin_bot.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, fare, start_area, end_area, key_points, notes FROM route")
        routes = cursor.fetchall()
        
        routes_data = []
        for route in routes:
            name, fare, start_area, end_area, key_points_json, notes = route
            try:
                key_points = json.loads(key_points_json) if key_points_json else []
            except:
                key_points = []
            
            route_data = {
                'routeName': name,
                'fare': f"{fare} جنيه مصري",
                'startArea': start_area or '',
                'endArea': end_area or '',
                'keyPoints': key_points,
                'notes': notes or ''
            }
            routes_data.append(route_data)
        
        conn.close()
        return routes_data
    except Exception as e:
        print(f"خطأ في قراءة الخطوط من قاعدة البيانات: {e}")
        return []

def get_neighborhoods_from_db():
    """قراءة جميع الأحياء والأماكن من قاعدة البيانات"""
    try:
        conn = sqlite3.connect('instance/admin_bot.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT neighborhood, category, name FROM location ORDER BY neighborhood, category, name")
        locations = cursor.fetchall()
        
        neighborhood_data = {}
        for location in locations:
            neighborhood, category, name = location
            
            if neighborhood not in neighborhood_data:
                neighborhood_data[neighborhood] = {}
            
            if category not in neighborhood_data[neighborhood]:
                neighborhood_data[neighborhood][category] = []
            
            neighborhood_data[neighborhood][category].append(name)
        
        conn.close()
        return neighborhood_data
    except Exception as e:
        print(f"خطأ في قراءة الأماكن من قاعدة البيانات: {e}")
        return {}

def search_locations_by_name(location_name: str, limit: int = 10):
    """البحث عن الأماكن بالاسم مع معلومات التصنيف"""
    try:
        conn = sqlite3.connect('instance/admin_bot.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # البحث بالتطابق الجزئي
        query = """
        SELECT name, neighborhood, category, coordinates, 
               location_type, walking_distance, location_notes
        FROM locations 
        WHERE name LIKE ? OR name LIKE ? OR name LIKE ?
        ORDER BY 
            CASE 
                WHEN name = ? THEN 1
                WHEN name LIKE ? THEN 2
                ELSE 3
            END,
            location_type DESC
        LIMIT ?
        """
        
        search_term = f"%{location_name}%"
        exact_term = location_name
        start_term = f"{location_name}%"
        
        cursor.execute(query, (search_term, start_term, exact_term, exact_term, start_term, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'name': row['name'],
                'neighborhood': row['neighborhood'],
                'category': row['category'],
                'coordinates': row['coordinates'],
                'location_type': row['location_type'] or 'direct',
                'walking_distance': row['walking_distance'] or 0,
                'location_notes': row['location_notes']
            })
        
        conn.close()
        return results
        
    except Exception as e:
        print(f"خطأ في البحث عن الأماكن: {e}")
        return []

def get_routes_serving_location(location_name: str):
    """الحصول على الخطوط التي تخدم مكان معين"""
    try:
        conn = sqlite3.connect('instance/admin_bot.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # البحث في نقاط الخطوط الأساسية
        query = """
        SELECT id, name, start_area, end_area, key_points, fare, notes
        FROM routes 
        WHERE key_points LIKE ?
        ORDER BY name
        """
        
        cursor.execute(query, (f"%{location_name}%",))
        
        results = []
        for row in cursor.fetchall():
            # فحص إضافي للتأكد من وجود المكان في النقاط
            key_points = json.loads(row['key_points']) if row['key_points'] else []
            location_found = any(location_name.lower() in point.lower() for point in key_points if isinstance(point, str))
            
            if location_found:
                results.append({
                    'id': row['id'],
                    'name': row['name'],
                    'start_area': row['start_area'],
                    'end_area': row['end_area'],
                    'key_points': key_points,
                    'fare': row['fare'],
                    'notes': row['notes']
                })
        
        conn.close()
        return results
        
    except Exception as e:
        print(f"خطأ في البحث عن الخطوط: {e}")
        return []

def find_route_connections(from_route_id: int, to_route_id: int):
    """البحث عن الروابط بين خطين"""
    try:
        conn = sqlite3.connect('instance/admin_bot.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
        SELECT rc.connection_point, rc.walking_time, rc.connection_notes,
               r1.name as from_route_name, r2.name as to_route_name
        FROM route_connections rc
        JOIN routes r1 ON rc.from_route_id = r1.id
        JOIN routes r2 ON rc.to_route_id = r2.id
        WHERE (rc.from_route_id = ? AND rc.to_route_id = ?) 
           OR (rc.from_route_id = ? AND rc.to_route_id = ?)
        """
        
        cursor.execute(query, (from_route_id, to_route_id, to_route_id, from_route_id))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'connection_point': row['connection_point'],
                'walking_time': row['walking_time'],
                'connection_notes': row['connection_notes'],
                'from_route_name': row['from_route_name'],
                'to_route_name': row['to_route_name']
            })
        
        conn.close()
        return results
        
    except Exception as e:
        print(f"خطأ في البحث عن روابط المواصلات: {e}")
        return []

def find_best_route_with_transfers(start_location: str, end_location: str):
    """البحث عن أفضل مسار مع إمكانية التحويل"""
    
    # البحث عن الأماكن أولاً
    start_locations = search_locations_by_name(start_location, 5)
    end_locations = search_locations_by_name(end_location, 5)
    
    if not start_locations or not end_locations:
        return {
            'status': 'no_locations_found',
            'message': 'لم يتم العثور على إحدى المواقع أو كليهما'
        }
    
    # اختيار أفضل تطابق
    start_loc = start_locations[0]
    end_loc = end_locations[0]
    
    # البحث عن الخطوط المباشرة
    start_routes = get_routes_serving_location(start_loc['name'])
    end_routes = get_routes_serving_location(end_loc['name'])
    
    # البحث عن مسارات مباشرة
    direct_routes = []
    for start_route in start_routes:
        for end_route in end_routes:
            if start_route['id'] == end_route['id']:
                # نفس الخط - تحقق من الترتيب
                key_points = start_route['key_points']
                start_indices = [i for i, point in enumerate(key_points) 
                               if start_loc['name'].lower() in point.lower()]
                end_indices = [i for i, point in enumerate(key_points) 
                             if end_loc['name'].lower() in point.lower()]
                
                if start_indices and end_indices:
                    if any(s_idx < e_idx for s_idx in start_indices for e_idx in end_indices):
                        direct_routes.append({
                            'route': start_route,
                            'start_location': start_loc,
                            'end_location': end_loc
                        })
    
    if direct_routes:
        return {
            'status': 'direct_route_found',
            'routes': direct_routes
        }
    
    # البحث عن مسارات بالتحويل
    transfer_routes = []
    
    for start_route in start_routes:
        for end_route in end_routes:
            if start_route['id'] != end_route['id']:
                # البحث عن رابط بين الخطين
                route_connections = find_route_connections(start_route['id'], end_route['id'])
                
                for connection in route_connections:
                    transfer_routes.append({
                        'start_route': start_route,
                        'end_route': end_route,
                        'connection': connection,
                        'start_location': start_loc,
                        'end_location': end_loc
                    })
    
    if transfer_routes:
        return {
            'status': 'transfer_route_found',
            'routes': transfer_routes
        }
    
    return {
        'status': 'no_route_found',
        'message': 'لم يتم العثور على مسار مناسب',
        'start_locations': start_locations,
        'end_locations': end_locations
    }

def update_bot_data():
    """تحديث ملف البيانات للبوت"""
    try:
        routes_data = get_routes_from_db()
        neighborhood_data = get_neighborhoods_from_db()
        
        # كتابة البيانات في ملف data_dynamic.py
        with open('data_dynamic.py', 'w', encoding='utf-8') as f:
            f.write('# -*- coding: utf-8 -*-\n')
            f.write('"""\n')
            f.write('ملف البيانات المتغير - يتم تحديثه تلقائياً من قاعدة البيانات\n')
            f.write('"""\n\n')
            
            f.write('# بيانات الخطوط من قاعدة البيانات\n')
            f.write(f'routes_data = {repr(routes_data)}\n\n')
            
            f.write('# بيانات الأحياء من قاعدة البيانات\n')
            f.write(f'neighborhood_data = {repr(neighborhood_data)}\n')
        
        print("✅ تم تحديث بيانات البوت بنجاح!")
        return True
    except Exception as e:
        print(f"❌ خطأ في تحديث بيانات البوت: {e}")
        return False

if __name__ == "__main__":
    update_bot_data()