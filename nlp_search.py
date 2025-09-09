# -*- coding: utf-8 -*-
"""
نظام معالجة اللغة الطبيعية للبحث المباشر في المواصلات
"""

import re
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher

# استيراد مساعد قاعدة البيانات
try:
    from database_helper import (
        search_locations_by_name, 
        find_best_route_with_transfers,
        get_routes_serving_location
    )
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

class NLPSearchSystem:
    def __init__(self, neighborhood_data: Dict):
        self.neighborhood_data = neighborhood_data
        self.landmarks_index = self._build_landmarks_index()
        
        # كلمات ربط عربية شائعة
        self.from_keywords = ['من', 'من عند', 'بدءاً من', 'انطلاقاً من', 'ابتداءً من']
        self.to_keywords = ['إلى', 'الى', 'لـ', 'ل', 'حتى', 'وصولاً إلى', 'باتجاه']
        self.question_keywords = ['إزاي', 'ازاي', 'كيف', 'طريقة', 'أروح', 'اروح', 'أوصل', 'اوصل']
    
    def _build_landmarks_index(self) -> Dict[str, Dict]:
        """بناء فهرس لجميع المعالم للبحث السريع"""
        index = {}
        for neighborhood, categories in self.neighborhood_data.items():
            for category, landmarks in categories.items():
                for landmark in landmarks:
                    if isinstance(landmark, dict):
                        name = landmark.get('name', '').lower()
                        index[name] = {
                            'neighborhood': neighborhood,
                            'category': category,
                            'data': landmark
                        }
                    elif isinstance(landmark, str):
                        name = landmark.lower()
                        index[name] = {
                            'neighborhood': neighborhood,
                            'category': category,
                            'data': {'name': landmark, 'served_by': {}}
                        }
        return index
    
    def similarity_score(self, text1: str, text2: str) -> float:
        """حساب درجة التشابه بين نصين"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def find_best_match(self, query: str, min_score: float = 0.6) -> Optional[Dict]:
        """البحث عن أفضل تطابق لمعلم معين"""
        query = query.lower().strip()
        best_match = None
        best_score = min_score
        
        for landmark_name, landmark_info in self.landmarks_index.items():
            score = self.similarity_score(query, landmark_name)
            if score > best_score:
                best_score = score
                best_match = {
                    'name': landmark_name,
                    'score': score,
                    'info': landmark_info
                }
        
        return best_match
    
    def extract_locations_from_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """استخراج نقطتي البداية والوجهة من النص"""
        text = text.replace('؟', '').replace('?', '').strip()
        
        # البحث عن أنماط "من X إلى Y"
        from_to_pattern = r'(?:من|من عند)\s+(.+?)\s+(?:إلى|الى|لـ|ل|حتى)\s+(.+?)(?:\s|$)'
        match = re.search(from_to_pattern, text)
        
        if match:
            start_location = match.group(1).strip()
            end_location = match.group(2).strip()
            return start_location, end_location
        
        # البحث عن أنماط "إزاي أروح X"
        how_to_go_pattern = r'(?:إزاي|ازاي|كيف)\s+(?:أروح|اروح|أوصل|اوصل)\s+(.+?)(?:\s|$)'
        match = re.search(how_to_go_pattern, text)
        
        if match:
            destination = match.group(1).strip()
            return None, destination  # البداية غير محددة
        
        # البحث عن مواقع بكلمات ربط
        parts = []
        for keyword in self.from_keywords + self.to_keywords:
            if keyword in text:
                parts = text.split(keyword)
                break
        
        if len(parts) >= 2:
            potential_start = parts[0].strip()
            potential_end = parts[1].strip()
            
            # تنظيف النص من كلمات الاستفهام
            for q_word in self.question_keywords:
                potential_start = potential_start.replace(q_word, '').strip()
                potential_end = potential_end.replace(q_word, '').strip()
            
            return potential_start or None, potential_end or None
        
        return None, None
    
    def search_route_from_text(self, text: str) -> Dict:
        """البحث عن مسار من النص المكتوب"""
        # أولاً البحث عن المناطق السكنية المبسطة
        residential_match = self.parse_residential_areas(text)
        if residential_match:
            return residential_match
        
        start_text, end_text = self.extract_locations_from_text(text)
        
        result = {
            'status': 'error',
            'message': 'لم أتمكن من فهم طلبك. يرجى المحاولة مرة أخرى.',
            'start_location': None,
            'end_location': None,
            'suggestions': []
        }
        
        if start_text:
            start_match = self.find_best_match(start_text)
            if start_match:
                result['start_location'] = start_match
        
        if end_text:
            end_match = self.find_best_match(end_text)
            if end_match:
                result['end_location'] = end_match
        
        # إذا تم العثور على موقع واحد على الأقل
        if result['start_location'] or result['end_location']:
            result['status'] = 'partial_match'
            if result['start_location'] and result['end_location']:
                result['status'] = 'success'
                result['message'] = f"✅ تم العثور على مسار من {result['start_location']['name']} إلى {result['end_location']['name']}"
            elif result['start_location']:
                result['message'] = f"✅ تم العثور على نقطة البداية: {result['start_location']['name']}. يرجى تحديد الوجهة."
            else:
                result['message'] = f"✅ تم العثور على الوجهة: {result['end_location']['name']}. يرجى تحديد نقطة البداية."
        
        return result

    def get_suggestions_for_text(self, text: str, limit: int = 5) -> List[str]:
        """الحصول على اقتراحات للنص المدخل"""
        text = text.lower().strip()
        suggestions = []
        
        for landmark_name, landmark_info in self.landmarks_index.items():
            if text in landmark_name:
                suggestion = f"{landmark_info['data'].get('name', landmark_name)} - {landmark_info['neighborhood']}"
                if suggestion not in suggestions:
                    suggestions.append(suggestion)
            
            if len(suggestions) >= limit:
                break
        
        return suggestions

    def parse_residential_areas(self, query: str) -> Dict:
        """تحليل المناطق السكنية المبسطة"""
        # إزالة كلمات مثل "السكنية"، "منطقة"
        query = re.sub(r'\b(السكنية|السكنيه|منطقة|منطقه)\b', '', query)
        query = query.strip()
        
        # البحث عن نمط "من X لـ Y" أو "X للـ Y" أو "X لـ Y"
        patterns = [
            r'من\s+(.+?)\s+(?:لـ|ل|إلى|الى)\s+(.+)',
            r'(.+?)\s+(?:للـ|للـ|لـ|ل)\s+(.+)',
            r'(.+?)\s+إلى\s+(.+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                start_area = match.group(1).strip()
                end_area = match.group(2).strip()
                
                # البحث عن أقرب مطابقة للمناطق السكنية
                start_match = self.find_residential_area(start_area)
                end_match = self.find_residential_area(end_area)
                
                if start_match and end_match:
                    return {
                        'status': 'success',
                        'type': 'residential_route',
                        'start_area': start_match,
                        'end_area': end_match,
                        'message': f'🚌 البحث عن مسار من منطقة {start_match} إلى منطقة {end_match}',
                        'confidence': 0.85
                    }
        
        return None
    
    def find_residential_area(self, area_name: str) -> str:
        """البحث عن المنطقة السكنية الأقرب"""
        area_name = area_name.lower().strip()
        
        # قائمة المناطق السكنية الشائعة
        residential_areas = [
            "بوروتكس", "السلام", "المناخ", "الشرق", "العرب",
            "الزهور", "المنطقة الأولى", "المنطقة الثانية", 
            "المنطقة الثالثة", "المنطقة الرابعة", "المنطقة الخامسة", "المنطقة السادسة",
            "منطقة شمال الحرية", "قشلاق السواحل", "حي ناصر"
        ]
        
        # البحث المباشر
        for area in residential_areas:
            if area_name == area.lower():
                return area
        
        # البحث الجزئي
        for area in residential_areas:
            if area_name in area.lower() or area.lower() in area_name:
                return area
        
        # البحث بالتشابه
        best_match = None
        best_ratio = 0.6
        
        for area in residential_areas:
            ratio = SequenceMatcher(None, area_name, area.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = area
        
        return best_match

    def enhanced_search_with_database(self, query_text: str) -> Dict:
        """البحث المحسن باستخدام قاعدة البيانات"""
        if not DATABASE_AVAILABLE:
            return self.search(query_text)
        
        try:
            # استخراج المواقع من النص
            start_location, end_location = self.extract_locations_from_text(query_text)
            
            if not start_location or not end_location:
                return {
                    'success': False,
                    'message': 'لم أتمكن من فهم نقطتي البداية والوجهة من رسالتك. يرجى إعادة كتابة الطلب بوضوح.'
                }
            
            # البحث في قاعدة البيانات
            route_result = find_best_route_with_transfers(start_location, end_location)
            
            if route_result['status'] == 'direct_route_found':
                return self._format_direct_route_result(route_result['routes'])
            elif route_result['status'] == 'transfer_route_found':
                return self._format_transfer_route_result(route_result['routes'])
            elif route_result['status'] == 'no_locations_found':
                return {
                    'success': False,
                    'message': f'لم أجد المواقع التالية: {start_location} أو {end_location}. يرجى التأكد من كتابة الأسماء بشكل صحيح.'
                }
            else:
                return self._format_no_route_result(route_result, start_location, end_location)
                
        except Exception as e:
            # في حالة حدوث خطأ، استخدم النظام القديم
            return self.search(query_text)

    def _format_direct_route_result(self, routes: List[Dict]) -> Dict:
        """تنسيق نتائج المسارات المباشرة"""
        message = "🚌 **تم العثور على مسارات مباشرة:**\n\n"
        
        for i, route_info in enumerate(routes, 1):
            route = route_info['route']
            start_loc = route_info['start_location']
            end_loc = route_info['end_location']
            
            message += f"{i}. **{route['name']}**\n"
            message += f"   🚏 من: {start_loc['name']}"
            
            # إضافة معلومات التصنيف مع تقدير زمني
            if start_loc['location_type'] == 'nearby':
                distance = start_loc['walking_distance']
                walking_time = max(1, round(distance / 80))  # تقريباً 80 متر في الدقيقة
                message += f" (🚶 مشي {distance}م ~ {walking_time} دق)"
            
            message += f"\n   🛑 إلى: {end_loc['name']}"
            
            if end_loc['location_type'] == 'nearby':
                distance = end_loc['walking_distance']
                walking_time = max(1, round(distance / 80))  # تقريباً 80 متر في الدقيقة
                message += f" (🚶 مشي {distance}م ~ {walking_time} دق)"
            
            message += f"\n   💰 التعريفة: {route['fare']} جنيه\n"
            
            # إضافة الملاحظات الخاصة بالموقع
            if start_loc.get('location_notes'):
                message += f"   📝 ملاحظة البداية: {start_loc['location_notes']}\n"
            if end_loc.get('location_notes'):
                message += f"   📝 ملاحظة الوجهة: {end_loc['location_notes']}\n"
            
            if route.get('notes'):
                message += f"   📋 ملاحظات الخط: {route['notes']}\n"
            
            message += "\n"
        
        message += "💡 **نصيحة:** تأكد من السائق للتأكيد من نقاط الركوب والنزول الصحيحة."
        
        return {
            'success': True,
            'message': message,
            'route_type': 'direct'
        }

    def _format_transfer_route_result(self, routes: List[Dict]) -> Dict:
        """تنسيق نتائج المسارات بالتحويل"""
        message = "🔄 **تم العثور على مسارات بالتحويل:**\n\n"
        
        for i, route_info in enumerate(routes, 1):
            start_route = route_info['start_route']
            end_route = route_info['end_route']
            connection = route_info['connection']
            start_loc = route_info['start_location']
            end_loc = route_info['end_location']
            
            message += f"{i}. **المسار بالتحويل:**\n"
            message += f"   🚌 الخط الأول: {start_route['name']}\n"
            message += f"   🚏 اركب من: {start_loc['name']}"
            
            if start_loc['location_type'] == 'nearby':
                distance = start_loc['walking_distance']
                walking_time = max(1, round(distance / 80))
                message += f" (🚶 {distance}م ~ {walking_time}د)"
            
            message += f"\n   🔄 انزل عند: {connection['connection_point']}\n"
            message += f"   🚶 امش {connection['walking_time']} دقائق للوصول للخط التالي\n"
            
            if connection.get('connection_notes'):
                message += f"   📝 ملاحظة التحويل: {connection['connection_notes']}\n"
            
            message += f"   🚌 الخط الثاني: {end_route['name']}\n"
            message += f"   🛑 انزل عند: {end_loc['name']}"
            
            if end_loc['location_type'] == 'nearby':
                message += f" (مشي {end_loc['walking_distance']}م)"
            
            total_fare = (start_route.get('fare', 0) or 0) + (end_route.get('fare', 0) or 0)
            message += f"\n   💰 إجمالي التعريفة: {total_fare} جنيه\n"
            message += f"   ⏱️ وقت التحويل: {connection['walking_time']} دقيقة\n\n"
        
        message += "⚠️ **تنبيه:** تأكد من مواعيد المواصلات وخطط لوقت إضافي للتحويل."
        
        return {
            'success': True,
            'message': message,
            'route_type': 'transfer'
        }

    def _format_no_route_result(self, route_result: Dict, start_location: str, end_location: str) -> Dict:
        """تنسيق نتيجة عدم وجود مسار"""
        message = f"❌ لم أجد مسار مباشر أو بالتحويل من {start_location} إلى {end_location}.\n\n"
        
        if 'start_locations' in route_result and route_result['start_locations']:
            message += "🔍 **مواقع مشابهة لنقطة البداية:**\n"
            for loc in route_result['start_locations'][:3]:
                message += f"   • {loc['name']} ({loc['neighborhood']})\n"
        
        if 'end_locations' in route_result and route_result['end_locations']:
            message += "\n🔍 **مواقع مشابهة للوجهة:**\n"
            for loc in route_result['end_locations'][:3]:
                message += f"   • {loc['name']} ({loc['neighborhood']})\n"
        
        message += "\n💡 يرجى التحقق من كتابة الأسماء أو جرب استخدام القائمة التفاعلية."
        
        return {
            'success': False,
            'message': message
        }