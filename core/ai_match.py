"""
AI Match — Scoring compatibilité bien et préférences client
Algorithme de recommandation pour INTELYA HAVEN

Score calculé sur 100 points :
- Budget : 30 points
- Localisation : 25 points
- Nombre de chambres : 20 points
- Équipements : 15 points
- Type de bien : 10 points
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


def calculate_ai_match_score(property_obj, user_preferences):
    """
    Calcule le score de compatibilité entre un bien et les préférences d'un client.
    Retourne un score entre 0 et 100.
    """
    score = 0

    # 1. BUDGET (30 points)
    budget_max = user_preferences.get('budget_max', 0)
    budget_min = user_preferences.get('budget_min', 0)
    prop_price = float(property_obj.price)

    if budget_max > 0:
        if prop_price <= budget_max:
            if budget_min > 0 and prop_price >= budget_min:
                score += 30  # Dans la fourchette exacte
            elif prop_price <= budget_max * 0.8:
                score += 25  # En dessous du budget — très bien
            else:
                score += 20  # Dans le budget
        elif prop_price <= budget_max * 1.1:
            score += 10  # Légèrement au-dessus
    else:
        score += 15  # Pas de budget défini — score neutre

    # 2. LOCALISATION (25 points)
    preferred_city  = user_preferences.get('city', '').lower()
    preferred_zones = [z.lower() for z in user_preferences.get('neighborhoods', [])]
    prop_city  = property_obj.city.lower()
    prop_zone  = property_obj.neighborhood.lower()

    if preferred_city and preferred_city == prop_city:
        score += 15
        if preferred_zones and any(z in prop_zone or prop_zone in z for z in preferred_zones):
            score += 10  # Quartier préféré aussi
        else:
            score += 5   # Bonne ville mais autre quartier
    elif not preferred_city:
        score += 10  # Pas de préférence de ville

    # 3. NOMBRE DE CHAMBRES (20 points)
    preferred_bedrooms = user_preferences.get('bedrooms', 0)
    prop_bedrooms      = property_obj.bedrooms

    if preferred_bedrooms > 0:
        if prop_bedrooms == preferred_bedrooms:
            score += 20  # Exactement le bon nombre
        elif abs(prop_bedrooms - preferred_bedrooms) == 1:
            score += 12  # +/- 1 chambre
        elif prop_bedrooms > preferred_bedrooms:
            score += 8   # Plus de chambres que demandé
    else:
        score += 10  # Pas de préférence

    # 4. ÉQUIPEMENTS AFRICAINS (15 points)
    wants_generator = user_preferences.get('generator', False)
    wants_parking   = user_preferences.get('parking', False)
    wants_borehole  = user_preferences.get('borehole', False)
    wants_furnished = user_preferences.get('furnished', False)

    amenity_score = 0
    amenity_count = sum([wants_generator, wants_parking, wants_borehole, wants_furnished])

    if amenity_count > 0:
        if wants_generator and property_obj.has_generator:
            amenity_score += 1
        if wants_parking and property_obj.has_parking:
            amenity_score += 1
        if wants_borehole and property_obj.has_borehole:
            amenity_score += 1
        if wants_furnished and property_obj.is_furnished:
            amenity_score += 1
        score += int((amenity_score / amenity_count) * 15)
    else:
        score += 8  # Pas de préférence d'équipements

    # 5. TYPE DE BIEN (10 points)
    preferred_type = user_preferences.get('property_type', '')
    if preferred_type and preferred_type == property_obj.property_type:
        score += 10
    elif not preferred_type:
        score += 5

    return min(score, 100)  # Max 100


def get_recommendations_for_user(user, limit=10):
    """
    Retourne les biens recommandés pour un utilisateur
    basé sur son historique et ses préférences.
    Cache Redis 10 minutes.
    """
    cache_key = f"recommendations:{user.id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        from apps.properties.models import Property
        from apps.visits.models import VisitRequest

        # Analyser l'historique des visites pour déduire les préférences
        past_visits = VisitRequest.objects.filter(
            client=user, status__in=['completed', 'scheduled']
        ).select_related('visit_property').order_by('-created_at')[:10]

        # Construire les préférences automatiquement depuis l'historique
        preferences = _build_preferences_from_history(user, past_visits)

        # Récupérer les biens disponibles
        available_properties = Property.objects.filter(
            status='available'
        ).select_related('agent', 'owner').prefetch_related('photos')[:200]

        # Calculer le score pour chaque bien
        scored_properties = []
        for prop in available_properties:
            score = calculate_ai_match_score(prop, preferences)
            if score > 20:  # Minimum 20% de compatibilité
                scored_properties.append({
                    'property_id': str(prop.id),
                    'score': score,
                    'property': prop
                })

        # Trier par score décroissant
        scored_properties.sort(key=lambda x: x['score'], reverse=True)
        top_properties = scored_properties[:limit]

        cache.set(cache_key, top_properties, 600)  # Cache 10 minutes
        return top_properties

    except Exception as e:
        logger.error(f"[AI MATCH] Erreur recommendations: {e}")
        return []


def _build_preferences_from_history(user, past_visits):
    """
    Déduit les préférences d'un utilisateur depuis son historique
    """
    preferences = {}

    # Préférences sauvegardées manuellement
    if hasattr(user, 'preferences'):
        prefs = user.preferences
        preferences.update({
            'budget_min': getattr(prefs, 'budget_min', 0),
            'budget_max': getattr(prefs, 'budget_max', 0),
            'city': getattr(prefs, 'preferred_city', ''),
            'bedrooms': getattr(prefs, 'preferred_bedrooms', 0),
            'property_type': getattr(prefs, 'preferred_type', ''),
        })

    # Déduire depuis l'historique des visites si pas de préférences
    if past_visits and not preferences.get('city'):
        cities      = [v.visit_property.city for v in past_visits if v.visit_property]
        neighborhoods = [v.visit_property.neighborhood for v in past_visits if v.visit_property]
        prices      = [float(v.visit_property.price) for v in past_visits if v.visit_property]
        bedrooms    = [v.visit_property.bedrooms for v in past_visits if v.visit_property]

        if cities:
            from collections import Counter
            preferences['city']          = Counter(cities).most_common(1)[0][0]
            preferences['neighborhoods'] = list(set(neighborhoods))
        if prices:
            preferences['budget_max'] = max(prices) * 1.2
            preferences['budget_min'] = min(prices) * 0.8
        if bedrooms:
            preferences['bedrooms'] = round(sum(bedrooms) / len(bedrooms))

    return preferences


def invalidate_user_recommendations(user_id):
    """Invalide le cache des recommandations d'un utilisateur"""
    cache.delete(f"recommendations:{user_id}")
