import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from core.utils import generate_referral_code

User = get_user_model()


@pytest.fixture(autouse=True)
def reset_axes():
    """Vide les tentatives Axes entre chaque test"""
    try:
        from axes.models import AccessAttempt, AccessLog
        AccessAttempt.objects.all().delete()
        AccessLog.objects.all().delete()
    except Exception:
        pass
    yield
    try:
        from axes.models import AccessAttempt, AccessLog
        AccessAttempt.objects.all().delete()
        AccessLog.objects.all().delete()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def disable_throttling(settings):
    """Désactive le throttling, axes et ratelimit pour tous les tests"""
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {
            "anon": "10000/hour",
            "user": "10000/hour",
            "auth": "10000/minute",
            "payments": "10000/hour",
            "uploads": "10000/hour",
            "search": "10000/hour",
        },
    }
    settings.AXES_ENABLED = False
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def create_user():
    def _create_user(**kwargs):
        defaults = {
            "first_name": "Test",
            "last_name": "User",
            "password": "TestPass123!",
            "is_phone_verified": True,
            "terms_accepted": True,
        }
        defaults.update(kwargs)
        password = defaults.pop("password")

        if "referral_code" not in defaults:
            code = generate_referral_code()
            while User.objects.filter(referral_code=code).exists():
                code = generate_referral_code()
            defaults["referral_code"] = code

        user = User(**defaults)
        user.set_password(password)
        user.save()
        return user
    return _create_user


@pytest.fixture
def client_user(create_user):
    return create_user(
        email="client@test.com",
        phone="+237670000001",
        role="client",
    )


@pytest.fixture
def agent_user(create_user):
    user = create_user(
        email="agent@test.com",
        phone="+237670000002",
        role="agent",
        is_validated=True,
    )
    from apps.agents.models import AgentProfile
    AgentProfile.objects.get_or_create(
        user=user,
        defaults={
            "working_city": "Douala",
            "commission_type": "percent",
            "commission_value": 10,
            "visit_fee": 5000,
            "visit_fee_is_free": False,
        }
    )
    return user


@pytest.fixture
def owner_user(create_user):
    user = create_user(
        email="owner@test.com",
        phone="+237670000003",
        role="owner",
        is_validated=True,
    )
    from apps.owners.models import OwnerProfile
    OwnerProfile.objects.get_or_create(
        user=user,
        defaults={"mtn_momo_number": "+237670000003"}
    )
    return user


@pytest.fixture
def admin_user(create_user):
    return create_user(
        email="admin@test.com",
        phone="+237670000004",
        role="admin",
        is_validated=True,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def property_obj(owner_user, agent_user):
    from apps.properties.models import Property, PropertyPhoto, PropertyVideo
    from apps.agents.models import OwnerAgentRelation, AgentProfile
    import datetime
    import io
    from PIL import Image
    from django.core.files.base import ContentFile

    OwnerAgentRelation.objects.get_or_create(
        owner=owner_user,
        agent=agent_user,
        defaults={
            "status": "active",
            "contract_start": datetime.date.today(),
            "agency": AgentProfile.objects.get(user=agent_user).agency,
        }
    )
    prop = Property.objects.create(
        owner=owner_user,
        agent=agent_user,
        title="Appartement Test",
        description="Belle description suffisamment longue pour valider les contraintes minimales de la plateforme INTELYA HAVEN qui requiert au moins cinquante mots dans la description du bien immobilier",
        property_type="apartment",
        status="available",
        price=150000,
        payment_period="monthly",
        bedrooms=3,
        bathrooms=2,
        area_sqm=120,
        city="Douala",
        neighborhood="Bonanjo",
        full_address="Rue Test N°1, Bonanjo, Douala",
        is_furnished=True,
        has_generator=True,
        has_parking=True,
    )

    # Respecte le minimum de publication (MIN_PROPERTY_PHOTOS photos +
    # video >= MIN_VIDEO_DURATION_SECONDS) pour que ce bien apparaisse par
    # defaut dans la recherche publique, comme la grande majorite des tests
    # qui utilisent ce fixture s'y attendent.
    for i in range(4):
        buf = io.BytesIO()
        Image.new('RGB', (100, 100)).save(buf, format='JPEG')
        PropertyPhoto.objects.create(
            property=prop,
            photo=ContentFile(buf.getvalue(), name=f'photo{i}.jpg'),
        )
    PropertyVideo.objects.create(property=prop, duration_seconds=90)

    return prop


@pytest.fixture
def client_with_agent(create_user, agent_user):
    """Client lié à un agent"""
    from apps.agents.models import ClientAgentRelation, AgentProfile
    user = create_user(
        email="client_linked@test.com",
        phone="+237670000020",
        role="client",
    )
    ClientAgentRelation.objects.get_or_create(
        client=user,
        agent=agent_user,
        defaults={"is_active": True, "agency": AgentProfile.objects.get(user=agent_user).agency}
    )
    return user


@pytest.fixture
def auth_client_with_agent(api_client, client_with_agent):
    api_client.force_authenticate(user=client_with_agent)
    return api_client


@pytest.fixture
def auth_client(api_client, client_user):
    api_client.force_authenticate(user=client_user)
    return api_client


@pytest.fixture
def auth_agent(api_client, agent_user):
    api_client.force_authenticate(user=agent_user)
    return api_client


@pytest.fixture
def auth_owner(api_client, owner_user):
    api_client.force_authenticate(user=owner_user)
    return api_client


@pytest.fixture
def auth_admin(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client
