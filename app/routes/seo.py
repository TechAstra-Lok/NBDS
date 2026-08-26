import logging
from datetime import datetime, timezone
from flask import Blueprint, render_template, make_response, url_for, request, current_app
from app import db
from app.models import BloodBank, BloodRequest, News, Notice, PublicBloodBankCache

logger = logging.getLogger(__name__)

seo_bp = Blueprint('seo', __name__)


# ── robots.txt ─────────────────────────────────────────
@seo_bp.route('/robots.txt')
def robots_txt():
    site_url = request.url_root.rstrip('/')
    content = f"""# robots.txt for National Blood Donors Society Nepal
User-agent: *
Disallow: /admin/
Disallow: /bloodbank/
Disallow: /donor/forgot-pin
Disallow: /donor/force-change-pin
Disallow: /api/
Disallow: /*?*status=
Disallow: /*?*page=
Disallow: /*?*search=
Allow: /
Allow: /blood-banks
Allow: /blood-banks/
Allow: /blood-request
Allow: /find-donors
Allow: /news
Allow: /news/
Allow: /about
Allow: /contact
Allow: /faq
Allow: /donor/guidelines

Sitemap: {site_url}/sitemap.xml
"""
    response = make_response(content)
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response


# ── sitemap.xml ────────────────────────────────────────
@seo_bp.route('/sitemap.xml')
def sitemap_xml():
    site_url = request.url_root.rstrip('/')
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    pages = []

    # 1. Primary Public Static Pages
    static_routes = [
        ('/', '1.0', 'daily'),
        ('/find-donors', '0.9', 'daily'),
        ('/blood-request', '0.9', 'hourly'),
        ('/blood-banks', '0.9', 'daily'),
        ('/donor/register', '0.8', 'weekly'),
        ('/donor/guidelines', '0.8', 'monthly'),
        ('/news', '0.7', 'daily'),
        ('/about', '0.6', 'monthly'),
        ('/contact', '0.6', 'monthly'),
        ('/faq', '0.6', 'monthly'),
    ]
    for path, priority, changefreq in static_routes:
        pages.append({
            'loc': f"{site_url}{path}",
            'lastmod': now_str,
            'priority': priority,
            'changefreq': changefreq
        })

    # 2. Individual Public Blood Bank Detail Pages
    try:
        banks = BloodBank.query.filter_by(is_active=True).all()
        for b in banks:
            updated = b.updated_at.strftime('%Y-%m-%d') if b.updated_at else now_str
            pages.append({
                'loc': f"{site_url}/blood-banks/{b.id}",
                'lastmod': updated,
                'priority': '0.8',
                'changefreq': 'daily'
            })
    except Exception as e:
        logger.warning("Error fetching blood banks for sitemap: %s", e)

    # 3. Location SEO Hub Pages (Provinces & Districts with Active Blood Banks)
    try:
        provinces = db.session.query(BloodBank.province).filter(
            BloodBank.is_active == True,
            BloodBank.province.isnot(None)
        ).distinct().all()

        for (p_name,) in provinces:
            if not p_name:
                continue
            slug = p_name.lower().replace(' ', '-').replace('pradesh', '').strip('-')
            pages.append({
                'loc': f"{site_url}/blood-banks/location/{slug}",
                'lastmod': now_str,
                'priority': '0.7',
                'changefreq': 'weekly'
            })

            # Districts under this province
            districts = db.session.query(BloodBank.district).filter(
                BloodBank.is_active == True,
                BloodBank.province == p_name,
                BloodBank.district.isnot(None)
            ).distinct().all()

            for (d_name,) in districts:
                if not d_name:
                    continue
                d_slug = d_name.lower().replace(' ', '-').strip('-')
                pages.append({
                    'loc': f"{site_url}/blood-banks/location/{slug}/{d_slug}",
                    'lastmod': now_str,
                    'priority': '0.7',
                    'changefreq': 'weekly'
                })
    except Exception as e:
        logger.warning("Error fetching location hubs for sitemap: %s", e)

    # 4. News Articles
    try:
        news_items = News.query.filter_by(is_published=True).order_by(News.created_at.desc()).limit(100).all()
        for item in news_items:
            updated = item.created_at.strftime('%Y-%m-%d') if item.created_at else now_str
            pages.append({
                'loc': f"{site_url}/news/{item.id}",
                'lastmod': updated,
                'priority': '0.6',
                'changefreq': 'monthly'
            })
    except Exception as e:
        logger.warning("Error fetching news for sitemap: %s", e)

    # 5. Public Blood Request Board
    pages.append({
        'loc': f"{site_url}/blood-requests",
        'lastmod': now_str,
        'priority': '0.8',
        'changefreq': 'hourly'
    })

    # Render XML
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for p in pages:
        xml_lines.append('  <url>')
        xml_lines.append(f"    <loc>{p['loc']}</loc>")
        xml_lines.append(f"    <lastmod>{p['lastmod']}</lastmod>")
        xml_lines.append(f"    <changefreq>{p['changefreq']}</changefreq>")
        xml_lines.append(f"    <priority>{p['priority']}</priority>")
        xml_lines.append('  </url>')
    xml_lines.append('</urlset>')

    response = make_response('\n'.join(xml_lines))
    response.headers['Content-Type'] = 'application/xml; charset=utf-8'
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response


# ── Nepal Location SEO Hubs ────────────────────────────
@seo_bp.route('/blood-banks/location/<province_slug>')
@seo_bp.route('/blood-banks/location/<province_slug>/<district_slug>')
def location_blood_banks(province_slug, district_slug=None):
    """
    Search-Engine Optimized Local Blood Bank Hub.
    Only serves pages where meaningful data/blood banks exist.
    """
    # Normalize slug to search term
    clean_p_slug = province_slug.replace('-', ' ').title()

    query = BloodBank.query.filter_by(is_active=True)
    query = query.filter(BloodBank.province.ilike(f"%{clean_p_slug}%"))

    clean_d_slug = None
    if district_slug:
        clean_d_slug = district_slug.replace('-', ' ').title()
        query = query.filter(BloodBank.district.ilike(f"%{clean_d_slug}%"))

    blood_banks = query.order_by(BloodBank.name).all()

    if not blood_banks:
        # Avoid thin empty pages — return 404 or redirect to general directory
        return render_template('errors/404.html'), 404

    province_name = blood_banks[0].province or clean_p_slug
    district_name = blood_banks[0].district if district_slug else None

    # Aggregate inventory summary across these local banks
    bank_ids = [b.id for b in blood_banks]
    caches = PublicBloodBankCache.query.filter(PublicBloodBankCache.blood_bank_id.in_(bank_ids)).all()

    stock_totals = {
        'A+': sum(c.a_pos or 0 for c in caches),
        'A-': sum(c.a_neg or 0 for c in caches),
        'B+': sum(c.b_pos or 0 for c in caches),
        'B-': sum(c.b_neg or 0 for c in caches),
        'AB+': sum(c.ab_pos or 0 for c in caches),
        'AB-': sum(c.ab_neg or 0 for c in caches),
        'O+': sum(c.o_pos or 0 for c in caches),
        'O-': sum(c.o_neg or 0 for c in caches),
    }

    # Location title & meta
    if district_name:
        page_title = f"Blood Banks in {district_name}, {province_name} | Blood Availability & Emergency Contacts"
        meta_desc = f"Find verified blood banks, live inventory availability, emergency hotline numbers, and blood reservation services in {district_name}, {province_name}, Nepal."
        h1_heading = f"Blood Banks & Transfusion Centers in {district_name}"
    else:
        page_title = f"Blood Banks in {province_name} | Nepal Blood Bank Directory"
        meta_desc = f"Comprehensive directory of verified blood transfusion centers and hospital blood banks in {province_name}, Nepal with real-time stock levels."
        h1_heading = f"Blood Transfusion Centers in {province_name}"

    return render_template(
        'seo/location_hub.html',
        blood_banks=blood_banks,
        province_name=province_name,
        district_name=district_name,
        province_slug=province_slug,
        district_slug=district_slug,
        stock_totals=stock_totals,
        page_title=page_title,
        meta_desc=meta_desc,
        h1_heading=h1_heading
    )
