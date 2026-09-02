# 🔍 Forensic System Architecture Directory

**Total Models**: 39 Database Models (100% indexed)  
**Total Routes & Endpoints**: 137 URLs / API Endpoints  
**Total Blueprints**: 6 (`public`, `admin`, `bloodbank`, `api`, `notifications`, `seo`)  
**Realtime WebSocket Channels**: Socket.IO Live Alerts & Room Management  
**Scheduled Background Tasks**: APScheduler Cron & Lifecycle Engine  

---

## 🗄️ Part 1: All 39 Database Models & Tables

| # | Model Class | Table Name | Columns | Core Purpose |
|---|---|---|---|---|
| 1 | `User` | `users` | 9 | System Administrators & RBAC roles (`superadmin`, `admin`, `moderator`, `content_manager`) |
| 2 | `Donor` | `donors` | 46 | Registered Blood Donors, 7-province location, PIN auth, blood group, stats & cooldown |
| 3 | `DonorDonationHistory` | `donor_donation_history` | 10 | Immutable donation logs, bag barcode, verification status, hospital logs |
| 4 | `DonorNotificationPreference` | `donor_notification_preferences` | 11 | Multi-channel alert settings (Email, SMS, Web Push, In-App, DND quiet hours) |
| 5 | `DonorResponse` | `donor_responses` | 6 | Donor response state to emergency broadcast requests (`accepted`, `declined`, `on_the_way`) |
| 6 | `BloodBank` | `blood_banks` | 35 | Central blood banks, geographic coordinates, parent hospitals, license, emergency flags |
| 7 | `BloodBankAccount` | `blood_bank_accounts` | 13 | Independent authentication accounts for blood bank operational staff |
| 8 | `BloodBankAlertSettings` | `blood_bank_alert_settings` | 13 | Configurable blood bank thresholds, stock alerts, expiring units, auto-dispatch |
| 9 | `BloodBankLoginHistory` | `blood_bank_login_history` | 6 | Audit trail of blood bank logins, IP addresses, user agents, security lockout records |
| 10 | `BloodBankNotification` | `blood_bank_notifications` | 14 | In-app alerts for blood bank managers (reservations, low stock, transfer orders) |
| 11 | `BloodBankNotificationDelivery` | `blood_bank_notification_deliveries` | 6 | Delivery logs of blood bank alerts to staff channels |
| 12 | `BloodBankPasswordHistory` | `blood_bank_password_history` | 4 | Security compliance storing previous password hashes to prevent re-use |
| 13 | `BloodBankShift` | `blood_bank_shifts` | 13 | Shift definitions (Morning, Evening, Night, Emergency On-Call) per blood bank |
| 14 | `BloodBankShiftAssignment` | `blood_bank_shift_assignments` | 8 | Staff-to-shift roster schedule with check-in/out timestamps |
| 15 | `BloodInventory` | `blood_inventory` | 11 | Aggregated inventory per blood group & component (Whole Blood, Platelets, Plasma, RBC) |
| 16 | `BloodInventoryMovement` | `blood_inventory_movements` | 6 | Inflow/Outflow ledger tracking additions, reservations, donations, disposals |
| 17 | `BloodInventoryTransaction` | `blood_inventory_transactions` | 6 | Transaction receipts for hospital blood issues, wastage, and returns |
| 18 | `BloodBag` | `blood_bags` | 13 | Individual physical blood bag tracking with unique barcode/QR code and test flags |
| 19 | `BloodRequest` | `blood_requests` | 27 | Public & hospital patient emergency blood requests with hospital form verification |
| 20 | `BloodReservation` | `blood_reservations` | 13 | Patient hold reservations against live blood bank inventory with 4-hour timeout |
| 21 | `BloodTransfer` | `blood_transfers` | 10 | Inter-bank blood component transfer requests, logistics dispatch & confirmations |
| 22 | `LowStockAlert` | `low_stock_alerts` | 7 | Automated alerts triggered when blood inventory breaches critical thresholds |
| 23 | `PublicBloodBankCache` | `public_blood_bank_cache` | 11 | High-speed denormalized cache of available units per blood group for public view |
| 24 | `LabTestResult` | `lab_test_results` | 7 | Serology, HIV, Hepatitis, Syphilis screening results for collected blood units |
| 25 | `StaffMember` | `staff_members` | 24 | Personnel directory (lab technicians, phlebotomists, nurses, receptionists, drivers) |
| 26 | `Volunteer` | `volunteers` | 15 | Community volunteers, blood drive coordinators, active status, contact info |
| 27 | `Partner` | `partners` | 10 | Partner organizations, hospitals, Red Cross chapters, sponsors, website URLs |
| 28 | `News` | `news` | 14 | Blood donation campaign news, articles, publication dates, view counts |
| 29 | `Notice` | `notices` | 11 | Public bulletins, emergency announcements, priority badges, expiry schedules |
| 30 | `Advertisement` | `advertisements` | 13 | Banner ads, sponsor placements, impression & click-through analytics counters |
| 31 | `SuccessStory` | `success_stories` | 13 | Donor & patient testimonials, AI safety moderation score, approval status |
| 32 | `Contact` | `contacts` | 8 | Public contact form submissions, inquiries, resolution notes |
| 33 | `Notification` | `notifications` | 10 | Core notification entity for donors, patients, and broadcast recipients |
| 34 | `NotificationDeliveryLog` | `notification_delivery_logs` | 12 | Delivery attempts via Email (SMTP), SMS, Web Push, and in-app channels |
| 35 | `NotificationQueue` | `notification_queue` | 12 | Asynchronous message dispatch queue with retry backoff and rate-limiting |
| 36 | `PushSubscription` | `push_subscriptions` | 9 | Browser Web Push API subscription endpoints and encryption keys (P256DH, Auth) |
| 37 | `AuditLog` | `audit_logs` | 6 | Immutable compliance trail of all administrative actions, data edits, and logins |
| 38 | `SiteConfig` | `site_configs` | 5 | Key-value application runtime configuration overrides |
| 39 | `SiteVisitor` | `site_visitors` | 8 | Realtime analytics tracking daily unique visitors, page views, and referrer sources |

---

## 🌐 Part 2: All 137 Routes & API Endpoints

### 1. Public Blueprint (`public_bp` — 33 Endpoints)
| HTTP Method | Route URL | Function / Endpoint | Purpose |
|---|---|---|---|
| `GET` | `/` | `public.index` | Landing page, live counters, search form, blood stock ticker |
| `GET` | `/about` | `public.about` | About Nepali Blood Donors Society mission & vision |
| `GET` | `/faq` | `public.faq` | Frequently Asked Questions regarding blood donation in Nepal |
| `GET` | `/donor-guidelines` | `public.donor_guidelines` | Eligibility requirements, intervals, and health criteria |
| `GET` | `/search` | `public.global_search` | Global unified search across donors, blood banks, and news |
| `GET` | `/find-donors` | `public.find_donors` | Filterable donor directory by province, district, blood group |
| `GET`, `POST` | `/become-donor` | `public.become_donor` | Public donor registration form with duplicate prevention |
| `GET`, `POST` | `/donor/login` | `public.donor_login` | Donor PIN login with rate-limiting & temporary lock |
| `GET` | `/donor/<donor_id>` | `public.donor_profile` | Public or authenticated donor profile card & history |
| `GET` | `/donor/<donor_id>/photo` | `public.donor_photo` | Stream compressed JPEG donor avatar directly from database |
| `GET` | `/donor/<donor_id>/qr` | `public.donor_qr` | Generates dynamic QR code for digital donor card |
| `GET`, `POST` | `/donor/forgot-pin` | `public.donor_forgot_pin` | Request administrative PIN reset for donor account |
| `GET`, `POST` | `/donor/force-change-pin`| `public.donor_force_change_pin` | Mandatory PIN change upon first login or admin reset |
| `GET` | `/blood-banks` | `public.blood_banks` | National blood bank directory with Google Maps routing |
| `GET` | `/blood-banks/<bank_id>`| `public.blood_bank_detail` | Detailed blood bank profile, live stock summary, contact info |
| `GET`, `POST` | `/blood-banks/<bank_id>/reserve` | `public.reserve_blood` | Patient emergency blood reservation against live inventory |
| `GET` | `/blood-requests` | `public.blood_request_board` | Public real-time emergency blood requests bulletin board |
| `GET`, `POST` | `/blood-request` | `public.blood_request_form` | Post new emergency blood request with prescription upload |
| `GET` | `/blood-requests/<request_ref>` | `public.single_blood_request` | Dedicated status page for individual blood request |
| `GET`, `POST` | `/blood-requests/manage`| `public.manage_blood_request` | Manage existing request status using phone & PIN |
| `POST` | `/blood-requests/<id>/update-status` | `public.public_update_request_status` | Update blood request state (`fulfilled`, `cancelled`) |
| `GET`, `POST` | `/contact` | `public.contact` | Public inquiry contact form |
| `GET`, `POST` | `/become-volunteer` | `public.become_volunteer` | Volunteer application registration |
| `GET`, `POST` | `/volunteer/login` | `public.volunteer_login` | Volunteer authentication portal |
| `GET`, `POST` | `/success-stories` | `public.success_stories` | Community impact testimonials with AI text safety filter |
| `POST` | `/success-stories/<story_id>/delete` | `public.delete_success_story` | User deletion of authored story |
| `GET` | `/news` | `public.news_list` | Organization news, announcements, blood camp schedules |
| `GET` | `/ai-assistant` | `public.ai_assistant` | Dedicated interactive page for Raktadata AI Assistant |
| `GET` | `/ad/click/<ad_id>` | `public.ad_click` | Tracks banner click metric and redirects to sponsor URL |
| `GET` | `/set-language/<lang>` | `public.set_language` | Switches locale between Nepali (`ne`) and English (`en`) |
| `GET` | `/logout` | `public.logout` | Clears all session credentials |
| `GET` | `/sw.js` | `public.service_worker` | PWA Service Worker caching core offline assets |
| `GET` | `/manifest.json` | `public.manifest` | PWA Web App Manifest for mobile & desktop installation |
| `GET` | `/health` | `public.health_check` | Production health check for load balancer uptime probes |
| `GET` | `/api/donor/<donor_id>/availability` | `public.donor_availability_api` | Real-time JSON availability check for a specific donor |
| `GET` | `/api/nearest-blood-bank`| `public.nearest_blood_bank` | Haversine GPS geo-lookup for nearest blood transfusion center |

---

### 2. REST API Blueprint (`api_bp` — `/api/v1` — 14 Endpoints)
| HTTP Method | Route URL | Function / Endpoint | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/stats` | `api.stats` | Public aggregate statistics (total donors, active requests) |
| `GET` | `/api/v1/donors/search` | `api.search_donors` | High-speed JSON donor query by blood group & district |
| `GET` | `/api/v1/requests/active`| `api.active_requests` | Real-time active emergency blood requests JSON feed |
| `GET` | `/api/v1/blood-banks` | `api.blood_banks_api` | Public blood bank listing with geo-coordinates |
| `GET` | `/api/v1/blood-banks/<bank_id>/inventory` | `api.blood_bank_inventory_api` | Available units per blood group for a specific bank |
| `GET` | `/api/v1/blood-banks/<bank_id>/reservations` | `api.blood_bank_reservations_api` | Active reservations on a blood bank |
| `GET` | `/api/v1/blood-banks/<bank_id>/alerts` | `api.blood_bank_alerts_api` | Critical low stock alert summary |
| `GET` | `/api/v1/blood-banks/<bank_id>/transfers` | `api.blood_bank_transfers_api` | Inter-bank transfer orders |
| `POST` | `/api/v1/raktadata-helper` | `api.raktadata_helper` | Gemini AI Assistant multi-turn medical QA endpoint |
| `POST` | `/api/v1/raktadata-helper/stream` | `api.raktadata_helper_stream` | Server-Sent Events (SSE) streaming response for AI chat |
| `POST` | `/api/v1/raktadata-helpher` | `api.raktadata_helper` | Backward-compatibility alias for AI helper |
| `POST` | `/api/v1/raktadata-helpher/stream` | `api.raktadata_helper_stream` | Backward-compatibility alias for AI helper stream |
| `POST` | `/api/v1/ad/impression/<ad_id>` | `api.track_impression` | Increment ad view counter without reloading page |

---

### 3. Blood Bank Portal Blueprint (`bloodbank_bp` — `/bloodbank` — 25 Endpoints)
| HTTP Method | Route URL | Function / Endpoint | Purpose |
|---|---|---|---|
| `GET`, `POST` | `/bloodbank/login` | `bloodbank.login` | Blood bank manager & staff authentication portal |
| `GET` | `/bloodbank/logout` | `bloodbank.logout` | Terminate blood bank session |
| `GET` | `/bloodbank/dashboard` | `bloodbank.dashboard` | Blood bank control dashboard, stats, low stock warnings |
| `GET`, `POST` | `/bloodbank/change-password` | `bloodbank.change_password` | Staff password change with history validation |
| `GET` | `/bloodbank/inventory` | `bloodbank.inventory` | Live inventory grid by group, component, expiry |
| `GET`, `POST` | `/bloodbank/inventory/add` | `bloodbank.add_inventory` | Add newly collected blood bags into stock |
| `GET`, `POST` | `/bloodbank/inventory/<id>/edit` | `bloodbank.edit_inventory` | Update stock levels and minimum thresholds |
| `POST` | `/bloodbank/inventory/<id>/delete` | `bloodbank.delete_inventory` | Remove expired or damaged blood component units |
| `GET` | `/bloodbank/reservations`| `bloodbank.reservations` | Manage pending patient blood reservations |
| `POST` | `/bloodbank/reservations/add` | `bloodbank.add_reservation` | Manual in-person reservation created by desk staff |
| `POST` | `/bloodbank/reservations/<id>/status` | `bloodbank.update_reservation_status` | Fulfill, dispense, or cancel a blood reservation |
| `GET` | `/bloodbank/staff` | `bloodbank.staff` | Blood bank employee roster & credentials |
| `GET`, `POST` | `/bloodbank/staff/add` | `bloodbank.add_staff` | Register new lab technician / phlebotomist |
| `GET`, `POST` | `/bloodbank/staff/<id>/edit` | `bloodbank.edit_staff` | Edit staff role, contact info, shift group |
| `POST` | `/bloodbank/staff/<id>/delete` | `bloodbank.delete_staff` | Deactivate staff member account |
| `GET` | `/bloodbank/shifts` | `bloodbank.shifts` | Shift schedule management (Morning/Evening/Night) |
| `GET`, `POST` | `/bloodbank/shifts/add` | `bloodbank.add_shift` | Create new operational shift definition |
| `GET`, `POST` | `/bloodbank/shifts/<id>/edit` | `bloodbank.edit_shift` | Update shift hours and minimum staffing rules |
| `POST` | `/bloodbank/shifts/assign` | `bloodbank.assign_staff_shift` | Assign specific staff member to a shift |
| `POST` | `/bloodbank/shifts/assignment/<id>/remove` | `bloodbank.remove_staff_shift` | Unassign staff from shift |
| `GET`, `POST` | `/bloodbank/settings/alerts`| `bloodbank.alert_settings` | Configure critical stock alert thresholds and SMS recipients |
| `GET` | `/bloodbank/notifications`| `bloodbank.notifications` | View blood bank activity alerts |
| `POST` | `/bloodbank/notifications/<id>/read` | `bloodbank.mark_notification_read` | Mark individual notification as read |
| `POST` | `/bloodbank/notifications/read-all` | `bloodbank.mark_all_notifications_read` | Mark all notifications read |
| `POST` | `/bloodbank/notifications/<id>/archive` | `bloodbank.archive_notification` | Archive old alert |
| `GET` | `/bloodbank/api/notifications/poll` | `bloodbank.poll_notifications` | JSON polling endpoint for live desktop alert popup |

---

### 4. Notification Engine Blueprint (`notifications_bp` — `/notifications` — 10 Endpoints)
| HTTP Method | Route URL | Function / Endpoint | Purpose |
|---|---|---|---|
| `GET`, `POST` | `/notifications/preferences` | `notifications.preferences` | Donor web UI for notification preferences |
| `GET` | `/notifications/api/list` | `notifications.api_list` | Fetch JSON list of user's notifications |
| `GET` | `/notifications/api/unread-count` | `notifications.api_unread_count` | Badge counter of unread notifications |
| `POST` | `/notifications/api/mark-read/<notif_id>`| `notifications.api_mark_read` | Mark notification read |
| `POST` | `/notifications/api/mark-all-read` | `notifications.api_mark_all_read` | Mark all read |
| `DELETE` | `/notifications/api/delete/<notif_id>` | `notifications.api_delete` | Delete notification |
| `GET`, `PUT` | `/notifications/api/preferences` | `notifications.api_preferences` | REST API to read/update notification preferences |
| `POST` | `/notifications/api/push/subscribe` | `notifications.api_push_subscribe` | Save browser Web Push VAPID subscription |
| `POST` | `/notifications/api/push/unsubscribe` | `notifications.api_push_unsubscribe` | Remove browser Web Push subscription |
| `POST` | `/notifications/api/respond` | `notifications.api_respond` | Donor accepts/declines emergency blood broadcast |

---

### 5. SEO & Indexing Blueprint (`seo_bp` — 4 Endpoints)
| HTTP Method | Route URL | Function / Endpoint | Purpose |
|---|---|---|---|
| `GET` | `/robots.txt` | `seo.robots_txt` | Search engine crawler rules (disallows `/admin/`, links sitemap) |
| `GET` | `/sitemap.xml` | `seo.sitemap_xml` | Dynamic XML sitemap listing all provinces, districts, banks, and news |
| `GET` | `/blood-banks/location/<province_slug>` | `seo.location_blood_banks` | Dynamic province landing page for local search optimization |
| `GET` | `/blood-banks/location/<province_slug>/<district_slug>` | `seo.location_blood_banks` | Dynamic district landing page for localized blood searches |

---

### 6. Admin Panel Blueprint (`admin_bp` — `/admin` — 51 Endpoints)
| HTTP Method | Route URL | Function / Endpoint | Purpose |
|---|---|---|---|
| `GET`, `POST` | `/admin/login` | `admin.login` | Admin authentication with brute-force protection |
| `GET` | `/admin/logout` | `admin.logout` | Admin session logout |
| `GET` | `/admin/dashboard` | `admin.dashboard` | Master executive dashboard with realtime metrics |
| `GET` | `/admin/data-quality` | `admin.data_quality` | Duplicate donor detection using fuzzy token matching |
| `GET` | `/admin/audit-logs` | `admin.audit_logs` | Security audit trail of all system mutations |
| `GET` | `/admin/donors` | `admin.donors` | Donor management table with multi-filter & export |
| `GET`, `POST` | `/admin/donors/add` | `admin.add_donor` | Administrative registration of new donor |
| `GET`, `POST` | `/admin/donors/<id>/edit` | `admin.edit_donor` | Update donor information & blood group |
| `POST` | `/admin/donors/<id>/delete` | `admin.delete_donor` | Delete donor record |
| `POST` | `/admin/donors/<id>/toggle-active` | `admin.toggle_donor_active` | Deactivate/Reactivate donor |
| `POST` | `/admin/donors/<id>/verify-phone` | `admin.verify_donor_phone` | Manually mark donor phone verified |
| `POST` | `/admin/donors/<id>/reset-pin` | `admin.admin_reset_donor_pin` | Administrative PIN reset to temporary code |
| `POST` | `/admin/donors/<id>/unlock-pin` | `admin.admin_unlock_donor_pin` | Unlock PIN after failed attempt lockout |
| `GET` | `/admin/donors/export/csv` | `admin.export_donors_csv` | Export donor database to CSV |
| `GET` | `/admin/donors/export/excel` | `admin.export_donors_excel` | Export donor database to formatted Excel (`.xlsx`) |
| `GET` | `/admin/donors/export/pdf` | `admin.export_donors_pdf` | Generate printable PDF donor registry report |
| `GET` | `/admin/blood-requests` | `admin.blood_requests` | All emergency blood requests monitoring |
| `GET`, `POST` | `/admin/blood-requests/add` | `admin.add_blood_request` | Post emergency blood request from admin desk |
| `GET`, `POST` | `/admin/blood-requests/<id>/edit` | `admin.edit_blood_request` | Edit patient details or required units |
| `POST` | `/admin/blood-requests/<id>/status` | `admin.update_request_status` | Update request state (`active`, `fulfilled`, `cancelled`) |
| `POST` | `/admin/blood-requests/<id>/delete` | `admin.delete_blood_request` | Delete blood request record |
| `GET` | `/admin/blood-banks` | `admin.blood_banks` | Central directory of all blood banks in Nepal |
| `GET`, `POST` | `/admin/blood-banks/add` | `admin.add_blood_bank` | Register new hospital / Red Cross blood bank |
| `GET`, `POST` | `/admin/blood-banks/<id>/edit` | `admin.edit_blood_bank` | Edit blood bank coordinates, phone, services |
| `POST` | `/admin/blood-banks/<id>/delete` | `admin.delete_blood_bank` | Delete blood bank |
| `POST` | `/admin/blood-banks/<id>/toggle-status` | `admin.toggle_blood_bank_status` | Activate/Deactivate blood bank |
| `GET`, `POST` | `/admin/blood-banks/<id>/account` | `admin.manage_blood_bank_account`| Create/manage login credentials for blood bank staff |
| `GET` | `/admin/blood-banks/export/excel` | `admin.export_blood_banks_excel` | Export blood banks directory to Excel |
| `GET` | `/admin/blood-banks/export/pdf` | `admin.export_blood_banks_pdf` | Generate printable PDF of all national blood banks |
| `GET` | `/admin/staff` | `admin.staff_members` | Staff members directory |
| `GET`, `POST` | `/admin/staff/add` | `admin.add_staff_member` | Add new staff member |
| `GET`, `POST` | `/admin/staff/<id>/edit` | `admin.edit_staff_member` | Edit staff credentials & role |
| `POST` | `/admin/staff/<id>/delete` | `admin.delete_staff_member` | Delete staff member |
| `POST` | `/admin/staff/<id>/toggle-status` | `admin.toggle_staff_member_status` | Enable/Disable staff login access |
| `GET` | `/admin/news` | `admin.news_list` | News & campaign articles list |
| `GET`, `POST` | `/admin/news/add` | `admin.add_news` | Publish new blood drive article |
| `GET`, `POST` | `/admin/news/<id>/edit` | `admin.edit_news` | Edit existing news post |
| `POST` | `/admin/news/<id>/delete` | `admin.delete_news` | Delete news post |
| `GET` | `/admin/notices` | `admin.notices` | Public bulletin & notice board manager |
| `GET`, `POST` | `/admin/notices/add` | `admin.add_notice` | Post urgent notice with priority badge |
| `GET`, `POST` | `/admin/notices/<id>/edit` | `admin.edit_notice` | Edit notice content & duration |
| `POST` | `/admin/notices/<id>/delete` | `admin.delete_notice` | Delete notice |
| `GET` | `/admin/volunteers` | `admin.volunteers` | Volunteer applications review |
| `POST` | `/admin/volunteers/<id>/approve` | `admin.approve_volunteer` | Approve volunteer application |
| `POST` | `/admin/volunteers/<id>/toggle-active` | `admin.toggle_volunteer_active` | Toggle volunteer active status |
| `POST` | `/admin/volunteers/<id>/delete` | `admin.delete_volunteer` | Delete volunteer record |
| `GET` | `/admin/partners` | `admin.partners` | Partners & affiliate organizations manager |
| `GET`, `POST` | `/admin/partners/add` | `admin.add_partner` | Add hospital/partner logo & website |
| `GET`, `POST` | `/admin/partners/<id>/edit` | `admin.edit_partner` | Edit partner details |
| `POST` | `/admin/partners/<id>/delete` | `admin.delete_partner` | Delete partner |
| `GET` | `/admin/advertisements` | `admin.advertisements` | Banner advertisement manager & stats |
| `GET`, `POST` | `/admin/advertisements/add` | `admin.add_advertisement` | Create ad placement & schedule |
| `GET`, `POST` | `/admin/advertisements/<id>/edit` | `admin.edit_advertisement` | Edit ad banner image & destination URL |
| `POST` | `/admin/advertisements/<id>/delete` | `admin.delete_advertisement` | Delete banner ad |
| `GET` | `/admin/contacts` | `admin.contacts` | Inquiries and feedback received from contact form |
| `POST` | `/admin/contacts/<id>/delete` | `admin.delete_contact` | Delete contact inquiry |
| `GET` | `/admin/success-stories` | `admin.success_stories` | Review community submitted testimonials |
| `POST` | `/admin/success-stories/<id>/approve` | `admin.approve_success_story` | Approve testimonial for public display |
| `POST` | `/admin/success-stories/<id>/delete` | `admin.delete_success_story` | Delete testimonial |
| `GET` | `/admin/users` | `admin.users` | Admin user accounts & RBAC management |
| `GET`, `POST` | `/admin/users/add` | `admin.add_user` | Provision new admin/moderator account |
| `GET`, `POST` | `/admin/users/<id>/edit` | `admin.edit_user` | Edit admin role & permissions |
| `POST` | `/admin/users/<id>/delete` | `admin.delete_user` | Delete admin account |

---

## ⚡ Part 3: Realtime WebSockets & Background Tasks

### WebSocket Handlers (`app/sockets.py`)
* `connect`: Authenticates connecting client and establishes socket session.
* `disconnect`: Cleans up active socket connection.
* `join_bloodbank`: Joins manager to blood bank's private alert room (`bloodbank_<bank_id>`).
* `leave_bloodbank`: Leaves blood bank alert room.

### Scheduled Background Engine (`app/tasks.py`)
* `recalculate_donor_availability_job`: Recalculates 90-day cooldown status across all donors.
* `expire_outdated_blood_requests_job`: Automatically archives requests older than 7 days.
* `sync_public_blood_bank_cache_job`: Recalculates cached blood unit counts for instant public viewing.
* `cleanup_expired_reservations_job`: Releases reserved blood units back to stock after 4-hour expiry.
