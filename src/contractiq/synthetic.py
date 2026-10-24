"""Sample contracts and procurement data for fictional GCC suppliers.

The contracts are generated from one template per language, so every clause value is known.
That makes them usable for evaluating Arabic questions on Arabic contracts, and keeps the
procurement data (Text-to-SQL) consistent with what the contracts say.

    python -m contractiq.synthetic
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta

from contractiq.db import apply_schema, connect
from contractiq.ingest import upsert_contract

BUYER_EN = "Al-Waha Healthcare Group"
BUYER_AR = "مجموعة الواحة للرعاية الصحية"


@dataclass
class Supplier:
    name: str
    name_ar: str
    country: str
    country_ar: str
    contract_type: str  # Supply / Distributor / Transportation
    language: str
    number: str
    start: date
    end: date
    penalty_pct_per_day: float
    penalty_cap_pct: int
    termination_delay_days: int
    renewal_notice_days: int
    payment_days: int
    warranty_months: int
    min_annual_sar: int
    liability_cap_months: int
    convenience_notice_days: int
    late_rate: float  # share of purchase orders delivered late (procurement data)


SUPPLIERS = [
    Supplier("Al-Sharq Pharma", "الشرق للأدوية", "Saudi Arabia", "المملكة العربية السعودية",
             "Supply", "en", "2025-014", date(2025, 1, 15), date(2027, 1, 14),
             0.5, 10, 30, 60, 60, 24, 2_400_000, 12, 90, 0.18),
    Supplier("Gulf Medical Supplies", "الخليج للمستلزمات الطبية", "Saudi Arabia", "المملكة العربية السعودية",
             "Supply", "ar", "2025-031", date(2025, 12, 1), date(2026, 11, 30),
             0.3, 8, 45, 30, 45, 12, 1_200_000, 6, 60, 0.08),
    Supplier("Riyadh Logistics", "الرياض للخدمات اللوجستية", "Saudi Arabia", "المملكة العربية السعودية",
             "Transportation", "ar", "2024-077", date(2024, 12, 1), date(2026, 11, 30),
             1.0, 15, 15, 60, 30, 6, 800_000, 3, 30, 0.22),
    Supplier("Najd Distribution", "نجد للتوزيع", "Saudi Arabia", "المملكة العربية السعودية",
             "Distributor", "en", "2025-052", date(2025, 12, 15), date(2026, 12, 14),
             0.4, 10, 30, 45, 60, 12, 1_500_000, 12, 90, 0.12),
    Supplier("Red Sea Freight", "البحر الأحمر للشحن", "Saudi Arabia", "المملكة العربية السعودية",
             "Transportation", "en", "2025-066", date(2025, 11, 1), date(2026, 10, 31),
             0.8, 12, 20, 30, 30, 6, 600_000, 6, 30, 0.25),
    Supplier("Al-Noor Healthcare", "النور للرعاية الصحية", "Saudi Arabia", "المملكة العربية السعودية",
             "Supply", "ar", "2026-008", date(2026, 2, 1), date(2028, 1, 31),
             0.5, 10, 30, 90, 60, 24, 3_000_000, 12, 120, 0.05),
    Supplier("Emirates Cold Chain", "الإمارات لسلاسل التبريد", "United Arab Emirates", "الإمارات العربية المتحدة",
             "Transportation", "en", "2026-019", date(2026, 4, 1), date(2027, 3, 31),
             1.0, 10, 10, 60, 45, 6, 900_000, 6, 60, 0.10),
    Supplier("Bahrain Pharma Trading", "البحرين لتجارة الأدوية", "Bahrain", "مملكة البحرين",
             "Distributor", "ar", "2024-090", date(2024, 10, 1), date(2026, 9, 30),
             0.5, 10, 30, 30, 60, 12, 700_000, 6, 60, 0.15),
]

SCOPE_EN = {
    "Supply": "the supply of pharmaceutical products and medical consumables listed in Schedule A",
    "Distributor": "the distribution of the Buyer's pharmaceutical products within the Kingdom of Saudi Arabia",
    "Transportation": "temperature-controlled transportation of pharmaceutical products between the Buyer's warehouses and facilities",
}
SCOPE_AR = {
    "Supply": "توريد المنتجات الدوائية والمستلزمات الطبية المدرجة في الملحق (أ)",
    "Distributor": "توزيع المنتجات الدوائية الخاصة بالمشتري داخل المملكة العربية السعودية",
    "Transportation": "نقل المنتجات الدوائية في بيئة مبردة بين مستودعات ومنشآت المشتري",
}
TITLE_EN = {"Supply": "SUPPLY AGREEMENT", "Distributor": "DISTRIBUTION AGREEMENT",
            "Transportation": "TRANSPORTATION AGREEMENT"}
TITLE_AR = {"Supply": "اتفاقية توريد", "Distributor": "اتفاقية توزيع", "Transportation": "اتفاقية نقل"}


def contract_en(s: Supplier) -> str:
    return f"""{TITLE_EN[s.contract_type]} No. {s.number}

This Agreement is made between {BUYER_EN}, a company registered in the Kingdom of Saudi Arabia (the "Buyer"), and {s.name}, a company registered in {s.country} (the "Supplier").

1. DEFINITIONS
"Products" means the goods or services described in Clause 2. "Purchase Order" means a written order issued by the Buyer under this Agreement. "Business Day" means a day on which banks are open in Riyadh.

2. SCOPE
2.1 This Agreement governs {SCOPE_EN[s.contract_type]}.
2.2 Each delivery shall be made against a Purchase Order stating quantities, prices and the required delivery date.

3. TERM
3.1 This Agreement takes effect on {s.start:%d %B %Y} and expires on {s.end:%d %B %Y}, unless terminated earlier under Clause 14.

4. RENEWAL
4.1 This Agreement renews automatically for successive one (1) year terms unless either party gives written notice of non-renewal at least {s.renewal_notice_days} days before the expiry date.

5. MINIMUM COMMITMENT
5.1 The Buyer shall place Purchase Orders with a total value of at least SAR {s.min_annual_sar:,} in each contract year.

6. PRICES AND PAYMENT
6.1 Prices are fixed for the first contract year and may be revised once a year by mutual written agreement.
6.2 The Buyer shall pay each undisputed invoice within {s.payment_days} days of receipt.

7. QUALITY AND STORAGE
7.1 The Supplier shall store and handle all Products in accordance with the requirements of the Saudi Food and Drug Authority, including temperature-controlled conditions where required.
7.2 The Buyer may reject any delivery that does not meet the agreed specifications.

8. AUDIT
8.1 The Buyer may audit the Supplier's records, facilities and temperature logs relating to this Agreement once per contract year on ten (10) Business Days' notice.

9. DELIVERY AND PERFORMANCE
9.1 Delivery schedule. The Supplier shall deliver the Products by the date stated in each Purchase Order.
9.2 Late delivery penalty. If the Supplier fails to deliver by that date, the Supplier shall pay a penalty of {s.penalty_pct_per_day}% of the value of the delayed shipment for each day of delay, capped at {s.penalty_cap_pct}% of that value.
9.3 Notice of delay. The Supplier must notify the Buyer promptly, and in any case within two (2) Business Days, of any anticipated delay.

10. WARRANTY
10.1 The Supplier warrants that the Products will conform to their specifications for a period of {s.warranty_months} months from delivery.

11. INSURANCE
11.1 The Supplier shall maintain product liability and goods-in-transit insurance with a reputable insurer for the full term of this Agreement and provide certificates on request.

12. LIMITATION OF LIABILITY
12.1 Except for fraud, wilful misconduct or breach of Clause 13, each party's total liability under this Agreement is capped at the amounts paid or payable by the Buyer in the {s.liability_cap_months} months preceding the claim.

13. CONFIDENTIALITY
13.1 Each party shall keep confidential all information received from the other party and use it only to perform this Agreement.

14. TERMINATION
14.1 The Buyer may terminate this Agreement with immediate effect by written notice if any delivery is delayed by more than {s.termination_delay_days} days.
14.2 Either party may terminate this Agreement for convenience by giving {s.convenience_notice_days} days' written notice.

15. ASSIGNMENT
15.1 Neither party may assign or transfer this Agreement without the prior written consent of the other party.

16. GOVERNING LAW AND DISPUTES
16.1 This Agreement is governed by the laws of the Kingdom of Saudi Arabia.
16.2 Disputes that are not settled amicably within thirty (30) days shall be referred to the competent courts in Riyadh.
"""


def contract_ar(s: Supplier) -> str:
    return f"""{TITLE_AR[s.contract_type]} رقم {s.number}

أُبرمت هذه الاتفاقية بين {BUYER_AR}، وهي شركة مسجلة في المملكة العربية السعودية ("المشتري")، و{s.name_ar}، وهي شركة مسجلة في {s.country_ar} ("المورد").

1. التعريفات
"المنتجات" تعني السلع أو الخدمات الموضحة في البند 2. "أمر الشراء" يعني الطلب الكتابي الصادر من المشتري بموجب هذه الاتفاقية. "يوم العمل" يعني اليوم الذي تفتح فيه البنوك في الرياض.

2. النطاق
2.1 تنظم هذه الاتفاقية {SCOPE_AR[s.contract_type]}.
2.2 يتم كل توريد بموجب أمر شراء يحدد الكميات والأسعار وتاريخ التسليم المطلوب.

3. المدة
3.1 تسري هذه الاتفاقية اعتباراً من {s.start:%Y-%m-%d} وتنتهي في {s.end:%Y-%m-%d}، ما لم تُنهَ قبل ذلك وفقاً للبند 14.

4. التجديد
4.1 تتجدد هذه الاتفاقية تلقائياً لمدد متتالية مدة كل منها سنة واحدة، ما لم يُخطر أحد الطرفين الآخر كتابياً بعدم رغبته في التجديد قبل تاريخ الانتهاء بـ {s.renewal_notice_days} يوماً على الأقل.

5. الحد الأدنى للالتزام
5.1 يلتزم المشتري بإصدار أوامر شراء لا تقل قيمتها الإجمالية عن {s.min_annual_sar:,} ريال سعودي في كل سنة تعاقدية.

6. الأسعار والدفع
6.1 تكون الأسعار ثابتة خلال السنة التعاقدية الأولى، ويجوز مراجعتها مرة واحدة سنوياً باتفاق كتابي بين الطرفين.
6.2 يسدد المشتري كل فاتورة غير متنازع عليها خلال {s.payment_days} يوماً من تاريخ استلامها.

7. الجودة والتخزين
7.1 يلتزم المورد بتخزين المنتجات ومناولتها وفقاً لاشتراطات الهيئة العامة للغذاء والدواء، بما في ذلك التبريد عند الحاجة.
7.2 يحق للمشتري رفض أي شحنة لا تطابق المواصفات المتفق عليها.

8. التدقيق
8.1 يحق للمشتري تدقيق سجلات المورد ومنشآته وسجلات درجات الحرارة المتعلقة بهذه الاتفاقية مرة واحدة في كل سنة تعاقدية، بعد إشعار مدته عشرة (10) أيام عمل.

9. التسليم والأداء
9.1 جدول التسليم: يلتزم المورد بتسليم المنتجات في التاريخ المحدد في كل أمر شراء.
9.2 غرامة التأخير في التسليم: إذا تأخر المورد عن التسليم في ذلك التاريخ، يدفع غرامة قدرها {s.penalty_pct_per_day}% من قيمة الشحنة المتأخرة عن كل يوم تأخير، بحد أقصى {s.penalty_cap_pct}% من تلك القيمة.
9.3 الإشعار بالتأخير: يلتزم المورد بإشعار المشتري فوراً، وفي جميع الأحوال خلال يومي عمل، بأي تأخير متوقع.

10. الضمان
10.1 يضمن المورد مطابقة المنتجات لمواصفاتها لمدة {s.warranty_months} شهراً من تاريخ التسليم.

11. التأمين
11.1 يلتزم المورد بالاحتفاظ بتأمين على مسؤولية المنتجات وتأمين على البضائع أثناء النقل لدى شركة تأمين معتمدة طوال مدة هذه الاتفاقية، وتقديم الشهادات عند الطلب.

12. حدود المسؤولية
12.1 باستثناء حالات الاحتيال أو سوء السلوك المتعمد أو الإخلال بالبند 13، لا تتجاوز المسؤولية الإجمالية لأي طرف المبالغ المدفوعة أو المستحقة على المشتري خلال {s.liability_cap_months} أشهر السابقة للمطالبة.

13. السرية
13.1 يلتزم كل طرف بالحفاظ على سرية جميع المعلومات التي يتلقاها من الطرف الآخر وعدم استخدامها إلا لتنفيذ هذه الاتفاقية.

14. الإنهاء
14.1 يحق للمشتري إنهاء هذه الاتفاقية فوراً بإشعار كتابي إذا تجاوز التأخير في أي تسليم {s.termination_delay_days} يوماً.
14.2 يحق لأي من الطرفين إنهاء هذه الاتفاقية دون سبب بموجب إشعار كتابي مدته {s.convenience_notice_days} يوماً.

15. التنازل
15.1 لا يجوز لأي من الطرفين التنازل عن هذه الاتفاقية أو نقلها دون موافقة كتابية مسبقة من الطرف الآخر.

16. القانون الواجب التطبيق وتسوية النزاعات
16.1 تخضع هذه الاتفاقية لأنظمة المملكة العربية السعودية.
16.2 تُحال النزاعات التي لا تتم تسويتها ودياً خلال ثلاثين (30) يوماً إلى المحاكم المختصة في مدينة الرياض.
"""


def title(s: Supplier) -> str:
    return f"{TITLE_EN[s.contract_type].title()} {s.number} - {s.name}"


def purchase_orders(s: Supplier, rng: random.Random) -> list[tuple]:
    """Monthly-ish orders from the contract start until today (or the contract end)."""
    today = date(2026, 10, 24)
    orders, d, i = [], s.start + timedelta(days=rng.randint(3, 15)), 1
    monthly = s.min_annual_sar / 12
    while d <= min(today, s.end):
        promised = d + timedelta(days=rng.choice([7, 10, 14, 21]))
        amount = round(monthly * rng.uniform(0.6, 1.5), 2)
        if promised > today:
            delivered, status = None, "open"
        elif rng.random() < 0.03:
            delivered, status = None, "cancelled"
        else:
            delay = rng.randint(1, 20) if rng.random() < s.late_rate else -rng.randint(0, 2)
            delivered, status = promised + timedelta(days=delay), "delivered"
            if delivered > today:  # late and not arrived yet: still open, not delivered in the future
                delivered, status = None, "open"
        orders.append((f"PO-{s.number}-{i:03d}", d, promised, delivered, amount, status))
        d += timedelta(days=rng.randint(20, 40))
        i += 1
    return orders


def main() -> None:
    rng = random.Random(42)
    with connect() as conn:
        apply_schema(conn)
        n_po = 0
        for s in SUPPLIERS:
            text = contract_en(s) if s.language == "en" else contract_ar(s)
            cid = upsert_contract(conn, title=title(s), source="synthetic", contract_type=s.contract_type,
                                  language=s.language, text=text, supplier=s.name, supplier_ar=s.name_ar,
                                  start_date=s.start, end_date=s.end)
            sid = conn.execute(
                """INSERT INTO suppliers (name, country, category) VALUES (%s, %s, %s)
                   ON CONFLICT (name) DO UPDATE SET country = EXCLUDED.country RETURNING id""",
                (s.name, s.country, s.contract_type),
            ).fetchone()[0]
            conn.execute("DELETE FROM purchase_orders WHERE supplier_id = %s", (sid,))
            pos = purchase_orders(s, rng)
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO purchase_orders (po_number, supplier_id, contract_id, order_date,
                           promised_date, delivered_date, amount_sar, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    [(po, sid, cid, od, pd, dd, amt, st) for po, od, pd, dd, amt, st in pos],
                )
            n_po += len(pos)
        print(f"{len(SUPPLIERS)} sample contracts, {n_po} purchase orders")


if __name__ == "__main__":
    main()
