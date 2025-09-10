# -*- coding: utf-8 -*-
"""
ملف الدوال المساعدة للبوت
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any, Optional

def build_keyboard(items: List, prefix: str, back_target: Optional[str] = None) -> InlineKeyboardMarkup:
    """بناء لوحة المفاتيح التفاعلية"""
    keyboard = []
    row = []
    max_per_row = 2
    
    for item_data in items:
        if isinstance(item_data, dict):
            item_text = item_data.get("name")
            callback_identifier = item_text
        elif isinstance(item_data, str):
            item_text = item_data
            callback_identifier = item_data
        else:
            continue
            
        if item_text and callback_identifier:
            # تقصير البيانات لتجنب خطأ Telegram (64 byte limit)
            callback_identifier = callback_identifier[:30] if len(callback_identifier) > 30 else callback_identifier
            callback_data_str = f"{prefix}:{callback_identifier}"
            
            # التأكد من أن البيانات لا تتجاوز 64 بايت
            if len(callback_data_str.encode('utf-8')) <= 64:
                row.append(InlineKeyboardButton(item_text, callback_data=callback_data_str))
                
                if len(row) == max_per_row:
                    keyboard.append(row)
                    row = []
    
    if row:
        keyboard.append(row)
    
    # إضافة أزرار التنقل
    nav_buttons = []
    if back_target:
        nav_buttons.append(InlineKeyboardButton("⬅️ رجوع", callback_data=f"back_to_{back_target}"))
    nav_buttons.append(InlineKeyboardButton("❌ إلغاء", callback_data="cancel_action"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    return InlineKeyboardMarkup(keyboard)

def find_route_logic(start_landmark: str, end_landmark: str, routes_data: List[Dict]) -> str:
    """
    البحث عن أفضل مسار بين معلمين - محسن مع دعم الأماكن القريبة
    """
    
    # البحث عن المسارات المباشرة
    direct_routes = []
    nearby_routes = []  # للأماكن القريبة
    
    # تحسين البحث - استخدام مطابقة أفضل
    def find_location_in_route(location: str, route_points: List[str]) -> List[int]:
        """البحث عن مكان في نقاط الخط مع مطابقة محسنة"""
        indices = []
        location_clean = location.lower().strip()
        
        for i, point in enumerate(route_points):
            if isinstance(point, str):
                point_clean = point.lower().strip()
                # مطابقة دقيقة أولاً
                if location_clean == point_clean:
                    indices.append((i, 'exact'))
                # مطابقة جزئية
                elif location_clean in point_clean or point_clean in location_clean:
                    indices.append((i, 'partial'))
                # مطابقة بالكلمات المفتاحية
                elif any(word in point_clean for word in location_clean.split() if len(word) > 2):
                    indices.append((i, 'keyword'))
        
        return indices
    
    for route in routes_data:
        key_points = route.get('keyPoints', [])
        if not key_points:
            continue
            
        # البحث المحسن عن النقاط
        start_matches = find_location_in_route(start_landmark, key_points)
        end_matches = find_location_in_route(end_landmark, key_points)
        
        if start_matches and end_matches:
            # التحقق من الترتيب الصحيح
            valid_routes = []
            for start_idx, start_type in start_matches:
                for end_idx, end_type in end_matches:
                    if start_idx < end_idx:
                        valid_routes.append({
                            'start_idx': start_idx,
                            'end_idx': end_idx,
                            'start_type': start_type,
                            'end_type': end_type,
                            'start_point': key_points[start_idx],
                            'end_point': key_points[end_idx]
                        })
            
            if valid_routes:
                # ترتيب حسب دقة المطابقة
                priority_order = {'exact': 3, 'partial': 2, 'keyword': 1}
                valid_routes.sort(key=lambda x: priority_order.get(x['start_type'], 0) + priority_order.get(x['end_type'], 0), reverse=True)
                
                direct_routes.append({
                    'route': route,
                    'matches': valid_routes
                })
    
    if direct_routes:
        result = "🚌 **تم العثور على مسارات مباشرة:**\n\n"
        for i, route_info in enumerate(direct_routes, 1):
            route = route_info['route']
            best_match = route_info['matches'][0]  # أفضل مطابقة
            
            result += f"{i}. **{route.get('routeName', 'خط غير محدد')}**\n"
            result += f"   🚏 نقطة الركوب: {best_match['start_point']}\n"
            result += f"   🛑 نقطة النزول: {best_match['end_point']}\n"
            result += f"   💰 التعريفة: {route.get('fare', 'غير محددة')}\n"
            
            # إضافة معلومات الأماكن القريبة إذا كانت المطابقة جزئية
            if best_match['start_type'] != 'exact':
                result += f"   🚶 المكان قريب من: {best_match['start_point']} (5 دقائق مشي تقريباً)\n"
            if best_match['end_type'] != 'exact':
                result += f"   🚶 الوجهة قريبة من: {best_match['end_point']} (5 دقائق مشي تقريباً)\n"
            
            if route.get('notes'):
                result += f"   📝 ملاحظات: {route.get('notes')}\n"
            result += "\n"
        
        result += "💡 **نصيحة:** تأكد من السائق للتأكيد من نقاط الركوب والنزول الصحيحة.\n"
        result += "🚶 **للأماكن القريبة:** المشي لمدة 5 دقائق تقريباً."
        return result
    
    else:
        # البحث عن مسارات بتبديل
        potential_connections = []
        
        for route1 in routes_data:
            for route2 in routes_data:
                if route1 == route2:
                    continue
                
                # البحث عن نقاط مشتركة للتبديل
                route1_points = route1.get('keyPoints', [])
                route2_points = route2.get('keyPoints', [])
                
                # هل يخدم route1 نقطة البداية؟
                route1_has_start = any(start_landmark.lower() in str(point).lower() 
                                     for point in route1_points)
                
                # هل يخدم route2 نقطة النهاية؟ 
                route2_has_end = any(end_landmark.lower() in str(point).lower() 
                                   for point in route2_points)
                
                if route1_has_start and route2_has_end:
                    # البحث عن نقاط التبديل المشتركة
                    common_points = []
                    for p1 in route1_points:
                        for p2 in route2_points:
                            if isinstance(p1, str) and isinstance(p2, str):
                                if p1.lower() == p2.lower() or \
                                   (len(p1) > 5 and len(p2) > 5 and 
                                    (p1.lower() in p2.lower() or p2.lower() in p1.lower())):
                                    common_points.append(p1)
                    
                    if common_points:
                        potential_connections.append({
                            'route1': route1,
                            'route2': route2,
                            'transfer_points': common_points
                        })
        
        if potential_connections:
            result = "🔄 **مسارات بتبديل متاحة:**\n\n"
            for i, conn in enumerate(potential_connections[:3], 1):  # أول 3 خيارات
                result += f"{i}. **{conn['route1'].get('routeName')}** ← **{conn['route2'].get('routeName')}**\n"
                result += f"   🔄 نقاط التبديل: {', '.join(conn['transfer_points'][:2])}\n"
                fare1 = conn['route1'].get('fare', 'غير محددة')
                fare2 = conn['route2'].get('fare', 'غير محددة') 
                result += f"   💰 التعريفة: {fare1} + {fare2}\n\n"
            
            result += "📝 **ملاحظة:** قد تحتاج لسؤال السائق عن أفضل نقاط التبديل."
            return result
        
        else:
            return f"""
❌ **عذراً، لم أجد مساراً مباشراً بين {start_landmark} و {end_landmark}**

💡 **اقتراحات:**
• تأكد من صحة أسماء الأماكن
• جرب البحث عن معالم قريبة من وجهتك
• استخدم البحث الذكي بكتابة السؤال مباشرة
• أو استخدم وسائل مواصلات أخرى (تاكسي، أوبر، إلخ)

🔍 **للمساعدة:** جرب البحث الذكي واكتب مثلاً "إزاي أروح من [مكان قريب من {start_landmark}] لـ [مكان قريب من {end_landmark}]؟"
            """

def validate_callback_data(callback_data: str) -> bool:
    """التحقق من صحة بيانات الCallback"""
    if not callback_data:
        return False
    
    # التحقق من الطول
    if len(callback_data.encode('utf-8')) > 64:
        return False
    
    # التحقق من التنسيق
    if ':' not in callback_data:
        return False
    
    return True

def format_time_ago(timestamp_str: str) -> str:
    """تنسيق الوقت النسبي"""
    try:
        from datetime import datetime
        
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now(timestamp.tzinfo)
        
        diff = now - timestamp
        
        if diff.days > 0:
            return f"منذ {diff.days} يوم"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"منذ {hours} ساعة"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"منذ {minutes} دقيقة"
        else:
            return "الآن"
    except:
        return "غير معروف"